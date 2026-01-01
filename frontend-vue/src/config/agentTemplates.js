/**
 * Agent 预设模板库
 * 为新手用户提供快速开始的方案
 */

// 模板定义
export const AGENT_TEMPLATES = {
  weather: {
    id: 'weather',
    name: '天气查询助手',
    icon: '🌤️',
    category: 'tool',
    difficulty: 'easy',
    estimatedTime: '5分钟',
    description: '查询城市天气，支持多个城市同时查询',
    features: [
      '自动识别城市名称',
      '调用天气API获取实时数据',
      '友好的结果展示'
    ],
    demoInput: '北京今天天气怎么样？',
    demoOutput: '北京今天多云，气温15-25°C，空气质量良好。',
    config: {
      nodes: [
        {
          id: 0,
          type: 'planner',
          label: '规划器',
          description: '理解用户查询意图',
          position: { x: 50, y: 100 },
          data: {
            prompt: '分析用户的天气查询需求，提取城市名称',
            max_steps: 3
          },
          inputs: ['user_query'],
          outputs: ['plan']
        },
        {
          id: 1,
          type: 'tool_executor',
          label: '天气查询',
          description: '调用天气API',
          position: { x: 300, y: 100 },
          data: {
            toolId: 'weather_tool',
            arguments: {
              city: '{{user_query}}'
            },
            on_error: 'continue'
          },
          inputs: ['plan'],
          outputs: ['tool_result']
        },
        {
          id: 2,
          type: 'synthesizer',
          label: '结果合成',
          description: '生成友好的回复',
          position: { x: 550, y: 100 },
          data: {
            synthesis_prompt: '将天气数据转换为友好的自然语言回复',
            include_sources: false
          },
          inputs: ['tool_result'],
          outputs: ['final_answer']
        }
      ],
      connections: [
        { from: 0, to: 1 },
        { from: 1, to: 2 }
      ],
      metadata: {
        template: 'weather',
        version: '1.0'
      }
    }
  },

  search_summarize: {
    id: 'search_summarize',
    name: '搜索+总结助手',
    icon: '🔍',
    category: 'knowledge',
    difficulty: 'easy',
    estimatedTime: '5分钟',
    description: '搜索网络信息并生成总结报告',
    features: [
      '网络搜索最新信息',
      '智能筛选相关内容',
      '生成结构化总结'
    ],
    demoInput: '最新的AI技术进展有哪些？',
    demoOutput: '根据搜索结果，最近AI领域有以下进展：\n1. GPT-4 Turbo发布...\n2. 多模态模型突破...',
    config: {
      nodes: [
        {
          id: 0,
          type: 'planner',
          label: '规划器',
          description: '分析搜索需求',
          position: { x: 50, y: 100 },
          data: {
            prompt: '理解用户的信息需求，规划搜索策略',
            max_steps: 5
          },
          inputs: ['user_query'],
          outputs: ['plan']
        },
        {
          id: 1,
          type: 'tool_executor',
          label: '网络搜索',
          description: '搜索相关信息',
          position: { x: 300, y: 100 },
          data: {
            toolId: 'web_search_tool',
            arguments: {
              query: '{{user_query}}',
              num_results: 5
            },
            on_error: 'continue'
          },
          inputs: ['plan'],
          outputs: ['tool_result']
        },
        {
          id: 2,
          type: 'synthesizer',
          label: '智能总结',
          description: '生成总结报告',
          position: { x: 550, y: 100 },
          data: {
            synthesis_prompt: '分析搜索结果，生成结构化的总结报告，突出关键信息',
            include_sources: true
          },
          inputs: ['tool_result'],
          outputs: ['final_answer']
        }
      ],
      connections: [
        { from: 0, to: 1 },
        { from: 1, to: 2 }
      ],
      metadata: {
        template: 'search_summarize',
        version: '1.0'
      }
    }
  },

  knowledge_qa: {
    id: 'knowledge_qa',
    name: '知识库问答',
    icon: '💡',
    category: 'knowledge',
    difficulty: 'medium',
    estimatedTime: '10分钟',
    description: '基于上传文档的智能问答系统',
    features: [
      '语义检索相关文档',
      '基于文档内容回答',
      '标注信息来源'
    ],
    demoInput: '公司的休假政策是什么？',
    demoOutput: '根据员工手册第3章，公司提供年假15天...\n\n来源：员工手册 p.12',
    config: {
      nodes: [
        {
          id: 0,
          type: 'knowledge_search',
          label: '知识库检索',
          description: '检索相关文档',
          position: { x: 50, y: 100 },
          data: {
            top_k: 5,
            min_score: 0.6
          },
          inputs: ['user_query'],
          outputs: ['retrieved_contexts']
        },
        {
          id: 1,
          type: 'llm_call',
          label: 'LLM回答',
          description: '基于文档生成回答',
          position: { x: 350, y: 100 },
          data: {
            system_prompt: '你是专业的知识库助手。根据提供的文档内容回答问题，如果文档中没有相关信息，请明确说明。',
            temperature: 0.3,
            max_tokens: 1000
          },
          inputs: ['retrieved_contexts'],
          outputs: ['llm_response']
        },
        {
          id: 2,
          type: 'synthesizer',
          label: '结果整合',
          description: '添加来源标注',
          position: { x: 650, y: 100 },
          data: {
            synthesis_prompt: '整合回答并标注信息来源',
            include_sources: true
          },
          inputs: ['llm_response', 'retrieved_contexts'],
          outputs: ['final_answer']
        }
      ],
      connections: [
        { from: 0, to: 1 },
        { from: 1, to: 2 }
      ],
      metadata: {
        template: 'knowledge_qa',
        version: '1.0'
      }
    }
  },

  code_assistant: {
    id: 'code_assistant',
    name: '代码分析助手',
    icon: '🐛',
    category: 'tool',
    difficulty: 'medium',
    estimatedTime: '10分钟',
    description: '分析代码、提供优化建议、生成改进版本',
    features: [
      '代码质量分析',
      '性能优化建议',
      '生成改进版本'
    ],
    demoInput: '[粘贴一段代码]',
    demoOutput: '代码分析：\n1. 复杂度过高\n2. 缺少错误处理\n\n优化建议：...\n\n改进版本：...',
    config: {
      nodes: [
        {
          id: 0,
          type: 'planner',
          label: '分析规划',
          description: '规划分析步骤',
          position: { x: 50, y: 50 },
          data: {
            prompt: '分析代码，规划优化策略：1.质量检查 2.性能分析 3.改进建议',
            max_steps: 5
          },
          inputs: ['user_query'],
          outputs: ['plan']
        },
        {
          id: 1,
          type: 'llm_call',
          label: '代码分析',
          description: '分析代码质量',
          position: { x: 300, y: 50 },
          data: {
            system_prompt: '你是代码审查专家。分析代码的质量、性能、可维护性，提供具体建议。',
            temperature: 0.2,
            max_tokens: 2000
          },
          inputs: ['plan'],
          outputs: ['analysis']
        },
        {
          id: 2,
          type: 'llm_call',
          label: '生成改进',
          description: '生成优化代码',
          position: { x: 300, y: 200 },
          data: {
            system_prompt: '根据分析结果，生成优化后的代码版本，保持功能不变。',
            temperature: 0.3,
            max_tokens: 2000
          },
          inputs: ['analysis'],
          outputs: ['improved_code']
        },
        {
          id: 3,
          type: 'synthesizer',
          label: '结果整合',
          description: '整合分析和改进',
          position: { x: 550, y: 125 },
          data: {
            synthesis_prompt: '整合分析报告和改进代码，生成完整的优化方案',
            include_sources: false
          },
          inputs: ['analysis', 'improved_code'],
          outputs: ['final_answer']
        }
      ],
      connections: [
        { from: 0, to: 1 },
        { from: 1, to: 2 },
        { from: 2, to: 3 }
      ],
      metadata: {
        template: 'code_assistant',
        version: '1.0'
      }
    }
  },

  content_creator: {
    id: 'content_creator',
    name: '内容创作助手',
    icon: '📝',
    category: 'creative',
    difficulty: 'easy',
    estimatedTime: '5分钟',
    description: '根据主题生成多版本创意内容',
    features: [
      '生成多个创意版本',
      '不同风格和角度',
      '可选择最佳方案'
    ],
    demoInput: '写一篇关于AI的科普文章',
    demoOutput: '【版本1 - 通俗易懂】...\n【版本2 - 专业深度】...\n【版本3 - 趣味性】...',
    config: {
      nodes: [
        {
          id: 0,
          type: 'planner',
          label: '创作规划',
          description: '规划内容结构',
          position: { x: 50, y: 100 },
          data: {
            prompt: '理解创作需求，规划内容结构和风格',
            max_steps: 3
          },
          inputs: ['user_query'],
          outputs: ['plan']
        },
        {
          id: 1,
          type: 'llm_call',
          label: '版本1-通俗',
          description: '生成通俗版本',
          position: { x: 300, y: 50 },
          data: {
            system_prompt: '以通俗易懂的方式创作内容，适合普通读者',
            temperature: 0.8,
            max_tokens: 1500
          },
          inputs: ['plan'],
          outputs: ['version1']
        },
        {
          id: 2,
          type: 'llm_call',
          label: '版本2-专业',
          description: '生成专业版本',
          position: { x: 300, y: 150 },
          data: {
            system_prompt: '以专业深度的方式创作内容，适合专业人士',
            temperature: 0.6,
            max_tokens: 1500
          },
          inputs: ['plan'],
          outputs: ['version2']
        },
        {
          id: 3,
          type: 'synthesizer',
          label: '整合输出',
          description: '整合所有版本',
          position: { x: 550, y: 100 },
          data: {
            synthesis_prompt: '整合多个版本，标注不同风格',
            include_sources: false
          },
          inputs: ['version1', 'version2'],
          outputs: ['final_answer']
        }
      ],
      connections: [
        { from: 0, to: 1 },
        { from: 0, to: 2 },
        { from: 1, to: 3 },
        { from: 2, to: 3 }
      ],
      metadata: {
        template: 'content_creator',
        version: '1.0'
      }
    }
  }
};

// 模板分类
export const TEMPLATE_CATEGORIES = {
  tool: {
    label: '工具调用',
    icon: '🔧',
    description: '调用外部工具完成任务'
  },
  knowledge: {
    label: '知识处理',
    icon: '📚',
    description: '检索和处理知识信息'
  },
  creative: {
    label: '创意生成',
    icon: '✨',
    description: '生成创意内容'
  }
};

// 难度级别
export const DIFFICULTY_LEVELS = {
  easy: { label: '简单', color: '#10b981', description: '5-10分钟完成' },
  medium: { label: '中等', color: '#f59e0b', description: '10-20分钟完成' },
  hard: { label: '复杂', color: '#ef4444', description: '20分钟以上' }
};

// 工具函数
export function getAllTemplates() {
  return Object.values(AGENT_TEMPLATES);
}

export function getTemplateById(id) {
  return AGENT_TEMPLATES[id];
}

export function getTemplatesByCategory(category) {
  return getAllTemplates().filter(t => t.category === category);
}
