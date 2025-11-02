"""
Agent Builder - 动态构建和执行自定义Agent工作流
参考 n8n 和 Coze 的模式：支持节点式工作流，动态组合工具
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.orm import Session

from .config import Settings
from .database import AgentConfig, ToolRecord
from .graph_agent import AgentState, invoke_llm, knowledge_search_node
from .tool_service import execute_tool

logger = logging.getLogger(__name__)


# ==================== 节点类型定义 ====================

NODE_TYPES = {
    "planner": "规划器",
    "router": "路由器",
    "knowledge_search": "知识库检索",
    "tool_executor": "工具执行器",
    "condition": "条件判断",
    "synthesizer": "合成器",
    "llm_call": "LLM调用",
}


def create_dynamic_node(
    node_config: Dict[str, Any],
    settings: Settings,
    session: Session,
    tool_records: List[ToolRecord],
) -> callable:
    """
    根据节点配置动态创建节点函数
    
    Args:
        node_config: 节点配置 {type, data, ...}
        settings: 配置对象
        session: 数据库会话
        tool_records: 可用工具列表
    
    Returns:
        节点函数
    """
    node_type = node_config.get("type", "")
    node_data = node_config.get("data", {})
    
    async def dynamic_node(state: AgentState) -> Dict[str, Any]:
        """动态节点执行函数"""
        logger.info(f"🔧 [动态节点] {node_type}: {node_data.get('label', '')}")
        
        if node_type == "planner":
            return await handle_planner_node(state, settings, tool_records, node_data)
        elif node_type == "knowledge_search":
            # 使用 graph_agent 中的知识库检索节点
            from .graph_agent import knowledge_search_node as rag_search_node
            result = rag_search_node(state, settings)
            # 确保返回的数据格式正确
            if "retrieved_contexts" in result:
                # 转换为列表格式（RetrievedContext -> dict）
                retrieved = result["retrieved_contexts"]
                if retrieved:
                    result["retrieved_contexts"] = [
                        {
                            "document_id": ctx.document_id if hasattr(ctx, 'document_id') else ctx.get('document_id'),
                            "original_name": ctx.original_name if hasattr(ctx, 'original_name') else ctx.get('original_name'),
                            "content": ctx.content[:500] if hasattr(ctx, 'content') else ctx.get('content', '')[:500]
                        }
                        for ctx in retrieved
                    ]
            return result
        elif node_type == "tool_executor":
            return await handle_tool_executor_node(state, settings, session, tool_records, node_data)
        elif node_type == "condition":
            return handle_condition_node(state, node_data)
        elif node_type == "llm_call":
            return await handle_llm_call_node(state, settings, node_data)
        elif node_type == "synthesizer":
            return await handle_synthesizer_node(state, settings, node_data)
        elif node_type == "delay":
            return handle_delay_node(state, node_data)
        elif node_type == "variable":
            return handle_variable_node(state, node_data)
        elif node_type == "loop":
            return handle_loop_node(state, node_data)
        else:
            logger.warning(f"未知节点类型: {node_type}")
            return {"thoughts": [f"跳过未知节点: {node_type}"]}
    
    return dynamic_node


async def handle_planner_node(
    state: AgentState,
    settings: Settings,
    tool_records: List[ToolRecord],
    node_data: Dict[str, Any],
) -> Dict[str, Any]:
    """处理规划器节点"""
    user_query = state.get("user_query", "")
    custom_prompt = node_data.get("prompt", "")
    
    planning_prompt = custom_prompt or f"分析用户问题：{user_query}，制定执行计划。"
    
    try:
        reply, _ = await invoke_llm(
            messages=[{"role": "user", "content": planning_prompt}],
            settings=settings,
            temperature=0.3,
            max_tokens=500,
        )
        
        return {
            "plan": reply,
            "thoughts": [f"规划完成: {reply[:100]}..."],
        }
    except Exception as e:
        logger.error(f"规划器失败: {e}")
        return {"plan": "使用默认规划", "thoughts": [f"规划异常: {str(e)}"]}


async def handle_tool_executor_node(
    state: AgentState,
    settings: Settings,
    session: Session,
    tool_records: List[ToolRecord],
    node_data: Dict[str, Any],
) -> Dict[str, Any]:
    """处理工具执行器节点"""
    tool_id = node_data.get("toolId")
    tool_args = node_data.get("arguments", {})
    user_query = state.get("user_query", "")
    
    if not tool_id:
        return {"observations": ["工具ID未指定"], "error": "Missing tool_id"}
    
    # 查找工具
    selected_tool = next((t for t in tool_records if t.id == tool_id), None)
    if not selected_tool:
        return {"observations": [f"工具 {tool_id} 不存在"], "error": "Tool not found"}
    
    # 如果参数为空，尝试从用户查询中智能提取
    if not tool_args:
        tool_args = extract_tool_args_from_query(selected_tool, user_query, state)
    
    try:
        result = execute_tool(
            tool=selected_tool,
            arguments=tool_args,
            settings=settings,
            session=session,
        )
        
        tool_result = {
            "tool_name": selected_tool.name,
            "output": result,
            "arguments": tool_args,
        }
        
        return {
            "tool_results": [tool_result],
            "observations": [f"工具 {selected_tool.name} 执行成功"],
            "thoughts": [f"调用工具: {selected_tool.name}"],
        }
    except Exception as e:
        logger.error(f"工具执行失败: {e}")
        return {
            "observations": [f"工具执行失败: {str(e)}"],
            "error": str(e),
        }


def extract_tool_args_from_query(
    tool: ToolRecord,
    user_query: str,
    state: AgentState,
) -> Dict[str, Any]:
    """
    从用户查询中智能提取工具参数
    
    参考 graph_agent.py 中的参数提取逻辑
    """
    import json
    import re
    
    try:
        config = json.loads(tool.config or "{}")
        builtin_key = config.get("builtin_key", "")
    except:
        builtin_key = ""
    
    args = {}
    
    # 天气工具
    if builtin_key == "get_weather":
        # 提取城市名
        from .graph_agent import extract_city_from_query
        city = extract_city_from_query(user_query)
        args = {"city": city}
    
    # 搜索工具
    elif builtin_key == "web_search":
        from .graph_agent import extract_search_query
        query = extract_search_query(user_query)
        args = {"query": query, "num_results": 5}
    
    # 知识库检索工具
    elif builtin_key == "search_knowledge":
        # 使用用户查询作为检索关键词
        args = {"query": user_query, "top_k": 3}
    
    # 笔记工具
    elif builtin_key == "write_note":
        # 从状态中提取信息，生成笔记内容
        tool_results = state.get("tool_results", [])
        
        # 优先查找搜索结果
        search_result = None
        weather_result = None
        llm_result = None
        
        for tr in tool_results:
            tool_name = str(tr.get("tool_name", "")).lower()
            if "搜索" in tool_name or "search" in tool_name or "web_search" in tool_name:
                search_result = tr
            elif "天气" in tool_name or "weather" in tool_name:
                weather_result = tr
            elif "llm" in tool_name or "总结" in tool_name or "llm_call" in tool_name:
                llm_result = tr
        
        if search_result:
            # 从搜索结果中提取内容
            search_output = search_result.get("output", "")
            search_query = search_result.get("arguments", {}).get("query", "搜索结果")
            # 清理文件名中的特殊字符
            safe_query = search_query.replace(" ", "_").replace("/", "_").replace("\\", "_")[:30]
            filename = f"{safe_query}_笔记_{datetime.now().strftime('%Y%m%d')}.txt"
            # 使用搜索结果作为笔记内容（如果太长则截取）
            content = f"查询主题：{search_query}\n\n搜索结果：\n{search_output[:1500]}"
            args = {"filename": filename, "content": content}
        elif llm_result:
            # 使用LLM总结结果
            llm_output = llm_result.get("output", "")
            filename = f"总结笔记_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            content = f"用户查询：{user_query}\n\n总结内容：\n{llm_output[:1500]}"
            args = {"filename": filename, "content": content}
        elif weather_result:
            # 原有天气逻辑
            city = weather_result.get("arguments", {}).get("city", "未知城市")
            filename = f"{city}_提醒_{datetime.now().strftime('%Y%m%d')}.txt"
            content = f"根据天气查询结果，提醒：{weather_result.get('output', '')[:200]}"
            args = {"filename": filename, "content": content}
        else:
            # 默认笔记：使用所有工具结果
            all_outputs = []
            for tr in tool_results:
                tool_name = tr.get("tool_name", "工具")
                output = tr.get("output", "")
                if output:
                    all_outputs.append(f"【{tool_name}】\n{output[:500]}\n")
            
            if all_outputs:
                filename = f"笔记_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                content = f"用户查询：{user_query}\n\n处理结果：\n" + "\n".join(all_outputs)
            else:
                filename = f"笔记_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                content = f"用户查询：{user_query}\n\n处理结果：已完成"
            args = {"filename": filename, "content": content}
    
    # 绘图工具
    elif builtin_key == "draw_diagram":
        # 提取主题
        topic = user_query[:30].replace("搜索", "").replace("查询", "").strip()
        args = {
            "filename": f"{topic}_mindmap.md",
            "diagram_code": f"mindmap\n  root(({topic}))\n    信息1\n    信息2",
            "diagram_type": "mindmap"
        }
    
    # 获取网页内容工具
    elif builtin_key == "fetch_webpage":
        # 如果之前有搜索结果，尝试从结果中提取URL
        tool_results = state.get("tool_results", [])
        import re
        
        for tr in tool_results:
            if "搜索" in str(tr.get("tool_name", "")) or "search" in str(tr.get("tool_name", "")).lower():
                # 从搜索结果中提取第一个URL
                output = tr.get("output", "")
                # 提取URL（匹配 http:// 或 https:// 开头的URL）
                urls = re.findall(r'https?://[^\s\n\)]+', output)
                if urls:
                    args = {"url": urls[0]}
                    break
        
        if not args:
            # 如果没有找到URL，尝试从用户查询中提取
            urls = re.findall(r'https?://[^\s\n\)]+', user_query)
            if urls:
                args = {"url": urls[0]}
            else:
                # 如果还是没有，尝试使用搜索结果中的链接（如果有）
                args = {"url": ""}  # 会导致工具报错，但比静默失败好
    
    return args


def handle_condition_node(state: AgentState, node_data: Dict[str, Any]) -> Dict[str, Any]:
    """处理条件判断节点（类似 n8n 的 IF 节点）"""
    condition_type = node_data.get("conditionType", "always")  # always, contains, equals
    condition_value = node_data.get("conditionValue", "")
    
    should_continue = True
    
    if condition_type == "contains":
        # 检查工具结果或用户查询中是否包含某个值
        # 优先检查最近的工具结果
        tool_results = state.get("tool_results", [])
        check_text = ""
        
        if tool_results:
            # 检查最近的工具结果
            last_result = tool_results[-1]
            check_text = str(last_result.get("output", ""))
        else:
            # 如果没有工具结果，检查用户查询
            check_text = state.get("user_query", "")
        
        should_continue = condition_value.lower() in check_text.lower()
        logger.info(f"🔀 条件判断: 检查 '{condition_value}' 是否在文本中 -> {should_continue}")
        
    elif condition_type == "equals":
        # 检查状态值是否等于某个值
        check_field = node_data.get("checkField", "user_query")
        state_value = str(state.get(check_field, ""))
        should_continue = state_value == condition_value
    
    return {
        "next_action": "continue" if should_continue else "skip",
        "thoughts": [f"条件判断: {condition_type} = {should_continue}"],
        "observations": [f"条件 '{condition_value}' {'满足' if should_continue else '不满足'}"],
    }


async def handle_llm_call_node(
    state: AgentState,
    settings: Settings,
    node_data: Dict[str, Any],
) -> Dict[str, Any]:
    """处理自定义LLM调用节点"""
    prompt_template = node_data.get("prompt", "")
    user_query = state.get("user_query", "")
    
    # 替换模板变量
    prompt = prompt_template.replace("{{user_query}}", user_query)
    
    # 可以从状态中提取其他变量
    tool_results = state.get("tool_results", [])
    if tool_results:
        last_result = tool_results[-1].get("output", "") if tool_results else ""
        prompt = prompt.replace("{{last_tool_result}}", last_result[:500])
    
    try:
        reply, _ = await invoke_llm(
            messages=[{"role": "user", "content": prompt}],
            settings=settings,
            temperature=node_data.get("temperature", 0.7),
            max_tokens=node_data.get("maxTokens", 1000),
        )
        
        return {
            "thoughts": [reply[:200]],
            "observations": [f"LLM调用完成: {reply[:100]}..."],
        }
    except Exception as e:
        logger.error(f"LLM调用失败: {e}")
        return {"error": str(e)}


async def handle_synthesizer_node(
    state: AgentState,
    settings: Settings,
    node_data: Dict[str, Any],
) -> Dict[str, Any]:
    """处理合成器节点"""
    from .graph_agent import synthesizer_node
    
    # 如果有自定义提示词，修改状态
    custom_prompt = node_data.get("prompt", "")
    
    # 如果没有自定义提示词，使用改进的默认提示词
    if not custom_prompt:
        tool_results = state.get("tool_results", [])
        retrieved_contexts = state.get("retrieved_contexts", [])
        
        # 构建默认提示词
        default_prompt_parts = [
            "请根据以下信息生成详细、完整的回复：",
            "",
            f"用户查询：{state.get('user_query', '')}",
            ""
        ]
        
        if tool_results:
            default_prompt_parts.append("工具执行结果：")
            for tr in tool_results:
                tool_name = tr.get("tool_name", "工具")
                output = tr.get("output", "")
                if output:
                    default_prompt_parts.append(f"【{tool_name}】")
                    default_prompt_parts.append(f"{output[:1000]}")  # 限制长度
                    default_prompt_parts.append("")
        
        if retrieved_contexts:
            default_prompt_parts.append("知识库检索结果：")
            for ctx in retrieved_contexts[:3]:
                default_prompt_parts.append(f"- {ctx.get('content', '')[:300]}")
            default_prompt_parts.append("")
        
        default_prompt_parts.extend([
            "请整合以上所有信息，生成一个详细、有用的回答。",
            "如果用户要求写入笔记，请确认笔记内容已包含相关的重要信息。",
            "如果查询涉及搜索，请确保在回复中包含搜索到的关键信息，而不是只说'已写入笔记'。"
        ])
        
        custom_prompt = "\n".join(default_prompt_parts)
    
    if custom_prompt:
        # 临时修改用户查询以包含自定义提示
        original_query = state.get("user_query", "")
        state["user_query"] = f"{original_query}\n\n{custom_prompt}"
    
    result = await synthesizer_node(state, settings)
    
    # 恢复原始查询
    if custom_prompt:
        state["user_query"] = original_query
    
    return result


def handle_delay_node(state: AgentState, node_data: Dict[str, Any]) -> Dict[str, Any]:
    """处理延迟等待节点"""
    import asyncio
    
    seconds = node_data.get("seconds", 1)
    try:
        seconds = float(seconds)
        if seconds > 0:
            # 注意：在同步函数中使用 asyncio.sleep 需要特殊处理
            # 这里只是标记延迟，实际延迟由执行器控制
            logger.info(f"⏱️ 延迟等待 {seconds} 秒")
        return {
            "thoughts": [f"延迟等待 {seconds} 秒"],
            "observations": [f"已等待 {seconds} 秒"],
        }
    except:
        return {"thoughts": ["延迟参数无效"]}


def handle_variable_node(state: AgentState, node_data: Dict[str, Any]) -> Dict[str, Any]:
    """处理变量设置节点"""
    var_name = node_data.get("variableName", "")
    var_value = node_data.get("variableValue", "")
    
    if not var_name:
        return {"observations": ["变量名未设置"]}
    
    # 替换模板变量
    if "{{last_tool_result}}" in var_value:
        tool_results = state.get("tool_results", [])
        if tool_results:
            last_result = tool_results[-1].get("output", "")
            var_value = var_value.replace("{{last_tool_result}}", str(last_result)[:500])
    
    if "{{user_query}}" in var_value:
        var_value = var_value.replace("{{user_query}}", state.get("user_query", ""))
    
    # 存储到状态（可以扩展AgentState添加variables字段）
    return {
        "thoughts": [f"设置变量 {var_name} = {var_value[:50]}..."],
        "observations": [f"变量 {var_name} 已设置"],
    }


def handle_loop_node(state: AgentState, node_data: Dict[str, Any]) -> Dict[str, Any]:
    """处理循环执行节点（简化版）"""
    max_iterations = node_data.get("maxIterations", 5)
    condition = node_data.get("condition", "")
    
    current_step = state.get("current_step", 0)
    
    if current_step >= max_iterations:
        return {
            "next_action": "break",
            "thoughts": [f"达到最大迭代次数 {max_iterations}，退出循环"],
        }
    
    # 检查循环条件
    if condition:
        # 简化版：检查条件是否满足
        tool_results = state.get("tool_results", [])
        if tool_results:
            last_output = str(tool_results[-1].get("output", ""))
            if condition.lower() not in last_output.lower():
                return {
                    "next_action": "break",
                    "thoughts": [f"循环条件不满足，退出循环"],
                }
    
    return {
        "next_action": "continue",
        "thoughts": [f"循环继续，当前迭代 {current_step + 1}/{max_iterations}"],
    }


def build_dynamic_graph(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    settings: Settings,
    session: Session,
    tool_records: List[ToolRecord],
) -> StateGraph:
    """
    根据节点和边配置动态构建LangGraph工作流
    
    Args:
        nodes: 节点列表 [{id, type, data, ...}]
        edges: 边列表 [{source, target, ...}]
        settings: 配置对象
        session: 数据库会话
        tool_records: 可用工具列表
    
    Returns:
        编译后的LangGraph图
    """
    logger.info(f"🏗️ 构建动态工作流: {len(nodes)} 个节点, {len(edges)} 条边")
    
    workflow = StateGraph(AgentState)
    node_map = {}  # node_id -> node_function
    
    # 1. 添加所有节点
    for node_config in nodes:
        node_id = node_config.get("id")
        node_type = node_config.get("type")
        
        if not node_id or not node_type:
            logger.warning(f"跳过无效节点: {node_config}")
            continue
        
        # 创建节点函数
        node_func = create_dynamic_node(node_config, settings, session, tool_records)
        workflow.add_node(node_id, node_func)
        node_map[node_id] = node_config
    
    # 2. 设置入口点（找到没有入边的节点作为起始）
    source_nodes = {edge["source"] for edge in edges}
    target_nodes = {edge["target"] for edge in edges}
    entry_nodes = [n for n in node_map.keys() if n not in target_nodes]
    
    if entry_nodes:
        workflow.set_entry_point(entry_nodes[0])
    else:
        # 如果没有边，使用第一个节点
        if nodes:
            workflow.set_entry_point(nodes[0]["id"])
    
    # 3. 添加边（条件边或普通边）
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        condition = edge.get("condition")  # 条件边的判断函数
        
        if source not in node_map or target not in node_map:
            logger.warning(f"跳过无效边: {source} -> {target}")
            continue
        
        if condition:
            # 条件边（类似 n8n 的 IF 节点分支）
            def make_router(source_id: str, target_id: str, cond: str):
                def route_func(state: AgentState) -> str:
                    # 检查条件
                    if cond == "always":
                        return target_id
                    elif cond == "condition_true":
                        # 检查上一个节点的 next_action
                        next_action = state.get("next_action", "")
                        return target_id if next_action == "continue" else END
                    else:
                        return target_id
                
                return route_func
            
            workflow.add_conditional_edges(
                source,
                make_router(source, target, condition),
                {target: target, END: END},
            )
        else:
            # 普通边
            workflow.add_edge(source, target)
    
    # 4. 添加结束边（找到没有出边的节点）
    outgoing_edges = {edge["source"] for edge in edges}
    exit_nodes = [n for n in node_map.keys() if n not in outgoing_edges]
    
    for exit_node in exit_nodes:
        workflow.add_edge(exit_node, END)
    
    logger.info("✅ 动态工作流构建完成")
    return workflow


async def execute_custom_agent(
    agent_config: AgentConfig,
    user_query: str,
    settings: Settings,
    session: Session,
    tool_records: List[ToolRecord],
    conversation_history: List[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    执行自定义Agent配置
    
    Args:
        agent_config: Agent配置对象
        user_query: 用户查询
        settings: 配置对象
        session: 数据库会话
        tool_records: 可用工具列表
        conversation_history: 对话历史
    
    Returns:
        执行结果
    """
    try:
        # 解析配置
        config_data = json.loads(agent_config.config)
        nodes = config_data.get("nodes", [])
        edges = config_data.get("edges", [])
        
        # 构建动态图
        workflow = build_dynamic_graph(nodes, edges, settings, session, tool_records)
        
        # 编译图
        checkpointer = MemorySaver()
        app = workflow.compile(checkpointer=checkpointer)
        
        # 初始化状态
        initial_state: AgentState = {
            "user_query": user_query,
            "conversation_history": conversation_history or [],
            "plan": None,
            "current_step": 0,
            "max_iterations": 20,
            "available_tools": [tool.id for tool in tool_records],
            "tool_calls_made": [],
            "tool_results": [],
            "skipped_tasks": [],
            "use_knowledge_base": any(n.get("type") == "knowledge_search" for n in nodes),
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
        }
        
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        
        # 执行工作流
        final_state = await app.ainvoke(initial_state, config=config)
        
        return {
            "success": True,
            "final_answer": final_state.get("final_answer", "执行完成"),
            "thoughts": final_state.get("thoughts", []),
            "observations": final_state.get("observations", []),
            "tool_results": final_state.get("tool_results", []),
            "retrieved_contexts": final_state.get("retrieved_contexts", []),
            "thread_id": thread_id,
        }
    
    except Exception as e:
        logger.error(f"执行自定义Agent失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "final_answer": f"执行失败: {str(e)}",
        }


async def stream_custom_agent(
    agent_config: AgentConfig,
    user_query: str,
    settings: Settings,
    session: Session,
    tool_records: List[ToolRecord],
    conversation_history: List[Dict[str, str]] = None,
):
    """
    流式执行自定义Agent（用于前端实时展示）
    """
    try:
        config_data = json.loads(agent_config.config)
        nodes = config_data.get("nodes", [])
        edges = config_data.get("edges", [])
        
        workflow = build_dynamic_graph(nodes, edges, settings, session, tool_records)
        checkpointer = MemorySaver()
        app = workflow.compile(checkpointer=checkpointer)
        
        initial_state: AgentState = {
            "user_query": user_query,
            "conversation_history": conversation_history or [],
            "plan": None,
            "current_step": 0,
            "max_iterations": 20,
            "available_tools": [tool.id for tool in tool_records],
            "tool_calls_made": [],
            "tool_results": [],
            "skipped_tasks": [],
            "use_knowledge_base": any(n.get("type") == "knowledge_search" for n in nodes),
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
        }
        
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        
        # 流式执行
        final_answer = None
        async for event in app.astream(initial_state, config=config):
            for node_name, node_output in event.items():
                if node_name != "__end__":
                    # 检查是否有最终答案
                    if "final_answer" in node_output and node_output["final_answer"]:
                        final_answer = node_output["final_answer"]
                    
                    yield {
                        "event": "node_output",
                        "node": node_name,
                        "data": node_output,
                        "timestamp": datetime.now().isoformat(),
                    }
        
        # 如果还没有发送最终答案，现在发送
        if final_answer:
            yield {
                "event": "final_answer",
                "content": final_answer,
                "timestamp": datetime.now().isoformat(),
            }
        
        yield {
            "event": "completed",
            "thread_id": thread_id,
        }
    
    except Exception as e:
        logger.error(f"流式执行失败: {e}", exc_info=True)
        yield {
            "event": "error",
            "message": str(e),
        }

