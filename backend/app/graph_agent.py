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
from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Sequence, TypedDict

import httpx
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from sqlalchemy.orm import Session

from .config import Settings
from .database import ToolRecord
from .rag_service import retrieve_context
from .tool_service import execute_tool, parse_tool_call

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
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            response = await client.post(endpoint, json=payload, headers=headers)

        if response.status_code != 200:
            logger.error(
                "DeepSeek API error %s: %s", response.status_code, response.text
            )
            return f"API 调用失败: {response.status_code}", {}

        data = response.json()
        reply = data["choices"][0]["message"]["content"]
        return reply, data
    
    except Exception as e:
        logger.error(f"LLM 调用异常: {e}")
        return f"LLM 调用失败: {str(e)}", {}


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
    
    # 决策相关
    next_action: Optional[str]  # 下一步动作：tool_call, search_kb, synthesize, complete
    needs_human_input: bool  # 是否需要人工介入
    human_feedback: Optional[str]  # 人工反馈
    
    # 质量控制
    reflection: Optional[str]  # 反思结果
    quality_score: float  # 质量评分 0-1
    
    # 最终输出
    final_answer: Optional[str]  # 最终答案
    is_complete: bool  # 是否完成
    error: Optional[str]  # 错误信息


# ==================== 核心节点函数 ====================

async def planner_node(
    state: AgentState,
    settings: Settings,
    tool_records: List[ToolRecord],
) -> Dict[str, Any]:
    """
    规划器节点：使用 LLM 分析用户问题，生成智能执行计划
    """
    logger.info("🧠 [规划器] 开始智能分析任务...")
    
    user_query = state["user_query"]
    use_knowledge_base = state.get("use_knowledge_base", False)
    
    # 格式化工具描述
    tools_desc = format_tools_description(tool_records)
    
    # 构建智能规划提示词
    planning_prompt = f"""你是一个智能任务规划助手。请分析用户问题，制定执行计划。

用户问题：{user_query}

可用工具：
{tools_desc}

知识库：{"已启用" if use_knowledge_base else "未启用"}

请以 JSON 格式输出计划：
{{
  "task_type": "信息查询|工具调用|知识检索|复合任务",
  "analysis": "任务分析简述",
  "steps": ["步骤1", "步骤2", ...],
  "required_tools": ["tool_id_1", ...],
  "need_knowledge_base": true/false,
  "expected_result": "预期结果描述"
}}

注意：
1. task_type 从以下选择：信息查询、工具调用、知识检索、复合任务
2. steps 应该是具体的执行步骤
3. required_tools 是需要调用的工具ID列表，如果不需要工具则为空数组
4. 只返回 JSON，不要其他解释
"""
    
    try:
        # 调用 LLM 进行规划
        llm_response, _ = await invoke_llm(
            messages=[{"role": "user", "content": planning_prompt}],
            settings=settings,
            temperature=0.3,  # 低温度保证规划稳定
            max_tokens=1000
        )
        
        # 解析 LLM 返回的 JSON
        plan_data = parse_json_from_llm(llm_response)
        
        task_type = plan_data.get("task_type", "信息查询")
        analysis = plan_data.get("analysis", "分析任务中...")
        steps = plan_data.get("steps", ["分析问题", "生成答案"])
        
        logger.info(f"📋 规划完成：{task_type}, {len(steps)} 个步骤")
        
        # 格式化为可读文本
        plan_text = f"""任务类型：{task_type}
任务分析：{analysis}

执行步骤：
{chr(10).join(f"{i+1}. {step}" for i, step in enumerate(steps))}

预期结果：{plan_data.get('expected_result', '为用户提供准确答案')}
"""
        
        thought = f"智能规划完成：识别为【{task_type}】，共 {len(steps)} 个步骤"
        
        return {
            "plan": plan_text,
            "current_step": 0,
            "thoughts": [thought],
            "next_action": "route"
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
    
    # 检查是否超过最大迭代次数
    if current_step >= max_iterations:
        return {
            "next_action": "synthesize",
            "thoughts": [f"已达到最大迭代次数({max_iterations})，准备生成最终答案"],
            "current_step": current_step + 1
        }
    
    # 如果第一步，先进行简单判断（优化性能）
    if current_step == 0:
        kb_searched = any("知识库" in obs for obs in observations)
        
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
    
    # 步骤 >= 1，使用 LLM 智能决策
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
- 知识库检索状态：{kb_status_detail}
- 工具执行结果数：{len(tool_results)}

最近观察：
{chr(10).join("- " + obs for obs in observations[-3:]) if observations else "暂无观察"}

请判断下一步应该做什么：
A. search_kb - 需要从知识库检索信息
B. tool_executor - 需要调用外部工具获取数据
C. synthesize - 信息已足够，可以生成最终答案

要求：
1. 如果启用了知识库但还没检索（知识库检索状态显示"未检索"），优先选择 A
2. 如果知识库已经检索过（知识库检索状态显示"已检索"），不要重复选择 A，应该选择 B 或 C
3. 如果问题需要多个工具（如：搜索+绘图），必须执行完所有工具后再选择 C
4. 如果问题需要实时数据（天气、搜索等），但还没调用相应工具，选择 B
5. 如果已有足够信息且所有必要工具都已执行，选择 C
6. 只回复一个字母（A/B/C），不要解释
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
        
        # 防止重复搜索：如果已经检索过，不再选择 search_kb
        if use_knowledge_base and not kb_searched and current_step < 2:
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
    """工具执行器节点：智能选择并执行工具"""
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

    pending_task: Optional[str] = None
    for task in tasks:
        if task in completed_tasks or task in skipped_task_keys:
            continue
        pending_task = task
        break

    if not pending_task:
        return {
            "thoughts": ["天气结果未找到"],
            "observations": ["所有已识别任务均已完成或跳过"],
            "next_action": "synthesize",
        }

    selected_tool = tool_index.get(pending_task)
    if not selected_tool:
        reason = f"找不到任务 {pending_task} 对应的工具"
        logger.warning(reason)
        return {
            "skipped_tasks": [{"task": pending_task, "reason": reason}],
            "observations": [reason],
            "thoughts": ["找不到可用工具"],
        }

    logger.info("✅ 选择工具：任务 %s，工具名 %s", pending_task, selected_tool.name)

    tool_args: Dict[str, Any] = {}
    action_description = ""

    if pending_task == "weather":
        city = extract_city_from_query(user_query)
        tool_args = {"city": city}
        action_description = f"查询{city}天气"
    elif pending_task == "search":
        search_query = extract_search_query(user_query)
        tool_args = {"query": search_query, "num_results": 6}
        action_description = f"搜索'{search_query}'获取信息"
    elif pending_task == "diagram":
        # 检查是否有搜索结果，如果有，使用 LLM 生成高质量的思维导图
        search_context = None
        for result in reversed(tool_results):
            task_id = result.get("task")
            if task_id == "search":
                search_context = result.get("output", "")[:2000]  # 增加上下文长度
                break
        
        # 如果有搜索结果，使用 LLM 生成思维导图
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
    elif pending_task == "note":
        weather_result = None
        for result in reversed(tool_results):
            task_id = result.get("task")
            tool_name = result.get("tool_name", "")
            if task_id == "weather" or "天气" in tool_name:
                weather_result = result
                break

        if not weather_result:
            reason = "笔记任务依赖天气结果，但未找到"
            logger.warning(reason)
            return {
                "skipped_tasks": [{"task": "note", "reason": reason}],
                "observations": [reason],
                "thoughts": ["天气结果未找到"],
            }

        weather_text = weather_result.get("output", "")
        if not detect_rain_in_text(weather_text):
            reason = "天气预报无降雨，无需提醒带伞"
            logger.info(reason)
            return {
                "skipped_tasks": [{"task": "note", "reason": reason}],
                "observations": [reason],
                "thoughts": ["不满足条件，跳过"],
            }

        city_from_weather = weather_result.get("arguments", {}).get("city")
        if not city_from_weather:
            city_from_weather = extract_city_from_query(user_query)
        filename = build_note_filename(city_from_weather)
        note_content = build_note_content(city_from_weather, weather_text, user_query)
        tool_args = {"filename": filename, "content": note_content}
        action_description = f"为{city_from_weather}创建带伞提醒"
    else:
        reason = f"无法处理任务类型：{pending_task}"
        logger.warning(reason)
        return {
            "skipped_tasks": [{"task": pending_task, "reason": reason}],
            "observations": [reason],
            "thoughts": ["已生成最终答案"],
        }

    try:
        result = execute_tool(
            tool=selected_tool,
            arguments=tool_args,
            settings=settings,
            session=session,
        )
    except Exception as exc:
        logger.error("工具执行失败: %s", exc)
        return {
            "observations": [f"工具调用失败：{exc}"],
            "error": str(exc),
            "thoughts": ["工具执行失败"],
        }

    timestamp = datetime.now().isoformat()
    tool_call_record = {
        "tool_id": selected_tool.id,
        "tool_name": selected_tool.name,
        "task": pending_task,
        "arguments": tool_args,
        "result": result,
        "timestamp": timestamp,
    }

    tool_result_record = {
        "tool_name": selected_tool.name,
        "task": pending_task,
        "output": result,
        "arguments": tool_args,
    }

    observation = f"工具[{selected_tool.name}] 执行完成：{action_description}"
    if result:
        observation += f"，结果：{result[:200]}"

    thought = f"完成任务 {pending_task}，调用了 {selected_tool.name}"

    return {
        "tool_calls_made": [tool_call_record],
        "tool_results": [tool_result_record],
        "observations": [observation],
        "thoughts": [thought],
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


async def synthesizer_node(
    state: AgentState,
    settings: Settings,
) -> Dict[str, Any]:
    """合成器节点：使用 LLM 综合所有信息生成最终答案"""
    logger.info("✨ [合成器] 使用 LLM 生成最终答案...")

    user_query = state.get("user_query", "")
    retrieved_contexts = state.get("retrieved_contexts", [])
    tool_results = state.get("tool_results", [])
    skipped_tasks = state.get("skipped_tasks", [])

    # 构建信息上下文
    context_parts: List[str] = []
    
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
    
    # 判断是否有足够信息
    has_info = bool(retrieved_contexts or tool_results)
    
    try:
        if not has_info:
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
            # 有信息：要求 LLM 综合回答
            all_context = "\n\n".join(context_parts)
            synthesis_prompt = f"""用户问题：{user_query}

我已经为你收集了以下信息：

{all_context}

请基于以上信息，综合回答用户问题。

要求：
1. 优先引用具体的信息来源（知识库或工具结果）
2. 如果信息不完整，请说明缺少什么
3. 保持客观准确，不要编造内容
4. 回答要有条理，使用 Markdown 格式
5. 如果有工具执行结果，请重点突出
"""
        
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
    "search": ["搜索", "查找", "搜一下", "调查", "look up", "research", "扩散模型", "最新进展"],
    "diagram": ["思维导图", "流程图", "画图", "绘制", "diagram", "flowchart", "结构图", "图表", "导图"],
    "note": ["笔记", "提醒", "记录", "备忘", "记下来", "note", "带伞", "提醒我"],
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
    weather_indicators = ["天气", "气温", "下雨", "降雨", "明天", "今天", "后天", "weather", "forecast"]
    for indicator in weather_indicators:
        if indicator in query_original or indicator in normalized:
            task_scores["weather"] += 10  # 高权重
    
    # 如果提到城市名+时间词，大概率是天气查询
    has_city = any(city in query_original for city in COMMON_CHINESE_CITIES)
    has_time = any(t in query_original for t in ["明天", "今天", "后天", "tomorrow", "today"])
    if has_city and has_time:
        task_scores["weather"] += 15
    
    # 2. 搜索任务检测
    search_strong_keywords = ["搜索", "查找", "搜一下", "research", "最新进展", "扩散模型"]
    for keyword in search_strong_keywords:
        if keyword in query_original or keyword in normalized:
            task_scores["search"] += 8
    
    # 3. 图表任务检测
    diagram_keywords = ["思维导图", "流程图", "画图", "绘制", "diagram", "导图", "画个"]
    for keyword in diagram_keywords:
        if keyword in query_original or keyword in normalized:
            task_scores["diagram"] += 10
    
    # 4. 笔记任务检测
    note_keywords = ["笔记", "提醒", "记录", "备忘", "带伞", "提醒我", "写个笔记"]
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
        return await planner_node(state, settings, tool_records)
    
    async def router_wrapper(state: AgentState) -> Dict[str, Any]:
        return await router_node(state, settings)
    
    async def synthesizer_wrapper(state: AgentState) -> Dict[str, Any]:
        return await synthesizer_node(state, settings)
    
    async def tool_executor_wrapper(state: AgentState) -> Dict[str, Any]:
        return await tool_executor_node(state, settings, session, tool_records)
    
    # 添加节点
    workflow.add_node("planner", planner_wrapper)
    workflow.add_node("router", router_wrapper)
    workflow.add_node(
        "knowledge_search",
        lambda state: knowledge_search_node(state, settings)
    )
    workflow.add_node("tool_executor", tool_executor_wrapper)
    workflow.add_node("reflector", reflector_node)
    workflow.add_node("synthesizer", synthesizer_wrapper)
    # 暂时禁用人工介入节点（未完全实现）
    # workflow.add_node("human_input", human_input_node)
    
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
            "tool_executor": "tool_executor",
            "reflector": "reflector",
            "synthesizer": "synthesizer"
        }
    )
    
    workflow.add_edge("knowledge_search", "router")
    workflow.add_edge("tool_executor", "router")
    workflow.add_edge("reflector", "synthesizer")
    
    # 合成器后结束
    workflow.add_edge("synthesizer", END)
    
    # 人工介入流程（可选）
    # workflow.add_conditional_edges(
    #     "reflector",
    #     route_after_reflection,
    #     {
    #         "human_input": "human_input",
    #         "synthesizer": "synthesizer"
    #     }
    # )
    # workflow.add_edge("human_input", "router")
    
    logger.info("✅ LangGraph Agent 工作流构建完成")
    
    return workflow


async def run_agent(
    user_query: str,
    settings: Settings,
    session: Session,
    tool_records: List[ToolRecord],
    use_knowledge_base: bool = False,
    conversation_history: List[Dict[str, str]] = None,
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
    
    Returns:
        包含 Agent 完整执行过程的字典
    """
    logger.info(f"🚀 启动 LangGraph Agent 处理问题: {user_query}")
    
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
        "error": None
    }
    
    # 生成唯一的线程ID（用于检查点）
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    # 执行工作流
    try:
        final_state = await app.ainvoke(initial_state, config=config)
        
        logger.info("✅ LangGraph Agent 执行完成")
        
        return {
            "success": True,
            "final_answer": final_state.get("final_answer", "未能生成答案"),
            "thoughts": final_state.get("thoughts", []),
            "observations": final_state.get("observations", []),
            "tool_results": final_state.get("tool_results", []),
            "retrieved_contexts": final_state.get("retrieved_contexts", []),
            "plan": final_state.get("plan", ""),
            "quality_score": final_state.get("quality_score", 0.0),
            "reflection": final_state.get("reflection", ""),
            "thread_id": thread_id,
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


async def stream_agent(
    user_query: str,
    settings: Settings,
    session: Session,
    tool_records: List[ToolRecord],
    use_knowledge_base: bool = False,
    conversation_history: List[Dict[str, str]] = None,
):
    """
    流式运行 LangGraph Agent，实时返回每个节点的执行结果
    
    用于前端实时展示 Agent 的思考过程
    """
    logger.info(f"🌊 启动流式 LangGraph Agent: {user_query}")
    
    workflow = create_agent_graph(settings, session, tool_records)
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    initial_state: AgentState = {
        "user_query": user_query,
        "conversation_history": conversation_history or [],
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
        "error": None
    }
    
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    # 流式执行
    async for event in app.astream(initial_state, config=config):
        # event 是一个字典，键是节点名，值是该节点的输出
        for node_name, node_output in event.items():
            if node_name != "__end__":
                yield {
                    "event": "node_output",
                    "node": node_name,
                    "data": node_output,
                    "timestamp": datetime.now().isoformat()
                }
    
    # 流式结束
    yield {
        "event": "completed",
        "thread_id": thread_id,
        "timestamp": datetime.now().isoformat()
    }

