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
    const useTools = ref(true);  // 🔧 启用工具（上网搜索等），默认开启
    const timelineSteps = ref([]);

    // 🔐 用户ID（从localStorage获取，用于隔离不同账号的记忆）
    const currentUserId = ref(localStorage.getItem('user_id') || null);
    if (!currentUserId.value) {
        console.warn('⚠️ 未找到用户ID，请先登录');
    } else {
        console.log('🔐 当前用户ID:', currentUserId.value);
    }

    // 🔒 记忆模式
    const isGlobalMemory = ref(false); // 全局记忆模式（跨对话记忆）
    const isDeepThinkMode = ref(false); // 深度思考模式（显示思考过程）
    
    // 全局记忆session ID（每个用户独立，包含user_id以隔离）
    const globalMemorySessionId = ref(
        currentUserId.value 
            ? `global_memory_${currentUserId.value}_${Date.now()}`
            : `global_memory_${Date.now()}`
    );

    // 多会话管理
    const sessions = ref(new Map());
    const abortControllers = ref(new Map());
    
    // 思考步骤缓存（用于持久化）
    const thinkingStepsCache = ref(new Map());

    // Computed - 当前会话的消息列表
    const messages = computed(() => {
        if (!currentSessionId.value) return [];
        const session = sessions.value.get(currentSessionId.value);
        // 返回数组副本以确保Vue能追踪到变化
        return session ? [...session.messages] : [];
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
        
        console.log('🛑 开始停止生成 - Session:', sid);
        console.log('🛑 当前abortControllers:', Array.from(abortControllers.value.keys()));
        
        // 停止请求
        if (abortControllers.value.has(sid)) {
            console.log('🛑 找到AbortController，执行abort');
            const controller = abortControllers.value.get(sid);
            controller.abort();
            abortControllers.value.delete(sid);
        } else {
            console.log('⚠️ 未找到AbortController');
        }
        
        // 无论是否有abortController，都设置状态为IDLE
        // 这样可以确保loading状态被清除
        const session = sessions.value.get(sid);
        if (session) {
            console.log('🛑 设置会话状态为IDLE，当前状态:', session.status);
        }
        
        setSessionStatus(sid, SESSION_STATUS.IDLE);
        isLoading.value = false;
        
        // 强制触发响应式更新
        sessions.value = new Map(sessions.value);
        
        console.log('✅ 已停止生成 - Session:', sid, '新状态:', SESSION_STATUS.IDLE);
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
            const endpoint = isMultiAgentMode.value ? '/chat/multi-agent/stream' : '/chat/agent/stream';
            
            // 🔒 根据记忆模式决定使用哪个session_id
            const apiSessionId = isGlobalMemory.value ? globalMemorySessionId.value : sessionId;
            
            const response = await fetch(`${apiBase}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    messages: requestMessages,
                    use_knowledge_base: useKnowledgeBase.value,
                    session_id: apiSessionId,  // 使用根据模式选择的session_id
                    user_id: currentUserId.value,  // 🔐 必须传递用户ID，隔离不同账号的记忆
                    use_tools: useTools.value,  // 🔧 独立的工具开关，不依赖多智能体模式
                    model: 'deepseek-chat',
                    // 🔒 记忆控制：显式告知后端是否共享记忆
                    memory_mode: isGlobalMemory.value ? 'global' : 'session',
                    share_memory: isGlobalMemory.value,  // 布尔值，后端优先使用此字段
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
                if (done) {
                    console.log('✅ 流式传输完成 - Session:', sessionId);
                    console.log('📊 最终消息内容长度:', session.messages[msgIndex]?.content?.length || 0);
                    break;
                }
                
                buffer += decoder.decode(value, { stream: true });
                // 按照SSE规范，用双换行符分割事件块
                const events = buffer.split('\n\n');
                buffer = events.pop() || '';
                
                for (const eventText of events) {
                    if (!eventText.trim()) continue;
                    
                    const lines = eventText.split('\n');
                    let eventType = '';
                    let eventData = null;
                    
                    // 解析事件块中的event和data行
                    for (const line of lines) {
                        if (line.startsWith('event: ')) {
                            eventType = line.slice(7).trim();
                        } else if (line.startsWith('data: ')) {
                            const data = line.slice(6);
                            if (data === '[DONE]') {
                                console.log('📨 收到[DONE]标记 - Session:', sessionId);
                                break;
                            }
                            try {
                                eventData = JSON.parse(data);
                            } catch (e) {
                                console.error('JSON解析失败:', e, data);
                            }
                        }
                    }
                    
                    // 只有当有数据时才处理（eventType可能为空，从data.type获取）
                    if (eventData) {
                        // 优先使用SSE event字段，否则使用JSON中的type字段
                        const finalEventType = eventType || eventData.type;
                        
                        console.log('🔍 处理事件 - eventType:', finalEventType, 'hasContent:', !!eventData.content);
                        
                        // 处理内容事件
                        if (finalEventType === 'assistant_final' || finalEventType === 'content' || finalEventType === 'message' || finalEventType === 'assistant_draft') {
                            const content = eventData.content || eventData.message || '';
                            if (content) {
                                // assistant_final是完整内容，直接替换
                                const updatedMessage = { ...session.messages[msgIndex], content };
                                session.messages.splice(msgIndex, 1, updatedMessage);
                                
                                // 强制触发响应式更新
                                sessions.value = new Map(sessions.value);
                                
                                console.log('📝 ✅ 已更新消息，事件:', finalEventType, '长度:', content.length, 'SessionId:', sessionId);
                                if (onStream) {
                                    onStream(content, sessionId);
                                }
                            }
                        } else if (finalEventType === 'agent_thought') {
                            // 🔥 详细思考内容
                            const nodeName = eventData.node || 'agent';
                            const thoughtText = eventData.thought || '';
                            
                            if (thoughtText) {
                                // 添加到思考步骤
                                if (isDeepThinkMode.value) {
                                    addThinkingStep(sessionId, msgIndex, {
                                        type: nodeName,
                                        title: getNodeTitle(nodeName),
                                        content: thoughtText,
                                        status: 'processing'
                                    });
                                }
                                
                                // 添加到timeline
                                addTimelineStep({
                                    icon: '💭',
                                    title: getNodeTitle(nodeName),
                                    content: thoughtText,
                                    status: 'running',
                                    type: 'thoughts'
                                });
                            }
                        } else if (finalEventType === 'agent_observation') {
                            // 🔥 观察结果
                            const nodeName = eventData.node || 'agent';
                            const observationText = eventData.observation || '';
                            
                            if (observationText) {
                                if (isDeepThinkMode.value) {
                                    addThinkingStep(sessionId, msgIndex, {
                                        type: 'observation',
                                        title: '观察结果',
                                        content: observationText,
                                        status: 'completed'
                                    });
                                }
                                
                                addTimelineStep({
                                    icon: '👁️',
                                    title: '观察结果',
                                    content: observationText,
                                    status: 'running',
                                    type: 'observations'
                                });
                            }
                        } else if (finalEventType === 'agent_node') {
                            // 节点状态
                            const nodeName = eventData.node || 'step';
                            
                            if (isDeepThinkMode.value && eventData.status !== 'completed') {
                                addThinkingStep(sessionId, msgIndex, {
                                    type: nodeName,
                                    title: getNodeTitle(nodeName),
                                    content: '开始执行...',
                                    status: 'processing'
                                });
                            }
                            
                            addTimelineStep({
                                icon: '🔄',
                                title: getNodeTitle(nodeName),
                                content: eventData.status || '执行中',
                                status: eventData.status === 'completed' ? 'completed' : 'running',
                                type: 'tools'
                            });
                        } else if (finalEventType === 'agent_execution' || finalEventType === 'orchestrator_plan') {
                            // 其他timeline事件
                            addTimelineStep({
                                icon: eventData.icon || '🔄',
                                title: eventData.name || eventData.agent || eventData.node || '处理中',
                                content: eventData.thought || eventData.observation || eventData.plan || '',
                                status: eventData.status || 'running',
                                type: 'observations'
                            });
                        }
                    }
                }
            }
            
            // 流式传输完成，强制最后一次响应式更新确保界面刷新
            console.log('🎨 流式传输完成，强制刷新界面 - Session:', sessionId);
            console.log('📊 消息最终状态 - 消息数:', session.messages.length, '最后一条长度:', session.messages[msgIndex]?.content?.length || 0);
            
            // 💾 保存思考步骤（如果有）
            if (isDeepThinkMode.value && session.messages[msgIndex]?.thinkingSteps) {
                const messageId = session.messages[msgIndex].id;
                saveThinkingSteps(sessionId, messageId, session.messages[msgIndex].thinkingSteps);
            }
            
            sessions.value = new Map(sessions.value);
            
            // 设置状态为已完成
            console.log('🎨 设置会话状态为已完成 - Session:', sessionId);
            setSessionStatus(sessionId, SESSION_STATUS.COMPLETED);
            
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
                console.log('⏹️ 请求已取消 - Session:', sessionId);
                
                // 在当前消息中添加停止标记
                if (session.messages[msgIndex]) {
                    const currentContent = session.messages[msgIndex].content;
                    if (!currentContent || currentContent.trim() === '') {
                        // 如果没有内容，显示停止提示
                        const stoppedMessage = { ...session.messages[msgIndex], content: '⏹️ 已停止生成' };
                        session.messages.splice(msgIndex, 1, stoppedMessage);
                        sessions.value = new Map(sessions.value);
            } else {
                        // 如果已有部分内容，在末尾添加停止标记
                        const stoppedMessage = { ...session.messages[msgIndex], content: currentContent + '\n\n⏹️ *已停止生成*' };
                        session.messages.splice(msgIndex, 1, stoppedMessage);
                        sessions.value = new Map(sessions.value);
            }
                }
                
                setSessionStatus(sessionId, SESSION_STATUS.IDLE);
                isLoading.value = false;
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
    
    function setUseTools(value) {
        useTools.value = value;
        console.log('🔧 工具调用:', value ? '开启' : '关闭');
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
            const endpoint = isMultiAgentMode.value ? '/chat/multi-agent/stream' : '/chat/agent/stream';
            
            // 🔒 根据记忆模式决定使用哪个session_id
            const apiSessionId = isGlobalMemory.value ? globalMemorySessionId.value : sessionId;
            
            const response = await fetch(`${apiBase}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    messages: requestMessages,
                    use_knowledge_base: useKnowledgeBase.value,
                    session_id: apiSessionId,  // 使用根据模式选择的session_id
                    user_id: currentUserId.value,  // 🔐 传递用户ID
                    use_tools: useTools.value,  // 🔧 独立的工具开关
                    model: 'deepseek-chat',
                    memory_mode: isGlobalMemory.value ? 'global' : 'session',
                    share_memory: isGlobalMemory.value,
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
                if (done) {
                    console.log('✅ 流式传输完成（编辑模式） - Session:', sessionId);
                    console.log('📊 最终消息内容长度:', session.messages[msgIndex]?.content?.length || 0);
                    break;
                }
                
                buffer += decoder.decode(value, { stream: true });
                // 按照SSE规范，用双换行符分割事件块
                const events = buffer.split('\n\n');
                buffer = events.pop() || '';
                
                for (const eventText of events) {
                    if (!eventText.trim()) continue;
                    
                    const lines = eventText.split('\n');
                    let eventType = '';
                    let eventData = null;
                    
                    // 解析事件块中的event和data行
                    for (const line of lines) {
                        if (line.startsWith('event: ')) {
                            eventType = line.slice(7).trim();
                        } else if (line.startsWith('data: ')) {
                            const data = line.slice(6);
                            if (data === '[DONE]') {
                                console.log('📨 收到[DONE]标记（编辑模式） - Session:', sessionId);
                                break;
                            }
                            try {
                                eventData = JSON.parse(data);
                            } catch (e) {
                                console.error('JSON解析失败:', e, data);
                            }
                        }
                    }
                    
                    // 只有当有数据时才处理
                    if (eventData) {
                        const finalEventType = eventType || eventData.type;
                        
                        console.log('🔍 处理事件（编辑模式） - eventType:', finalEventType, 'hasContent:', !!eventData.content);
                        
                        // 处理内容事件
                        if (finalEventType === 'assistant_final' || finalEventType === 'content' || finalEventType === 'message' || finalEventType === 'assistant_draft') {
                            const content = eventData.content || eventData.message || '';
                            if (content) {
                                const updatedMessage = { ...session.messages[msgIndex], content };
                                session.messages.splice(msgIndex, 1, updatedMessage);
                                
                                // 强制触发响应式更新
                                sessions.value = new Map(sessions.value);
                                
                                console.log('📝 ✅ 已更新消息（编辑模式），事件:', finalEventType, '长度:', content.length, 'SessionId:', sessionId);
                                if (onStream) {
                                    onStream(content, sessionId);
                                }
                            }
                        } else if (finalEventType === 'agent_thought') {
                            // 🔥 详细思考内容
                            const nodeName = eventData.node || 'agent';
                            const thoughtText = eventData.thought || '';
                            
                            if (thoughtText) {
                                if (isDeepThinkMode.value) {
                                    addThinkingStep(sessionId, msgIndex, {
                                        type: nodeName,
                                        title: getNodeTitle(nodeName),
                                        content: thoughtText,
                                        status: 'processing'
                                    });
                                }
                                
                                addTimelineStep({
                                    icon: '💭',
                                    title: getNodeTitle(nodeName),
                                    content: thoughtText,
                                    status: 'running',
                                    type: 'thoughts'
                                });
                            }
                        } else if (finalEventType === 'agent_observation') {
                            // 🔥 观察结果
                            const nodeName = eventData.node || 'agent';
                            const observationText = eventData.observation || '';
                            
                            if (observationText) {
                                if (isDeepThinkMode.value) {
                                    addThinkingStep(sessionId, msgIndex, {
                                        type: 'observation',
                                        title: '观察结果',
                                        content: observationText,
                                        status: 'completed'
                                    });
                                }
                                
                                addTimelineStep({
                                    icon: '👁️',
                                    title: '观察结果',
                                    content: observationText,
                                    status: 'running',
                                    type: 'observations'
                                });
                            }
                        } else if (finalEventType === 'agent_node') {
                            // 节点状态
                            const nodeName = eventData.node || 'step';
                            
                            if (isDeepThinkMode.value && eventData.status !== 'completed') {
                                addThinkingStep(sessionId, msgIndex, {
                                    type: nodeName,
                                    title: getNodeTitle(nodeName),
                                    content: '开始执行...',
                                    status: 'processing'
                                });
                            }
                            
                            addTimelineStep({
                                icon: '🔄',
                                title: getNodeTitle(nodeName),
                                content: eventData.status || '执行中',
                                status: eventData.status === 'completed' ? 'completed' : 'running',
                                type: 'tools'
                            });
                        } else if (finalEventType === 'agent_execution' || finalEventType === 'orchestrator_plan') {
                            // 其他事件
                            addTimelineStep({
                                icon: eventData.icon || '🔄',
                                title: eventData.name || eventData.agent || eventData.node || '处理中',
                                content: eventData.thought || eventData.observation || eventData.plan || '',
                                status: eventData.status || 'running',
                                type: 'observations'
                            });
                        }
                    }
                }
            }
            
            // 流式传输完成，强制最后一次响应式更新确保界面刷新
            console.log('🎨 流式传输完成，强制刷新界面（编辑模式） - Session:', sessionId);
            console.log('📊 消息最终状态 - 消息数:', session.messages.length, '最后一条长度:', session.messages[msgIndex]?.content?.length || 0);
            
            // 💾 保存思考步骤（如果有）
            if (isDeepThinkMode.value && session.messages[msgIndex]?.thinkingSteps) {
                const messageId = session.messages[msgIndex].id;
                saveThinkingSteps(sessionId, messageId, session.messages[msgIndex].thinkingSteps);
            }
            
            sessions.value = new Map(sessions.value);
            
            // 设置状态为已完成
            console.log('🎨 设置会话状态为已完成（编辑模式） - Session:', sessionId);
            setSessionStatus(sessionId, SESSION_STATUS.COMPLETED);
            
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
                console.log('⏹️ 请求已取消（编辑模式） - Session:', sessionId);
                
                // 在当前消息中添加停止标记
                if (session.messages[msgIndex]) {
                    const currentContent = session.messages[msgIndex].content;
                    if (!currentContent || currentContent.trim() === '') {
                        // 如果没有内容，显示停止提示
                        const stoppedMessage = { ...session.messages[msgIndex], content: '⏹️ 已停止生成' };
                        session.messages.splice(msgIndex, 1, stoppedMessage);
                        sessions.value = new Map(sessions.value);
                    } else {
                        // 如果已有部分内容，在末尾添加停止标记
                        const stoppedMessage = { ...session.messages[msgIndex], content: currentContent + '\n\n⏹️ *已停止生成*' };
                        session.messages.splice(msgIndex, 1, stoppedMessage);
                        sessions.value = new Map(sessions.value);
                    }
                }
                
                setSessionStatus(sessionId, SESSION_STATUS.IDLE);
                isLoading.value = false;
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
    
    // ========== 深度思考辅助函数 ==========
    
    /**
     * 获取节点标题（中文）
     */
    function getNodeTitle(nodeName) {
        const titleMap = {
            'planner': '规划分析',
            'executor': '执行任务',
            'reviewer': '检查结果',
            'aggregator': '整合答案',
            'tools': '工具调用',
            'tool_call': '使用工具',
            'agent': 'AI思考',
            'observation': '观察结果',
            'understand': '理解问题',
            'plan': '制定计划',
            'analyze': '深入分析',
            'synthesis': '综合结论',
            'verify': '验证结果',
            'search': '搜索信息',
            'calculate': '计算处理',
            'reasoning': '逻辑推理',
            'conclusion': '得出结论'
        };
        return titleMap[nodeName] || nodeName;
    }
    
    /**
     * 添加思考步骤（深度思考模式）
     */
    function addThinkingStep(sessionId, messageIndex, stepData) {
        if (!isDeepThinkMode.value) return;
        
        const session = sessions.value.get(sessionId);
        if (!session || !session.messages[messageIndex]) return;
        
        const message = session.messages[messageIndex];
        
        // 初始化思考步骤数组
        if (!message.thinkingSteps) {
            message.thinkingSteps = [];
        }
        
        // 查找是否已存在相同类型和标题的步骤
        const existingIndex = message.thinkingSteps.findIndex(
            step => step.type === stepData.type && step.title === stepData.title
        );
        
        if (existingIndex >= 0) {
            // 更新现有步骤
            message.thinkingSteps[existingIndex] = {
                ...message.thinkingSteps[existingIndex],
                ...stepData,
                timestamp: Date.now()
            };
        } else {
            // 添加新步骤
            message.thinkingSteps.push({
                ...stepData,
                timestamp: Date.now()
            });
        }
        
        // 强制触发响应式更新
        sessions.value = new Map(sessions.value);
        
        console.log('💭 添加思考步骤:', stepData.title, '状态:', stepData.status);
    }
    
    /**
     * 保存思考步骤到localStorage
     */
    function saveThinkingSteps(sessionId, messageId, steps) {
        try {
            const key = `thinking_${sessionId}_${messageId}`;
            localStorage.setItem(key, JSON.stringify(steps));
            
            // 也保存到内存
            if (!thinkingStepsCache.value.has(sessionId)) {
                thinkingStepsCache.value.set(sessionId, new Map());
            }
            thinkingStepsCache.value.get(sessionId).set(messageId, steps);
            
            console.log('💾 保存思考步骤:', steps.length, '个');
        } catch (e) {
            console.warn('保存思考步骤失败:', e);
        }
    }
    
    /**
     * 加载思考步骤
     */
    function loadThinkingSteps(sessionId, messageId) {
        // 先从内存查找
        if (thinkingStepsCache.value.has(sessionId)) {
            const sessionCache = thinkingStepsCache.value.get(sessionId);
            if (sessionCache.has(messageId)) {
                return sessionCache.get(sessionId).get(messageId);
            }
        }
        
        // 从localStorage加载
        try {
            const key = `thinking_${sessionId}_${messageId}`;
            const saved = localStorage.getItem(key);
            if (saved) {
                const parsed = JSON.parse(saved);
                console.log('📥 加载思考步骤:', parsed.length, '个');
                return parsed;
            }
        } catch (e) {
            console.warn('加载思考步骤失败:', e);
        }
        
        return null;
    }
    
    /**
     * 切换全局记忆模式
     */
    function toggleGlobalMemory(enabled) {
        isGlobalMemory.value = enabled;
        console.log('全局记忆模式:', enabled ? '开启🌐' : '关闭🔒');
        console.log(enabled ? '所有对话共享记忆' : '每个对话独立记忆');
    }
    
    /**
     * 切换深度思考模式
     */
    function toggleDeepThink(enabled) {
        isDeepThinkMode.value = enabled;
        console.log('深度思考模式:', enabled ? '开启💭' : '关闭');
    }
    
    /**
     * 🔄 重新生成AI答案
     */
    async function regenerateAnswer(messageId, onStream) {
        const sessionId = currentSessionId.value;
        if (!sessionId) {
            console.error('没有当前会话');
            return;
        }
        
        const session = sessions.value.get(sessionId);
        if (!session) {
            console.error('找不到会话');
            return;
        }
        
        // 找到要重新生成的消息
        const msgIndex = session.messages.findIndex(m => m.id === messageId);
        if (msgIndex === -1) {
            console.error('找不到消息:', messageId);
            return;
        }
        
        const message = session.messages[msgIndex];
        if (message.role !== 'assistant') {
            console.error('只能重新生成AI消息');
            return;
        }
        
        // 找到对应的用户问题（前一个用户消息）
        let userMessage = null;
        for (let i = msgIndex - 1; i >= 0; i--) {
            if (session.messages[i].role === 'user') {
                userMessage = session.messages[i];
                break;
            }
        }
        
        if (!userMessage) {
            console.error('找不到对应的用户问题');
            return;
        }
        
        console.log('🔄 重新生成答案，问题:', userMessage.content);
        
        // 初始化版本数据（如果没有）
        if (!message.versions) {
            message.versions = [message.content]; // 保存当前内容作为第一个版本
            message.currentVersion = 0;
        }
        
        // 清空当前内容，显示loading
        message.content = '';
        setSessionStatus(sessionId, SESSION_STATUS.GENERATING);
        isLoading.value = true;
        
        // 清空timeline
        clearTimelineSteps();
        
        // 添加重新生成步骤
        addTimelineStep({
            icon: '🔄',
            title: '重新生成',
            content: '正在重新生成回复...',
            status: 'running',
            type: 'thoughts'
        });
        
        try {
            // 创建AbortController
            const controller = new AbortController();
            abortControllers.value.set(sessionId, controller);
            
            // 选择API端点
            const endpoint = isMultiAgentMode.value ? '/chat/multi-agent/stream' : '/chat/agent/stream';
            
            // 🔒 根据记忆模式决定使用哪个session_id
            const apiSessionId = isGlobalMemory.value ? globalMemorySessionId.value : sessionId;
            
            // 构建请求消息（只包含到用户问题为止的历史）
            const requestMessages = session.messages
                .slice(0, msgIndex)  // 只包含到AI消息之前
                .filter(m => m.role === 'user' || m.role === 'assistant')
                .map(m => ({
                    role: m.role,
                    content: m.content
                }));
            
            const response = await fetch(`${apiBase}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    messages: requestMessages,
                    use_knowledge_base: useKnowledgeBase.value,
                    session_id: apiSessionId,
                    user_id: currentUserId.value,
                    use_tools: useTools.value,
                    model: 'deepseek-chat',
                    memory_mode: isGlobalMemory.value ? 'global' : 'session',
                    share_memory: isGlobalMemory.value,
                    temperature: 0.7
                }),
                signal: controller.signal
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            // 读取流式响应
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    console.log('✅ 重新生成完成');
                    break;
                }
                
                buffer += decoder.decode(value, { stream: true });
                const events = buffer.split('\n\n');
                buffer = events.pop() || '';
                
                for (const eventText of events) {
                    if (!eventText.trim()) continue;
                    
                    const lines = eventText.split('\n');
                    let eventType = '';
                    let eventData = null;
                    
                    for (const line of lines) {
                        if (line.startsWith('event: ')) {
                            eventType = line.slice(7).trim();
                        } else if (line.startsWith('data: ')) {
                            const data = line.slice(6);
                            if (data === '[DONE]') break;
                            try {
                                eventData = JSON.parse(data);
                            } catch (e) {
                                console.error('JSON解析失败:', e, data);
                            }
                        }
                    }
                    
                    if (eventData) {
                        const finalEventType = eventType || eventData.type;
                        
                        // 处理内容事件
                        if (finalEventType === 'assistant_final' || finalEventType === 'content' || finalEventType === 'message' || finalEventType === 'assistant_draft') {
                            const content = eventData.content || eventData.message || '';
                            if (content) {
                                message.content = content;
                                sessions.value = new Map(sessions.value);
                                
                                if (onStream) {
                                    onStream(content, sessionId);
                                }
                            }
                        } else if (finalEventType === 'agent_thought') {
                            const thoughtText = eventData.thought || '';
                            if (thoughtText && isDeepThinkMode.value) {
                                addThinkingStep(sessionId, msgIndex, {
                                    type: eventData.node || 'agent',
                                    title: getNodeTitle(eventData.node || 'agent'),
                                    content: thoughtText,
                                    status: 'processing'
                                });
                            }
                            
                            addTimelineStep({
                                icon: '💭',
                                title: getNodeTitle(eventData.node || 'agent'),
                                content: thoughtText,
                                status: 'running',
                                type: 'thoughts'
                            });
                        } else if (finalEventType === 'agent_observation') {
                            const observationText = eventData.observation || '';
                            if (observationText && isDeepThinkMode.value) {
                                addThinkingStep(sessionId, msgIndex, {
                                    type: 'observation',
                                    title: '观察结果',
                                    content: observationText,
                                    status: 'completed'
                                });
                            }
                        }
                    }
                }
            }
            
            // 保存为新版本
            message.versions.push(message.content);
            message.currentVersion = message.versions.length - 1;
            
            // 💾 保存思考步骤（如果有）
            if (isDeepThinkMode.value && message.thinkingSteps) {
                saveThinkingSteps(sessionId, messageId, message.thinkingSteps);
            }
            
            sessions.value = new Map(sessions.value);
            setSessionStatus(sessionId, SESSION_STATUS.COMPLETED);
            
            console.log('✅ 重新生成完成，新版本:', message.currentVersion + 1, '/', message.versions.length);
            
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('重新生成被取消');
                message.content = '生成已取消';
            } else {
                console.error('重新生成失败:', error);
                message.content = `❌ 重新生成失败: ${error.message}`;
            }
            
            sessions.value = new Map(sessions.value);
            setSessionStatus(sessionId, SESSION_STATUS.IDLE);
            throw error;
        } finally {
            abortControllers.value.delete(sessionId);
            isLoading.value = false;
        }
    }

    return {
        // 状态
        messages,
        currentSessionId,
        isLoading,
        hasMessages,
        isMultiAgentMode,
        useKnowledgeBase,
        useTools,                 // 🔧 新增：工具开关
        timelineSteps,
        sessions,
        SESSION_STATUS,
        // 🔐 新增：用户和记忆模式
        currentUserId,
        isGlobalMemory,
        isDeepThinkMode,
        globalMemorySessionId,
        thinkingStepsCache,
        
        // 消息管理
        addMessage,
        clearMessages,
        sendMessage,
        editAndResendMessage,
        regenerateAnswer,         // 🔄 新增：重新生成答案
        
        // 会话管理
        setSessionId,
        ensureSession,
        setSessionStatus,
        getSessionStatus,
        stopGeneration,
        
        // 模式切换
        toggleMultiAgentMode,
        setMultiAgentMode,
        setUseKnowledgeBase,
        setUseTools,              // 🔧 新增：设置工具开关
        toggleGlobalMemory,       // 🔒 新增
        toggleDeepThink,          // 💭 新增
        
        // 深度思考
        addThinkingStep,          // 💭 新增
        saveThinkingSteps,        // 💾 新增
        loadThinkingSteps,        // 📥 新增
        getNodeTitle,             // 🔄 新增
        
        // Timeline
        addTimelineStep,
        clearTimelineSteps,
        updateLastTimelineStep
    };
});
