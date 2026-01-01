/**
 * Agent Builder 节点类型定义（前端）
 *
 * 与后端 node_config.py 同步
 * 此文件定义了所有可用的节点类型，供画布组件使用
 *
 * [优化] 解决前后端节点定义不同步的问题
 */

// 节点分类定义
export const NODE_CATEGORIES = {
  control: { label: '控制流', icon: '🎛️' },
  llm: { label: 'LLM', icon: '🤖' },
  data: { label: '数据', icon: '📊' },
  tool: { label: '工具', icon: '🔧' },
  logic: { label: '逻辑', icon: '🧮' },
};

// 所有可用节点定义（与后端同步的10种类型）
export const AVAILABLE_NODES = {
  // 控制流节点
  planner: {
    type: 'planner',
    label: '规划器',
    icon: '🧠',
    category: 'control',
    description: '分析用户查询并制定详细的执行计划',
    inputs: ['user_query', 'conversation_history'],
    outputs: ['plan', '思考过程'],
    configFields: [
      {
        name: 'prompt',
        label: '规划提示词',
        fieldType: 'textarea',
        default: '请根据用户的问题，制定详细的解决方案。',
        required: false,
        placeholder: '输入自定义规划提示词',
        description: '指导规划器如何分析和制定计划',
      },
      {
        name: 'max_steps',
        label: '最大步骤数',
        fieldType: 'number',
        default: 5,
        required: false,
        description: '规划的最大步骤数限制',
      },
    ],
    isStartNode: true,
  },

  router: {
    type: 'router',
    label: '路由器',
    icon: '🔀',
    category: 'control',
    description: '根据条件选择下一步执行路径',
    inputs: ['current_state', 'plan'],
    outputs: ['next_node'],
    configFields: [
      {
        name: 'routing_logic',
        label: '路由逻辑',
        fieldType: 'select',
        required: true,
        options: [
          { value: 'needs_tool', label: '需要工具调用' },
          { value: 'needs_knowledge', label: '需要知识检索' },
          { value: 'can_answer', label: '可以直接回答' },
          { value: 'needs_clarification', label: '需要澄清' },
          { value: 'custom', label: '自定义条件' },
        ],
        description: '选择路由决策逻辑',
      },
      {
        name: 'custom_condition',
        label: '自定义条件',
        fieldType: 'code',
        required: false,
        placeholder: 'state["tool_calls_made"] < 3',
        description: '当routing_logic为custom时，填写Python条件表达式',
      },
    ],
  },

  // 数据节点
  knowledge_search: {
    type: 'knowledge_search',
    label: '知识库检索',
    icon: '📚',
    category: 'data',
    description: '从知识库中检索相关文档片段',
    inputs: ['user_query'],
    outputs: ['retrieved_contexts'],
    configFields: [
      {
        name: 'top_k',
        label: '返回结果数',
        fieldType: 'number',
        default: 5,
        required: true,
        description: '返回最相关的K个文档片段',
      },
      {
        name: 'min_score',
        label: '最小相似度分数',
        fieldType: 'number',
        default: 0.5,
        required: false,
        description: '只返回相似度高于此分数的结果（0-1之间）',
      },
    ],
  },

  // 工具节点
  tool_executor: {
    type: 'tool_executor',
    label: '工具执行器',
    icon: '🔧',
    category: 'tool',
    description: '调用外部工具（搜索、天气、计算等）',
    inputs: ['tool_id', 'arguments'],
    outputs: ['tool_result'],
    configFields: [
      {
        name: 'toolId',
        label: '选择工具',
        fieldType: 'select',
        required: true,
        options: [], // 运行时从API加载
        description: '选择要执行的工具',
      },
      {
        name: 'arguments',
        label: '工具参数',
        fieldType: 'json',
        required: false,
        placeholder: '{"query": "{{user_query}}"}',
        description: '工具调用参数（支持模板变量如{{user_query}}）',
      },
      {
        name: 'on_error',
        label: '错误处理',
        fieldType: 'select',
        default: 'continue',
        options: [
          { value: 'continue', label: '继续执行' },
          { value: 'retry', label: '重试一次' },
          { value: 'fail', label: '终止流程' },
        ],
        description: '工具执行失败时的处理方式',
      },
    ],
  },

  // 逻辑节点
  condition: {
    type: 'condition',
    label: '条件判断',
    icon: '❓',
    category: 'logic',
    description: '根据条件判断执行不同分支',
    inputs: ['state'],
    outputs: ['branch_result'],
    configFields: [
      {
        name: 'condition',
        label: '判断条件',
        fieldType: 'code',
        required: true,
        placeholder: 'state["tool_results"] is not None',
        description: 'Python条件表达式，返回True/False',
      },
      {
        name: 'true_branch',
        label: 'True分支',
        fieldType: 'text',
        required: true,
        placeholder: 'next_node_id',
        description: '条件为True时跳转的节点ID',
      },
      {
        name: 'false_branch',
        label: 'False分支',
        fieldType: 'text',
        required: true,
        placeholder: 'alternative_node_id',
        description: '条件为False时跳转的节点ID',
      },
    ],
  },

  // LLM节点
  llm_call: {
    type: 'llm_call',
    label: 'LLM调用',
    icon: '🤖',
    category: 'llm',
    description: '调用大语言模型生成回复',
    inputs: ['messages', 'system_prompt'],
    outputs: ['llm_response'],
    configFields: [
      {
        name: 'system_prompt',
        label: '系统提示词',
        fieldType: 'textarea',
        required: true,
        placeholder: '你是一个专业的助手...',
        description: '定义LLM的角色和行为',
      },
      {
        name: 'temperature',
        label: '温度参数',
        fieldType: 'number',
        default: 0.7,
        required: false,
        description: '控制回复的随机性（0-1之间，越高越随机）',
      },
      {
        name: 'max_tokens',
        label: '最大Token数',
        fieldType: 'number',
        default: 2000,
        required: false,
        description: '限制生成回复的最大长度',
      },
    ],
  },

  synthesizer: {
    type: 'synthesizer',
    label: '合成器',
    icon: '🔗',
    category: 'llm',
    description: '综合多个信息源生成最终回答',
    inputs: ['tool_results', 'retrieved_contexts', 'user_query'],
    outputs: ['final_answer'],
    configFields: [
      {
        name: 'synthesis_prompt',
        label: '合成提示词',
        fieldType: 'textarea',
        default: '请综合以下信息，给出完整准确的回答：',
        required: false,
        description: '指导如何综合多个信息源',
      },
      {
        name: 'include_sources',
        label: '包含信息源',
        fieldType: 'checkbox',
        default: true,
        description: '是否在回答中标注信息来源',
      },
    ],
    isEndNode: true,
  },

  // 辅助节点
  delay: {
    type: 'delay',
    label: '延迟等待',
    icon: '⏱️',
    category: 'control',
    description: '延迟指定时间后继续执行',
    inputs: [],
    outputs: [],
    configFields: [
      {
        name: 'seconds',
        label: '延迟秒数',
        fieldType: 'number',
        default: 1,
        required: true,
        description: '等待的秒数',
      },
    ],
  },

  variable: {
    type: 'variable',
    label: '变量设置',
    icon: '💾',
    category: 'logic',
    description: '设置或修改状态变量',
    inputs: ['state'],
    outputs: ['state'],
    configFields: [
      {
        name: 'variable_name',
        label: '变量名',
        fieldType: 'text',
        required: true,
        placeholder: 'my_variable',
        description: '要设置的变量名',
      },
      {
        name: 'variable_value',
        label: '变量值',
        fieldType: 'text',
        required: true,
        placeholder: '{{user_query}} or static value',
        description: '变量值（支持模板变量）',
      },
    ],
  },

  loop: {
    type: 'loop',
    label: '循环执行',
    icon: '🔄',
    category: 'control',
    description: '重复执行指定节点序列',
    inputs: ['state'],
    outputs: ['state'],
    configFields: [
      {
        name: 'max_iterations',
        label: '最大迭代次数',
        fieldType: 'number',
        default: 3,
        required: true,
        description: '循环的最大次数',
      },
      {
        name: 'exit_condition',
        label: '退出条件',
        fieldType: 'code',
        required: false,
        placeholder: 'state["is_complete"] == True',
        description: '满足此条件时退出循环',
      },
    ],
  },
};

// 工具函数

/**
 * 根据分类获取节点列表
 */
export function getNodesByCategory(category) {
  return Object.values(AVAILABLE_NODES).filter(
    (node) => node.category === category
  );
}

/**
 * 获取所有节点类型列表
 */
export function getAllNodeTypes() {
  return Object.values(AVAILABLE_NODES);
}

/**
 * 根据类型获取节点定义
 */
export function getNodeType(type) {
  return AVAILABLE_NODES[type];
}

/**
 * 验证节点配置
 * @returns 错误消息数组，空数组表示验证通过
 */
export function validateNodeConfig(nodeType, config) {
  const node = getNodeType(nodeType);
  if (!node) {
    return [`未知的节点类型: ${nodeType}`];
  }

  const errors = [];
  node.configFields.forEach((field) => {
    if (field.required && !config[field.name]) {
      errors.push(`缺少必填字段: ${field.label} (${field.name})`);
    }
  });

  return errors;
}

/**
 * 为节点创建默认配置
 */
export function createDefaultConfig(nodeType) {
  const node = getNodeType(nodeType);
  if (!node) return {};

  const config = {};
  node.configFields.forEach((field) => {
    if (field.default !== undefined) {
      config[field.name] = field.default;
    }
  });

  return config;
}
