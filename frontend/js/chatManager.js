/* ===== 聊天管理器 - 处理消息发送、接收和渲染 ===== */

/**
 * 聊天管理器类 - 支持多会话并发
 */
class ChatManager {
    constructor() {
        this.API_BASE = 'http://127.0.0.1:8000';
        this.currentSessionId = null;
        this.isMultiAgentMode = false;
        
        // 多会话管理
        this.sessions = new Map(); // sessionId -> { status, abortController, messages, lastQuestion, containerDiv }
        
        // 会话状态
        this.SESSION_STATUS = {
            IDLE: 'idle',
            GENERATING: 'generating',
            COMPLETED: 'completed'
        };
        
        // 主消息容器
        this.mainContainer = null;
    }

    /**
     * 初始化聊天管理器
     */
    init() {
        this.mainContainer = document.getElementById('messagesContainer');
        if (!this.mainContainer) {
            console.error('❌ 找不到消息容器');
            return;
        }
        
        this.setupEventListeners();
        this.loadSessionFromUrl();
        console.log('✅ 聊天管理器初始化成功');
    }

    /**
     * 设置事件监听器
     */
    setupEventListeners() {
        const sendBtn = document.getElementById('sendBtn');
        const stopBtn = document.getElementById('stopBtn');
        const messageInput = document.getElementById('messageInput');
        
        if (sendBtn) {
            sendBtn.addEventListener('click', () => this.sendMessage());
        }
        
        if (stopBtn) {
            stopBtn.addEventListener('click', () => this.stopCurrentRequest());
        }
        
        if (messageInput) {
            // Enter发送，Shift+Enter换行
            messageInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
            
            // 自动调整高度
            messageInput.addEventListener('input', function() {
                this.style.height = 'auto';
                this.style.height = Math.min(this.scrollHeight, 200) + 'px';
            });
        }
    }

    /**
     * 从URL加载会话
     */
    loadSessionFromUrl() {
        const urlParams = new URLSearchParams(window.location.search);
        const sessionId = urlParams.get('session_id');
        
        if (sessionId) {
            this.currentSessionId = sessionId;
            this.ensureSession(sessionId);
            // 显示当前会话容器
            this.showCurrentSession();
            this.loadHistoryMessages(sessionId);
        } else {
            this.currentSessionId = this.generateSessionId();
            this.ensureSession(this.currentSessionId);
            // 显示当前会话容器
            this.showCurrentSession();
        }
    }
    
    /**
     * 显示当前会话的容器
     */
    showCurrentSession() {
        if (!this.currentSessionId) return;
        
        const session = this.sessions.get(this.currentSessionId);
        if (session && session.containerDiv) {
            session.containerDiv.style.display = 'block';
            console.log('✅ 显示会话容器:', this.currentSessionId);
            
            // 隐藏空状态
            this.hideEmptyState();
        }
    }
    
    /**
     * 隐藏空状态
     */
    hideEmptyState() {
        const emptyState = document.querySelector('.empty-state');
        if (emptyState) {
            emptyState.style.display = 'none';
        }
    }
    
    /**
     * 确保会话存在
     */
    ensureSession(sessionId) {
        if (!this.sessions.has(sessionId)) {
            // 创建会话专属的消息容器
            const containerDiv = document.createElement('div');
            containerDiv.className = 'session-messages';
            containerDiv.id = `session-${sessionId}`;
            containerDiv.style.display = 'none'; // 默认隐藏
            
            // 添加到主容器
            if (this.mainContainer) {
                this.mainContainer.appendChild(containerDiv);
            }
            
            this.sessions.set(sessionId, {
                status: this.SESSION_STATUS.IDLE,
                abortController: null,
                messages: [],
                lastQuestion: '',
                lastAnswer: '',
                containerDiv: containerDiv  // 保存容器引用
            });
            
            console.log('✅ 创建会话容器:', sessionId);
        }
    }
    
    /**
     * 获取会话状态
     */
    getSessionStatus(sessionId) {
        const session = this.sessions.get(sessionId);
        return session ? session.status : this.SESSION_STATUS.IDLE;
    }
    
    /**
     * 设置会话状态
     */
    setSessionStatus(sessionId, status) {
        this.ensureSession(sessionId);
        const session = this.sessions.get(sessionId);
        session.status = status;
        this.updateSendButton(sessionId);
    }

    /**
     * 生成会话ID
     */
    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);
    }

    /**
     * 发送消息 - 支持多会话并发
     */
    async sendMessage() {
        const messageInput = document.getElementById('messageInput');
        const message = messageInput.value;
        const sessionId = this.currentSessionId;
        
        // 验证输入
        const validation = InputValidator.validateMessage(message);
        if (!validation.valid) {
            notificationManager.show(validation.error, 'error');
            return;
        }
        
        // 检查当前会话是否正在生成
        const currentStatus = this.getSessionStatus(sessionId);
        if (currentStatus === this.SESSION_STATUS.GENERATING) {
            notificationManager.show('当前对话正在生成中，请先停止或等待完成', 'warning');
            return;
        }
        
        // 确保会话存在
        this.ensureSession(sessionId);
        
        // 保存用户问题
        const session = this.sessions.get(sessionId);
        session.lastQuestion = validation.value;
        
        // 隐藏空状态
        this.hideEmptyState();
        
        // 添加用户消息到界面
        this.addUserMessage(validation.value);
        
        // 清空输入框
        messageInput.value = '';
        messageInput.style.height = 'auto';
        
        // 创建AI消息占位符
        const agentMessageDiv = this.createAgentMessage();
        
        if (!agentMessageDiv) {
            console.error('❌ 创建消息失败');
            return;
        }
        
        // 设置状态为生成中
        this.setSessionStatus(sessionId, this.SESSION_STATUS.GENERATING);
        
        try {
            // 获取配置
            const useKB = document.getElementById('useKB')?.checked || false;
            const useTools = document.getElementById('useTools')?.checked || false;
            
            // 选择API端点
            const endpoint = this.isMultiAgentMode 
                ? '/chat/multi-agent/stream'
                : '/chat/agent/stream';
            
            // 发送请求（异步，不阻塞切换）
            await this.streamChat(validation.value, useKB, useTools, endpoint, agentMessageDiv, sessionId);
            
        } catch (error) {
            console.error('发送消息失败:', error);
            const contentDiv = agentMessageDiv.querySelector('.message-content');
            contentDiv.innerHTML = `<p style="color: var(--error-color);">❌ 发送失败: ${error.message}</p>`;
            notificationManager.show('发送消息失败', 'error');
            this.setSessionStatus(sessionId, this.SESSION_STATUS.IDLE);
        }
    }

    /**
     * 流式聊天 - 支持多会话
     */
    async streamChat(message, useKB, useTools, endpoint, agentMessageDiv, sessionId) {
        // 为当前会话创建 AbortController
        const session = this.sessions.get(sessionId);
        session.abortController = new AbortController();
        
        const response = await fetch(`${this.API_BASE}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                messages: [{ role: 'user', content: message }],
                session_id: sessionId,
                use_knowledge_base: useKB,
                use_tools: useTools
            }),
            signal: session.abortController.signal
        });
        
        if (!response.ok) {
            this.setSessionStatus(sessionId, this.SESSION_STATUS.IDLE);
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullContent = '';
        
        const contentDiv = agentMessageDiv.querySelector('.message-content');
        
        // 检查是否是当前活跃会话
        const isCurrentSession = () => this.currentSessionId === sessionId;
        
        try {
            while (true) {
                const { done, value } = await reader.read();
                
                if (done) {
                    console.log('✅ 流式传输完成 - Session:', sessionId);
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
                            try {
                                eventData = JSON.parse(line.slice(6));
                            } catch (e) {
                                console.error('JSON解析失败:', e, line);
                            }
                        }
                    }
                    
                    if (eventType && eventData) {
                        // 只在当前会话时打印详细日志
                        if (isCurrentSession()) {
                            console.log('📨 收到事件:', eventType, eventData);
                        }
                        
                        if (eventType === 'content' || eventType === 'message') {
                            fullContent += eventData.content || eventData.message || '';
                            // 更新消息内容（DOM始终存在，无论是否当前会话）
                            this.updateMessageContent(contentDiv, fullContent);
                            
                            // 只在当前会话时才滚动
                            if (isCurrentSession() && this.mainContainer) {
                                this.mainContainer.scrollTop = this.mainContainer.scrollHeight;
                            }
                        } else if (eventType === 'node' || eventType === 'status') {
                            // 只在当前会话时更新时间线
                            if (isCurrentSession()) {
                                this.handleNodeUpdate(eventData);
                            }
                        }
                    }
                }
            }
            
            // 保存完整回答
            session.lastAnswer = fullContent;
            
            // 最终渲染
            this.finalizeMessage(contentDiv, fullContent);
            
            // 移除ID
            agentMessageDiv.removeAttribute('id');
            
            // 设置状态为已完成
            this.setSessionStatus(sessionId, this.SESSION_STATUS.COMPLETED);
            
            // 如果不是当前会话，发送通知
            if (!isCurrentSession()) {
                this.showCompletionNotification(sessionId, session.lastQuestion, fullContent);
            }
            
            // 如果是当前会话，滚动到底部
            if (isCurrentSession() && this.mainContainer) {
                this.mainContainer.scrollTop = this.mainContainer.scrollHeight;
            }
            
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('⏹️ 用户停止生成 - Session:', sessionId);
                contentDiv.innerHTML += '<p style="color: var(--text-secondary); font-style: italic;">⏹️ 已停止生成</p>';
            } else {
                throw error;
            }
        } finally {
            // 清理 AbortController
            session.abortController = null;
        }
    }

    /**
     * 更新消息内容
     */
    updateMessageContent(contentDiv, content) {
        if (!content) return;
        
        if (typeof marked !== 'undefined') {
            const rendered = marked.parse(content);
            // 使用DOMPurify清理（如果可用）
            if (typeof DOMPurify !== 'undefined') {
                contentDiv.innerHTML = DOMPurify.sanitize(rendered);
            } else {
                contentDiv.innerHTML = rendered;
            }
        } else {
            contentDiv.textContent = content;
        }
        
        // 代码高亮
        if (typeof hljs !== 'undefined') {
            contentDiv.querySelectorAll('pre code').forEach(block => {
                try {
                    hljs.highlightElement(block);
                } catch (e) {
                    console.warn('代码高亮失败:', e);
                }
            });
        }
        
        // 注意：不在这里滚动，由调用者决定是否需要滚动
    }

    /**
     * 最终渲染消息
     */
    async finalizeMessage(contentDiv, content) {
        if (!content) {
            console.warn('⚠️ 内容为空，无法渲染');
            return;
        }
        
        console.log('🎨 最终渲染，内容长度:', content.length);
        
        // 渲染Markdown
        if (typeof marked !== 'undefined') {
            const rendered = marked.parse(content);
            if (typeof DOMPurify !== 'undefined') {
                contentDiv.innerHTML = DOMPurify.sanitize(rendered);
            } else {
                contentDiv.innerHTML = rendered;
            }
        } else {
            contentDiv.textContent = content;
        }
        
        // 代码高亮
        if (typeof hljs !== 'undefined') {
            contentDiv.querySelectorAll('pre code').forEach(block => {
                try {
                    hljs.highlightElement(block);
                } catch (e) {
                    console.warn('代码高亮失败:', e);
                }
            });
        }
        
        // 渲染Mermaid图表
        if (typeof mermaid !== 'undefined') {
            const mermaidBlocks = contentDiv.querySelectorAll('code.language-mermaid');
            console.log('📊 发现', mermaidBlocks.length, '个Mermaid图表');
            
            for (const block of mermaidBlocks) {
                const mermaidCode = block.textContent;
                const mermaidDiv = document.createElement('div');
                mermaidDiv.className = 'mermaid';
                mermaidDiv.id = `mermaid-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
                mermaidDiv.textContent = mermaidCode;
                mermaidDiv.setAttribute('data-mermaid-code', mermaidCode);
                mermaidDiv.style.cursor = 'zoom-in';
                block.parentElement.replaceWith(mermaidDiv);
                
                try {
                    await mermaid.run({ nodes: [mermaidDiv] });
                    mermaidDiv.onclick = (e) => {
                        e.preventDefault();
                        this.openMermaidModal(mermaidCode);
                    };
                } catch (err) {
                    console.error('Mermaid渲染失败:', err);
                }
            }
        }
        
        // 图片点击放大
        contentDiv.querySelectorAll('img').forEach(img => {
            img.onclick = () => this.openImageModal(img.src);
        });
        
        // 添加复制按钮
        this.addCopyButtons(contentDiv);
    }

    /**
     * 处理节点更新（时间线）
     */
    handleNodeUpdate(data) {
        console.log('📊 节点更新:', data);
        
        const timelineContent = document.getElementById('timelineContent');
        const statsBar = document.getElementById('statsBar');
        
        if (!timelineContent) {
            console.warn('时间线容器未找到');
            return;
        }
        
        // 清除"等待任务开始"提示
        const waitingMsg = timelineContent.querySelector('p[style*="color: #9ca3af"]');
        if (waitingMsg) {
            waitingMsg.remove();
        }
        
        // 创建节点卡片
        const nodeDiv = document.createElement('div');
        nodeDiv.className = 'timeline-node';
        
        // 根据节点类型设置样式
        let nodeClass = 'timeline-node-default';
        let icon = '🔹';
        
        if (data.node === 'planner' || data.type === 'planning') {
            nodeClass = 'timeline-node-thought';
            icon = '🧠';
        } else if (data.node === 'tools' || data.type === 'tool_call') {
            nodeClass = 'timeline-node-tool';
            icon = '🔧';
        } else if (data.type === 'observation') {
            nodeClass = 'timeline-node-observation';
            icon = '👁️';
        }
        
        nodeDiv.classList.add(nodeClass);
        
        const timestamp = new Date().toLocaleTimeString('zh-CN', { 
            hour: '2-digit', 
            minute: '2-digit',
            second: '2-digit'
        });
        
        let contentHtml = '';
        if (data.thought) {
            contentHtml = `<div class="timeline-content">${this.escapeHtml(data.thought)}</div>`;
        } else if (data.action) {
            contentHtml = `<div class="timeline-content">执行工具: ${this.escapeHtml(data.action)}</div>`;
        } else if (data.observation) {
            contentHtml = `<div class="timeline-content">${this.escapeHtml(data.observation)}</div>`;
        } else if (data.message) {
            contentHtml = `<div class="timeline-content">${this.escapeHtml(data.message)}</div>`;
        } else if (data.status) {
            contentHtml = `<div class="timeline-content">${this.escapeHtml(data.status)}</div>`;
        }
        
        nodeDiv.innerHTML = `
            <div class="timeline-node-header">
                <span class="timeline-node-icon">${icon}</span>
                <span class="timeline-node-title">${data.node || data.type || '步骤'}</span>
                <span class="timeline-node-time">${timestamp}</span>
            </div>
            ${contentHtml}
        `;
        
        timelineContent.appendChild(nodeDiv);
        
        // 自动滚动到底部
        timelineContent.scrollTop = timelineContent.scrollHeight;
        
        // 显示统计栏
        if (statsBar) {
            statsBar.style.display = 'flex';
            
            // 更新节点计数
            const nodeCount = document.getElementById('nodeCount');
            if (nodeCount) {
                const count = timelineContent.querySelectorAll('.timeline-node').length;
                nodeCount.textContent = count;
            }
        }
    }

    /**
     * 添加用户消息
     */
    addUserMessage(content) {
        const session = this.sessions.get(this.currentSessionId);
        if (!session || !session.containerDiv) {
            console.error('❌ 找不到会话容器');
            return;
        }
        
        const time = new Date().toLocaleTimeString('zh-CN', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        messageDiv.innerHTML = `
            <div class="message-header">
                <div class="avatar">👤</div>
                <div class="message-role">你</div>
                <div class="message-time">${time}</div>
            </div>
            <div class="message-content">${this.escapeHtml(content)}</div>
        `;
        
        session.containerDiv.appendChild(messageDiv);
        
        if (this.mainContainer) {
            this.mainContainer.scrollTop = this.mainContainer.scrollHeight;
        }
    }

    /**
     * 创建AI消息占位符
     */
    createAgentMessage() {
        const session = this.sessions.get(this.currentSessionId);
        if (!session || !session.containerDiv) {
            console.error('❌ 找不到会话容器');
            return null;
        }
        
        const time = new Date().toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message agent-message';
        messageDiv.id = 'currentAgentMessage';
        messageDiv.innerHTML = `
            <div class="message-header">
                <div class="avatar">🤖</div>
                <div class="message-role">AI Agent</div>
                <div class="message-time">${time}</div>
            </div>
            <div class="message-content">
                <div class="loading-enhanced">
                    <div class="loading-spinner"></div>
                    <span>AI正在思考中...</span>
                </div>
            </div>
        `;
        
        session.containerDiv.appendChild(messageDiv);
        
        if (this.mainContainer) {
            this.mainContainer.scrollTop = this.mainContainer.scrollHeight;
        }
        
        return messageDiv;
    }

    /**
     * 加载历史消息
     */
    async loadHistoryMessages(sessionId) {
        try {
            const response = await fetch(`${this.API_BASE}/conversation/${sessionId}/history?limit=100`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const messages = await response.json();
            const session = this.sessions.get(sessionId);
            
            if (!session || !session.containerDiv) {
                console.error('❌ 找不到会话容器');
                return;
            }
            
            // 清空会话容器
            session.containerDiv.innerHTML = '';
            
            messages.forEach(msg => {
                if (msg.role === 'user') {
                    this.addUserMessage(msg.content);
                } else if (msg.role === 'assistant') {
                    this.addAssistantMessage(msg.content);
                }
            });
            
            // 如果有消息，隐藏空状态
            if (messages.length > 0) {
                this.hideEmptyState();
            }
            
        } catch (error) {
            console.error('加载历史消息失败:', error);
            notificationManager.show('加载历史记录失败', 'error');
        }
    }

    /**
     * 添加助手消息
     */
    addAssistantMessage(content) {
        const session = this.sessions.get(this.currentSessionId);
        if (!session || !session.containerDiv) {
            console.error('❌ 找不到会话容器');
            return;
        }
        
        const time = new Date().toLocaleTimeString('zh-CN', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message agent-message';
        
        const renderedContent = marked.parse(content);
        const sanitizedContent = DOMPurify.sanitize(renderedContent);
        
        messageDiv.innerHTML = `
            <div class="message-header">
                <div class="avatar">🤖</div>
                <div class="message-role">AI Agent</div>
                <div class="message-time">${time}</div>
            </div>
            <div class="message-content">${sanitizedContent}</div>
        `;
        
        session.containerDiv.appendChild(messageDiv);
        
        // 代码高亮
        if (typeof hljs !== 'undefined') {
            messageDiv.querySelectorAll('pre code').forEach(block => {
                try {
                    hljs.highlightElement(block);
                } catch (e) {}
            });
        }
        
        if (this.mainContainer) {
            this.mainContainer.scrollTop = this.mainContainer.scrollHeight;
        }
    }

    /**
     * 添加复制按钮
     */
    addCopyButtons(contentDiv) {
        contentDiv.querySelectorAll('pre').forEach(pre => {
            if (pre.querySelector('.copy-btn')) return;
            
            const button = document.createElement('button');
            button.className = 'copy-btn';
            button.textContent = '📋 复制';
            button.onclick = async () => {
                const code = pre.querySelector('code')?.textContent || '';
                try {
                    await navigator.clipboard.writeText(code);
                    button.textContent = '✅ 已复制';
                    setTimeout(() => {
                        button.textContent = '📋 复制';
                    }, 2000);
                } catch (err) {
                    console.error('复制失败:', err);
                }
            };
            
            pre.style.position = 'relative';
            pre.appendChild(button);
        });
    }

    /**
     * 打开图片模态框
     */
    openImageModal(src) {
        const modal = document.getElementById('imageModal');
        const img = document.getElementById('modalImage');
        if (modal && img) {
            img.src = src;
            modal.classList.add('active');
        }
    }

    /**
     * 打开Mermaid模态框
     */
    openMermaidModal(code) {
        const modal = document.getElementById('mermaidModal');
        const content = document.getElementById('modalMermaidContent');
        if (modal && content) {
            content.innerHTML = `<div class="mermaid">${code}</div>`;
            modal.classList.add('active');
            
            if (typeof mermaid !== 'undefined') {
                mermaid.run({ nodes: content.querySelectorAll('.mermaid') });
            }
        }
    }

    /**
     * 转义HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 切换多智能体模式
     */
    toggleMultiAgentMode(enabled) {
        this.isMultiAgentMode = enabled;
        console.log('多智能体模式:', enabled ? '开启' : '关闭');
    }

    /**
     * 停止当前会话的生成
     */
    stopCurrentRequest() {
        const sessionId = this.currentSessionId;
        const session = this.sessions.get(sessionId);
        
        if (session && session.abortController) {
            session.abortController.abort();
            session.abortController = null;
            this.setSessionStatus(sessionId, this.SESSION_STATUS.IDLE);
            notificationManager.show('⏹️ 已停止生成', 'info');
        }
    }
    
    /**
     * 更新发送/停止按钮状态
     */
    updateSendButton(sessionId) {
        // 只更新当前会话的按钮
        if (sessionId !== this.currentSessionId) return;
        
        const sendBtn = document.getElementById('sendBtn');
        const stopBtn = document.getElementById('stopBtn');
        const status = this.getSessionStatus(sessionId);
        
        if (status === this.SESSION_STATUS.GENERATING) {
            // 显示停止按钮
            if (sendBtn) sendBtn.style.display = 'none';
            if (stopBtn) stopBtn.style.display = 'flex';
        } else {
            // 显示发送按钮
            if (sendBtn) sendBtn.style.display = 'flex';
            if (stopBtn) stopBtn.style.display = 'none';
        }
    }
    
    /**
     * 切换到指定会话
     */
    switchToSession(sessionId) {
        console.log('🔄 切换会话:', sessionId);
        
        // 检查当前会话是否在生成中
        const currentStatus = this.getSessionStatus(this.currentSessionId);
        if (currentStatus === this.SESSION_STATUS.GENERATING) {
            notificationManager.show('💼 当前对话已切换到后台继续生成', 'info', 3000);
        }
        
        // 隐藏当前会话的容器
        if (this.currentSessionId) {
            const currentSession = this.sessions.get(this.currentSessionId);
            if (currentSession && currentSession.containerDiv) {
                currentSession.containerDiv.style.display = 'none';
            }
        }
        
        // 切换会话ID
        this.currentSessionId = sessionId;
        this.ensureSession(sessionId);
        
        // 显示新会话的容器
        const newSession = this.sessions.get(sessionId);
        if (newSession && newSession.containerDiv) {
            newSession.containerDiv.style.display = 'block';
            console.log('📂 已显示会话容器:', sessionId);
            
            // 滚动到底部
            if (this.mainContainer) {
                this.mainContainer.scrollTop = this.mainContainer.scrollHeight;
            }
        } else {
            console.error('❌ 找不到会话容器:', sessionId);
        }
        
        // 更新UI按钮状态
        this.updateSendButton(sessionId);
        
        // 提示新会话状态
        const newStatus = this.getSessionStatus(sessionId);
        if (newStatus === this.SESSION_STATUS.GENERATING) {
            notificationManager.show('⚙️ 该对话正在后台生成中...', 'info', 2000);
        }
    }
    
    /**
     * 显示后台生成完成通知
     */
    showCompletionNotification(sessionId, question, answer) {
        console.log('📢 后台生成完成通知 - Session:', sessionId);
        
        // 截取问题和答案
        const truncatedQuestion = question.length > 30 
            ? question.substring(0, 30) + '...' 
            : question;
        
        const truncatedAnswer = answer.length > 100 
            ? answer.substring(0, 100) + '...' 
            : answer;
        
        // 创建富文本通知
        const notificationHtml = `
            <div style="max-width: 350px;">
                <div style="font-weight: 600; margin-bottom: 6px; color: var(--text-primary);">
                    ${this.escapeHtml(truncatedQuestion)}
                </div>
                <div style="font-size: 13px; color: var(--text-secondary); line-height: 1.5;">
                    ${this.escapeHtml(truncatedAnswer)}
                </div>
            </div>
        `;
        
        // 显示通知（使用增强的通知系统）
        if (window.notificationManager && window.notificationManager.showRich) {
            window.notificationManager.showRich(notificationHtml, 'success', 5000);
        } else {
            notificationManager.show(`✅ 对话生成完成：${truncatedQuestion}`, 'success', 3000);
        }
    }
}

// 暴露类到全局作用域（供init.js检测）
window.ChatManager = ChatManager;

// 导出（用于模块系统）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ChatManager };
}

