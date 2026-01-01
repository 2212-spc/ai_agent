"""
Agent Builder 节点配置定义

此文件定义了所有可用的节点类型及其配置，确保前后端同步。
前端通过 API 读取这些定义来动态生成节点库和配置表单。

[优化] 解决前后端节点定义不同步的问题
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class ConfigField(BaseModel):
    """节点配置字段定义"""
    name: str = Field(..., description="字段名称（代码中使用的key）")
    label: str = Field(..., description="字段显示标签（用户可见）")
    field_type: str = Field(..., description="字段类型：text, textarea, select, json, code, number, checkbox")
    default: Optional[Any] = Field(None, description="默认值")
    required: bool = Field(False, description="是否必填")
    options: Optional[List[Dict[str, str]]] = Field(None, description="选项列表（对于select类型）")
    placeholder: Optional[str] = Field(None, description="占位符文本")
    description: Optional[str] = Field(None, description="字段说明")


class NodeType(BaseModel):
    """节点类型定义"""
    type: str = Field(..., description="节点类型唯一标识符")
    label: str = Field(..., description="节点显示名称")
    icon: str = Field(..., description="节点图标（emoji或icon class）")
    category: str = Field(..., description="节点分类：control, llm, data, tool, logic")
    description: str = Field(..., description="节点功能描述")
    inputs: List[str] = Field(default_factory=list, description="输入参数列表")
    outputs: List[str] = Field(default_factory=list, description="输出参数列表")
    config_fields: List[ConfigField] = Field(default_factory=list, description="配置字段列表")
    is_start_node: bool = Field(False, description="是否可以作为起始节点")
    is_end_node: bool = Field(False, description="是否可以作为结束节点")


# ==============================================
# 所有可用节点定义（10种类型）
# ==============================================

AVAILABLE_NODES: Dict[str, NodeType] = {
    # 控制流节点
    "planner": NodeType(
        type="planner",
        label="规划器",
        icon="🧠",
        category="control",
        description="分析用户查询并制定详细的执行计划",
        inputs=["user_query", "conversation_history"],
        outputs=["plan", "思考过程"],
        config_fields=[
            ConfigField(
                name="prompt",
                label="规划提示词",
                field_type="textarea",
                default="请根据用户的问题，制定详细的解决方案。",
                required=False,
                placeholder="输入自定义规划提示词",
                description="指导规划器如何分析和制定计划"
            ),
            ConfigField(
                name="max_steps",
                label="最大步骤数",
                field_type="number",
                default=5,
                required=False,
                description="规划的最大步骤数限制"
            )
        ],
        is_start_node=True,
    ),

    "router": NodeType(
        type="router",
        label="路由器",
        icon="🔀",
        category="control",
        description="根据条件选择下一步执行路径",
        inputs=["current_state", "plan"],
        outputs=["next_node"],
        config_fields=[
            ConfigField(
                name="routing_logic",
                label="路由逻辑",
                field_type="select",
                required=True,
                options=[
                    {"value": "needs_tool", "label": "需要工具调用"},
                    {"value": "needs_knowledge", "label": "需要知识检索"},
                    {"value": "can_answer", "label": "可以直接回答"},
                    {"value": "needs_clarification", "label": "需要澄清"},
                    {"value": "custom", "label": "自定义条件"},
                ],
                description="选择路由决策逻辑"
            ),
            ConfigField(
                name="custom_condition",
                label="自定义条件",
                field_type="code",
                required=False,
                placeholder='例如: state["tool_calls_made"] < 3',
                description="当routing_logic为custom时，填写Python条件表达式"
            )
        ],
    ),

    # 数据节点
    "knowledge_search": NodeType(
        type="knowledge_search",
        label="知识库检索",
        icon="📚",
        category="data",
        description="从知识库中检索相关文档片段",
        inputs=["user_query"],
        outputs=["retrieved_contexts"],
        config_fields=[
            ConfigField(
                name="top_k",
                label="返回结果数",
                field_type="number",
                default=5,
                required=True,
                description="返回最相关的K个文档片段"
            ),
            ConfigField(
                name="min_score",
                label="最小相似度分数",
                field_type="number",
                default=0.5,
                required=False,
                description="只返回相似度高于此分数的结果（0-1之间）"
            )
        ],
    ),

    # 工具节点
    "tool_executor": NodeType(
        type="tool_executor",
        label="工具执行器",
        icon="🔧",
        category="tool",
        description="调用外部工具（搜索、天气、计算等）",
        inputs=["tool_id", "arguments"],
        outputs=["tool_result"],
        config_fields=[
            ConfigField(
                name="toolId",
                label="选择工具",
                field_type="select",
                required=True,
                options=[],  # 运行时从数据库加载
                description="选择要执行的工具"
            ),
            ConfigField(
                name="arguments",
                label="工具参数",
                field_type="json",
                required=False,
                placeholder='{"query": "{{user_query}}"}',
                description="工具调用参数（支持模板变量如{{user_query}}）"
            ),
            ConfigField(
                name="on_error",
                label="错误处理",
                field_type="select",
                default="continue",
                options=[
                    {"value": "continue", "label": "继续执行"},
                    {"value": "retry", "label": "重试一次"},
                    {"value": "fail", "label": "终止流程"},
                ],
                description="工具执行失败时的处理方式"
            )
        ],
    ),

    # 逻辑节点
    "condition": NodeType(
        type="condition",
        label="条件判断",
        icon="❓",
        category="logic",
        description="根据条件判断执行不同分支",
        inputs=["state"],
        outputs=["branch_result"],
        config_fields=[
            ConfigField(
                name="condition",
                label="判断条件",
                field_type="code",
                required=True,
                placeholder='state["tool_results"] is not None',
                description="Python条件表达式，返回True/False"
            ),
            ConfigField(
                name="true_branch",
                label="True分支",
                field_type="text",
                required=True,
                placeholder="next_node_id",
                description="条件为True时跳转的节点ID"
            ),
            ConfigField(
                name="false_branch",
                label="False分支",
                field_type="text",
                required=True,
                placeholder="alternative_node_id",
                description="条件为False时跳转的节点ID"
            )
        ],
    ),

    # LLM节点
    "llm_call": NodeType(
        type="llm_call",
        label="LLM调用",
        icon="🤖",
        category="llm",
        description="调用大语言模型生成回复",
        inputs=["messages", "system_prompt"],
        outputs=["llm_response"],
        config_fields=[
            ConfigField(
                name="system_prompt",
                label="系统提示词",
                field_type="textarea",
                required=True,
                placeholder="你是一个专业的助手...",
                description="定义LLM的角色和行为"
            ),
            ConfigField(
                name="temperature",
                label="温度参数",
                field_type="number",
                default=0.7,
                required=False,
                description="控制回复的随机性（0-1之间，越高越随机）"
            ),
            ConfigField(
                name="max_tokens",
                label="最大Token数",
                field_type="number",
                default=2000,
                required=False,
                description="限制生成回复的最大长度"
            )
        ],
    ),

    "synthesizer": NodeType(
        type="synthesizer",
        label="合成器",
        icon="🔗",
        category="llm",
        description="综合多个信息源生成最终回答",
        inputs=["tool_results", "retrieved_contexts", "user_query"],
        outputs=["final_answer"],
        config_fields=[
            ConfigField(
                name="synthesis_prompt",
                label="合成提示词",
                field_type="textarea",
                default="请综合以下信息，给出完整准确的回答：",
                required=False,
                description="指导如何综合多个信息源"
            ),
            ConfigField(
                name="include_sources",
                label="包含信息源",
                field_type="checkbox",
                default=True,
                description="是否在回答中标注信息来源"
            )
        ],
        is_end_node=True,
    ),

    # 辅助节点
    "delay": NodeType(
        type="delay",
        label="延迟等待",
        icon="⏱️",
        category="control",
        description="延迟指定时间后继续执行",
        inputs=[],
        outputs=[],
        config_fields=[
            ConfigField(
                name="seconds",
                label="延迟秒数",
                field_type="number",
                default=1,
                required=True,
                description="等待的秒数"
            )
        ],
    ),

    "variable": NodeType(
        type="variable",
        label="变量设置",
        icon="💾",
        category="logic",
        description="设置或修改状态变量",
        inputs=["state"],
        outputs=["state"],
        config_fields=[
            ConfigField(
                name="variable_name",
                label="变量名",
                field_type="text",
                required=True,
                placeholder="my_variable",
                description="要设置的变量名"
            ),
            ConfigField(
                name="variable_value",
                label="变量值",
                field_type="text",
                required=True,
                placeholder="{{user_query}} or static value",
                description="变量值（支持模板变量）"
            )
        ],
    ),

    "loop": NodeType(
        type="loop",
        label="循环执行",
        icon="🔄",
        category="control",
        description="重复执行指定节点序列",
        inputs=["state"],
        outputs=["state"],
        config_fields=[
            ConfigField(
                name="max_iterations",
                label="最大迭代次数",
                field_type="number",
                default=3,
                required=True,
                description="循环的最大次数"
            ),
            ConfigField(
                name="exit_condition",
                label="退出条件",
                field_type="code",
                required=False,
                placeholder='state["is_complete"] == True',
                description="满足此条件时退出循环"
            )
        ],
    ),
}


# ==============================================
# 节点分类
# ==============================================

NODE_CATEGORIES = {
    "control": {"label": "控制流", "icon": "🎛️"},
    "llm": {"label": "LLM", "icon": "🤖"},
    "data": {"label": "数据", "icon": "📊"},
    "tool": {"label": "工具", "icon": "🔧"},
    "logic": {"label": "逻辑", "icon": "🧮"},
}


# ==============================================
# 工具函数
# ==============================================

def get_all_node_types() -> Dict[str, Dict[str, Any]]:
    """
    获取所有节点类型的序列化字典
    供API端点返回给前端
    """
    return {
        node_type: node.model_dump()
        for node_type, node in AVAILABLE_NODES.items()
    }


def get_node_type(node_type: str) -> Optional[NodeType]:
    """根据类型获取节点定义"""
    return AVAILABLE_NODES.get(node_type)


def validate_node_config(node_type: str, config: Dict[str, Any]) -> List[str]:
    """
    验证节点配置的完整性
    返回错误消息列表，空列表表示验证通过
    """
    node = get_node_type(node_type)
    if not node:
        return [f"未知的节点类型: {node_type}"]

    errors = []
    for field in node.config_fields:
        if field.required and field.name not in config:
            errors.append(f"缺少必填字段: {field.label} ({field.name})")

    return errors


def get_nodes_by_category(category: str) -> List[NodeType]:
    """根据分类获取节点列表"""
    return [
        node for node in AVAILABLE_NODES.values()
        if node.category == category
    ]
