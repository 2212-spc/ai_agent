"""
多智能体协调器（Multi-Agent Orchestrator）
负责任务分解、智能体选择、协调执行和结果汇总
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from .agent_roles import (
    AGENT_REGISTRY,
    analysis_specialist_node,
    retrieval_specialist_node,
    summarization_specialist_node,
    verification_specialist_node,
)
from .config import Settings
from .database import ToolRecord
from .graph_agent import invoke_llm, parse_json_from_llm
from .shared_workspace import (
    AgentMessage,
    MultiAgentState,
    SharedWorkspace,
    SubTask,
    create_initial_multi_agent_state,
)

logger = logging.getLogger(__name__)


# ==================== 协调器节点函数 ====================

async def orchestrator_planner_node(
    state: MultiAgentState,
    settings: Settings,
) -> Dict[str, Any]:
    """
    协调器 - 规划节点
    
    职责：
    1. 理解用户意图
    2. 分解任务为子任务
    3. 选择合适的智能体
    4. 制定执行策略
    """
    logger.info("🎯 [协调器-规划] 开始任务分解...")
    
    workspace = SharedWorkspace(state)
    user_query = state.get("user_query", "")
    
    # 使用 LLM 进行智能任务分解
    planning_prompt = f"""你是一个多智能体系统的协调器。请分析用户问题，制定执行计划。

用户问题：{user_query}

可用的智能体：
1. **检索专家**（retrieval_specialist）- 知识库检索、网络搜索、信息收集
2. **分析专家**（analysis_specialist）- 深度分析、内容理解、数据提取
3. **总结专家**（summarization_specialist）- 信息整合、报告生成、答案合成
4. **验证专家**（verification_specialist）- 质量检查、事实核查（可选，仅用于高质量要求场景）

请生成任务分解计划，以 JSON 格式输出：
{{
  "task_type": "信息检索|数据分析|内容创作|复合任务",
  "complexity": "简单|中等|复杂",
  "sub_tasks": [
    {{
      "task_id": "task_1",
      "task_type": "retrieval|analysis|summarization|verification",
      "description": "详细的任务描述，包括具体目标和预期输出",
      "assigned_agent": "agent_id",
      "depends_on": []  // 依赖的前置任务ID列表（空数组表示无依赖）
    }},
    ...
  ],
  "execution_mode": "sequential|parallel",
  "reasoning": "任务分解的理由"
}}

【重要规则 - 必须遵守】：
1. **任务依赖关系必须正确**：
   - 检索专家（retrieval_specialist）通常是第一步，无依赖
   - 分析专家（analysis_specialist）依赖检索专家的结果
   - 总结专家（summarization_specialist）依赖所有前置分析任务
   - 验证专家（verification_specialist）必须依赖总结专家，因为它需要验证最终答案

2. **验证专家使用规则**：
   - 只在以下场景使用验证专家：
     * 用户明确要求"验证"、"检查"、"确保准确"
     * 涉及事实性信息、数据报告、研究报告等高质量要求场景
   - 如果使用验证专家，必须放在最后，且依赖总结专家：
     {{"task_id": "task_final", "assigned_agent": "verification_specialist", "depends_on": ["summary_task_id"]}}

3. **执行顺序示例**（复杂研究任务）：
   task_1: retrieval_specialist (无依赖)
   task_2: analysis_specialist (依赖 task_1)
   task_3: analysis_specialist (依赖 task_1，可并行于task_2)
   task_4: summarization_specialist (依赖 task_2, task_3)
   task_5: verification_specialist (依赖 task_4) ← 可选，仅高质量要求时添加

4. **简化原则**（⭐重要）：
   - **简单问答**（定义、解释、单一概念）：仅使用总结专家（1个智能体）或 检索专家 → 总结专家（2个智能体）
   - **中等复杂度**（需要分析但不需深度研究）：检索专家 → 分析专家 → 总结专家（3个智能体）
   - **复杂研究**（多角度、深度分析、质量要求高）：检索专家 → 多个分析专家 → 总结专家 → 验证专家（4-5个智能体）

5. **优先使用简化流程**：
   - 如果问题可以直接回答，不要使用检索专家
   - 优先2-3个智能体的流程
   - 只在必要时使用验证专家

只返回 JSON，不要其他解释。
"""
    
    try:
        llm_response, _ = await invoke_llm(
            messages=[{"role": "user", "content": planning_prompt}],
            settings=settings,
            temperature=0.3,
            max_tokens=1500,
        )
        
        plan_data = parse_json_from_llm(llm_response)
        
        task_type = plan_data.get("task_type", "复合任务")
        complexity = plan_data.get("complexity", "中等")
        sub_tasks_data = plan_data.get("sub_tasks", [])
        execution_mode = plan_data.get("execution_mode", "sequential")
        reasoning = plan_data.get("reasoning", "")
        
        logger.info(
            f"📋 任务分解完成：{task_type}（{complexity}），"
            f"{len(sub_tasks_data)} 个子任务，{execution_mode} 执行"
        )
        
        # 创建子任务对象
        sub_tasks = []
        for i, task_data in enumerate(sub_tasks_data):
            subtask = SubTask(
                task_id=task_data.get("task_id", f"task_{i+1}"),
                task_type=task_data.get("task_type", "unknown"),
                description=task_data.get("description", ""),
                assigned_agent=task_data.get("assigned_agent", ""),
            )
            workspace.add_subtask(subtask)
            sub_tasks.append(subtask)
        
        # 生成计划摘要
        plan_summary = f"""任务分解计划：
类型：{task_type}
复杂度：{complexity}
执行模式：{execution_mode}
子任务数：{len(sub_tasks)}

子任务列表：
{chr(10).join(f"{i+1}. [{t.assigned_agent}] {t.description}" for i, t in enumerate(sub_tasks))}

理由：{reasoning}
"""
        
        return {
            "orchestrator_plan": plan_summary,
            "execution_mode": execution_mode,
            "thoughts": [f"协调器完成任务分解：{len(sub_tasks)} 个子任务"],
            "observations": [f"执行计划已生成，模式：{execution_mode}"],
        }
    
    except Exception as e:
        logger.error(f"❌ 任务分解失败: {e}", exc_info=True)
        
        # 降级：使用简单的默认计划
        default_subtasks = [
            SubTask(
                task_id="task_1",
                task_type="retrieval",
                description="检索相关信息",
                assigned_agent="retrieval_specialist",
            ),
            SubTask(
                task_id="task_2",
                task_type="summarization",
                description="生成最终回答",
                assigned_agent="summarization_specialist",
            ),
        ]
        
        for task in default_subtasks:
            workspace.add_subtask(task)
        
        return {
            "orchestrator_plan": "使用默认执行计划（2个子任务）",
            "execution_mode": "sequential",
            "thoughts": [f"使用默认计划（规划失败：{str(e)[:50]}）"],
        }


async def orchestrator_executor_node(
    state: MultiAgentState,
    settings: Settings,
    session: Session,
    tool_records: List[ToolRecord],
) -> Dict[str, Any]:
    """
    协调器 - 执行节点
    
    职责：
    1. 根据计划顺序执行子任务
    2. 调度智能体执行
    3. 监控执行状态
    """
    logger.info("⚙️ [协调器-执行] 开始协调智能体执行...")
    
    workspace = SharedWorkspace(state)
    execution_mode = state.get("execution_mode", "sequential")
    
    # 获取待执行的子任务
    pending_tasks = workspace.get_pending_subtasks()
    
    if not pending_tasks:
        logger.info("✅ 所有子任务已完成")
        return {
            "thoughts": ["所有子任务已执行完成"],
            "next_action": "complete",
        }
    
    # 获取下一个要执行的任务
    next_task = pending_tasks[0]
    
    logger.info(
        f"📌 执行子任务: {next_task.task_id} "
        f"[{next_task.assigned_agent}] - {next_task.description}"
    )
    
    # 更新任务状态
    workspace.update_subtask_status(next_task.task_id, "in_progress")
    
    # 发送任务分配消息
    workspace.send_message(
        from_agent="orchestrator",
        to_agent=next_task.assigned_agent,
        message_type="task_request",
        content={
            "task_id": next_task.task_id,
            "description": next_task.description,
        },
    )
    
    return {
        "thoughts": [f"调度智能体执行: {next_task.assigned_agent}"],
        "observations": [f"开始执行任务: {next_task.description}"],
        "next_action": f"execute_{next_task.assigned_agent}",
    }


async def orchestrator_aggregator_node(
    state: MultiAgentState,
    settings: Settings,
) -> Dict[str, Any]:
    """
    协调器 - 汇总节点
    
    职责：
    1. 收集所有智能体的结果
    2. 整合和汇总
    3. 生成最终输出
    """
    logger.info("📊 [协调器-汇总] 开始汇总所有结果...")
    
    workspace = SharedWorkspace(state)
    
    # 获取最终答案（由总结专家生成）
    final_answer = workspace.get_shared_data("final_answer", "")
    
    if not final_answer:
        # 如果没有总结专家的结果，从其他智能体结果中提取
        retrieval_results = workspace.get_shared_data("retrieval_results", {})
        analysis_result = workspace.get_shared_data("analysis_result", {})
        
        if retrieval_results or analysis_result:
            final_answer = "已收集相关信息，但未生成完整总结。"
        else:
            final_answer = "未能收集到有效结果。"
    
    # 获取质量评分
    verification_result = workspace.get_shared_data("verification_result", {})
    quality_score = verification_result.get("overall_score", 7) / 10.0
    
    # 收集所有智能体的思考和观察
    all_thoughts = []
    all_observations = []
    
    agent_thoughts = state.get("agent_thoughts", {})
    agent_observations = state.get("agent_observations", {})
    
    for agent_id, thoughts in agent_thoughts.items():
        agent_name = AGENT_REGISTRY.get(agent_id, {}).get("name", agent_id)
        all_thoughts.extend([f"[{agent_name}] {t}" for t in thoughts])
    
    for agent_id, observations in agent_observations.items():
        agent_name = AGENT_REGISTRY.get(agent_id, {}).get("name", agent_id)
        all_observations.extend([f"[{agent_name}] {o}" for o in observations])
    
    logger.info(f"✅ 汇总完成，最终答案长度：{len(final_answer)} 字符")
    
    return {
        "final_answer": final_answer,
        "quality_score": quality_score,
        "is_complete": True,
        "thoughts": all_thoughts,
        "observations": all_observations,
    }


# ==================== 路由函数 ====================

def route_after_planning(state: MultiAgentState) -> str:
    """规划后的路由"""
    return "executor"


def route_after_execution(state: MultiAgentState) -> str:
    """执行后的路由"""
    next_action = state.get("next_action", "")
    
    if next_action == "complete":
        return "aggregator"
    
    # 根据 next_action 路由到具体的智能体
    if next_action.startswith("execute_"):
        agent_id = next_action.replace("execute_", "")
        return agent_id
    
    return "aggregator"


def route_after_agent(state: MultiAgentState) -> str:
    """智能体执行后的路由"""
    workspace = SharedWorkspace(state)
    
    # 检查是否所有子任务都完成
    if workspace.all_subtasks_completed():
        return "aggregator"
    
    # 继续执行下一个子任务
    return "executor"


def should_end(state: MultiAgentState) -> str:
    """判断是否结束"""
    is_complete = state.get("is_complete", False)
    return END if is_complete else "continue"


# ==================== 多智能体工作流构建 ====================

def create_multi_agent_graph(
    settings: Settings,
    session: Session,
    tool_records: List[ToolRecord],
) -> StateGraph:
    """
    创建多智能体协作工作流
    
    工作流：
    1. 协调器规划 -> 任务分解
    2. 协调器执行 -> 调度智能体
    3. 智能体执行 -> 各专家执行任务
    4. 协调器汇总 -> 整合结果
    """
    logger.info("🏗️ 构建多智能体协作工作流...")
    
    workflow = StateGraph(MultiAgentState)
    
    # ========== 协调器节点 ==========
    
    async def planner_wrapper(state: MultiAgentState) -> Dict[str, Any]:
        return await orchestrator_planner_node(state, settings)
    
    async def executor_wrapper(state: MultiAgentState) -> Dict[str, Any]:
        return await orchestrator_executor_node(state, settings, session, tool_records)
    
    async def aggregator_wrapper(state: MultiAgentState) -> Dict[str, Any]:
        return await orchestrator_aggregator_node(state, settings)
    
    workflow.add_node("planner", planner_wrapper)
    workflow.add_node("executor", executor_wrapper)
    workflow.add_node("aggregator", aggregator_wrapper)
    
    # ========== 智能体节点 ==========
    
    async def retrieval_wrapper(state: MultiAgentState) -> Dict[str, Any]:
        return await retrieval_specialist_node(state, settings, session, tool_records)
    
    async def analysis_wrapper(state: MultiAgentState) -> Dict[str, Any]:
        return await analysis_specialist_node(state, settings, session)
    
    async def summarization_wrapper(state: MultiAgentState) -> Dict[str, Any]:
        return await summarization_specialist_node(state, settings, session, tool_records=tool_records)
    
    async def verification_wrapper(state: MultiAgentState) -> Dict[str, Any]:
        return await verification_specialist_node(state, settings, session)
    
    workflow.add_node("retrieval_specialist", retrieval_wrapper)
    workflow.add_node("analysis_specialist", analysis_wrapper)
    workflow.add_node("summarization_specialist", summarization_wrapper)
    workflow.add_node("verification_specialist", verification_wrapper)
    
    # ========== 设置流程 ==========
    
    workflow.set_entry_point("planner")
    
    # 规划 -> 执行
    workflow.add_edge("planner", "executor")
    
    # 执行 -> 路由到智能体或汇总
    workflow.add_conditional_edges(
        "executor",
        route_after_execution,
        {
            "retrieval_specialist": "retrieval_specialist",
            "analysis_specialist": "analysis_specialist",
            "summarization_specialist": "summarization_specialist",
            "verification_specialist": "verification_specialist",
            "aggregator": "aggregator",
        },
    )
    
    # 智能体 -> 继续执行或汇总
    for agent_id in ["retrieval_specialist", "analysis_specialist", "summarization_specialist", "verification_specialist"]:
        workflow.add_conditional_edges(
            agent_id,
            route_after_agent,
            {
                "executor": "executor",
                "aggregator": "aggregator",
            },
        )
    
    # 汇总 -> 结束
    workflow.add_edge("aggregator", END)
    
    logger.info("✅ 多智能体工作流构建完成")
    
    return workflow


# ==================== 执行函数 ====================

async def run_multi_agent(
    user_query: str,
    settings: Settings,
    session: Session,
    tool_records: List[ToolRecord],
    use_knowledge_base: bool = True,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    execution_mode: str = "sequential",
) -> Dict[str, Any]:
    """
    运行多智能体系统
    
    Args:
        user_query: 用户查询
        settings: 配置
        session: 数据库会话
        tool_records: 可用工具列表
        use_knowledge_base: 是否使用知识库
        conversation_history: 对话历史
        session_id: 会话ID
        user_id: 用户ID
        execution_mode: 执行模式（sequential 或 parallel）
    
    Returns:
        执行结果
    """
    logger.info(f"🚀 启动多智能体系统处理问题: {user_query}")
    
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # 构建工作流
    workflow = create_multi_agent_graph(settings, session, tool_records)
    
    # 编译图
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    # 初始化状态
    initial_state = create_initial_multi_agent_state(
        user_query=user_query,
        conversation_history=conversation_history,
        session_id=session_id,
        user_id=user_id,
        use_knowledge_base=use_knowledge_base,
        available_tools=[tool.id for tool in tool_records],
        execution_mode=execution_mode,
    )
    
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    # 执行工作流
    try:
        final_state = await app.ainvoke(initial_state, config=config)
        
        logger.info("✅ 多智能体系统执行完成")
        
        return {
            "success": True,
            "final_answer": final_state.get("final_answer", "未能生成答案"),
            "orchestrator_plan": final_state.get("orchestrator_plan", ""),
            "sub_tasks": final_state.get("sub_tasks", []),
            "agent_results": final_state.get("agent_results", {}),
            "thoughts": final_state.get("thoughts", []),
            "observations": final_state.get("observations", []),
            "quality_score": final_state.get("quality_score", 0.0),
            "thread_id": thread_id,
            "session_id": session_id,
        }
    
    except Exception as e:
        logger.error(f"❌ 多智能体系统执行失败: {e}", exc_info=True)
        return {
            "success": False,
            "final_answer": f"系统执行出错：{str(e)}",
            "error": str(e),
        }


async def stream_multi_agent(
    user_query: str,
    settings: Settings,
    session: Session,
    tool_records: List[ToolRecord],
    use_knowledge_base: bool = True,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    execution_mode: str = "sequential",
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    流式运行多智能体系统
    
    用于前端实时展示各智能体的执行过程
    """
    logger.info(f"🌊 启动流式多智能体系统: {user_query}")
    
    if not session_id:
        session_id = str(uuid.uuid4())
    
    workflow = create_multi_agent_graph(settings, session, tool_records)
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    initial_state = create_initial_multi_agent_state(
        user_query=user_query,
        conversation_history=conversation_history,
        session_id=session_id,
        user_id=user_id,
        use_knowledge_base=use_knowledge_base,
        available_tools=[tool.id for tool in tool_records],
        execution_mode=execution_mode,
    )
    
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    # 流式执行
    async for event in app.astream(initial_state, config=config):
        for node_name, node_output in event.items():
            if node_name != "__end__":
                # 判断节点类型
                if node_name == "planner":
                    event_type = "orchestrator_plan"
                elif node_name == "executor":
                    event_type = "orchestrator_execute"
                elif node_name == "aggregator":
                    event_type = "orchestrator_aggregate"
                elif node_name in AGENT_REGISTRY:
                    event_type = "agent_execution"
                else:
                    event_type = "node_output"
                
                yield {
                    "event": event_type,
                    "node": node_name,
                    "data": node_output,
                    "timestamp": datetime.now().isoformat(),
                }
    
    # 完成
    yield {
        "event": "completed",
        "thread_id": thread_id,
        "timestamp": datetime.now().isoformat(),
    }

