/* ===== 聊天管理器 - 处理消息发送、接收和渲染 ===== */

/**
 * 聊天管理器类
 */
class ChatManager {
    constructor() {
        this.API_BASE = 'http://127.0.0.1:8000';
        this.currentSessionId = null;
        this.currentAbortController = null;
        this.isSending = false;
        this.isMultiAgentMode = false;
    }

    /**
     * 初始化聊天管理器
     */
    init() {
        this.setupEventListeners();
        this.loadSessionFromUrl();
        console.log('✅ 聊天管理器初始化成功');
    }

    /**
     * 设置事件监听器
     */
    setupEventListeners() {
        const sendBtn = document.getElementById('sendBtn');
        const messageInput = document.getElementById('messageInput');
        
        if (sendBtn) {
            sendBtn.addEventListener('click', () => this.sendMessage());
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
            this.loadHistoryMessages(sessionId);
        } else {
            this.currentSessionId = this.generateSessionId();
        }
    }

    /**
     * 生成会话ID
     */
    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);
    }

    /**
     * 发送消息
     */
    async sendMessage() {
        const messageInput = document.getElementById('messageInput');
        const message = messageInput.value;
        
        // 验证输入
        const validation = InputValidator.validateMessage(message);
        if (!validation.valid) {
            notificationManager.show(validation.error, 'error');
            return;
        }
        
        if (this.isSending) {
            notificationManager.show('请等待当前消息发送完成', 'warning');
            return;
        }
        
        this.isSending = true;
        
        // 添加用户消息到界面
        this.addUserMessage(validation.value);
        
        // 清空输入框
        messageInput.value = '';
        messageInput.style.height = 'auto';
        
        // 创建AI消息占位符
        const agentMessageDiv = this.createAgentMessage();
        
        try {
            // 获取配置
            const useKB = document.getElementById('useKB')?.checked || false;
            const useTools = document.getElementById('useTools')?.checked || false;
            
            // 选择API端点
            const endpoint = this.isMultiAgentMode 
                ? '/chat/multi-agent/stream'
                : '/chat/agent/stream';
            
            // 发送请求
            await this.streamChat(validation.value, useKB, useTools, endpoint, agentMessageDiv);
            
        } catch (error) {
            console.error('发送消息失败:', error);
            const contentDiv = agentMessageDiv.querySelector('.message-content');
            contentDiv.innerHTML = `<p style="color: var(--error-color);">❌ 发送失败: ${error.message}</p>`;
            notificationManager.show('发送消息失败', 'error');
        } finally {
            this.isSending = false;
        }
    }

    /**
     * 流式聊天
     */
    async streamChat(message, useKB, useTools, endpoint, agentMessageDiv) {
        this.currentAbortController = new AbortController();
        
        const response = await fetch(`${this.API_BASE}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                messages: [{ role: 'user', content: message }],
                session_id: this.currentSessionId,
                use_knowledge_base: useKB,
                use_tools: useTools
            }),
            signal: this.currentAbortController.signal
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullContent = '';
        
        const contentDiv = agentMessageDiv.querySelector('.message-content');
        
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) {
                console.log('✅ 流式传输完成');
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
                    console.log('📨 收到事件:', eventType, eventData);
                    
                    if (eventType === 'content' || eventType === 'message') {
                        fullContent += eventData.content || eventData.message || '';
                        this.updateMessageContent(contentDiv, fullContent);
                    } else if (eventType === 'node' || eventType === 'status') {
                        this.handleNodeUpdate(eventData);
                    }
                }
            }
        }
        
        // 最终渲染
        this.finalizeMessage(contentDiv, fullContent);
        
        // 移除ID
        agentMessageDiv.removeAttribute('id');
    }

    /**
     * 更新消息内容
     */
    updateMessageContent(contentDiv, content) {
        if (!content) return;
        
        console.log('📝 更新内容，长度:', content.length);
        
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
        
        // 滚动到底部
        const container = document.getElementById('messagesContainer');
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
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
        // 这里可以更新时间线显示
        console.log('节点更新:', data);
    }

    /**
     * 添加用户消息
     */
    addUserMessage(content) {
        const container = document.getElementById('messagesContainer');
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
        
        container.appendChild(messageDiv);
        container.scrollTop = container.scrollHeight;
    }

    /**
     * 创建AI消息占位符
     */
    createAgentMessage() {
        const container = document.getElementById('messagesContainer');
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
        
        container.appendChild(messageDiv);
        container.scrollTop = container.scrollHeight;
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
            const container = document.getElementById('messagesContainer');
            container.innerHTML = '';
            
            messages.forEach(msg => {
                if (msg.role === 'user') {
                    this.addUserMessage(msg.content);
                } else if (msg.role === 'assistant') {
                    this.addAssistantMessage(msg.content);
                }
            });
            
        } catch (error) {
            console.error('加载历史消息失败:', error);
            notificationManager.show('加载历史记录失败', 'error');
        }
    }

    /**
     * 添加助手消息
     */
    addAssistantMessage(content) {
        const container = document.getElementById('messagesContainer');
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
        
        container.appendChild(messageDiv);
        
        // 代码高亮
        if (typeof hljs !== 'undefined') {
            messageDiv.querySelectorAll('pre code').forEach(block => {
                try {
                    hljs.highlightElement(block);
                } catch (e) {}
            });
        }
        
        container.scrollTop = container.scrollHeight;
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
     * 停止当前请求
     */
    stopCurrentRequest() {
        if (this.currentAbortController) {
            this.currentAbortController.abort();
            this.currentAbortController = null;
            this.isSending = false;
            notificationManager.show('已停止生成', 'info');
        }
    }
}

// 暴露类到全局作用域（供init.js检测）
window.ChatManager = ChatManager;

// 导出（用于模块系统）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ChatManager };
}
