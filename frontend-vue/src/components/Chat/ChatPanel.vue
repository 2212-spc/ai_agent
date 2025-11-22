<script setup>
import { ref, computed, nextTick, watch } from 'vue';
import { useChatStore } from '../../stores/chat';
import { marked } from 'marked';

const chatStore = useChatStore();
const messageInput = ref('');
const chatContainer = ref(null);

const messages = computed(() => chatStore.messages);
const isLoading = computed(() => chatStore.isLoading);

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
                :class="[`message-${msg.role}`, msg.type === 'error' ? 'message-error' : '']"
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
            <textarea
                v-model="messageInput"
                @keydown="handleKeyDown"
                placeholder="输入消息... (Enter发送, Shift+Enter换行)"
                class="message-input"
                rows="3"
                :disabled="isLoading"
            ></textarea>
            <button
                @click="sendMessage"
                class="btn btn-primary send-btn"
                :disabled="!messageInput.trim() || isLoading"
            >
                {{ isLoading ? '发送中...' : '发送' }}
            </button>
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

.message-text {
    color: var(--text-primary);
    line-height: 1.6;
    word-wrap: break-word;
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
    padding: 16px;
    background: var(--bg-primary);
    border-top: 1px solid var(--border-primary);
    display: flex;
    gap: 12px;
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

.send-btn {
    height: 40px;
    min-width: 80px;
}
</style>
