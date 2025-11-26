<script setup>
import { ref, computed, nextTick, watch, onMounted } from 'vue';
import { useChatStore } from '../../stores/chat';
import { marked } from 'marked';
import axios from 'axios';

const chatStore = useChatStore();
const messageInput = ref('');
const chatContainer = ref(null);
const fileInput = ref(null);
const attachedFiles = ref([]);
const showOptions = ref(false);
const editingMessageId = ref(null);
const copiedMessageId = ref(null);

const messages = computed(() => chatStore.messages);
const isLoading = computed(() => chatStore.isLoading);
const currentSessionId = computed(() => chatStore.currentSessionId);
const sessionStatus = computed(() => chatStore.getSessionStatus(currentSessionId.value));
const useKnowledgeBase = computed({
    get: () => chatStore.useKnowledgeBase,
    set: (val) => chatStore.setUseKnowledgeBase(val)
});

// 判断是否正在生成
const isGenerating = computed(() => {
    return sessionStatus.value === chatStore.SESSION_STATUS.GENERATING;
});

// 判断是否在编辑模式
const isEditMode = computed(() => editingMessageId.value !== null);

async function handleFileSelect(event) {
    const files = Array.from(event.target.files);
    
    // 上传每个文件到后端
    for (const file of files) {
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await axios.post('http://127.0.0.1:8000/documents/upload', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            });
            
            // 上传成功后添加到附件列表
            attachedFiles.value.push({
                name: file.name,
                size: file.size,
                id: response.data.id // 保存后端返回的文档ID
            });
        } catch (error) {
            console.error('文件上传失败:', error);
            alert(`文件 ${file.name} 上传失败: ${error.response?.data?.detail || error.message}`);
        }
    }
    
    event.target.value = ''; // 清空input以便重复选择同一文件
}

function removeFile(index) {
    attachedFiles.value.splice(index, 1);
}

function toggleOptions() {
    showOptions.value = !showOptions.value;
}

async function sendMessage() {
    const content = messageInput.value.trim();
    if (!content || isGenerating.value) return;

    try {
        // 如果是编辑模式，更新消息而不是发送新消息
        if (editingMessageId.value !== null) {
            await completeEdit(content);
            return;
        }

        messageInput.value = '';
        await chatStore.sendMessage(content, (streamContent, sessionId) => {
            // 流式更新回调
            if (sessionId === currentSessionId.value) {
                nextTick(() => scrollToBottom());
            }
        });
        await nextTick();
        scrollToBottom();
    } catch (error) {
        console.error('发送失败:', error);
    }
}

// 复制消息内容
async function copyMessage(messageId) {
    const message = messages.value.find(m => m.id === messageId);
    if (!message) return;

    try {
        await navigator.clipboard.writeText(message.content);
        copiedMessageId.value = messageId;
        setTimeout(() => {
            copiedMessageId.value = null;
        }, 2000);
    } catch (error) {
        console.error('复制失败:', error);
        alert('复制失败，请重试');
    }
}

// 编辑消息
function editMessage(messageId) {
    const message = messages.value.find(m => m.id === messageId);
    if (!message || message.role !== 'user') return;

    // 如果正在生成，先停止
    if (isGenerating.value) {
        stopGeneration();
    }

    // 进入编辑模式
    editingMessageId.value = messageId;
    messageInput.value = message.content;
    
    // 聚焦输入框
    nextTick(() => {
        const textarea = document.querySelector('.message-input');
        if (textarea) {
            textarea.focus();
        }
    });
}

// 取消编辑
function cancelEdit() {
    editingMessageId.value = null;
    messageInput.value = '';
}

// 完成编辑
async function completeEdit(newContent) {
    if (!editingMessageId.value || !newContent.trim()) {
        cancelEdit();
        return;
    }

    try {
        // 调用store的编辑方法
        await chatStore.editAndResendMessage(editingMessageId.value, newContent, (streamContent, sessionId) => {
            // 流式更新回调
            if (sessionId === currentSessionId.value) {
                nextTick(() => scrollToBottom());
            }
        });
        
        // 清空输入框和编辑状态
        messageInput.value = '';
        editingMessageId.value = null;
        
        await nextTick();
        scrollToBottom();
    } catch (error) {
        console.error('编辑失败:', error);
    }
}

function stopGeneration() {
    chatStore.stopGeneration(currentSessionId.value);
}

function scrollToBottom() {
    if (chatContainer.value) {
        chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
    }
}

function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

function renderMarkdown(content) {
    return marked(content);
}

watch(messages, () => {
    nextTick(() => scrollToBottom());
});
</script>

<template>
    <div class="chat-panel">
        <!-- Background Generation Notice -->
        <div v-if="isGenerating" class="generation-notice">
            <div class="notice-content">
                <span class="notice-icon">⚡</span>
                <span class="notice-text">AI 正在生成回复...</span>
            </div>
        </div>
        
        <!-- Messages Area -->
        <div class="messages-container" ref="chatContainer">
            <div v-if="messages.length === 0" class="empty-state">
                <div class="empty-state-icon">💬</div>
                <h3 class="empty-state-title">开始对话</h3>
                <p class="empty-state-subtitle">输入消息开始与AI Agent对话</p>
            </div>

            <div
                v-for="msg in messages"
                :key="msg.id"
                class="message"
                :class="[
                    `message-${msg.role}`, 
                    msg.type === 'error' ? 'message-error' : '', 
                    msg.type === 'info' ? 'message-info' : '',
                    editingMessageId === msg.id ? 'editing-active' : ''
                ]"
            >
                <div class="message-avatar">
                    {{ msg.role === 'user' ? '👤' : msg.role === 'assistant' ? '🤖' : '⚠️' }}
                </div>
                <div class="message-content-wrapper">
                <div class="message-content">
                    <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
                    <div class="message-time">{{ new Date(msg.timestamp).toLocaleTimeString() }}</div>
                    </div>
                    
                    <!-- 操作按钮 -->
                    <div class="message-actions" v-if="msg.role === 'user' || msg.role === 'assistant'">
                        <!-- 编辑按钮 - 只对用户消息显示 -->
                        <button 
                            v-if="msg.role === 'user'" 
                            class="action-btn edit-btn"
                            @click="editMessage(msg.id)"
                            title="编辑消息"
                        >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                            </svg>
                            <span class="action-text">编辑</span>
                        </button>
                        
                        <!-- 复制按钮 -->
                        <button 
                            class="action-btn copy-btn"
                            @click="copyMessage(msg.id)"
                            :title="copiedMessageId === msg.id ? '已复制' : '复制内容'"
                        >
                            <svg v-if="copiedMessageId !== msg.id" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                            </svg>
                            <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="20 6 9 17 4 12"></polyline>
                            </svg>
                            <span class="action-text">{{ copiedMessageId === msg.id ? '已复制' : '复制' }}</span>
                        </button>
                    </div>
                </div>
            </div>

            <div v-if="isGenerating" class="message message-assistant">
                <div class="message-avatar">🤖</div>
                <div class="message-content">
                    <div class="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                    <div class="message-time">AI 正在思考中...</div>
                </div>
            </div>
        </div>

        <!-- Input Area -->
        <div class="input-container" :class="{ 'edit-mode': isEditMode }">
            <!-- 编辑模式提示 -->
            <div v-if="isEditMode" class="edit-hint">
                <span class="edit-hint-icon">✏️</span>
                <span class="edit-hint-text">编辑模式：修改问题后按Enter重新发送</span>
                <button class="edit-hint-cancel" @click="cancelEdit">取消</button>
            </div>
            
            <!-- 附件显示 -->
            <div v-if="attachedFiles.length > 0" class="attached-files">
                <div v-for="(file, index) in attachedFiles" :key="index" class="attached-file">
                    <span class="file-icon">📎</span>
                    <span class="file-name">{{ file.name }}</span>
                    <span class="file-size">({{ (file.size / 1024).toFixed(1) }}KB)</span>
                    <button class="file-remove" @click="removeFile(index)">×</button>
                </div>
            </div>
            
            <div class="input-wrapper">
                <!-- 选项面板 -->
                <div v-show="showOptions" class="input-options-panel">
                    <label class="option-label">
                        <input type="checkbox" v-model="useKnowledgeBase">
                        <span>知识库</span>
                    </label>
                    <button class="option-attach" @click="$refs.fileInput.click()">
                        <span>📎 上传文件</span>
                    </button>
                </div>
                
                <div class="input-box">
                    <textarea
                        v-model="messageInput"
                        @keydown="handleKeyDown"
                        placeholder="输入消息... (Enter发送, Shift+Enter换行)"
                        class="message-input"
                        rows="3"
                        :disabled="isLoading"
                    ></textarea>
                    <div class="input-controls">
                        <button class="btn-icon" @click="toggleOptions" title="更多选项">
                            ＋
                        </button>
                        <button
                            v-if="!isGenerating"
                            @click="sendMessage"
                            class="send-btn"
                            :disabled="!messageInput.trim()"
                            title="发送消息"
                        >
                            ↑
                        </button>
                        <button
                            v-else
                            @click="stopGeneration"
                            class="send-btn stop-btn"
                            title="停止生成"
                        >
                            ■
                        </button>
                    </div>
                </div>
                
                <!-- 隐藏的文件输入 -->
                <input
                    ref="fileInput"
                    type="file"
                    multiple
                    accept="image/*,.pdf,.doc,.docx,.txt"
                    @change="handleFileSelect"
                    style="display: none;"
                />
            </div>
        </div>
    </div>
</template>

<style scoped>
.chat-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--bg-secondary);
}

.generation-notice {
    background: linear-gradient(90deg, #4CAF50 0%, #2196F3 100%);
    color: white;
    padding: 8px 16px;
    text-align: center;
    font-size: 13px;
    font-weight: 500;
    animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
    0%, 100% {
        opacity: 1;
    }
    50% {
        opacity: 0.8;
    }
}

.notice-content {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}

.notice-icon {
    font-size: 16px;
    animation: rotate 2s linear infinite;
}

@keyframes rotate {
    from {
        transform: rotate(0deg);
    }
    to {
        transform: rotate(360deg);
    }
}

.notice-text {
    font-size: 13px;
}

.messages-container {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
}

.message {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    animation: fadeIn 0.3s ease;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.message.editing-active {
    transform: scale(1.05);
    box-shadow: 
        0 0 0 3px rgba(255, 152, 0, 0.3),
        0 8px 24px rgba(255, 152, 0, 0.2),
        0 16px 48px rgba(255, 152, 0, 0.1);
    animation: editPulse 2s ease-in-out infinite;
}

@keyframes editPulse {
    0%, 100% {
        box-shadow: 
            0 0 0 3px rgba(255, 152, 0, 0.3),
            0 8px 24px rgba(255, 152, 0, 0.2),
            0 16px 48px rgba(255, 152, 0, 0.1);
    }
    50% {
        box-shadow: 
            0 0 0 5px rgba(255, 152, 0, 0.4),
            0 12px 32px rgba(255, 152, 0, 0.3),
            0 20px 56px rgba(255, 152, 0, 0.15);
    }
}

/* 编辑模式时模糊其他消息 */
.messages-container:has(.editing-active) .message:not(.editing-active) {
    filter: blur(3px);
    opacity: 0.4;
    transition: all 0.3s ease;
}

@keyframes fadeIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.message-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: var(--bg-tertiary);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
}

.message-content-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.message-content {
    background: var(--bg-primary);
    padding: 12px 16px;
    border-radius: 12px;
    border: 1px solid var(--border-primary);
}

.message-user .message-content {
    background: var(--primary-light);
    border-color: var(--primary-color);
}

.message-error .message-content {
    background: #fee;
    border-color: #fcc;
}

.message-info .message-content {
    background: #e3f2fd;
    border-color: #90caf9;
}

.message-system .message-avatar {
    background: #e3f2fd;
}

.message-info .message-avatar {
    background: #e3f2fd;
}

.message-text {
    color: var(--text-primary);
    line-height: 1.8;
    word-wrap: break-word;
}

.message-text :deep(p) {
    margin: 0.5em 0;
}

.message-text :deep(ul), .message-text :deep(ol) {
    margin: 0.5em 0;
    padding-left: 1.5em;
}

.message-text :deep(li) {
    margin: 0.3em 0;
}

.message-text :deep(code) {
    background: var(--bg-tertiary);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.9em;
    font-family: var(--font-mono);
}

.message-text :deep(pre) {
    background: var(--bg-tertiary);
    padding: 12px;
    border-radius: 8px;
    overflow-x: auto;
    margin: 0.8em 0;
}

.message-text :deep(pre code) {
    background: none;
    padding: 0;
}

.message-time {
    font-size: 11px;
    color: var(--text-secondary);
    margin-top: 6px;
    opacity: 0.8;
}

.typing-indicator {
    display: flex;
    gap: 4px;
    padding: 8px 0;
}

.typing-indicator span {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-tertiary);
    animation: typing 1.4s infinite;
}

.typing-indicator span:nth-child(2) {
    animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
    animation-delay: 0.4s;
}

@keyframes typing {
    0%, 60%, 100% {
        transform: translateY(0);
        opacity: 0.4;
    }
    30% {
        transform: translateY(-10px);
        opacity: 1;
    }
}

.input-container {
    padding: 16px 20px;
    background: var(--bg-primary);
    border-top: 1px solid var(--border-primary);
}

.attached-files {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 12px;
}

.attached-file {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background: var(--bg-tertiary);
    border-radius: 6px;
    font-size: 13px;
}

.file-icon {
    font-size: 14px;
}

.file-name {
    color: var(--text-primary);
}

.file-size {
    color: var(--text-tertiary);
    font-size: 11px;
}

.file-remove {
    background: none;
    border: none;
    color: var(--text-tertiary);
    cursor: pointer;
    font-size: 18px;
    padding: 0 4px;
    line-height: 1;
}

.file-remove:hover {
    color: var(--error-color);
}

.input-wrapper {
    position: relative;
}

.input-options-panel {
    display: flex;
    gap: 12px;
    padding: 8px 12px;
    background: var(--bg-tertiary);
    border-radius: 8px 8px 0 0;
    margin-bottom: -1px;
}

.option-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    cursor: pointer;
}

.option-label input[type="checkbox"] {
    cursor: pointer;
}

.option-attach {
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 13px;
    padding: 4px 8px;
    border-radius: 4px;
    transition: all 0.2s;
}

.option-attach:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
}

.input-box {
    display: flex;
    gap: 8px;
    align-items: flex-end;
}

.message-input {
    flex: 1;
    padding: 12px;
    border: 1px solid var(--border-secondary);
    border-radius: 8px;
    background: var(--bg-secondary);
    color: var(--text-primary);
    font-size: 14px;
    font-family: inherit;
    resize: none;
    transition: border-color 0.2s;
}

.message-input:focus {
    outline: none;
    border-color: var(--primary-color);
}

.message-input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.input-controls {
    display: flex;
    gap: 8px;
    align-items: center;
}

.send-btn {
    width: 40px;
    height: 40px;
    border-radius: 8px;
    background: var(--primary-color);
    color: white;
    border: none;
    font-size: 20px;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
}

.send-btn:hover:not(:disabled) {
    background: var(--primary-hover);
    transform: translateY(-1px);
}

.send-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.stop-btn {
    background: #f44336;
}

.stop-btn:hover:not(:disabled) {
    background: #d32f2f;
}

/* 消息操作按钮 */
.message-actions {
    display: flex;
    gap: 8px;
    align-items: center;
    padding-left: 48px; /* 与消息内容对齐 */
}

.action-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border: none;
    background: transparent;
    color: var(--text-tertiary);
    font-size: 13px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
    font-family: inherit;
}

.action-btn:hover {
    background: rgba(255, 152, 0, 0.1);
    color: #ff9800;
}

.action-btn svg {
    flex-shrink: 0;
}

.action-text {
    font-size: 13px;
}

.copy-btn.copied {
    color: #4CAF50;
}

/* 编辑提示条 */
.edit-hint {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    background: linear-gradient(90deg, #ff9800 0%, #ff6b6b 100%);
    color: white;
    border-radius: 8px 8px 0 0;
    font-size: 13px;
    font-weight: 500;
}

.edit-hint-icon {
    font-size: 16px;
}

.edit-hint-text {
    flex: 1;
}

.edit-hint-cancel {
    padding: 4px 12px;
    background: rgba(255, 255, 255, 0.2);
    border: none;
    color: white;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
    transition: all 0.2s;
}

.edit-hint-cancel:hover {
    background: rgba(255, 255, 255, 0.3);
}

/* 编辑模式下的输入框 */
.input-container.edit-mode .message-input {
    border-color: #ff9800;
    box-shadow: 0 0 0 3px rgba(255, 152, 0, 0.1);
}

.input-container.edit-mode .send-btn {
    background: #ff9800;
}

.input-container.edit-mode .send-btn:hover:not(:disabled) {
    background: #f57c00;
}

/* 响应式设计 */
@media (max-width: 768px) {
    .message-actions {
        padding-left: 12px;
    }
    
    .action-text {
        display: none;
    }
    
    .action-btn {
        padding: 6px;
        min-width: 32px;
        justify-content: center;
    }
}
</style>
