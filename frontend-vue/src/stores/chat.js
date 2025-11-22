import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import axios from 'axios';

export const useChatStore = defineStore('chat', () => {
    // State
    const messages = ref([]);
    const currentSessionId = ref(null);
    const isLoading = ref(false);
    const apiBase = 'http://127.0.0.1:8000';
    const isMultiAgentMode = ref(false);
    const useKnowledgeBase = ref(true);
    const timelineSteps = ref([]);

    // Computed
    const hasMessages = computed(() => messages.value.length > 0);

    // Actions
    function addMessage(message) {
        messages.value.push({
            ...message,
            id: Date.now(),
            timestamp: new Date().toISOString()
        });
    }

    function clearMessages() {
        messages.value = [];
    }

    async function sendMessage(content) {
        isLoading.value = true;
        clearTimelineSteps(); // 清空之前的timeline

        // 添加用户消息到本地
        const userMsg = {
            role: 'user',
            content,
            type: 'text'
        };
        addMessage(userMsg);
        
        // 添加初始timeline步骤
        addTimelineStep({
            icon: '📝',
            title: '接收消息',
            content: '正在处理用户输入...',
            status: 'completed',
            type: 'thoughts'
        });

        // 构建符合后端格式的请求
        const requestMessages = messages.value
            .filter(m => m.role === 'user' || m.role === 'assistant')
            .map(m => ({
                role: m.role,
                content: m.content
            }));

        try {
            // 添加知识库检索步骤
            if (useKnowledgeBase.value) {
                addTimelineStep({
                    icon: '📚',
                    title: '检索知识库',
                    content: '从知识库中搜索相关文档...',
                    status: 'running',
                    type: 'observations'
                });
            }
            
            // 添加AI推理步骤
            addTimelineStep({
                icon: '🤖',
                title: 'AI推理',
                content: `使用${isMultiAgentMode.value ? '多智能体' : 'DeepSeek'}模型生成回复...`,
                status: 'running',
                type: 'tools'
            });
            
            let response;
            
            // 根据模式选择不同的API端点
            if (isMultiAgentMode.value) {
                response = await axios.post(`${apiBase}/chat/multi-agent`, {
                    messages: requestMessages,
                    use_knowledge_base: useKnowledgeBase.value
                });
            } else {
                response = await axios.post(`${apiBase}/chat`, {
                    messages: requestMessages,
                    model: 'deepseek-chat',
                    temperature: 0.7
                });
            }
            
            // 更新timeline步骤为完成状态
            if (useKnowledgeBase.value) {
                timelineSteps.value[1].status = 'completed';
                timelineSteps.value[1].content = '成功检索到相关文档';
            }
            const aiStepIndex = useKnowledgeBase.value ? 2 : 1;
            timelineSteps.value[aiStepIndex].status = 'completed';
            timelineSteps.value[aiStepIndex].content = '成功生成回复';

            // 添加AI回复 (后端返回 reply 字段)
            if (response.data && response.data.reply) {
                addMessage({
                    role: 'assistant',
                    content: response.data.reply,
                    type: 'text'
                });
                
                // 添加完成步骤
                addTimelineStep({
                    icon: '✅',
                    title: '返回结果',
                    content: '回复已生成并显示',
                    status: 'completed',
                    type: 'observations'
                });
                
                // 保存会话到后端
                saveConversation();
            } else {
                console.error('响应数据格式错误:', response.data);
            }

            return response.data;
        } catch (error) {
            console.error('发送消息失败:', error);
            
            // 显示详细错误信息
            let errorMsg = '消息发送失败，请重试';
            if (error.response) {
                errorMsg = `错误 ${error.response.status}: ${error.response.data?.detail || '未知错误'}`;
            } else if (error.request) {
                errorMsg = '无法连接到服务器，请检查后端是否启动';
            }
            
            addMessage({
                role: 'system',
                content: errorMsg,
                type: 'error'
            });
            throw error;
        } finally {
            isLoading.value = false;
        }
    }

    function setSessionId(id) {
        currentSessionId.value = id;
    }

    function toggleMultiAgentMode() {
        isMultiAgentMode.value = !isMultiAgentMode.value;
    }

    function setMultiAgentMode(value) {
        isMultiAgentMode.value = value;
    }

    function setUseKnowledgeBase(value) {
        useKnowledgeBase.value = value;
    }

    function addTimelineStep(step) {
        timelineSteps.value.push({
            ...step,
            id: Date.now() + Math.random(),
            timestamp: new Date().toISOString()
        });
    }

    function clearTimelineSteps() {
        timelineSteps.value = [];
    }

    function updateLastTimelineStep(updates) {
        if (timelineSteps.value.length > 0) {
            const lastStep = timelineSteps.value[timelineSteps.value.length - 1];
            Object.assign(lastStep, updates);
        }
    }

    async function saveConversation() {
        try {
            // 生成会话ID（如果没有）
            if (!currentSessionId.value) {
                currentSessionId.value = `session-${Date.now()}`;
            }
            
            // 获取会话标题（使用第一条用户消息）
            const firstUserMessage = messages.value.find(m => m.role === 'user');
            const title = firstUserMessage ? 
                (firstUserMessage.content.slice(0, 30) + '...') : 
                '新对话';
            
            // 保存到后端
            await axios.post(`${apiBase}/conversations`, {
                session_id: currentSessionId.value,
                title: title,
                messages: messages.value.map(m => ({
                    role: m.role,
                    content: m.content,
                    timestamp: m.timestamp
                })),
                metadata: {
                    mode: isMultiAgentMode.value ? 'multi-agent' : 'single',
                    use_knowledge_base: useKnowledgeBase.value
                }
            });
        } catch (error) {
            console.error('保存会话失败:', error);
            // 不影响主流程，静默失败
        }
    }

    return {
        messages,
        currentSessionId,
        isLoading,
        hasMessages,
        isMultiAgentMode,
        useKnowledgeBase,
        timelineSteps,
        addMessage,
        clearMessages,
        sendMessage,
        setSessionId,
        toggleMultiAgentMode,
        setMultiAgentMode,
        setUseKnowledgeBase,
        addTimelineStep,
        clearTimelineSteps,
        updateLastTimelineStep
    };
});
