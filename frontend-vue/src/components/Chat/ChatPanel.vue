<script setup>
import { ref, computed, nextTick, watch } from 'vue';
import { useChatStore } from '../../stores/chat';
import { marked } from 'marked';
import axios from 'axios';

const chatStore = useChatStore();
const messageInput = ref('');
const chatContainer = ref(null);
const fileInput = ref(null);
const attachedFiles = ref([]);
const showOptions = ref(false);

const messages = computed(() => chatStore.messages);
const isLoading = computed(() => chatStore.isLoading);
const useKnowledgeBase = computed({
    get: () => chatStore.useKnowledgeBase,
    set: (val) => chatStore.setUseKnowledgeBase(val)
});

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
    if (!content || isLoading.value) return;

    try {
        await chatStore.sendMessage(content);
        messageInput.value = '';
        await nextTick();
        scrollToBottom();
    } catch (error) {
        console.error('发送失败:', error);
    }
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
                :class="[`message-${msg.role}`, msg.type === 'error' ? 'message-error' : '', msg.type === 'info' ? 'message-info' : '']"
            >
                <div class="message-avatar">
                    {{ msg.role === 'user' ? '👤' : msg.role === 'assistant' ? '🤖' : '⚠️' }}
                </div>
                <div class="message-content">
                    <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
                    <div class="message-time">{{ new Date(msg.timestamp).toLocaleTimeString() }}</div>
                </div>
            </div>

            <div v-if="isLoading" class="message message-assistant">
                <div class="message-avatar">🤖</div>
                <div class="message-content">
                    <div class="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Input Area -->
        <div class="input-container">
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
                            @click="sendMessage"
                            class="send-btn"
                            :disabled="!messageInput.trim() || isLoading"
                        >
                            ↑
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

.message-content {
    flex: 1;
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
    color: var(--text-tertiary);
    margin-top: 6px;
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
</style>
