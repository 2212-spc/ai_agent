"""
智能体角色定义
定义各个专家智能体的节点函数和能力
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .config import Settings
from .database import ToolRecord
from .graph_agent import invoke_llm, parse_json_from_llm
from .rag_service import retrieve_context
from .shared_workspace import MultiAgentState, SharedWorkspace
from .tool_service import execute_tool

logger = logging.getLogger(__name__)


# ==================== 检索专家（Retrieval Specialist） ====================

async def retrieval_specialist_node(
    state: MultiAgentState,
    settings: Settings,
    session: Session,
    tool_records: List[ToolRecord],
) -> Dict[str, Any]:
    """
    检索专家智能体
    
    职责：
    - 知识库检索（RAG）
    - 网络搜索
    - 文档查找
    
    能力：
    - 向量检索
    - 关键词搜索
    - 网页搜索工具
    """
    logger.info("🔍 [检索专家] 开始执行检索任务...")
    
    workspace = SharedWorkspace(state)
    agent_id = "retrieval_specialist"
    
    # 注册智能体
    workspace.register_agent(agent_id)
    workspace.update_agent_status(agent_id, "running")
    
    user_query = state.get("user_query", "")
    use_knowledge_base = state.get("use_knowledge_base", False)
    
    retrieval_results = {}
    thoughts = []
    observations = []
    
    try:
        # 1. 知识库检索
        if use_knowledge_base:
            try:
                logger.info("📚 执行知识库检索...")
                contexts = retrieve_context(
                    query=user_query,
                    settings=settings,
                    top_k=5,
                )
                
                if contexts:
                    retrieval_results["knowledge_base"] = [
                        {
                            "document_id": ctx.document_id,
                            "original_name": ctx.original_name,
                            "content": ctx.content[:500],
                        }
                        for ctx in contexts
                    ]
                    thoughts.append(f"从知识库检索到 {len(contexts)} 个相关片段")
                    observations.append(
                        f"知识库检索完成：找到 {len(contexts)} 个文档片段"
                    )
                else:
                    thoughts.append("知识库检索未找到相关内容")
                    observations.append("知识库为空或未找到相关内容")
            
            except Exception as e:
                logger.error(f"知识库检索失败: {e}")
                thoughts.append(f"知识库检索失败: {str(e)}")
        
        # 2. 网络搜索（如果有搜索工具）
        search_tool = None
        for tool in tool_records:
            try:
                import json
                config = json.loads(tool.config or "{}")
                if config.get("builtin_key") == "web_search":
                    search_tool = tool
                    break
            except:
                continue
        
        if search_tool and any(
            keyword in user_query.lower()
            for keyword in ["搜索", "查找", "最新", "search", "find"]
        ):
            try:
                logger.info("🌐 执行网络搜索...")
                
                # 提取搜索关键词
                from .graph_agent import extract_search_query
                search_query = extract_search_query(user_query)
                
                # 执行搜索
                search_result = execute_tool(
                    tool=search_tool,
                    arguments={"query": search_query, "num_results": 5},
                    settings=settings,
                    session=session,
                )
                
                retrieval_results["web_search"] = {
                    "query": search_query,
                    "results": search_result,
                }
                
                thoughts.append(f"执行了网络搜索：{search_query}")
                observations.append(f"网络搜索完成，关键词：{search_query}")
                
            except Exception as e:
                logger.error(f"网络搜索失败: {e}")
                thoughts.append(f"网络搜索失败: {str(e)}")
        
        # 3. 存储结果到共享工作空间
        workspace.store_agent_result(agent_id, retrieval_results)
        workspace.set_shared_data("retrieval_results", retrieval_results)
        
        # 4. 发送结果消息给协调器
        workspace.send_message(
            from_agent=agent_id,
            to_agent="orchestrator",
            message_type="result",
            content={
                "status": "completed",
                "retrieval_results": retrieval_results,
                "summary": f"检索完成，共找到 {len(retrieval_results)} 类结果",
            },
        )
        
        workspace.update_agent_status(agent_id, "completed")
        
        logger.info(f"✅ [检索专家] 执行完成，找到 {len(retrieval_results)} 类结果")
        
        return {
            "agent_thoughts": {agent_id: thoughts},
            "agent_observations": {agent_id: observations},
            "retrieved_contexts": retrieval_results.get("knowledge_base", []),
        }
    
    except Exception as e:
        logger.error(f"❌ [检索专家] 执行失败: {e}", exc_info=True)
        workspace.update_agent_status(agent_id, "failed")
        workspace.send_message(
            from_agent=agent_id,
            to_agent="orchestrator",
            message_type="error",
            content={"error": str(e)},
        )
        
        return {
            "agent_thoughts": {agent_id: [f"执行失败: {str(e)}"]},
            "error": str(e),
        }


# ==================== 分析专家（Analysis Specialist） ====================

async def analysis_specialist_node(
    state: MultiAgentState,
    settings: Settings,
) -> Dict[str, Any]:
    """
    分析专家智能体
    
    职责：
    - 数据分析
    - 内容理解
    - 关键信息提取
    
    能力：
    - 文本分析（使用 LLM）
    - 数据提取
    - 模式识别
    """
    logger.info("📊 [分析专家] 开始执行分析任务...")
    
    workspace = SharedWorkspace(state)
    agent_id = "analysis_specialist"
    
    workspace.register_agent(agent_id)
    workspace.update_agent_status(agent_id, "running")
    
    user_query = state.get("user_query", "")
    thoughts = []
    observations = []
    
    try:
        # 1. 获取检索专家的结果
        retrieval_results = workspace.get_shared_data("retrieval_results", {})
        
        if not retrieval_results:
            thoughts.append("未找到检索结果，使用用户查询进行分析")
            analysis_context = f"用户查询：{user_query}"
        else:
            # 构建分析上下文
            context_parts = []
            
            if "knowledge_base" in retrieval_results:
                kb_contexts = retrieval_results["knowledge_base"]
                context_parts.append(
                    f"知识库内容（{len(kb_contexts)} 个片段）:\n"
                    + "\n".join([
                        f"- {ctx.get('content', '')[:200]}"
                        for ctx in kb_contexts[:3]
                    ])
                )
            
            if "web_search" in retrieval_results:
                search_data = retrieval_results["web_search"]
                context_parts.append(
                    f"搜索结果（关键词: {search_data.get('query', '')}):\n"
                    f"{search_data.get('results', '')[:500]}"
                )
            
            analysis_context = "\n\n".join(context_parts)
            thoughts.append(f"获取到检索结果，准备分析")
        
        # 2. 使用 LLM 进行深度分析
        logger.info("🤔 使用 LLM 进行内容分析...")
        
        # 获取当前子任务的描述，以便针对性分析
        current_subtask = workspace.get_current_subtask()
        task_description = current_subtask.description if current_subtask else "深度分析内容"
        
        analysis_prompt = f"""你是一个资深的技术分析专家和研究顾问。请对以下内容进行深度、系统化的分析。

【任务要求】：{task_description}

【用户问题】：{user_query}

【待分析内容】：
{analysis_context}

【分析维度】请从以下多个维度进行深入分析：

1. **核心概念识别**：
   - 识别并解释核心技术概念、术语
   - 区分基础概念与高级概念

2. **关键信息提取**：
   - 提取重要事实、数据、统计信息
   - 识别关键论点和结论
   - 标注信息来源（如有）

3. **技术原理分析**（如适用）：
   - 解释技术实现原理
   - 分析技术架构和设计思路
   - 对比不同技术方案的优劣

4. **关联性分析**：
   - 发现概念之间的逻辑关系
   - 识别因果关系、演进关系
   - 构建知识图谱式的关联

5. **趋势与洞察**：
   - 识别技术演进趋势
   - 发现潜在问题和挑战
   - 预测未来发展方向

6. **批判性思考**：
   - 指出信息的局限性
   - 识别可能存在的偏见或争议
   - 提出需要进一步验证的点

以 JSON 格式输出分析结果：
{{
  "core_concepts": [
    {{"concept": "概念名称", "explanation": "详细解释", "importance": "high|medium|low"}}
  ],
  "key_facts": [
    {{"fact": "事实描述", "source": "来源（如有）", "confidence": "high|medium|low"}}
  ],
  "key_data": [
    {{"data_point": "数据点", "value": "具体数值或描述", "context": "背景说明"}}
  ],
  "technical_principles": [
    {{"principle": "原理名称", "explanation": "原理解释", "advantages": ["优势1"], "limitations": ["局限1"]}}
  ],
  "relationships": [
    {{"from": "概念A", "to": "概念B", "relationship_type": "因果|演进|对比|补充", "description": "关系描述"}}
  ],
  "trends_insights": [
    {{"trend": "趋势描述", "evidence": "支持证据", "implications": "影响分析"}}
  ],
  "critical_notes": [
    {{"note_type": "局限性|争议点|待验证", "description": "详细说明"}}
  ],
  "analysis_summary": "全面的分析总结（300-500字）",
  "confidence_score": 0.0-1.0
}}

要求：
- 分析要深入、系统、全面
- 保持客观，避免主观臆断
- 优先使用提供的内容，标注推理部分
- 长度：500-1000字的深度分析

只返回 JSON，不要其他解释。
"""
        
        llm_response, _ = await invoke_llm(
            messages=[{"role": "user", "content": analysis_prompt}],
            settings=settings,
            temperature=0.4,  # 稍高的温度以获得更有创意的洞察
            max_tokens=2500,  # 增加token限制以支持更深入的分析
        )
        
        # 解析 LLM 响应
        analysis_result = parse_json_from_llm(llm_response)
        
        thoughts.append("完成内容分析，提取了关键信息")
        observations.append(
            f"分析完成：识别 {len(analysis_result.get('core_topics', []))} 个核心主题，"
            f"{len(analysis_result.get('key_facts', []))} 个关键事实"
        )
        
        # 3. 存储结果
        workspace.store_agent_result(agent_id, analysis_result)
        workspace.set_shared_data("analysis_result", analysis_result)
        
        # 4. 发送结果消息
        workspace.send_message(
            from_agent=agent_id,
            to_agent="orchestrator",
            message_type="result",
            content={
                "status": "completed",
                "analysis_result": analysis_result,
            },
        )
        
        workspace.update_agent_status(agent_id, "completed")
        
        logger.info("✅ [分析专家] 分析完成")
        
        return {
            "agent_thoughts": {agent_id: thoughts},
            "agent_observations": {agent_id: observations},
        }
    
    except Exception as e:
        logger.error(f"❌ [分析专家] 执行失败: {e}", exc_info=True)
        workspace.update_agent_status(agent_id, "failed")
        workspace.send_message(
            from_agent=agent_id,
            to_agent="orchestrator",
            message_type="error",
            content={"error": str(e)},
        )
        
        return {
            "agent_thoughts": {agent_id: [f"执行失败: {str(e)}"]},
            "error": str(e),
        }


# ==================== 总结专家（Summarization Specialist） ====================

async def summarization_specialist_node(
    state: MultiAgentState,
    settings: Settings,
) -> Dict[str, Any]:
    """
    总结专家智能体
    
    职责：
    - 信息整合
    - 报告生成
    - 结构化输出
    
    能力：
    - 内容总结
    - 报告撰写
    - 格式转换
    """
    logger.info("📝 [总结专家] 开始执行总结任务...")
    
    workspace = SharedWorkspace(state)
    agent_id = "summarization_specialist"
    
    workspace.register_agent(agent_id)
    workspace.update_agent_status(agent_id, "running")
    
    user_query = state.get("user_query", "")
    thoughts = []
    observations = []
    
    try:
        # 1. 收集所有智能体的结果
        retrieval_results = workspace.get_shared_data("retrieval_results", {})
        analysis_result = workspace.get_shared_data("analysis_result", {})
        
        # 2. 构建总结上下文
        context_parts = []
        
        if retrieval_results:
            context_parts.append("## 检索结果")
            
            if "knowledge_base" in retrieval_results:
                kb_contexts = retrieval_results["knowledge_base"]
                context_parts.append(
                    f"知识库内容（{len(kb_contexts)} 个片段）:\n"
                    + "\n".join([
                        f"{i+1}. {ctx.get('content', '')[:300]}"
                        for i, ctx in enumerate(kb_contexts)
                    ])
                )
            
            if "web_search" in retrieval_results:
                search_data = retrieval_results["web_search"]
                context_parts.append(
                    f"网络搜索结果:\n{search_data.get('results', '')[:800]}"
                )
        
        if analysis_result:
            context_parts.append("## 分析结果")
            context_parts.append(f"核心主题: {', '.join(analysis_result.get('core_topics', []))}")
            context_parts.append(f"关键发现: " + "; ".join(analysis_result.get('key_findings', [])[:3]))
            context_parts.append(f"分析总结: {analysis_result.get('analysis_summary', '')}")
        
        full_context = "\n\n".join(context_parts)
        
        thoughts.append("收集了所有智能体的结果，准备生成总结")
        
        # 3. 使用 LLM 生成综合总结
        logger.info("✍️ 使用 LLM 生成综合总结...")
        
        # 获取当前子任务描述
        current_subtask = workspace.get_current_subtask()
        task_description = current_subtask.description if current_subtask else "生成全面的总结报告"
        
        # 检查是否有深度分析结果
        has_deep_analysis = analysis_result and "core_concepts" in analysis_result
        
        summarization_prompt = f"""你是一个资深的研究报告撰写专家。请基于以下信息，为用户生成一份高质量、结构化的研究报告或答案。

【任务要求】：{task_description}

【用户问题】：{user_query}

【收集到的信息】：
{full_context}

【报告撰写要求】：

1. **结构化组织**：
   - 使用清晰的 Markdown 格式
   - 合理的标题层级（# ## ### ）
   - 如果是研究报告，包含：引言、主要内容、结论
   - 如果是技术分析，包含：概述、技术原理、应用案例、趋势分析

2. **内容深度**：
   - 不要只是罗列信息，要进行深度整合和提炼
   - 建立不同信息点之间的逻辑联系
   - 提供清晰的论证和推理过程
   - 突出关键发现和核心洞察

3. **表达质量**：
   - 语言流畅、专业、准确
   - 避免重复和冗余
   - 使用具体的数据和案例支撑论点
   - 适当使用列表、表格等形式

4. **信息来源**：
   - 优先使用提供的检索结果和分析结果
   - 如果引用具体数据或观点，可注明来源
   - 区分事实陈述和推理结论

5. **完整性**：
   - 全面回答用户提出的所有问题点
   - 不遗漏关键信息
   - 如果信息不足，明确指出

6. **长度要求**：
   - 简单问题：300-600字
   - 中等复杂度：600-1200字
   - 复杂研究报告：1200-2000字

【特别注意】：
- 这是多智能体协作的最终输出，要体现高质量
- 整合所有前序智能体的工作成果
- 确保报告的专业性和可读性
{"- 已有深度分析结果，请充分利用分析专家提供的洞察" if has_deep_analysis else ""}

现在请生成最终报告：
"""
        
        final_answer, _ = await invoke_llm(
            messages=[{"role": "user", "content": summarization_prompt}],
            settings=settings,
            temperature=0.6,  # 平衡创造性和准确性
            max_tokens=3000,  # 增加token以支持更长的报告
        )
        
        # 检查是否是错误消息
        if final_answer.startswith("LLM 调用") or len(final_answer) < 50:
            logger.warning(f"⚠️ [总结专家] LLM 响应异常: {final_answer}")
            # 降级策略：生成简单总结
            fallback_answer = f"""# {user_query}

## 执行摘要
本次多智能体协作完成了以下工作：

### 检索结果
{"✅ 已完成知识库检索和网络搜索" if retrieval_results else "⚠️ 检索信息有限"}

### 分析结果
{"✅ 已完成深度分析" if analysis_result else "⚠️ 分析信息有限"}

## 说明
由于LLM响应超时或异常，系统生成了简化版报告。建议：
1. 重新提交问题
2. 简化问题描述
3. 检查网络连接

原始错误信息：{final_answer}
"""
            final_answer = fallback_answer
            thoughts.append("LLM响应异常，使用降级策略生成简化报告")
        else:
            thoughts.append("生成了综合总结回答")
        
        observations.append(f"总结完成，生成回答长度：{len(final_answer)} 字符")
        
        # 4. 存储结果
        workspace.store_agent_result(agent_id, {"final_answer": final_answer})
        workspace.set_shared_data("final_answer", final_answer)
        
        # 5. 发送结果消息
        workspace.send_message(
            from_agent=agent_id,
            to_agent="orchestrator",
            message_type="result",
            content={
                "status": "completed",
                "final_answer": final_answer,
            },
        )
        
        workspace.update_agent_status(agent_id, "completed")
        
        logger.info("✅ [总结专家] 总结完成")
        
        return {
            "agent_thoughts": {agent_id: thoughts},
            "agent_observations": {agent_id: observations},
            "final_answer": final_answer,
        }
    
    except Exception as e:
        logger.error(f"❌ [总结专家] 执行失败: {e}", exc_info=True)
        workspace.update_agent_status(agent_id, "failed")
        workspace.send_message(
            from_agent=agent_id,
            to_agent="orchestrator",
            message_type="error",
            content={"error": str(e)},
        )
        
        return {
            "agent_thoughts": {agent_id: [f"执行失败: {str(e)}"]},
            "error": str(e),
        }


# ==================== 验证专家（Verification Specialist） ====================

async def verification_specialist_node(
    state: MultiAgentState,
    settings: Settings,
) -> Dict[str, Any]:
    """
    验证专家智能体（可选）
    
    职责：
    - 质量检查
    - 事实核查
    - 一致性验证
    
    能力：
    - 信息验证
    - 质量评估
    """
    logger.info("✔️ [验证专家] 开始执行验证任务...")
    
    workspace = SharedWorkspace(state)
    agent_id = "verification_specialist"
    
    workspace.register_agent(agent_id)
    workspace.update_agent_status(agent_id, "running")
    
    thoughts = []
    observations = []
    
    try:
        # 1. 获取最终答案
        final_answer = workspace.get_shared_data("final_answer", "")
        
        if not final_answer:
            thoughts.append("未找到最终答案，跳过验证")
            workspace.update_agent_status(agent_id, "skipped")
            return {
                "agent_thoughts": {agent_id: thoughts},
            }
        
        # 2. 使用 LLM 进行质量评估
        logger.info("🔍 使用 LLM 进行质量验证...")
        
        verification_prompt = f"""请评估以下回答的质量：

回答内容：
{final_answer}

请从以下维度评估（0-10分）：
1. 准确性：信息是否准确可靠
2. 完整性：是否全面回答了问题
3. 清晰度：表达是否清晰易懂
4. 相关性：是否与问题相关

以 JSON 格式输出评估结果：
{{
  "accuracy_score": 0-10,
  "completeness_score": 0-10,
  "clarity_score": 0-10,
  "relevance_score": 0-10,
  "overall_score": 0-10,
  "issues": ["问题1", "问题2", ...],
  "suggestions": ["建议1", "建议2", ...],
  "verdict": "通过" 或 "需要改进"
}}

只返回 JSON，不要其他解释。
"""
        
        llm_response, _ = await invoke_llm(
            messages=[{"role": "user", "content": verification_prompt}],
            settings=settings,
            temperature=0.2,
            max_tokens=800,
        )
        
        verification_result = parse_json_from_llm(llm_response)
        
        overall_score = verification_result.get("overall_score", 7)
        verdict = verification_result.get("verdict", "通过")
        
        thoughts.append(f"完成质量验证，总分：{overall_score}/10")
        observations.append(f"验证结果：{verdict}，总分 {overall_score}/10")
        
        # 3. 存储结果
        workspace.store_agent_result(agent_id, verification_result)
        workspace.set_shared_data("verification_result", verification_result)
        
        # 4. 发送结果消息
        workspace.send_message(
            from_agent=agent_id,
            to_agent="orchestrator",
            message_type="result",
            content={
                "status": "completed",
                "verification_result": verification_result,
            },
        )
        
        workspace.update_agent_status(agent_id, "completed")
        
        logger.info(f"✅ [验证专家] 验证完成，结果：{verdict}")
        
        return {
            "agent_thoughts": {agent_id: thoughts},
            "agent_observations": {agent_id: observations},
            "quality_score": overall_score / 10.0,
        }
    
    except Exception as e:
        logger.error(f"❌ [验证专家] 执行失败: {e}", exc_info=True)
        workspace.update_agent_status(agent_id, "failed")
        workspace.send_message(
            from_agent=agent_id,
            to_agent="orchestrator",
            message_type="error",
            content={"error": str(e)},
        )
        
        return {
            "agent_thoughts": {agent_id: [f"执行失败: {str(e)}"]},
            "error": str(e),
        }


# ==================== 智能体注册表 ====================

AGENT_REGISTRY = {
    "retrieval_specialist": {
        "name": "检索专家",
        "description": "负责知识库检索和网络搜索",
        "node_function": retrieval_specialist_node,
        "capabilities": ["knowledge_base_retrieval", "web_search", "document_analysis"],
    },
    "analysis_specialist": {
        "name": "分析专家",
        "description": "负责数据分析和内容理解",
        "node_function": analysis_specialist_node,
        "capabilities": ["text_analysis", "data_extraction", "pattern_recognition"],
    },
    "summarization_specialist": {
        "name": "总结专家",
        "description": "负责信息整合和报告生成",
        "node_function": summarization_specialist_node,
        "capabilities": ["content_summarization", "report_generation", "format_conversion"],
    },
    "verification_specialist": {
        "name": "验证专家",
        "description": "负责质量检查和事实核查（可选）",
        "node_function": verification_specialist_node,
        "capabilities": ["quality_check", "fact_verification", "consistency_validation"],
    },
}


def get_agent_by_id(agent_id: str) -> Optional[Dict[str, Any]]:
    """根据ID获取智能体信息"""
    return AGENT_REGISTRY.get(agent_id)


def list_available_agents() -> List[Dict[str, Any]]:
    """列出所有可用的智能体"""
    return [
        {
            "id": agent_id,
            "name": info["name"],
            "description": info["description"],
            "capabilities": info["capabilities"],
        }
        for agent_id, info in AGENT_REGISTRY.items()
    ]

