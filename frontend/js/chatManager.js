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
        
        // 编辑状态
        this.editingMessageId = null;
        this.editingMessageDiv = null;
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
        this.setupScrollListener();
        this.loadSessionFromUrl();
        console.log('✅ 聊天管理器初始化成功');
    }
    
    /**
     * 设置滚动监听器 - 实时保存滚动位置
     */
    setupScrollListener() {
        if (!this.mainContainer) return;
        
        // 使用防抖优化性能
        let scrollTimer = null;
        this.mainContainer.addEventListener('scroll', () => {
            if (scrollTimer) {
                clearTimeout(scrollTimer);
            }
            
            scrollTimer = setTimeout(() => {
                if (this.currentSessionId) {
                    const session = this.sessions.get(this.currentSessionId);
                    if (session) {
                        session.scrollPosition = this.mainContainer.scrollTop;
                    }
                }
            }, 150); // 150ms防抖
        });
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
            
            // 根据会话是否有消息决定是否显示空状态
            if (session.containerDiv.children.length > 0) {
                this.hideEmptyState();
            } else {
                this.showEmptyState();
            }
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
     * 显示空状态
     */
    showEmptyState() {
        const emptyState = document.querySelector('.empty-state');
        if (emptyState) {
            emptyState.style.display = 'flex';
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
                containerDiv: containerDiv,  // 保存容器引用
                scrollPosition: 0  // 记录滚动位置
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
        
        // 如果在编辑模式，完成编辑
        if (this.editingMessageId) {
            await this.completeEdit(validation.value);
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
                    
                    if (eventType === 'content' || eventType === 'message' || eventType === 'assistant_final' || eventType === 'assistant_draft') {
                        const newContent = eventData.content || eventData.message || '';
                        if (newContent) {
                            // assistant_final和assistant_draft事件通常包含完整内容，直接替换
                            if (eventType === 'assistant_final' || eventType === 'assistant_draft') {
                                fullContent = newContent;
                                console.log('✅ 收到完整答案，类型:', eventType, '长度:', fullContent.length, 'SessionId:', sessionId);
                            } else {
                                fullContent += newContent;
                                console.log('📝 累积内容长度:', fullContent.length, 'SessionId:', sessionId);
                            }
                            // 更新消息内容（DOM始终存在，无论是否当前会话）
                            this.updateMessageContent(contentDiv, fullContent);
                            
                            // 只在当前会话时才滚动
                            if (isCurrentSession() && this.mainContainer) {
                                this.mainContainer.scrollTop = this.mainContainer.scrollHeight;
                            }
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
        
        console.log('🎯 流式传输完成，准备最终渲染 - Session:', sessionId, '内容长度:', fullContent.length);
        
        // 最终渲染
        this.finalizeMessage(contentDiv, fullContent);
        
        // 移除ID
        agentMessageDiv.removeAttribute('id');
            
            // 设置状态为已完成
            this.setSessionStatus(sessionId, this.SESSION_STATUS.COMPLETED);
            console.log('✅ 会话状态已设置为COMPLETED - Session:', sessionId);
            
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
        // 如果内容为空，不做任何处理（保持loading状态）
        if (!content || content.trim() === '') {
            console.log('⚠️ updateMessageContent: 内容为空，保持loading状态');
            return;
        }
        
        console.log('🔄 updateMessageContent: 更新内容，长度:', content.length);
        
        // 有内容时才移除loading状态
        const loadingDiv = contentDiv.querySelector('.loading-enhanced');
        if (loadingDiv) {
            console.log('🗑️ 移除loading状态');
            loadingDiv.remove();
        }
        
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
        console.log('🎨 最终渲染，内容长度:', content ? content.length : 0);
        
        // 移除loading状态（无论内容是否为空）
        const loadingDiv = contentDiv.querySelector('.loading-enhanced');
        if (loadingDiv) {
            loadingDiv.remove();
        }
        
        // 如果没有内容，显示提示信息
        if (!content || content.trim() === '') {
            console.warn('⚠️ 内容为空');
            contentDiv.innerHTML = '<p style="color: var(--text-secondary); font-style: italic;">⚠️ 生成内容为空</p>';
            // 显示复制按钮（即使内容为空）
            const copyBtn = contentDiv.querySelector('.copy-btn');
            if (copyBtn) {
                copyBtn.style.display = '';
            }
            return;
        }
        
        // 保存原始文本到data属性
        contentDiv.dataset.originalText = content;
        
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
        
        // 显示消息复制按钮（按钮在 message-content 内部）
        const copyBtn = contentDiv.querySelector('.copy-btn');
        if (copyBtn) {
            copyBtn.style.display = '';
        }
        
        // 添加代码块复制按钮
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
    addUserMessage(content, sessionId = null) {
        const sid = sessionId || this.currentSessionId;
        const session = this.sessions.get(sid);
        if (!session || !session.containerDiv) {
            console.error('❌ 找不到会话容器:', sid);
            return;
        }
        
        const time = new Date().toLocaleTimeString('zh-CN', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        
        // 生成唯一ID
        const messageId = 'msg-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        
        messageDiv.innerHTML = `
            <div class="message-header">
                <div class="avatar">👤</div>
                <div class="message-role">你</div>
                <div class="message-time">${time}</div>
            </div>
            <div class="message-content" data-message-id="${messageId}">
                ${this.escapeHtml(content)}
                <button class="edit-btn" onclick="chatManager.editMessage('${messageId}')" title="编辑">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                    <span class="edit-text">编辑</span>
                </button>
                <button class="copy-btn" onclick="chatManager.copyMessageContent('${messageId}')" title="复制">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                    <span class="copy-text">复制</span>
                </button>
            </div>
        `;
        
        // 保存原始文本到data属性
        const contentDiv = messageDiv.querySelector('.message-content');
        contentDiv.dataset.originalText = content;
        
        session.containerDiv.appendChild(messageDiv);
        
        if (this.mainContainer) {
            this.mainContainer.scrollTop = this.mainContainer.scrollHeight;
        }
    }

    /**
     * 创建AI消息占位符
     */
    createAgentMessage(sessionId = null) {
        const sid = sessionId || this.currentSessionId;
        const session = this.sessions.get(sid);
        if (!session || !session.containerDiv) {
            console.error('❌ 找不到会话容器:', sid);
            return null;
        }
        
        const time = new Date().toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message agent-message';
        messageDiv.id = 'currentAgentMessage';
        
        // 生成唯一ID
        const messageId = 'msg-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        
        messageDiv.innerHTML = `
            <div class="message-header">
                <div class="avatar">🤖</div>
                <div class="message-role">AI Agent</div>
                <div class="message-time">${time}</div>
            </div>
            <div class="message-content" data-message-id="${messageId}">
                <div class="loading-enhanced">
                    <div class="loading-spinner"></div>
                    <span>AI正在思考中...</span>
                </div>
                <button class="copy-btn" onclick="chatManager.copyMessageContent('${messageId}')" title="复制" style="display: none;">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                    <span class="copy-text">复制</span>
                </button>
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
                    this.addUserMessage(msg.content, sessionId);
                } else if (msg.role === 'assistant') {
                    this.addAssistantMessage(msg.content, sessionId);
                }
            });
            
            // 根据消息数量决定是否显示空状态
            if (messages.length > 0) {
                this.hideEmptyState();
            } else {
                // 如果是当前会话且没有消息，显示空状态
                if (sessionId === this.currentSessionId) {
                    this.showEmptyState();
                }
            }
            
        } catch (error) {
            console.error('加载历史消息失败:', error);
            notificationManager.show('加载历史记录失败', 'error');
        }
    }

    /**
     * 添加助手消息
     */
    addAssistantMessage(content, sessionId = null) {
        const sid = sessionId || this.currentSessionId;
        const session = this.sessions.get(sid);
        if (!session || !session.containerDiv) {
            console.error('❌ 找不到会话容器:', sid);
            return;
        }
        
        const time = new Date().toLocaleTimeString('zh-CN', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message agent-message';
        
        // 生成唯一ID
        const messageId = 'msg-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        
        const renderedContent = marked.parse(content);
        const sanitizedContent = DOMPurify.sanitize(renderedContent);
        
        messageDiv.innerHTML = `
            <div class="message-header">
                <div class="avatar">🤖</div>
                <div class="message-role">AI Agent</div>
                <div class="message-time">${time}</div>
            </div>
            <div class="message-content" data-message-id="${messageId}">
                ${sanitizedContent}
                <button class="copy-btn" onclick="chatManager.copyMessageContent('${messageId}')" title="复制">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                    <span class="copy-text">复制</span>
                </button>
            </div>
        `;
        
        // 保存原始文本到data属性
        const contentDiv = messageDiv.querySelector('.message-content');
        contentDiv.dataset.originalText = content;
        
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
     * 编辑消息
     */
    async editMessage(messageId) {
        const contentDiv = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!contentDiv) {
            console.error('找不到消息元素:', messageId);
            return;
        }
        
        // 获取原始文本
        const originalText = contentDiv.dataset.originalText || contentDiv.textContent.trim();
        const messageDiv = contentDiv.closest('.message');
        
        // 停止当前正在生成的对话
        if (this.getSessionStatus(this.currentSessionId) === this.SESSION_STATUS.GENERATING) {
            this.stopCurrentRequest();
            await new Promise(resolve => setTimeout(resolve, 300)); // 等待停止完成
        }
        
        // 进入编辑模式
        this.enterEditMode(messageDiv, originalText, messageId);
    }
    
    /**
     * 进入编辑模式
     */
    enterEditMode(messageDiv, originalText, messageId) {
        // 保存编辑状态
        this.editingMessageId = messageId;
        this.editingMessageDiv = messageDiv;
        
        // 添加编辑状态类
        document.body.classList.add('editing-mode');
        messageDiv.classList.add('editing-active');
        
        // 填充输入框
        const messageInput = document.getElementById('messageInput');
        if (messageInput) {
            messageInput.value = originalText;
            messageInput.focus();
            
            // 自动调整高度
            messageInput.style.height = 'auto';
            messageInput.style.height = Math.min(messageInput.scrollHeight, 300) + 'px';
        }
        
        // 显示编辑提示
        this.showEditingHint();
        
        // 滚动到编辑的消息
        messageDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    
    /**
     * 显示编辑提示
     */
    showEditingHint() {
        // 创建提示元素
        let hint = document.getElementById('editingHint');
        if (!hint) {
            hint = document.createElement('div');
            hint.id = 'editingHint';
            hint.className = 'editing-hint';
            hint.innerHTML = `
                <div class="hint-content">
                    <span class="hint-icon">✏️</span>
                    <span class="hint-text">编辑模式：修改问题后按Enter重新发送</span>
                    <button class="hint-cancel" onclick="chatManager.cancelEdit()">取消</button>
                </div>
            `;
            document.querySelector('.input-container').prepend(hint);
        }
    }
    
    /**
     * 取消编辑
     */
    cancelEdit() {
        // 移除编辑状态
        document.body.classList.remove('editing-mode');
        if (this.editingMessageDiv) {
            this.editingMessageDiv.classList.remove('editing-active');
        }
        
        // 清除输入框
        const messageInput = document.getElementById('messageInput');
        if (messageInput) {
            messageInput.value = '';
            messageInput.style.height = 'auto';
        }
        
        // 移除提示
        const hint = document.getElementById('editingHint');
        if (hint) {
            hint.remove();
        }
        
        // 清除编辑状态
        this.editingMessageId = null;
        this.editingMessageDiv = null;
    }
    
    /**
     * 完成编辑并重新发送
     */
    async completeEdit(newContent) {
        if (!this.editingMessageId || !this.editingMessageDiv) {
            console.error('没有正在编辑的消息');
            return;
        }
        
        const contentDiv = this.editingMessageDiv.querySelector('.message-content');
        const messageId = this.editingMessageId;
        
        // 删除旧的AI回复
        let nextMessage = this.editingMessageDiv.nextElementSibling;
        if (nextMessage && nextMessage.classList.contains('agent-message')) {
            nextMessage.remove();
        }
        
        // 更新问题内容（保留按钮）
        const buttons = Array.from(contentDiv.querySelectorAll('button'));
        const buttonsHTML = buttons.map(b => b.outerHTML).join('');
        contentDiv.innerHTML = this.escapeHtml(newContent) + buttonsHTML;
        contentDiv.dataset.originalText = newContent;
        
        // 取消编辑模式
        this.cancelEdit();
        
        // 重新发送消息
        await this.resendMessage(newContent);
    }
    
    /**
     * 重新发送消息（用于编辑后）
     */
    async resendMessage(content) {
        const sessionId = this.currentSessionId;
        
        // 确保会话存在
        this.ensureSession(sessionId);
        
        // 保存用户问题
        const session = this.sessions.get(sessionId);
        session.lastQuestion = content;
        
        // 隐藏空状态
        this.hideEmptyState();
        
        // 创建AI消息占位符
        const agentMessageDiv = this.createAgentMessage(sessionId);
        
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
            
            // 发送请求
            await this.streamChat(content, useKB, useTools, endpoint, agentMessageDiv, sessionId);
            
        } catch (error) {
            console.error('重新发送消息失败:', error);
            const contentDiv = agentMessageDiv.querySelector('.message-content');
            contentDiv.innerHTML = `<p style="color: var(--error-color);">❌ 发送失败: ${error.message}</p>`;
            notificationManager.show('发送消息失败', 'error');
            this.setSessionStatus(sessionId, this.SESSION_STATUS.IDLE);
        }
    }
    
    /**
     * 复制消息内容（保留原始格式）
     */
    async copyMessageContent(messageId) {
        const contentDiv = document.querySelector(`[data-message-id="${messageId}"]`);
        if (!contentDiv) {
            console.error('找不到消息元素:', messageId);
            notificationManager.show('复制失败', 'error');
            return;
        }
        
        // 获取原始文本（保留格式）
        const originalText = contentDiv.dataset.originalText || contentDiv.textContent;
        
        try {
            await navigator.clipboard.writeText(originalText);
            
            // 找到对应的复制按钮并更新状态
            const copyBtn = contentDiv.parentElement.querySelector('.copy-btn');
            if (copyBtn) {
                const originalHTML = copyBtn.innerHTML;
                copyBtn.innerHTML = `
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                    <span class="copy-text">已复制</span>
                `;
                copyBtn.classList.add('copied');
                
                setTimeout(() => {
                    copyBtn.innerHTML = originalHTML;
                    copyBtn.classList.remove('copied');
                }, 2000);
            }
            
            notificationManager.show('✅ 已复制到剪贴板', 'success', 1500);
        } catch (err) {
            console.error('复制失败:', err);
            // 降级方案
            this.fallbackCopyToClipboard(originalText);
        }
    }
    
    /**
     * 降级的复制方法（兼容老浏览器）
     */
    fallbackCopyToClipboard(text) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        textArea.style.top = '-9999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            const successful = document.execCommand('copy');
            if (successful) {
                notificationManager.show('✅ 已复制到剪贴板', 'success', 1500);
            } else {
                notificationManager.show('❌ 复制失败，请手动复制', 'error');
            }
        } catch (err) {
            console.error('复制失败:', err);
            notificationManager.show('❌ 复制失败，请手动复制', 'error');
        }
        
        document.body.removeChild(textArea);
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
            
            // 移除loading状态
            const currentAgentMessage = document.getElementById('currentAgentMessage');
            if (currentAgentMessage) {
                const contentDiv = currentAgentMessage.querySelector('.message-content');
                const loadingDiv = contentDiv?.querySelector('.loading-enhanced');
                if (loadingDiv) {
                    console.log('🗑️ 停止生成：移除loading状态');
                    loadingDiv.remove();
                }
            }
            
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
        
        // 保存当前会话的滚动位置
        if (this.currentSessionId && this.mainContainer) {
            const currentSession = this.sessions.get(this.currentSessionId);
            if (currentSession) {
                currentSession.scrollPosition = this.mainContainer.scrollTop;
                console.log('💾 保存会话滚动位置:', this.currentSessionId, '位置:', currentSession.scrollPosition);
            }
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
            
            // 如果容器是空的，加载历史消息
            if (newSession.containerDiv.children.length === 0) {
                console.log('📥 容器为空，加载历史消息...');
                this.loadHistoryMessages(sessionId);
            } else {
                // 如果有消息，隐藏空状态
                this.hideEmptyState();
            }
            
            // 恢复滚动位置（延迟到DOM渲染完成）
            if (this.mainContainer) {
                requestAnimationFrame(() => {
                    if (newSession.scrollPosition > 0) {
                        this.mainContainer.scrollTop = newSession.scrollPosition;
                        console.log('📍 恢复会话滚动位置:', sessionId, '位置:', newSession.scrollPosition);
                    } else {
                        // 如果没有保存的滚动位置，滚动到底部
                        this.mainContainer.scrollTop = this.mainContainer.scrollHeight;
                    }
                });
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
        
        // 截取问题（限制40字符）
        const truncatedQuestion = question.length > 40 
            ? question.substring(0, 40) + '...' 
            : question;
        
        // 截取答案（限制120字符）
        const truncatedAnswer = answer.length > 120 
            ? answer.substring(0, 120) + '...' 
            : answer;
        
        // 创建富文本通知
        const notificationHtml = `
            <div style="max-width: 380px; padding: 4px 0;">
                <div style="
                    font-weight: 700;
                    font-size: 15px;
                    margin-bottom: 8px;
                    color: var(--text-primary);
                    line-height: 1.4;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
                ">
                    ${this.escapeHtml(truncatedQuestion)}
                </div>
                <div style="
                    font-size: 13px;
                    font-weight: 400;
                    color: var(--text-secondary);
                    line-height: 1.6;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
                ">
                    ${this.escapeHtml(truncatedAnswer)}
                </div>
            </div>
        `;
        
        // 显示通知（使用增强的通知系统）
        if (window.notificationManager && window.notificationManager.showRich) {
            window.notificationManager.showRich(notificationHtml, 'success', 6000);
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

