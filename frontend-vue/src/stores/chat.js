import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import axios from 'axios';

// 会话状态枚举
const SESSION_STATUS = {
    IDLE: 'idle',
    GENERATING: 'generating',
    COMPLETED: 'completed'
};

export const useChatStore = defineStore('chat', () => {
    // State
    const currentSessionId = ref(null);
    const isLoading = ref(false);
    const apiBase = 'http://127.0.0.1:8000';
    const isMultiAgentMode = ref(false);
    const useKnowledgeBase = ref(true);
    const timelineSteps = ref([]);
    
    // 多会话管理
    const sessions = ref(new Map());
    const abortControllers = ref(new Map());

    // Computed - 当前会话的消息列表
    const messages = computed(() => {
        if (!currentSessionId.value) return [];
        const session = sessions.value.get(currentSessionId.value);
        return session ? session.messages : [];
    });
    
    const hasMessages = computed(() => messages.value.length > 0);

    // Actions
    function addMessage(message, sessionId = null) {
        const sid = sessionId || currentSessionId.value;
        if (!sid) return;
        
        const session = ensureSession(sid);
        session.messages.push({
            ...message,
            id: Date.now() + Math.random(), // 确保唯一性
            timestamp: new Date().toISOString()
        });
    }

    function clearMessages(sessionId = null) {
        const sid = sessionId || currentSessionId.value;
        if (!sid) return;
        
        const session = sessions.value.get(sid);
        if (session) {
            session.messages = [];
        }
    }
    
    // 确保会话存在
    function ensureSession(sessionId) {
        if (!sessions.value.has(sessionId)) {
            sessions.value.set(sessionId, {
                messages: [],
                status: SESSION_STATUS.IDLE,
                timeline: [],
                lastUpdate: Date.now()
            });
        }
        return sessions.value.get(sessionId);
    }
    
    // 设置会话状态
    function setSessionStatus(sessionId, status) {
        const session = ensureSession(sessionId);
        session.status = status;
        session.lastUpdate = Date.now();
    }
    
    // 获取会话状态
    function getSessionStatus(sessionId) {
        if (!sessions.value.has(sessionId)) {
            return SESSION_STATUS.IDLE;
        }
        return sessions.value.get(sessionId).status;
    }
    
    // 停止当前会话生成
    function stopGeneration(sessionId) {
        const sid = sessionId || currentSessionId.value;
        if (abortControllers.value.has(sid)) {
            abortControllers.value.get(sid).abort();
            abortControllers.value.delete(sid);
            setSessionStatus(sid, SESSION_STATUS.IDLE);
            isLoading.value = false;
        }
    }

    async function sendMessage(content, onStream) {
        // 生成或使用已有的session_id
        if (!currentSessionId.value) {
            currentSessionId.value = `session-${Date.now()}`;
            console.log('生成新的session_id:', currentSessionId.value);
        }

        const sessionId = currentSessionId.value;
        const session = ensureSession(sessionId);
        
        // 设置生成状态
        setSessionStatus(sessionId, SESSION_STATUS.GENERATING);
        isLoading.value = true;
        
        // 清空timeline
        clearTimelineSteps();

        // 添加用户消息到对应会话
        const userMsg = {
            role: 'user',
            content,
            type: 'text'
        };
        addMessage(userMsg, sessionId);
        
        // 添加初始timeline步骤
        addTimelineStep({
            icon: '📝',
            title: '接收消息',
            content: '正在处理用户输入...',
            status: 'completed',
            type: 'thoughts'
        });

        // 构建符合后端格式的请求（使用当前会话的消息）
        const requestMessages = session.messages
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
            
            // 创建AbortController用于取消请求
            const controller = new AbortController();
            abortControllers.value.set(sessionId, controller);
            
            // 根据模式选择不同的API端点
            const endpoint = isMultiAgentMode.value ? '/chat/agent/stream' : '/chat/stream';
            
            const response = await fetch(`${apiBase}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    messages: requestMessages,
                    use_knowledge_base: useKnowledgeBase.value,
                    session_id: sessionId,
                    use_tools: isMultiAgentMode.value,
                    model: 'deepseek-chat',
                    temperature: 0.7
                }),
                signal: controller.signal
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            // 创建AI消息占位符
            const aiMsg = {
                role: 'assistant',
                content: '',
                type: 'text'
            };
            addMessage(aiMsg, sessionId);
            const msgIndex = session.messages.length - 1;
            
            // 读取流式响应
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                
                for (const line of lines) {
                    if (!line.trim() || !line.startsWith('data: ')) continue;
                    
                    const data = line.slice(6);
                    if (data === '[DONE]') {
                        setSessionStatus(sessionId, SESSION_STATUS.COMPLETED);
                        break;
                    }
                    
                    try {
                        const parsed = JSON.parse(data);
                        
                        // 处理不同类型的事件
                        if (parsed.type === 'content') {
                            // 直接更新会话的消息内容
                            session.messages[msgIndex].content = parsed.content;
                            if (onStream) {
                                onStream(parsed.content, sessionId);
                            }
                        } else if (parsed.type === 'node') {
                            addTimelineStep({
                                icon: parsed.icon || '🔄',
                                title: parsed.name || '处理中',
                                content: parsed.thought || parsed.observation || '',
                                status: parsed.status || 'running',
                                type: parsed.node_type || 'observations'
                            });
                        }
                    } catch (e) {
                        console.error('解析SSE数据失败:', e, data);
                    }
                }
            }
            
            // 更新timeline步骤为完成状态
            if (useKnowledgeBase.value && timelineSteps.value.length > 1) {
                timelineSteps.value[1].status = 'completed';
                timelineSteps.value[1].content = '成功检索到相关文档';
            }
            const aiStepIndex = useKnowledgeBase.value ? 2 : 1;
            if (timelineSteps.value.length > aiStepIndex) {
                timelineSteps.value[aiStepIndex].status = 'completed';
                timelineSteps.value[aiStepIndex].content = '成功生成回复';
            }
            
            // 添加完成步骤
            addTimelineStep({
                icon: '✅',
                title: '返回结果',
                content: '回复已生成并显示',
                status: 'completed',
                type: 'observations'
            });
            
            // 如果当前会话不是活动会话,显示后台完成通知
            if (sessionId !== currentSessionId.value) {
                // 触发通知事件
                window.dispatchEvent(new CustomEvent('background-generation-complete', {
                    detail: {
                        sessionId,
                        question: content,
                        answer: session.messages[msgIndex].content
                    }
                }));
            }
            
            return session.messages[msgIndex].content;
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('请求已取消');
                setSessionStatus(sessionId, SESSION_STATUS.IDLE);
                return;
            }
            
            console.error('发送消息失败:', error);
            
            // 显示详细错误信息
            let errorMsg = '消息发送失败，请重试';
            if (error.response) {
                errorMsg = `错误 ${error.response.status}: ${error.response.data?.detail || '未知错误'}`;
            } else if (error.message) {
                errorMsg = `错误: ${error.message}`;
            }
            
            addMessage({
                role: 'system',
                content: errorMsg,
                type: 'error'
            }, sessionId);
            
            setSessionStatus(sessionId, SESSION_STATUS.IDLE);
            throw error;
        } finally {
            abortControllers.value.delete(sessionId);
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

    // 编辑并重新发送消息
    async function editAndResendMessage(messageId, newContent, onStream) {
        const sessionId = currentSessionId.value;
        if (!sessionId) return;

        const session = sessions.value.get(sessionId);
        if (!session) return;

        // 找到要编辑的消息
        const messageIndex = session.messages.findIndex(m => m.id === messageId);
        if (messageIndex === -1) return;

        const message = session.messages[messageIndex];
        if (message.role !== 'user') return;

        // 停止当前生成（如果有）
        if (getSessionStatus(sessionId) === SESSION_STATUS.GENERATING) {
            stopGeneration(sessionId);
        }

        // 更新消息内容
        message.content = newContent;
        message.timestamp = new Date().toISOString();

        // 删除该消息之后的所有AI回复
        const nextIndex = messageIndex + 1;
        if (nextIndex < session.messages.length && session.messages[nextIndex].role === 'assistant') {
            session.messages.splice(nextIndex, 1);
        }

        // 重新发送消息（使用更新后的历史）
        setSessionStatus(sessionId, SESSION_STATUS.GENERATING);
        isLoading.value = true;
        clearTimelineSteps();

        // 添加初始timeline步骤
        addTimelineStep({
            icon: '✏️',
            title: '编辑消息',
            content: '正在重新处理用户输入...',
            status: 'completed',
            type: 'thoughts'
        });

        // 构建请求消息（只包含到当前编辑消息为止的历史）
        const requestMessages = session.messages
            .slice(0, messageIndex + 1)
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
            
            // 创建AbortController
            const controller = new AbortController();
            abortControllers.value.set(sessionId, controller);
            
            // 选择API端点
            const endpoint = isMultiAgentMode.value ? '/chat/agent/stream' : '/chat/stream';
            
            const response = await fetch(`${apiBase}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    messages: requestMessages,
                    use_knowledge_base: useKnowledgeBase.value,
                    session_id: sessionId,
                    use_tools: isMultiAgentMode.value,
                    model: 'deepseek-chat',
                    temperature: 0.7
                }),
                signal: controller.signal
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            // 创建新的AI消息
            const aiMsg = {
                role: 'assistant',
                content: '',
                type: 'text'
            };
            addMessage(aiMsg, sessionId);
            const msgIndex = session.messages.length - 1;
            
            // 读取流式响应
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                
                for (const line of lines) {
                    if (!line.trim() || !line.startsWith('data: ')) continue;
                    
                    const data = line.slice(6);
                    if (data === '[DONE]') {
                        setSessionStatus(sessionId, SESSION_STATUS.COMPLETED);
                        break;
                    }
                    
                    try {
                        const parsed = JSON.parse(data);
                        
                        if (parsed.type === 'content') {
                            session.messages[msgIndex].content = parsed.content;
                            if (onStream) {
                                onStream(parsed.content, sessionId);
                            }
                        } else if (parsed.type === 'node') {
                            addTimelineStep({
                                icon: parsed.icon || '🔄',
                                title: parsed.name || '处理中',
                                content: parsed.thought || parsed.observation || '',
                                status: parsed.status || 'running',
                                type: parsed.node_type || 'observations'
                            });
                        }
                    } catch (e) {
                        console.error('解析SSE数据失败:', e, data);
                    }
                }
            }
            
            // 更新timeline步骤为完成状态
            if (useKnowledgeBase.value && timelineSteps.value.length > 1) {
                timelineSteps.value[1].status = 'completed';
                timelineSteps.value[1].content = '成功检索到相关文档';
            }
            const aiStepIndex = useKnowledgeBase.value ? 2 : 1;
            if (timelineSteps.value.length > aiStepIndex) {
                timelineSteps.value[aiStepIndex].status = 'completed';
                timelineSteps.value[aiStepIndex].content = '成功生成回复';
            }
            
            // 添加完成步骤
            addTimelineStep({
                icon: '✅',
                title: '返回结果',
                content: '回复已生成并显示',
                status: 'completed',
                type: 'observations'
            });
            
            return session.messages[msgIndex].content;
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('请求已取消');
                setSessionStatus(sessionId, SESSION_STATUS.IDLE);
                return;
            }
            
            console.error('重新发送消息失败:', error);
            
            let errorMsg = '消息重新发送失败，请重试';
            if (error.response) {
                errorMsg = `错误 ${error.response.status}: ${error.response.data?.detail || '未知错误'}`;
            } else if (error.message) {
                errorMsg = `错误: ${error.message}`;
            }
            
            addMessage({
                role: 'system',
                content: errorMsg,
                type: 'error'
            }, sessionId);
            
            setSessionStatus(sessionId, SESSION_STATUS.IDLE);
            throw error;
        } finally {
            abortControllers.value.delete(sessionId);
            isLoading.value = false;
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
        sessions,
        SESSION_STATUS,
        addMessage,
        clearMessages,
        sendMessage,
        setSessionId,
        toggleMultiAgentMode,
        setMultiAgentMode,
        setUseKnowledgeBase,
        addTimelineStep,
        clearTimelineSteps,
        updateLastTimelineStep,
        ensureSession,
        setSessionStatus,
        getSessionStatus,
        stopGeneration,
        editAndResendMessage
    };
});
