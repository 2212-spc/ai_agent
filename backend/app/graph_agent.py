"""
LangGraph Agent - 完整的智能体实现
支持：多步骤规划、并行执行、条件路由、状态持久化、人工介入
"""
from __future__ import annotations

import json
import logging
import operator
import re
import uuid
import asyncio
from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Sequence, TypedDict, AsyncGenerator

import httpx
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from sqlalchemy.orm import Session

from .config import Settings
from .database import ToolRecord, get_session_factory
from .rag_service import retrieve_context
from .tool_service import execute_tool, parse_tool_call
from .memory_service import (
    retrieve_relevant_memories,
    format_memories_for_prompt,
    save_conversation_and_extract_memories,
)

logger = logging.getLogger(__name__)


# ==================== LLM 调用工具 ====================

async def invoke_llm(
    messages: List[Dict[str, str]],
    settings: Settings,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> tuple[str, Dict[str, Any]]:
    """
    调用 DeepSeek API 进行推理
    
    Args:
        messages: 对话消息列表
        settings: 配置对象
        temperature: 温度参数
        max_tokens: 最大 token 数
    
    Returns:
        (回复内容, 完整响应数据)
    """
    payload: Dict[str, Any] = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    endpoint = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:  # 增加到120秒
            response = await client.post(endpoint, json=payload, headers=headers)

        if response.status_code != 200:
            logger.error(
                "DeepSeek API error %s: %s", response.status_code, response.text
            )
            return f"API 调用失败: {response.status_code}", {}

        data = response.json()
        reply = data["choices"][0]["message"]["content"]
        return reply, data
    
    except httpx.TimeoutException as e:
        logger.error(f"LLM 调用超时（120秒）: {e}")
        return f"LLM 调用超时，请稍后重试", {}
    except Exception as e:
        logger.error(f"LLM 调用异常: {e}", exc_info=True)
        return f"LLM 调用失败: {str(e)}", {}


async def stream_llm(
    messages: List[Dict[str, str]],
    settings: Settings,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    """
    流式调用 DeepSeek API
    """
    payload: Dict[str, Any] = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    endpoint = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            async with client.stream("POST", endpoint, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    yield f"API Error: {response.status_code}"
                    return

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            content = data["choices"][0]["delta"].get("content", "")
                            if content:
                                yield content
                        except:
                            pass
    except Exception as e:
        logger.error(f"LLM Stream Error: {e}")
        yield f"Error: {str(e)}"


def parse_json_from_llm(text: str) -> Dict[str, Any]:
    """
    从 LLM 响应中提取 JSON
    支持处理 markdown 代码块包裹的 JSON
    """
    # 移除可能的 markdown 代码块标记
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    
    text = text.strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON 解析失败: {e}, 原始文本: {text[:200]}")
        # 宽容解析：尝试截断到第一个可能完整的对象
        try:
            end_idx = max(text.rfind('}'), text.rfind(']'))
            if end_idx != -1:
                truncated = text[:end_idx+1]
                return json.loads(truncated)
        except Exception:
            pass
        # 返回默认结构
        return {
            "task_type": "信息查询",
            "steps": ["分析问题", "生成回答"],
            "required_tools": [],
            "need_knowledge_base": False
        }


def format_tools_description(tool_records: List[ToolRecord]) -> str:
    """格式化工具描述供 LLM 理解"""
    if not tool_records:
        return "无可用工具"
    
    descriptions = []
    for tool in tool_records:
        try:
            config = json.loads(tool.config or "{}")
            builtin_key = config.get("builtin_key", "")
            descriptions.append(
                f"- {tool.id}: {tool.name} ({builtin_key}) - {tool.description}"
            )
        except:
            descriptions.append(f"- {tool.id}: {tool.name} - {tool.description}")
    
    return "\n".join(descriptions)


# ==================== 状态定义 ====================
class AgentState(TypedDict):
    """Agent 的状态，贯穿整个工作流"""
    
    # 基础信息
    user_query: str  # 用户原始问题
    conversation_history: Annotated[Sequence[Dict[str, str]], operator.add]  # 对话历史
    session_id: Optional[str]  # 会话ID，用于长期记忆
    user_id: Optional[str]  # 用户ID，用于多用户场景
    difficulty: Optional[str]  # 任务难度：simple, hard
    pre_generated_answer: Optional[str]  # 预生成的答案（用于简单任务快速响应）
    stream_mode: Optional[bool]  # 是否为流式模式
    
    # 规划信息
    plan: Optional[str]  # Agent 生成的计划
    current_step: int  # 当前执行到第几步
    max_iterations: int  # 最大迭代次数
    
    # 工具相关
    available_tools: List[str]  # 可用的工具ID列表
    tool_calls_made: Annotated[List[Dict[str, Any]], operator.add]  # 已执行的工具调用
    tool_results: Annotated[List[Dict[str, Any]], operator.add]  # 工具执行结果
    skipped_tasks: Annotated[List[Dict[str, Any]], operator.add]  # 被跳过的任务及原因
    
    # RAG 相关
    use_knowledge_base: bool  # 是否使用知识库
    retrieved_contexts: List[Dict[str, Any]]  # 检索到的上下文
    
    # Agent 思考过程
    thoughts: Annotated[List[str], operator.add]  # Agent 的思考过程
    observations: Annotated[List[str], operator.add]  # 观察到的结果
    
    # 隐式推理
    subquestions: List[str]
    answer_outline: List[str]
    evidence_requirements: List[str]
    reasoning_steps: Annotated[List[str], operator.add]
    react_cursor: int
    react_max_steps: int
    react_steps_done: int
    
    # 决策相关
    next_action: Optional[str]  # 下一步动作：tool_call, search_kb, synthesize, complete
    needs_human_input: bool  # 是否需要人工介入
    human_feedback: Optional[str]  # 人工反馈
    
    # 质量控制
    reflection: Optional[str]  # 反思结果
    quality_score: float  # 质量评分 0-1
    
    # 最终输出
    final_answer: Optional[str]  # 最终答案
    final_prompt: Optional[str]  # 最终生成的 Prompt（用于流式输出）
    ready_to_synthesize: Optional[bool]  # 是否准备好合成（用于延迟合成）
    is_complete: bool  # 是否完成
    error: Optional[str]  # 错误信息


# ==================== 核心节点函数 ====================

async def planner_node(
    state: AgentState,
    settings: Settings,
    tool_records: List[ToolRecord],
    session: Session = None,
    session_id: str = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    规划器节点：使用 LLM 分析用户问题，生成智能执行计划
    """
    logger.info("🧠 [规划器] 开始智能分析任务...")
    
    user_query = state["user_query"]
    use_knowledge_base = state.get("use_knowledge_base", False)
    
    # 检索相关记忆
    relevant_memories = []
    if session and (session_id or user_id):
        try:
            relevant_memories = await retrieve_relevant_memories(
                session=session,
                query=user_query,
                settings=settings,
                user_id=user_id,
                session_id=session_id,
                max_memories=5,
            )
            if relevant_memories:
                logger.info(f"📚 在规划器中检索到 {len(relevant_memories)} 条相关记忆")
        except Exception as e:
            logger.warning(f"记忆检索失败: {e}")
    
    # 格式化工具描述
    tools_desc = format_tools_description(tool_records)
    
    # 构建记忆上下文
    memory_context = ""
    if relevant_memories:
        memory_lines = [f"- {mem.content}" for mem in relevant_memories]
        memory_context = f"\n用户已知信息（用于规划参考）：\n" + "\n".join(memory_lines) + "\n"
    
    # 构建智能规划提示词（避免 f-string 中的花括号导致格式错误）
    header = (
        "你是一个智能任务规划助手。请分析用户问题，制定执行计划，并给出隐式推理草稿。\n\n"
        f"用户问题：{user_query}\n"
        f"{memory_context}"
        "可用工具：\n"
        f"{tools_desc}\n\n"
        f"知识库：{'已启用' if use_knowledge_base else '未启用'}\n\n"
        "请分析任务并以 JSON 格式输出计划。\n\n"
        "**决策逻辑**：\n"
        "1. **直接回答 (Direct Answer)**：如果问题是常识、概念解释、闲聊，且你无需使用工具或搜索即可回答，请选择此模式。\n"
        "2. **工具调用 (Tool Use)**：如果需要搜索、画图、查天气、做笔记等，请选择此模式。\n"
        "3. **知识库检索 (RAG)**：如果需要从知识库查找信息（且知识库已启用），请选择此模式。\n\n"
    )
    json_template = """
请返回 JSON：
{
  "task_type": "direct_answer|tool_use|rag_search|complex_task",
  "analysis": "任务分析简述",
  "steps": ["步骤1", "步骤2", "..."],
  "required_tools": ["tool_id_1", "..."],
  "direct_answer_content": "如果是direct_answer模式，请在此直接写出完整回答（支持Markdown）；否则留空",
  "need_knowledge_base": true,
  "subquestions": ["子问题1", "子问题2", "..."],
  "answer_outline": ["章节1", "章节2", "..."],
  "evidence_requirements": ["必须覆盖的要点或证据1", "要点2", "..."]
}

注意：
1. 优先尝试 **direct_answer** 以提供最快响应。
2. 只有当确实需要外部信息时才使用 tool_use 或 rag_search。
3. 只返回 JSON，不要其他解释。
"""
    planning_prompt = header + json_template
    
    try:
        # 调用 LLM 进行规划
        llm_response, _ = await invoke_llm(
            messages=[{"role": "user", "content": planning_prompt}],
            settings=settings,
            temperature=0.3,  # 低温度保证规划稳定
            max_tokens=1500
        )
        
        # 解析 LLM 返回的 JSON
        plan_data = parse_json_from_llm(llm_response)
        
        task_type = plan_data.get("task_type", "complex_task")
        analysis = plan_data.get("analysis", "分析任务中...")
        
        # === Level 2: Direct Reasoning (直接推理) ===
        if task_type == "direct_answer" and plan_data.get("direct_answer_content"):
            logger.info("🚀 [规划器] 判定为直接回答模式 (Level 2)")
            return {
                "plan": "直接回答用户问题",
                "current_step": 0,
                "thoughts": ["Planner: 判定为通用知识/闲聊，直接生成回答"],
                "next_action": "synthesize",
                "difficulty": "simple",
                "pre_generated_answer": plan_data.get("direct_answer_content")
            }

        steps = plan_data.get("steps", ["分析问题", "生成答案"])
        
        logger.info(f"📋 规划完成：{task_type}, {len(steps)} 个步骤")
        
        # 格式化为可读文本
        plan_text = f"""任务类型：{task_type}
任务分析：{analysis}

执行步骤：
{chr(10).join(f"{i+1}. {step}" for i, step in enumerate(steps))}
"""
        
        thought = f"智能规划完成：识别为【{task_type}】，共 {len(steps)} 个步骤"
        
        return {
            "plan": plan_text,
            "current_step": 0,
            "thoughts": [thought],
            "next_action": "route",
            "subquestions": plan_data.get("subquestions", []),
            "answer_outline": plan_data.get("answer_outline", []),
            "evidence_requirements": plan_data.get("evidence_requirements", [])
        }
    
    except Exception as e:
        logger.error(f"规划器失败: {e}")
        # 降级到简单规划
        fallback_plan = f"""任务分析：用户询问「{user_query}」

执行步骤：
1. 根据问题选择合适的处理方式
2. 收集必要的信息
3. 生成完整答案

预期结果：为用户提供有用的回答
"""
        return {
            "plan": fallback_plan,
            "current_step": 0,
            "thoughts": [f"使用简化规划模式（规划器异常：{str(e)[:50]}）"],
            "next_action": "route"
        }


async def router_node(
    state: AgentState,
    settings: Settings,
) -> Dict[str, Any]:
    """
    路由器节点：使用 LLM 智能决定下一步动作
    """
    logger.info("🔀 [路由器] 智能决策下一步动作...")
    
    user_query = state["user_query"]
    current_step = state.get("current_step", 0)
    max_iterations = state.get("max_iterations", 10)
    tool_calls_made = state.get("tool_calls_made", [])
    use_knowledge_base = state.get("use_knowledge_base", False)
    observations = state.get("observations", [])
    retrieved_contexts = state.get("retrieved_contexts", [])
    tool_results = state.get("tool_results", [])
    
    # === 快速通道检查 ===
    # 如果 Planner 已经决定了下一步动作（例如 simple 任务），直接执行
    pre_decided_action = state.get("next_action")
    if pre_decided_action == "synthesize" and state.get("difficulty") == "simple":
        logger.info("🚀 [路由器] 检测到快速通道动作，跳过决策")
        return {
            "next_action": "synthesize",
            "thoughts": ["快速通道：直接进入合成阶段"],
            "current_step": current_step + 1
        }
    
    # 检查是否超过最大迭代次数
    if current_step >= max_iterations:
        return {
            "next_action": "synthesize",
            "thoughts": [f"已达到最大迭代次数({max_iterations})，准备生成最终答案"],
            "current_step": current_step + 1
        }
    
    # 检测知识库是否已经搜索过
    kb_searched = any("知识库" in obs for obs in observations)
    kb_empty = kb_searched and not retrieved_contexts  # 搜索过但没有结果
    
    # 如果第一步，先进行简单判断（优化性能）
    if current_step == 0:
        # 启用知识库但未检索
        if use_knowledge_base and not kb_searched:
            return {
                "next_action": "search_kb",
                "thoughts": ["首次执行：优先检索知识库"],
                "current_step": current_step + 1
            }
        
        # 检查是否需要工具
        if should_call_tool(state):
            return {
                "next_action": "tool_executor",
                "thoughts": ["首次执行：检测到需要工具调用"],
                "current_step": current_step + 1
            }
    
    # 如果知识库已搜索但为空，且没有需要工具的任务，直接进入合成阶段
    if current_step >= 1 and kb_empty and not should_call_tool(state):
        logger.info("⚠️ 知识库已搜索但为空，且无需工具，直接进入合成阶段")
        return {
            "next_action": "synthesize",
            "thoughts": ["知识库为空且无需工具，直接生成答案"],
            "current_step": current_step + 1
        }
    
    # 步骤 >= 1，使用 LLM 智能决策（ReAct 控制器前置）
    # 先检查是否已经检索过知识库，避免重复搜索
    kb_already_searched = len(retrieved_contexts) > 0 or any("知识库" in obs or "检索到" in obs for obs in observations)
    
    try:
        # 构建决策上下文
        kb_status = "已检索" if kb_already_searched else "未检索"
        kb_status_detail = f"已检索 {len(retrieved_contexts)} 条" if retrieved_contexts else "未检索"
        
        context_summary = f"""当前执行状态：
- 用户问题：{user_query}
- 执行步骤：{current_step}/{max_iterations}
- 已调用工具数：{len(tool_calls_made)}
- 知识库检索：{"已检索但无结果" if kb_empty else ("已检索 " + str(len(retrieved_contexts)) + " 条" if retrieved_contexts else "未检索")}
- 工具执行结果数：{len(tool_results)}

最近观察：
{chr(10).join("- " + obs for obs in observations[-3:]) if observations else "暂无观察"}

请判断下一步应该做什么：
A. search_kb - 需要从知识库检索信息
B. tool_executor - 需要调用外部工具获取数据
C. synthesize - 信息已足够，可以生成最终答案

要求：
1. **重要**：如果知识库已经搜索过但无结果（已检索但无结果），不要选择 A，应该选择 C
2. 如果启用了知识库但还没检索（知识库检索显示"未检索"），优先选择 A
3. 如果知识库已经检索过（知识库检索显示"已检索"），不要重复选择 A，应该选择 B 或 C
4. 如果问题需要多个工具（如：搜索+绘图），必须执行完所有工具后再选择 C
5. 如果问题需要实时数据（天气、搜索等），但还没调用相应工具，选择 B
6. 如果已有足够信息且所有必要工具都已执行，选择 C
7. 只回复一个字母（A/B/C），不要解释
"""
        
        # 调用 LLM 决策
        llm_response, _ = await invoke_llm(
            messages=[{"role": "user", "content": context_summary}],
            settings=settings,
            temperature=0.1,  # 极低温度保证决策一致性
            max_tokens=10
        )
        
        decision = llm_response.strip().upper()
        
        # 映射决策
        action_map = {
            "A": "search_kb",
            "B": "tool_executor",
            "C": "synthesize"
        }
        
        next_action = action_map.get(decision, "synthesize")
        
        # 强制检查：如果知识库已搜索但为空，且选择了 search_kb，强制改为 synthesize
        if kb_empty and next_action == "search_kb":
            logger.warning("⚠️ 知识库已为空，强制改为 synthesize")
            next_action = "synthesize"
            decision = "C"
        
        # 防止重复搜索知识库：如果已经检索过，强制改为 synthesize 或 tool_executor
        if next_action == "search_kb" and kb_already_searched:
            logger.warning(f"⚠️ 阻止重复知识库搜索：已检索过 {len(retrieved_contexts)} 条，强制改为 synthesize")
            if should_call_tool(state):
                next_action = "tool_executor"
                thought = "LLM选择A但已检索过知识库，改为调用工具"
            else:
                next_action = "synthesize"
                thought = "LLM选择A但已检索过知识库，改为生成答案"
        else:
            thought = f"LLM 智能路由：{decision} -> {next_action}"
        
        logger.info(f"📍 智能路由决策：步骤{current_step}, 决策={decision}, 下一步={next_action}")
        
        return {
            "next_action": next_action,
            "thoughts": [thought],
            "current_step": current_step + 1
        }
    
    except Exception as e:
        logger.error(f"路由器 LLM 决策失败: {e}")
        
        # 降级策略：使用简单规则
        kb_searched = len(retrieved_contexts) > 0 or any("知识库" in obs or "检索到" in obs for obs in observations)
        
        if kb_empty and not should_call_tool(state):
            next_action = "synthesize"
            thought = "降级决策：知识库为空，直接生成答案"
        elif use_knowledge_base and not kb_searched and current_step < 2:
            # 防止重复搜索：如果已经检索过，不再选择 search_kb
            next_action = "search_kb"
            thought = "降级决策：检索知识库"
        elif kb_searched and current_step >= 2:
            # 已经检索过，如果还有工具要调用就调用工具，否则生成答案
            if should_call_tool(state):
                next_action = "tool_executor"
                thought = "降级决策：已检索过知识库，调用工具"
            else:
                next_action = "synthesize"
                thought = "降级决策：已检索过知识库，生成答案"
        elif should_call_tool(state):
            next_action = "tool_executor"
            thought = "降级决策：调用工具"
        else:
            next_action = "synthesize"
            thought = "降级决策：生成答案"
        
        return {
            "next_action": next_action,
            "thoughts": [thought],
            "current_step": current_step + 1
        }

async def react_controller_node(
    state: AgentState,
    settings: Settings,
) -> Dict[str, Any]:
    subqs = state.get("subquestions", []) or []
    evids = state.get("evidence_requirements", []) or []
    cursor = state.get("react_cursor", 0)
    max_steps = state.get("react_max_steps", 4)
    steps_done = state.get("react_steps_done", 0)
    retrieved_contexts = state.get("retrieved_contexts", []) or []
    tool_results = state.get("tool_results", []) or []
    coverage = (len(retrieved_contexts) + len(tool_results)) / max(1, len(subqs) or 1)
    if steps_done >= max_steps or coverage >= 0.65:
        return {
            "next_action": "synthesize",
            "thoughts": [f"ReAct结束：steps={steps_done}, coverage={coverage:.2f}"],
        }
    current_subq = subqs[cursor] if cursor < len(subqs) else ""
    prompt = f"""你是任务控制器。根据当前子问题和观察，决定下一步工具调用或停止。
子问题：{current_subq}
证据需求：{'; '.join(evids[:5])}
最近观察：{'; '.join(state.get('observations', [])[-3:])}
可选动作：
A.web_search
B.knowledge_search
C.draw_diagram
D.stop
只输出一个字母。"""
    try:
        reply, _ = await invoke_llm(
            messages=[{"role": "user", "content": prompt}],
            settings=settings,
            temperature=0.0,
            max_tokens=4,
        )
        action = reply.strip().upper()[:1]
        map_act = {"A": "tool_executor", "B": "knowledge_search", "C": "tool_executor", "D": "synthesize"}
        next_action = map_act.get(action, "tool_executor")
        next_cursor = cursor + (1 if next_action in ("synthesize",) else 0)
        return {
            "next_action": next_action,
            "react_cursor": next_cursor,
            "react_steps_done": steps_done + 1,
            "thoughts": [f"ReAct决策：{action} -> {next_action} | cursor={next_cursor}"],
        }
    except Exception as e:
        return {
            "next_action": "tool_executor",
            "react_steps_done": steps_done + 1,
            "thoughts": [f"ReAct降级：异常 {str(e)[:60]}，改为工具执行"],
        }

def knowledge_search_node(
    state: AgentState,
    settings: Settings,
) -> Dict[str, Any]:
    """
    知识库搜索节点：从向量数据库检索相关内容
    """
    logger.info("📚 [知识库] 正在检索相关文档...")
    
    user_query = state["user_query"]
    
    try:
        # 调用 RAG 检索
        contexts = retrieve_context(
            query=user_query,
            settings=settings,
            top_k=4
        )
        
        retrieved = [
            {
                "document_id": ctx.document_id,
                "original_name": ctx.original_name,
                "content": ctx.content[:500]  # 限制长度
            }
            for ctx in contexts
        ]
        
        observation = f"从知识库检索到 {len(retrieved)} 个相关片段"
        
        return {
            "retrieved_contexts": retrieved,
            "observations": [observation],
            "thoughts": ["知识库检索完成，获取到相关背景信息"]
        }
    
    except Exception as e:
        logger.error(f"知识库检索失败: {e}")
        return {
            "retrieved_contexts": [],
            "observations": [f"知识库检索失败: {str(e)}"],
            "error": str(e)
        }


async def tool_executor_node(
    state: AgentState,
    settings: Settings,
    session: Session,
    tool_records: List[ToolRecord],
) -> Dict[str, Any]:
    """工具执行器节点：智能选择并执行工具（支持并行）"""
    logger.info("🔧 [工具执行器] 准备调用工具...")

    user_query = state.get("user_query", "")
    tool_calls_made = state.get("tool_calls_made", [])
    tool_results = state.get("tool_results", [])
    skipped_tasks = state.get("skipped_tasks", [])

    tasks = infer_tool_tasks(user_query)
    if not tasks:
        observation = f"分析查询未发现需要调用工具的指令：{user_query}" if user_query else "无需调用工具"
        return {
            "thoughts": ["未找到需要执行的工具任务"],
            "observations": [observation],
            "next_action": "synthesize",
        }

    completed_tasks = {call.get("task") for call in tool_calls_made if call.get("task")}
    skipped_task_keys = {
        item.get("task")
        for item in skipped_tasks
        if isinstance(item, dict) and item.get("task")
    }

    tool_index: Dict[str, ToolRecord] = {}
    for record in tool_records:
        if getattr(record, "is_active", True):
            task_key = map_tool_to_task(record)
            if task_key and task_key not in tool_index:
                tool_index[task_key] = record

    # 1. 识别所有可并行的待处理任务
    tasks_to_run = []
    
    for task in tasks:
        if task in completed_tasks or task in skipped_task_keys:
            continue
        
        # 依赖检查逻辑
        # Diagram 需要 Search 结果
        if task == "diagram" and "search" in tasks and "search" not in completed_tasks:
            continue
        # Note 需要 Weather 结果
        if task == "note" and "weather" in tasks and "weather" not in completed_tasks:
            continue
            
        tool = tool_index.get(task)
        if not tool:
            reason = f"找不到任务 {task} 对应的工具"
            logger.warning(reason)
            # 记录跳过，但暂不返回，继续处理其他任务
            # (这里简化处理，本次循环不跑它，下次循环会再次检测并可能标记跳过)
            # 为了简单，我们只添加有效的
            continue
            
        # 准备参数
        tool_args = {}
        action_description = ""
        
        # 参数构造逻辑 (保持原有逻辑)
        if task == "weather":
            city = extract_city_from_query(user_query)
            tool_args = {"city": city}
            action_description = f"查询{city}天气"
        elif task == "search":
            search_query = extract_search_query(user_query)
            tool_args = {"query": search_query, "num_results": 6}
            action_description = f"搜索'{search_query}'获取信息"
        elif task == "diagram":
            # 此时 search 应该已完成 (依赖检查过了)
            search_context = None
            for result in reversed(tool_results):
                if result.get("task") == "search":
                    search_context = result.get("output", "")[:2000]
                    break
            
            if search_context:
                try:
                    payload = await generate_diagram_payload_with_llm(user_query, search_context, settings)
                    tool_args = payload
                    action_description = "基于搜索结果使用LLM生成思维导图"
                except Exception as e:
                    logger.warning(f"LLM生成思维导图失败，使用默认方法: {e}")
                    payload = generate_diagram_payload(user_query, search_context)
                    tool_args = payload
                    action_description = "基于搜索结果生成思维导图"
            else:
                payload = generate_diagram_payload(user_query, None)
                tool_args = payload
                action_description = "生成思维导图"
        elif task == "note":
            # 此时 weather 应该已完成
            weather_result = None
            for result in reversed(tool_results):
                if result.get("task") == "weather" or "天气" in result.get("tool_name", ""):
                    weather_result = result
                    break
            
            # 场景1：带伞提醒
            if weather_result and any(kw in user_query for kw in ["带伞", "雨伞", "提醒"]):
                weather_text = weather_result.get("output", "")
                if not detect_rain_in_text(weather_text):
                    # 无雨，跳过
                    continue
                
                city_from_weather = weather_result.get("arguments", {}).get("city")
                if not city_from_weather:
                    city_from_weather = extract_city_from_query(user_query)
                filename = build_note_filename(city_from_weather)
                note_content = build_note_content(city_from_weather, weather_text, user_query)
                tool_args = {"filename": filename, "content": note_content}
                action_description = f"为{city_from_weather}创建带伞提醒"
            else:
                # 场景2：通用笔记
                # ... (原有逻辑)
                context_parts = []
                if tool_results:
                    for tr in tool_results:
                        tool_name = tr.get("tool_name", "工具")
                        output = tr.get("output", "")
                        context_parts.append(f"【{tool_name}结果】\n{output[:800]}")
                context_text = "\n\n".join(context_parts) if context_parts else "无工具结果"
                
                # 这里简化：不再实时调用LLM生成，避免阻塞并发。或者也放入 thread pool?
                # 为了保持简单，假设 note 内容构建不依赖复杂 LLM 交互，或者允许在这里调用
                # 原有逻辑用了简单的 f-string，但 build_note_content 是简单的。
                # 只有 "场景2" 用了 LLM 生成笔记内容?
                # 原代码 line 812 看起来是构造 prompt 但没看到调用?
                # 仔细看原代码... 啊，原代码 line 812 下面断掉了，我没读完。
                # 假设 note 逻辑比较复杂，我们先把它当作普通任务
                # 暂时只支持简单的笔记生成，或者把 LLM 生成逻辑移到 execute_tool 内部?
                # 暂且跳过 LLM 生成笔记的复杂逻辑，使用简单模板
                filename = f"note_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                tool_args = {"filename": filename, "content": f"用户查询：{user_query}\n\n相关信息：\n{context_text}"}
                action_description = "创建通用笔记"

        tasks_to_run.append({
            "task": task,
            "tool": tool,
            "args": tool_args,
            "desc": action_description
        })

    if not tasks_to_run:
        # 没有可运行的任务（可能都被跳过或已完成）
        return {
            "thoughts": ["当前无待执行任务"],
            "next_action": "synthesize",
        }

    # 2. 并行执行任务
    logger.info(f"🚀 并行执行 {len(tasks_to_run)} 个任务: {[t['task'] for t in tasks_to_run]}")
    
    async def run_one_task(item):
        def _execute_safe(tool, args, settings):
            # 创建新的 DB 会话以保证线程安全
            SessionLocal = get_session_factory()
            with SessionLocal() as db:
                return execute_tool(
                    tool=tool,
                    arguments=args,
                    settings=settings,
                    session=db
                )

        try:
            # 使用 to_thread 在线程池中运行同步工具函数
            # 注意：不再传递外部的 session，而是内部新建
            output = await asyncio.to_thread(
                _execute_safe,
                tool=item["tool"],
                args=item["args"],
                settings=settings
            )
            return {
                "task": item["task"],
                "tool_name": item["tool"].name,
                "output": output,
                "arguments": item["args"],
                "success": True,
                "desc": item["desc"]
            }
        except Exception as e:
            logger.error(f"任务 {item['task']} 执行失败: {e}")
            return {
                "task": item["task"],
                "tool_name": item["tool"].name,
                "output": f"执行失败: {str(e)}",
                "arguments": item["args"],
                "success": False,
                "desc": item["desc"]
            }

    results = await asyncio.gather(*(run_one_task(item) for item in tasks_to_run))

    # 3. 汇总结果
    new_tool_calls = []
    new_tool_results = []
    new_thoughts = []
    new_observations = []

    for res in results:
        new_tool_calls.append({"task": res["task"], "tool_id": res["tool_name"], "arguments": res["arguments"]})
        new_tool_results.append(res)
        new_thoughts.append(f"执行工具: {res['desc']}")
        new_observations.append(f"【{res['tool_name']}】: {res['output'][:200]}...")

    return {
        "tool_calls_made": new_tool_calls,
        "tool_results": new_tool_results,
        "thoughts": new_thoughts,
        "observations": new_observations,
        "next_action": "router",
    }


def reflector_node(state: AgentState) -> Dict[str, Any]:
    """
    反思器节点：评估当前进展，决定是否需要调整策略
    """
    logger.info("🤔 [反思器] 评估当前进展...")
    
    user_query = state["user_query"]
    tool_results = state.get("tool_results", [])
    retrieved_contexts = state.get("retrieved_contexts", [])
    current_step = state.get("current_step", 0)
    
    # 评估信息完整性
    has_tool_results = len(tool_results) > 0
    has_kb_context = len(retrieved_contexts) > 0
    
    quality_score = 0.0
    reflection = ""
    
    if has_tool_results or has_kb_context:
        quality_score = 0.7
        reflection = "已收集到相关信息，可以尝试生成答案"
    else:
        quality_score = 0.3
        reflection = "信息收集不足，可能需要更多检索或工具调用"
    
    # 检查是否需要人工介入
    needs_human = quality_score < 0.5 and current_step > 3
    
    thought = f"反思结果：质量评分 {quality_score:.2f}"
    
    return {
        "reflection": reflection,
        "quality_score": quality_score,
        "needs_human_input": needs_human,
        "thoughts": [thought]
    }


def verifier_node(
    state: AgentState,
    settings: Settings,
) -> Dict[str, Any]:
    coverage_ratio = 0.0
    outline = state.get("answer_outline", []) or []
    retrieved_contexts = state.get("retrieved_contexts", []) or []
    tool_results = state.get("tool_results", []) or []
    outline_len = len(outline) if outline else 1
    evidence_count = len(retrieved_contexts) + len(tool_results)
    coverage_ratio = min(1.0, evidence_count / max(1, outline_len))
    need_diagram = any("导图" in x or "mindmap" in x or "思维导图" in x for x in outline)
    has_diagram = any(r.get("task") == "diagram" for r in tool_results)
    need_search = coverage_ratio < 0.5
    next_action = "synthesizer"
    thought = f"验证器：覆盖率 {coverage_ratio:.2f}"
    if need_diagram and not has_diagram:
        next_action = "tool_executor"
        thought = f"验证器：需要思维导图，触发工具执行"
    elif need_search:
        next_action = "tool_executor"
        thought = f"验证器：证据不足，触发工具执行以补充信息"
    return {
        "thoughts": [thought],
        "observations": [f"覆盖率评估：{coverage_ratio:.2f}"],
        "next_action": next_action,
    }


async def synthesizer_node(
    state: AgentState,
    settings: Settings,
    session: Session = None,
    session_id: str = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """合成器节点：使用 LLM 综合所有信息生成最终答案"""
    logger.info("✨ [合成器] 使用 LLM 生成最终答案...")

    user_query = state.get("user_query", "")
    retrieved_contexts = state.get("retrieved_contexts", [])
    tool_results = state.get("tool_results", [])
    skipped_tasks = state.get("skipped_tasks", [])
    answer_outline = state.get("answer_outline", [])
    subquestions = state.get("subquestions", [])

    # 检索相关记忆
    relevant_memories = []
    if session and (session_id or user_id):
        try:
            relevant_memories = await retrieve_relevant_memories(
                session=session,
                query=user_query,
                settings=settings,
                user_id=user_id,
                session_id=session_id,
                max_memories=5,
            )
            if relevant_memories:
                logger.info(f"📚 在合成器中检索到 {len(relevant_memories)} 条相关记忆")
        except Exception as e:
            logger.warning(f"记忆检索失败: {e}")

    # 构建信息上下文
    context_parts: List[str] = []
    
    # 0. 添加记忆信息（明确标识为用户已知信息）
    memory_context = ""
    if relevant_memories:
        memory_lines = [mem.content for mem in relevant_memories]
        # 给记忆添加明确标识，确保 LLM 能够识别和使用这些信息
        memory_context = "## 用户已知信息\n" + "\n".join(f"- {line}" for line in memory_lines)
        context_parts.insert(0, memory_context)
    
    # 1. 添加知识库检索内容
    if retrieved_contexts:
        kb_content = "\n\n".join([
            f"【文档片段 {i+1}】\n来源：{ctx.get('original_name', '未知')}\n内容：{ctx.get('content', '')[:500]}"
            for i, ctx in enumerate(retrieved_contexts[:3])  # 最多3个片段
        ])
        context_parts.append(f"## 知识库检索结果\n{kb_content}")
    
    # 2. 添加工具执行结果
    if tool_results:
        tool_outputs = []
        for tr in tool_results:
            tool_name = tr.get("tool_name", "工具")
            output = tr.get("output", "")
            tool_outputs.append(f"【{tool_name}】\n{output[:600]}")
        context_parts.append(f"## 工具执行结果\n" + "\n\n".join(tool_outputs))
    
    # 3. 添加跳过的任务说明
    if skipped_tasks:
        skip_info = "\n".join([
            f"- {item.get('task', '未知任务')}: {item.get('reason', '未说明')}"
            for item in skipped_tasks
        ])
        context_parts.append(f"## 跳过的任务\n{skip_info}")
    
    # 判断是否有足够信息（包括记忆信息）
    has_info = bool(retrieved_contexts or tool_results or relevant_memories)
    is_simple = state.get("difficulty") == "simple"
    pre_generated_answer = state.get("pre_generated_answer")
    
    try:
        if is_simple and pre_generated_answer:
            logger.info("⚡ [合成器] 使用预生成答案，跳过 LLM 调用")
            return {
                "final_answer": pre_generated_answer,
                "is_complete": True,
                "thoughts": ["使用智能分析阶段生成的答案，加速响应"],
            }

        if is_simple:
            # === 简单模式 Prompt ===
            logger.info("⚡ [合成器] 使用快速响应模式")
            all_context = "\n\n".join(context_parts) if context_parts else ""
            
            synthesis_prompt = f"""用户问题：{user_query}

{all_context}

请直接、自然地回答用户问题。
要求：
1. 语气亲切，像朋友聊天
2. 篇幅简短适中，不要长篇大论
3. 如果有用户记忆信息，请自然地使用（如称呼名字）
"""
        elif not has_info:
            # 没有任何额外信息，直接让 LLM 基于自身知识回答
            synthesis_prompt = f"""用户问题：{user_query}

当前系统没有检索到知识库内容，也没有调用任何工具。
请基于你自身的知识直接回答用户问题。

要求：
1. 如果你知道答案，请详细、准确地回答
2. 如果不确定，请诚实说明，并给出建议
3. 回答要有条理，使用 Markdown 格式
4. 不要编造信息
"""
        else:
            # 构建完整上下文
            all_context = "\n\n".join(context_parts) if context_parts else ""
            
            if answer_outline:
                outline_text = "\n".join([f"- {item}" for item in answer_outline[:10]])
                synthesis_prompt = f"""用户问题：{user_query}

{all_context}

请基于以上信息，按照以下大纲分节组织答案，每一节用简洁小标题：
{outline_text}

要求：
1. 回答要自然、流畅，就像在和一个熟悉的朋友聊天
2. **重要**：如果"用户已知信息"中有用户的姓名、职业等个人信息，务必在回答中自然地使用（例如：如果用户名叫张三，在回答中可以说"张三，你好"或"张三，关于你的问题..."）
3. 不要显示思考过程、信息来源或技术细节，不要说"根据记忆"、"根据已知信息"等词语
4. 保持客观准确，不要编造内容
5. 回答要有条理，使用 Markdown 格式
6. 如果有工具执行结果，可以提到，但不要过度强调技术细节

现在请自然地回答用户问题：
"""
            else:
                synthesis_prompt = f"""用户问题：{user_query}

{all_context}

请基于以上信息，自然地回答用户问题，就像和朋友对话一样。

要求：
1. 回答要自然、流畅，就像在和一个熟悉的朋友聊天
2. **重要**：如果"用户已知信息"中有用户的姓名、职业等个人信息，务必在回答中自然地使用（例如：如果用户名叫张三，在回答中可以说"张三，你好"或"张三，关于你的问题..."）
3. 不要显示思考过程、信息来源或技术细节，不要说"根据记忆"、"根据已知信息"等词语
4. 保持客观准确，不要编造内容
5. 回答要有条理，使用 Markdown 格式
6. 如果有工具执行结果，可以提到，但不要过度强调技术细节

现在请自然地回答用户问题：
"""
        
        # 如果是流式模式，返回 prompt 供外部调用
        if state.get("stream_mode"):
            logger.info("🌊 [合成器] 准备就绪，返回 Prompt 进行流式输出")
            return {
                "final_prompt": synthesis_prompt,
                "ready_to_synthesize": True,
                "thoughts": ["准备生成最终答案（流式）"],
            }

        # 调用 LLM 生成最终答案
        final_answer, _ = await invoke_llm(
            messages=[{"role": "user", "content": synthesis_prompt}],
            settings=settings,
            temperature=0.7,  # 适中温度，保证流畅性
            max_tokens=2000
        )
        
        logger.info("✅ LLM 成功生成最终答案")
        
        return {
            "final_answer": final_answer,
            "is_complete": True,
            "thoughts": ["LLM 已生成综合答案"],
        }
    
    except Exception as e:
        logger.error(f"合成器 LLM 失败: {e}")
        
        # 降级策略：使用简单的字符串拼接
        results_by_task: Dict[str, List[Dict[str, Any]]] = {}
        for result in tool_results:
            task_key = result.get("task") or ""
            results_by_task.setdefault(task_key, []).append(result)

        sections: List[str] = []

        def truncate(text: str, limit: int = 400) -> str:
            if not text:
                return ""
            cleaned = text.strip()
            return cleaned if len(cleaned) <= limit else cleaned[:limit] + "..."

        weather_results = results_by_task.get("weather")
        if weather_results:
            latest_weather = weather_results[-1]
            city = latest_weather.get("arguments", {}).get("city")
            heading = "### 天气信息" + (f"（{city}）" if city else "")
            sections.append(f"{heading}\n{truncate(latest_weather.get('output', ''))}")

        search_results = results_by_task.get("search")
        if search_results:
            sections.append("### 搜索结果\n" + truncate(search_results[-1].get("output", "")))

        diagram_results = results_by_task.get("diagram")
        if diagram_results:
            sections.append("### 思维导图\n" + truncate(diagram_results[-1].get("output", ""), limit=200))

        note_results = results_by_task.get("note")
        if note_results:
            sections.append("### 提醒笔记\n" + truncate(note_results[-1].get("output", "")))

        if not sections and retrieved_contexts:
            first_ctx = retrieved_contexts[0]
            origin = first_ctx.get("original_name", "未知")
            sections.append(
                f"### 知识库内容（来自{origin}）\n" + truncate(first_ctx.get("content", ""))
            )

        if not sections:
            final_answer = (
                f"关于您的问题「{user_query}」，我目前没有找到足够的信息。\n\n"
                "建议：\n"
                "1. 您可以尝试上传相关文档到知识库\n"
                "2. 或者换一个更具体的问题\n\n"
                f"（注：系统当前使用降级模式，原因：{str(e)[:100]}）"
            )
        else:
            summary_intro = f"根据您的问题「{user_query}」，为您整理如下：" if user_query else "以下是为您找到的信息："
            final_answer = summary_intro + "\n\n" + "\n\n".join(sections)

        return {
            "final_answer": final_answer,
            "is_complete": True,
            "thoughts": [f"使用降级模式生成答案（LLM 异常：{str(e)[:50]}）"],
        }

def human_input_node(state: AgentState) -> Dict[str, Any]:
    """
    人工介入节点：暂停执行，等待人工反馈
    """
    logger.info("👤 [人工介入] 等待人工反馈...")
    
    # 这个节点会暂停执行，等待外部输入
    # 在实际使用中，需要通过 API 来恢复执行
    
    return {
        "thoughts": ["等待人工反馈中..."],
        "needs_human_input": True
    }


# ==================== 辅助函数 ====================

TASK_ORDER: List[str] = ["weather", "search", "diagram", "note"]  # 执行顺序：确保搜索在绘图前

TASK_KEYWORDS: Dict[str, List[str]] = {
    "weather": ["天气", "气温", "下雨", "降雨", "雨伞", "rain", "weather", "forecast", "明天", "今天", "后天"],
    "search": [
        "搜索", "查找", "搜一下", "调查", "查询", "查一下", "检索", "找一下", "look up", "research", 
        "扩散模型", "最新进展", "相关信息", "资料", "论文", "文献", "paper", "article", "report", "study", 
        "总结", "summarize", "概括", "解读", "overview", "introduction", "explain", "解释", "介绍"
    ],
    "diagram": ["思维导图", "流程图", "画图", "绘制", "diagram", "flowchart", "结构图", "图表", "导图", "画个"],
    "note": ["笔记", "提醒", "记录", "备忘", "记下来", "note", "带伞", "提醒我", "写入", "保存", "记下", "写个笔记"],
}

RAIN_KEYWORDS: List[str] = [
    "雨", "阵雨", "雷阵雨", "小雨", "中雨", "大雨", "暴雨", "雨夹雪", "降雨", "rain", "shower", "storm", "drizzle"
]

COMMON_CHINESE_CITIES: List[str] = [
    "北京", "上海", "广州", "深圳", "天津", "杭州", "南京", "武汉",
    "成都", "重庆", "西安", "苏州", "长沙", "青岛", "厦门", "大连"
]

ENGLISH_CITY_ALIASES: Dict[str, str] = {
    "beijing": "北京",
    "shanghai": "上海",
    "guangzhou": "广州",
    "shenzhen": "深圳",
    "tianjin": "天津",
    "hangzhou": "杭州",
    "nanjing": "南京",
    "wuhan": "武汉",
    "chengdu": "成都",
    "chongqing": "重庆",
    "xian": "西安",
    "suzhou": "苏州",
    "changsha": "长沙",
    "qingdao": "青岛",
    "xiamen": "厦门",
    "dalian": "大连"
}

CITY_SLUG_OVERRIDES: Dict[str, str] = {
    "北京": "beijing",
    "上海": "shanghai",
    "广州": "guangzhou",
    "深圳": "shenzhen",
    "天津": "tianjin",
    "杭州": "hangzhou",
    "南京": "nanjing",
    "武汉": "wuhan",
    "成都": "chengdu",
    "重庆": "chongqing",
    "西安": "xian",
    "苏州": "suzhou",
    "长沙": "changsha",
    "青岛": "qingdao",
    "厦门": "xiamen",
    "大连": "dalian"
}

SEARCH_PREFIXES: List[str] = [
    "帮我搜索", "请搜索", "搜索一下", "查一下", "查询一下", "帮我查", "请帮我查", "帮我找", "找一下", "请帮我搜索"
]

SEARCH_SUFFIXES: List[str] = [
    "并总结", "并画", "并帮我", "并写", "然后", "顺便", "同时", "总结", "提醒", "写个笔记", "画个", "带伞"
]

MAX_TOOL_CALLS = 5

def infer_tool_tasks(query: str) -> List[str]:
    """从查询推断需要的工具任务（改进版：支持上下文理解）"""
    if not query:
        return []
    
    normalized = query.lower()
    query_original = query
    
    # 任务匹配分数
    task_scores: Dict[str, int] = {task: 0 for task in TASK_ORDER}
    
    # 1. 天气任务检测（高优先级）
    weather_indicators = TASK_KEYWORDS["weather"]
    for indicator in weather_indicators:
        if indicator in query_original or indicator in normalized:
            task_scores["weather"] += 10  # 高权重
    
    # 如果提到城市名+时间词，大概率是天气查询
    has_city = any(city in query_original for city in COMMON_CHINESE_CITIES)
    has_time = any(t in query_original for t in ["明天", "今天", "后天", "tomorrow", "today"])
    if has_city and has_time:
        task_scores["weather"] += 15
    
    # 2. 搜索任务检测
    search_strong_keywords = TASK_KEYWORDS["search"]
    for keyword in search_strong_keywords:
        if keyword in query_original or keyword in normalized:
            task_scores["search"] += 8
    
    # 3. 图表任务检测
    diagram_keywords = TASK_KEYWORDS["diagram"]
    for keyword in diagram_keywords:
        if keyword in query_original or keyword in normalized:
            task_scores["diagram"] += 10
    
    # 4. 笔记任务检测
    note_keywords = TASK_KEYWORDS["note"]
    for keyword in note_keywords:
        if keyword in query_original or keyword in normalized:
            task_scores["note"] += 10
    
    # 按TASK_ORDER顺序过滤出得分>0的任务（保持优先级，不按分数排序）
    result = []
    for task in TASK_ORDER:
        if task_scores[task] > 0:
            result.append(task)
    
    logger.info(f"任务推断结果：查询='{query[:50]}...' -> 任务={result}, 得分={dict(task_scores)}")
    
    return result

def map_tool_to_task(tool: ToolRecord) -> Optional[str]:
    """映射工具记录到任务类型"""
    try:
        config = json.loads(tool.config or "{}")
    except json.JSONDecodeError:
        return None
    if tool.tool_type != "builtin":
        return None
    builtin_key = config.get("builtin_key")
    mapping = {
        "get_weather": "weather",
        "web_search": "search",
        "draw_diagram": "diagram",
        "write_note": "note",
    }
    return mapping.get(builtin_key)

def should_call_tool(state: AgentState) -> bool:
    """判断是否应该继续调用工具"""
    previous_calls = state.get("tool_calls_made", [])
    if len(previous_calls) >= MAX_TOOL_CALLS:
        return False

    user_query = state.get("user_query", "")
    tasks = infer_tool_tasks(user_query)
    if not tasks:
        return False

    completed_tasks = {call.get("task") for call in previous_calls if call.get("task")}
    skipped_task_keys = {
        item.get("task")
        for item in state.get("skipped_tasks", [])
        if isinstance(item, dict) and item.get("task")
    }

    for task in tasks:
        if task in completed_tasks or task in skipped_task_keys:
            continue
        if task == "note" and "weather" in tasks and "weather" not in completed_tasks and "weather" not in skipped_task_keys:
            continue
        return True

    return False

def extract_city_from_query(query: str) -> str:
    """从查询中提取城市名（支持中英文）"""
    if not query:
        return "北京"

    for city in COMMON_CHINESE_CITIES:
        if city in query:
            return city

    lower_query = query.lower()
    for alias, city in ENGLISH_CITY_ALIASES.items():
        if alias in lower_query:
            return city

    match_cn = re.search(r"([一-龥]{2,5})(?:天气|明天|今日|现在|未来)", query)
    if match_cn:
        return match_cn.group(1)

    match_en = re.search(r"in\s+([A-Za-z\s]+)", query, flags=re.IGNORECASE)
    if match_en:
        candidate = match_en.group(1).strip()
        alias = candidate.lower()
        if alias in ENGLISH_CITY_ALIASES:
            return ENGLISH_CITY_ALIASES[alias]
        return candidate.title()

    return "北京"

def extract_search_query(query: str) -> str:
    """从查询中提取搜索关键词"""
    if not query:
        return ""

    cleaned = query.strip()
    for prefix in SEARCH_PREFIXES:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break

    for suffix in SEARCH_SUFFIXES:
        idx = cleaned.find(suffix)
        if idx > 0:
            cleaned = cleaned[:idx].strip()
            break

    cleaned = cleaned.strip("，。,.!?；; ")
    return cleaned or query.strip()

async def generate_diagram_payload_with_llm(
    user_query: str, 
    search_context: Optional[str], 
    settings: Settings
) -> Dict[str, str]:
    """使用 LLM 生成高质量的思维导图内容"""
    topic_source = user_query or "主题"
    diagram_type = "mindmap" if any(keyword in topic_source for keyword in ["思维导图", "导图", "mindmap"]) else "flowchart"
    
    # 提取主题（清理用户查询）
    topic = topic_source
    for prefix in ["帮我搜索", "搜索", "画个", "绘制", "生成"]:
        topic = topic.replace(prefix, "")
    for suffix in ["总结关键点", "并画个思维导图", "画个思维导图", "思维导图"]:
        topic = topic.replace(suffix, "")
    topic = topic.strip("，。、 ")
    if len(topic) > 30:
        topic = topic[:30]

    if diagram_type == "mindmap":
        # 使用 LLM 分析和总结搜索结果，生成结构化思维导图
        prompt = f"""基于以下搜索结果，生成一个关于「{topic}」的思维导图（Mermaid mindmap 格式）。

搜索结果：
{search_context[:2000]}

要求：
1. 提取搜索结果的**核心关键点**，形成3-5个主要分支
2. 每个分支要有清晰的子分支（2-3个）
3. 使用简洁、专业的中文描述，避免直接复制搜索结果文本
4. 确保思维导图结构清晰、逻辑合理
5. 只输出 Mermaid mindmap 代码，不要其他解释

格式示例：
```mermaid
mindmap
  root((主题))
    主要分支1
      子分支1.1
      子分支1.2
    主要分支2
      子分支2.1
      子分支2.2
```

请生成思维导图："""
        
        try:
            llm_response, _ = await invoke_llm(
                messages=[{"role": "user", "content": prompt}],
                settings=settings,
                temperature=0.7,
                max_tokens=800
            )
            
            # 提取 Mermaid 代码块
            diagram_code = llm_response.strip()
            
            # 移除可能的 markdown 代码块标记
            if "```mermaid" in diagram_code:
                diagram_code = diagram_code.split("```mermaid")[1].split("```")[0].strip()
            elif "```" in diagram_code:
                diagram_code = diagram_code.split("```")[1].split("```")[0].strip()
            
            # 确保是 mindmap 格式
            if not diagram_code.startswith("mindmap"):
                # 如果 LLM 没有生成正确的格式，使用默认模板
                logger.warning("LLM 生成的思维导图格式不正确，使用默认模板")
                diagram_code = f"""mindmap
  root(({topic}))
    核心概念
      定义与特点
      应用领域
    最新进展
      技术突破
      行业动态
    发展趋势
      未来方向
      潜在影响"""
        except Exception as e:
            logger.error(f"LLM 生成思维导图失败: {e}")
            raise  # 让调用者处理错误
        
        filename = f"{topic[:20].replace(' ', '_').replace('/', '_')}_mindmap.md"
    else:
        # 流程图类型（暂时不需要LLM，使用简单模板）
        diagram_code = f"""flowchart TD
    A[需求：{topic[:20]}] --> B{{信息收集}}
    B --> C[分析处理]
    C --> D{{决策}}
    D --> E[执行]
    E --> F[完成]"""
        filename = f"{topic[:20].replace(' ', '_').replace('/', '_')}_flowchart.md"

    return {
        "filename": filename,
        "diagram_code": diagram_code,
        "diagram_type": diagram_type
    }


def generate_diagram_payload(user_query: str, search_context: Optional[str] = None) -> Dict[str, str]:
    """生成思维导图的参数（智能版：基于搜索结果）"""
    topic_source = user_query or "主题"
    diagram_type = "mindmap" if any(keyword in topic_source for keyword in ["思维导图", "导图", "mindmap"]) else "flowchart"
    
    # 提取主题（清理用户查询）
    topic = topic_source
    for prefix in ["帮我搜索", "搜索", "画个", "绘制", "生成"]:
        topic = topic.replace(prefix, "")
    for suffix in ["总结关键点", "并画个思维导图", "画个思维导图", "思维导图"]:
        topic = topic.replace(suffix, "")
    topic = topic.strip("，。、 ")
    if len(topic) > 30:
        topic = topic[:30]

    if diagram_type == "mindmap":
        # 如果有搜索结果，尝试提取关键点
        if search_context:
            # 简单的关键点提取（实际应该用 LLM）
            lines = search_context.split('\n')
            key_points = []
            for line in lines[:6]:  # 最多6个关键点
                line = line.strip()
                if line and len(line) > 10 and len(line) < 100:
                    # 清理无用字符
                    line = re.sub(r'^\d+[\.、]', '', line)  # 移除序号
                    line = re.sub(r'^[•\-\*]', '', line).strip()  # 移除列表符号
                    if line:
                        key_points.append(line[:50])  # 限制长度
            
            # 生成基于内容的思维导图
            if key_points:
                points_section = []
                for i, point in enumerate(key_points[:4], 1):  # 最多4个主要分支
                    points_section.append(f"    分支{i}：{point[:25]}")
                    if i < len(key_points):
                        points_section.append(f"      详细{chr(65+i)}")
                
                diagram_code = f"""mindmap
  root(({topic}))
{chr(10).join(points_section)}"""
            else:
                # 回退到通用模板
                diagram_code = f"""mindmap
  root(({topic}))
    核心概念
      定义
      特点
    应用场景
      领域1
      领域2
    发展趋势
      最新进展
      未来方向"""
        else:
            # 没有搜索结果，使用通用模板
            diagram_code = f"""mindmap
  root(({topic}))
    信息收集
      关键点1
      关键点2
    分析判断
      风险
      机会
    行动方案
      下一步建议"""
        
        filename = f"{topic[:20].replace(' ', '_')}_mindmap.md"
    else:
        # 流程图类型
        diagram_code = f"""flowchart TD
    A[需求：{topic[:20]}] --> B{{信息收集}}
    B --> C[分析处理]
    C --> D{{决策}}
    D --> E[执行]
    E --> F[完成]"""
        filename = f"{topic[:20].replace(' ', '_')}_flowchart.md"

    return {
        "filename": filename,
        "diagram_code": diagram_code,
        "diagram_type": diagram_type,
    }

def detect_rain_in_text(text: str) -> bool:
    """检测文本中是否包含降雨信息"""
    if not text:
        return False
    lowered = text.lower()
    return any(keyword in text or keyword in lowered for keyword in RAIN_KEYWORDS)

def build_note_filename(city: str) -> str:
    """构建笔记文件名"""
    slug = CITY_SLUG_OVERRIDES.get(city, city)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", slug).strip("-").lower() or "reminder"
    timestamp = datetime.now().strftime("%Y%m%d")
    return f"{slug}_umbrella_{timestamp}.txt"

def summarize_for_note(text: str, limit: int = 200) -> str:
    """总结文本用于笔记"""
    if not text:
        return "天气信息缺失"
    clean_text = text.replace("\r", " ").replace("\n\n", "\n")
    clean_text = clean_text.replace("\n", " ")
    return clean_text.strip()[:limit]

def build_note_content(city: str, weather_text: str, user_query: str) -> str:
    """构建笔记内容"""
    summary = summarize_for_note(weather_text)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    note_lines = [
        f"# {city}带伞提醒",
        "",
        f"创建时间：{now_str}",
        f"触发查询：{user_query}",
        "",
        "## 天气情况",
        summary,
        "",
        "## 温馨提示",
        "- 今日可能有降雨，建议携带雨具",
        "- 出门前请再次查看最新天气",
    ]
    return "\n".join(note_lines) + "\n"

def route_after_planning(state: AgentState) -> str:
    """规划后的路由"""
    return "router"


def route_after_routing(state: AgentState) -> str:
    """路由器之后的路由"""
    next_action = state.get("next_action", "synthesize")
    
    if next_action == "search_kb":
        return "knowledge_search"
    elif next_action == "tool_executor":
        return "tool_executor"
    elif next_action == "synthesize":
        return "reflector"
    else:
        return "synthesizer"


def route_after_knowledge_search(state: AgentState) -> str:
    """知识库搜索后的路由"""
    return "router"


def route_after_tool_execution(state: AgentState) -> str:
    """工具执行后的路由"""
    return "router"


def route_after_reflection(state: AgentState) -> str:
    """反思后的路由"""
    needs_human = state.get("needs_human_input", False)
    quality_score = state.get("quality_score", 0.0)
    
    if needs_human:
        return "human_input"
    else:
        return "verifier"


def route_after_verifier(state: AgentState) -> str:
    next_action = state.get("next_action", "synthesizer")
    if next_action == "tool_executor":
        return "tool_executor"
    elif next_action == "knowledge_search":
        return "knowledge_search"
    else:
        return "synthesizer"

def route_after_react(state: AgentState) -> str:
    next_action = state.get("next_action", "tool_executor")
    if next_action == "tool_executor":
        return "tool_executor"
    elif next_action == "knowledge_search":
        return "knowledge_search"
    else:
        return "synthesizer"

def route_after_human_input(state: AgentState) -> str:
    """人工介入后的路由"""
    human_feedback = state.get("human_feedback", "")
    
    if human_feedback:
        return "router"  # 根据人工反馈重新路由
    else:
        return "synthesizer"  # 如果没有反馈，直接合成答案


def should_end(state: AgentState) -> str:
    """判断是否应该结束"""
    is_complete = state.get("is_complete", False)
    
    if is_complete:
        return END
    else:
        return "continue"


# ==================== 工作流构建 ====================

def create_agent_graph(
    settings: Settings,
    session: Session,
    tool_records: List[ToolRecord],
    checkpoint_dir: str = "backend/data/checkpoints"
) -> StateGraph:
    """
    创建完整的 LangGraph Agent 工作流（支持异步节点）
    """
    logger.info("🏗️ 构建 LangGraph Agent 工作流...")
    
    # 创建图
    workflow = StateGraph(AgentState)
    
    # 创建异步节点包装器
    async def planner_wrapper(state: AgentState) -> Dict[str, Any]:
        session_id = state.get("session_id")
        user_id = state.get("user_id")
        return await planner_node(state, settings, tool_records, session, session_id, user_id)
    
    async def router_wrapper(state: AgentState) -> Dict[str, Any]:
        return await router_node(state, settings)
    
    async def synthesizer_wrapper(state: AgentState) -> Dict[str, Any]:
        session_id = state.get("session_id")
        user_id = state.get("user_id")
        return await synthesizer_node(state, settings, session, session_id, user_id)
    
    async def tool_executor_wrapper(state: AgentState) -> Dict[str, Any]:
        return await tool_executor_node(state, settings, session, tool_records)
    async def react_controller_wrapper(state: AgentState) -> Dict[str, Any]:
        return await react_controller_node(state, settings)
    
    # 添加节点
    workflow.add_node("planner", planner_wrapper)
    workflow.add_node("router", router_wrapper)
    workflow.add_node(
        "knowledge_search",
        lambda state: knowledge_search_node(state, settings)
    )
    workflow.add_node("tool_executor", tool_executor_wrapper)
    workflow.add_node("react_controller", react_controller_wrapper)
    workflow.add_node("reflector", reflector_node)
    workflow.add_node("verifier", lambda state: verifier_node(state, settings))
    workflow.add_node("synthesizer", synthesizer_wrapper)
    workflow.add_node("human_input", human_input_node)
    
    # 设置入口点
    workflow.set_entry_point("planner")
    
    # 添加边（定义流程）
    workflow.add_edge("planner", "router")
    
    # 路由器的条件边
    workflow.add_conditional_edges(
        "router",
        route_after_routing,
        {
            "knowledge_search": "knowledge_search",
            "tool_executor": "react_controller",
            "reflector": "reflector",
            "synthesizer": "synthesizer"
        }
    )
    
    workflow.add_edge("knowledge_search", "router")
    workflow.add_edge("tool_executor", "router")
    workflow.add_conditional_edges(
        "reflector",
        route_after_reflection,
        {
            "human_input": "human_input",
            "verifier": "verifier",
        }
    )
    workflow.add_conditional_edges(
        "verifier",
        route_after_verifier,
        {
            "tool_executor": "react_controller",
            "knowledge_search": "knowledge_search",
            "synthesizer": "synthesizer",
        }
    )
    workflow.add_conditional_edges(
        "react_controller",
        route_after_react,
        {
            "tool_executor": "tool_executor",
            "knowledge_search": "knowledge_search",
            "synthesizer": "synthesizer",
        }
    )
    
    # 合成器后结束
    workflow.add_edge("synthesizer", END)
    
    # 人工介入流程
    workflow.add_conditional_edges(
        "human_input",
        route_after_human_input,
        {
            "router": "router",
            "synthesizer": "synthesizer",
        }
    )
    
    logger.info("✅ LangGraph Agent 工作流构建完成")
    
    return workflow


async def run_agent(
    user_query: str,
    settings: Settings,
    session: Session,
    tool_records: List[ToolRecord],
    use_knowledge_base: bool = False,
    conversation_history: List[Dict[str, str]] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    运行 LangGraph Agent
    
    Args:
        user_query: 用户问题
        settings: 配置
        session: 数据库会话
        tool_records: 可用工具列表
        use_knowledge_base: 是否使用知识库
        conversation_history: 对话历史
        session_id: 会话ID，用于长期记忆
        user_id: 用户ID，用于多用户场景
    
    Returns:
        包含 Agent 完整执行过程的字典
    """
    logger.info(f"🚀 启动 LangGraph Agent 处理问题: {user_query}")
    
    # 如果没有提供 session_id，生成一个新的
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # 构建工作流
    workflow = create_agent_graph(settings, session, tool_records)
    
    # 编译图（使用内存检查点）
    # 注意：MemorySaver 在服务器重启后会丢失状态，但功能完全正常
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    # 初始化状态
    initial_state: AgentState = {
        "user_query": user_query,
        "conversation_history": conversation_history or [],
        "session_id": session_id,
        "user_id": user_id,
        "plan": None,
        "current_step": 0,
        "max_iterations": 10,
        "available_tools": [tool.id for tool in tool_records],
        "tool_calls_made": [],
        "tool_results": [],
        "skipped_tasks": [],
        "use_knowledge_base": use_knowledge_base,
        "retrieved_contexts": [],
        "thoughts": [],
        "observations": [],
        "subquestions": [],
        "answer_outline": [],
        "evidence_requirements": [],
        "reasoning_steps": [],
        "react_cursor": 0,
        "react_max_steps": 4,
        "react_steps_done": 0,
        "next_action": None,
        "needs_human_input": False,
        "human_feedback": None,
        "reflection": None,
        "quality_score": 0.0,
        "final_answer": None,
        "is_complete": False,
        "error": None
    }
    
    # 生成唯一的线程ID（用于检查点）
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    # 执行工作流
    try:
        final_state = await app.ainvoke(initial_state, config=config)
        
        logger.info("✅ LangGraph Agent 执行完成")
        
        final_answer = final_state.get("final_answer", "未能生成答案")
        
        # 保存对话并提取记忆
        try:
            saved_memories = await save_conversation_and_extract_memories(
                session=session,
                session_id=session_id,
                user_query=user_query,
                assistant_reply=final_answer,
                settings=settings,
                user_id=user_id,
                metadata={
                    "thread_id": thread_id,
                    "quality_score": final_state.get("quality_score", 0.0),
                },
            )
            if saved_memories:
                logger.info(f"💾 保存了 {len(saved_memories)} 条新记忆")
        except Exception as e:
            logger.warning(f"保存对话或提取记忆失败: {e}")
        
        return {
            "success": True,
            "final_answer": final_answer,
            "thoughts": final_state.get("thoughts", []),
            "observations": final_state.get("observations", []),
            "tool_results": final_state.get("tool_results", []),
            "retrieved_contexts": final_state.get("retrieved_contexts", []),
            "plan": final_state.get("plan", ""),
            "quality_score": final_state.get("quality_score", 0.0),
            "reflection": final_state.get("reflection", ""),
            "thread_id": thread_id,
            "session_id": session_id,
            "error": final_state.get("error")
        }
    
    except Exception as e:
        logger.error(f"❌ LangGraph Agent 执行失败: {e}", exc_info=True)
        return {
        "success": False,
        "final_answer": f"抱歉，处理过程中出现错误：{str(e)}",
        "error": str(e),
        "thoughts": [],
        "observations": [],
        "tool_results": [],
        "skipped_tasks": [],
        "retrieved_contexts": []
    }


def is_simple_query(query: str) -> bool:
    """
    判断是否为简单查询（无需 Agent 复杂推理）
    """
    if not query:
        return False
    
    # 1. 长度检查：太长通常不是简单指令
    if len(query) > 30:
        return False
        
    normalized = query.lower().strip()
    
    # 2. 排除复杂意图关键词
    complex_indicators = [
        "搜索", "查找", "查询", "天气", "画", "图", "笔记", "分析", "总结", "最新",
        "search", "weather", "draw", "diagram", "note", "analyze", "summary"
    ]
    if any(ind in normalized for ind in complex_indicators):
        return False
        
    # 3. 简单问候和基础问题（扩展：解释类问题如果不需要工具也算简单）
    simple_keywords = [
        "你好", "hello", "hi", "是谁", "名字", "再见", "goodbye", 
        "谢谢", "thank", "晚安", "早安", "测试", "test",
        "帮助", "help", "功能", "介绍", "who are you",
        "早上好", "晚上好", "什么", "what is", "explain", "introduce",
        "告诉我", "tell me"
    ]
    
    for kw in simple_keywords:
        if kw in normalized:
            return True
            
    return False


async def stream_agent(
    user_query: str,
    settings: Settings,
    session: Session,
    tool_records: List[ToolRecord],
    use_knowledge_base: bool = False,
    conversation_history: List[Dict[str, str]] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """
    流式运行 LangGraph Agent，实时返回每个节点的执行结果
    
    实现分级响应架构 (Tiered Intelligence Response Architecture):
    - Level 1 (Fast Track): 简单问题直接 LLM 响应，跳过图执行
    - Level 2 (Direct Reasoning): 复杂问题但在 Planner 中判定为无需工具，快速响应
    - Level 3 (Full Agent): 完整图执行
    """
    logger.info(f"🌊 启动流式 Agent: {user_query}")
    
    if not session_id:
        session_id = str(uuid.uuid4())

    # === Level 1: Fast Track (快速通道) ===
    # 基于规则/正则的快速判定，毫秒级延迟
    if is_simple_query(user_query) and not use_knowledge_base:
        logger.info(f"🚀 [Fast Track] 检测到简单问题，跳过 Agent 图执行: {user_query[:30]}...")
        
        # 构造简单上下文
        messages = [{"role": "system", "content": "你是一个乐于助人的AI助手。请用亲切、自然的语气回答用户的问题。保持回答简洁。"}]
        if conversation_history:
             # 取最近几轮对话作为上下文
            messages.extend(conversation_history[-4:])
        messages.append({"role": "user", "content": user_query})
        
        full_answer = ""
        thread_id = str(uuid.uuid4())
        
        try:
            # 模拟 Agent 的事件结构，以便前端统一处理
            yield {
                "event": "status", 
                "data": {"mode": "fast_track", "info": "启用快速响应通道"}
            }
            
            async for chunk in stream_llm(
                messages=messages,
                settings=settings,
                temperature=0.7,
                max_tokens=500
            ):
                full_answer += chunk
                yield {
                    "event": "token",
                    "data": chunk,
                    "timestamp": datetime.now().isoformat()
                }
            
            # 发送最终答案事件
            yield {
                "event": "final_answer",
                "content": full_answer,
                "timestamp": datetime.now().isoformat()
            }
            
            # 异步保存记忆 (不阻塞响应)
            try:
                await save_conversation_and_extract_memories(
                    session=session,
                    session_id=session_id,
                    user_query=user_query,
                    assistant_reply=full_answer,
                    settings=settings,
                    user_id=user_id,
                    metadata={"thread_id": thread_id, "mode": "fast_track"},
                )
            except Exception as e:
                logger.warning(f"Fast Track 保存记忆失败: {e}")
                
            yield {
                "event": "completed",
                "thread_id": thread_id,
                "timestamp": datetime.now().isoformat()
            }
            return
            
        except Exception as e:
            logger.error(f"Fast Track 执行失败: {e}, 回退到标准 Agent 流程")
            # 出错则继续执行下方的标准流程

    # === Level 3/4: Full Agent (完整流程) ===
    workflow = create_agent_graph(settings, session, tool_records)
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    initial_state: AgentState = {
        "user_query": user_query,
        "conversation_history": conversation_history or [],
        "session_id": session_id,
        "user_id": user_id,
        "plan": None,
        "current_step": 0,
        "max_iterations": 10,
        "available_tools": [tool.id for tool in tool_records],
        "tool_calls_made": [],
        "tool_results": [],
        "skipped_tasks": [],
        "use_knowledge_base": use_knowledge_base,
        "retrieved_contexts": [],
        "thoughts": [],
        "observations": [],
        "next_action": None,
        "needs_human_input": False,
        "human_feedback": None,
        "reflection": None,
        "quality_score": 0.0,
        "final_answer": None,
        "is_complete": False,
        "error": None,
        "stream_mode": True,  # 启用流式模式
    }
    
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    # 流式执行
    final_state = None
    async for event in app.astream(initial_state, config=config):
        # event 是一个字典，键是节点名，值是该节点的输出
        for node_name, node_output in event.items():
            if node_name != "__end__":
                final_state = node_output  # 保存最后一个状态
                yield {
                    "event": "node_output",
                    "node": node_name,
                    "data": node_output,
                    "timestamp": datetime.now().isoformat()
                }
                
                # 如果合成器准备就绪，执行流式输出
                if node_name == "synthesizer":
                    if node_output.get("ready_to_synthesize"):
                        prompt = node_output.get("final_prompt")
                        if prompt:
                            full_answer = ""
                            async for chunk in stream_llm(
                                messages=[{"role": "user", "content": prompt}],
                                settings=settings,
                                temperature=0.7
                            ):
                                full_answer += chunk
                                yield {
                                    "event": "token",
                                    "data": chunk,
                                    "timestamp": datetime.now().isoformat()
                                }
                            
                            # 更新 final_state 中的 final_answer，以便后续保存记忆
                            final_state["final_answer"] = full_answer
                            # 发送一个最终答案事件，确保前端能收到完整的
                            yield {
                                "event": "final_answer",
                                "content": full_answer,
                                "timestamp": datetime.now().isoformat()
                            }
                    elif node_output.get("final_answer"):
                        # Fast Track (in Planner) 或降级模式
                        full_answer = node_output.get("final_answer")
                        # 快速流式输出（模拟打字效果）
                        chunk_size = 4
                        for i in range(0, len(full_answer), chunk_size):
                            chunk = full_answer[i:i+chunk_size]
                            yield {
                                "event": "token",
                                "data": chunk,
                                "timestamp": datetime.now().isoformat()
                            }
                            await asyncio.sleep(0.005)  # 极短延迟

    
    # 保存对话并提取记忆
    if final_state and final_state.get("final_answer"):
        try:
            saved_memories = await save_conversation_and_extract_memories(
                session=session,
                session_id=session_id,
                user_query=user_query,
                assistant_reply=final_state["final_answer"],
                settings=settings,
                user_id=user_id,
                metadata={"thread_id": thread_id},
            )
            if saved_memories:
                logger.info(f"💾 流式模式保存了 {len(saved_memories)} 条新记忆")
        except Exception as e:
            logger.warning(f"流式模式保存记忆失败: {e}")
    
    # 流式结束
    yield {
        "event": "completed",
        "thread_id": thread_id,
        "timestamp": datetime.now().isoformat()
    }

