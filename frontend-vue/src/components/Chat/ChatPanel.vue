<script setup>
/**
 * ChatPanel - Redesigned with Cosmic Tech Design System
 * Features: Premium message bubbles, animations, modern UI
 */

import { ref, computed, nextTick, watch, onMounted } from 'vue';
import { useChatStore } from '../../stores/chat';
import { marked } from 'marked';
import axios from 'axios';
import Icon from '../ui/Icon.vue';

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

const isGenerating = computed(() => {
    return sessionStatus.value === chatStore.SESSION_STATUS.GENERATING;
});

watch(isGenerating, (newVal, oldVal) => {
    if (oldVal === true && newVal === false) {
        nextTick(() => {
            scrollToBottom();
            setTimeout(() => scrollToBottom(), 100);
        });
    }
});

const isEditMode = computed(() => editingMessageId.value !== null);

async function handleFileSelect(event) {
    const files = Array.from(event.target.files);

    for (const file of files) {
        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await axios.post('http://127.0.0.1:8000/documents/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            attachedFiles.value.push({
                name: file.name,
                size: file.size,
                id: response.data.id
            });
        } catch (error) {
            console.error('File upload failed:', error);
        }
    }

    event.target.value = '';
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
        if (editingMessageId.value !== null) {
            await completeEdit(content);
            return;
        }

        messageInput.value = '';
        await chatStore.sendMessage(content, (streamContent, sessionId) => {
            if (sessionId === currentSessionId.value) {
                nextTick(() => scrollToBottom());
            }
        });

        await nextTick();
        scrollToBottom();
        setTimeout(() => scrollToBottom(), 100);
        setTimeout(() => scrollToBottom(), 300);
    } catch (error) {
        console.error('Send failed:', error);
    }
}

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
        console.error('Copy failed:', error);
    }
}

function editMessage(messageId) {
    const message = messages.value.find(m => m.id === messageId);
    if (!message || message.role !== 'user') return;

    if (isGenerating.value) {
        stopGeneration();
    }

    editingMessageId.value = messageId;
    messageInput.value = message.content;

    nextTick(() => {
        const textarea = document.querySelector('.message-input');
        if (textarea) textarea.focus();
    });
}

function cancelEdit() {
    editingMessageId.value = null;
    messageInput.value = '';
}

async function completeEdit(newContent) {
    if (!editingMessageId.value || !newContent.trim()) {
        cancelEdit();
        return;
    }

    try {
        await chatStore.editAndResendMessage(editingMessageId.value, newContent, (streamContent, sessionId) => {
            if (sessionId === currentSessionId.value) {
                nextTick(() => scrollToBottom());
            }
        });

        messageInput.value = '';
        editingMessageId.value = null;

        await nextTick();
        scrollToBottom();
    } catch (error) {
        console.error('Edit failed:', error);
    }
}

function stopGeneration() {
    chatStore.stopGeneration(currentSessionId.value);
}

async function regenerateMessage(messageId) {
    if (isGenerating.value) return;

    try {
        await chatStore.regenerateAnswer(messageId, (streamContent, sessionId) => {
            if (sessionId === currentSessionId.value) {
                nextTick(() => scrollToBottom());
            }
        });

        await nextTick();
        scrollToBottom();
        setTimeout(() => scrollToBottom(), 100);
    } catch (error) {
        console.error('Regenerate failed:', error);
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

watch(messages, (newMessages, oldMessages) => {
    const needScroll = newMessages.length !== oldMessages?.length ||
                      (newMessages.length > 0 && oldMessages?.length > 0 &&
                       newMessages[newMessages.length - 1]?.content !== oldMessages[oldMessages.length - 1]?.content);

    if (needScroll) {
        nextTick(() => {
            scrollToBottom();
            setTimeout(() => scrollToBottom(), 50);
        });
    }
}, { deep: true });
</script>

<template>
    <div class="chat-panel">
        <!-- Generation Notice -->
        <Transition name="slide-down">
            <div v-if="isGenerating" class="generation-notice">
                <div class="notice-content">
                    <div class="notice-spinner">
                        <Icon name="sparkles" :size="18" class="animate-pulse" />
                    </div>
                    <span class="notice-text">AI 正在生成回复...</span>
                    <button class="notice-stop" @click="stopGeneration">
                        <Icon name="stop" :size="14" />
                        停止
                    </button>
                </div>
            </div>
        </Transition>

        <!-- Messages Area -->
        <div class="messages-container" ref="chatContainer">
            <!-- Empty State -->
            <div v-if="messages.length === 0" class="empty-state">
                <div class="empty-icon">
                    <Icon name="chat-bubble" :size="48" />
                </div>
                <h3 class="empty-title">开始对话</h3>
                <p class="empty-subtitle">输入消息开始与 AI Agent 对话</p>
                <div class="empty-suggestions">
                    <button class="suggestion-chip" @click="messageInput = '帮我分析一下...'">
                        <Icon name="sparkles" :size="14" />
                        帮我分析一下...
                    </button>
                    <button class="suggestion-chip" @click="messageInput = '请解释...'">
                        <Icon name="light-bulb" :size="14" />
                        请解释...
                    </button>
                    <button class="suggestion-chip" @click="messageInput = '如何实现...'">
                        <Icon name="cpu-chip" :size="14" />
                        如何实现...
                    </button>
                </div>
            </div>

            <!-- Messages -->
            <TransitionGroup name="message-list" tag="div" class="messages-list">
                <div
                    v-for="(msg, index) in messages"
                    :key="msg.id"
                    class="message-wrapper"
                    :class="[
                        `message-${msg.role}`,
                        { 'is-editing': editingMessageId === msg.id },
                        { 'is-error': msg.type === 'error' },
                        { 'is-info': msg.type === 'info' }
                    ]"
                    :style="{ '--index': index }"
                >
                    <!-- Avatar -->
                    <div class="message-avatar" :class="`avatar-${msg.role}`">
                        <Icon v-if="msg.role === 'user'" name="user" :size="18" />
                        <Icon v-else-if="msg.role === 'assistant'" name="sparkles" :size="18" />
                        <Icon v-else name="exclamation-circle" :size="18" />
                    </div>

                    <!-- Content -->
                    <div class="message-body">
                        <!-- Thinking Steps Panel -->
                        <div v-if="msg.thinkingSteps && msg.thinkingSteps.length > 0" class="thinking-panel">
                            <div class="thinking-header">
                                <Icon name="brain" :size="16" />
                                <span class="thinking-title">思考过程</span>
                                <span class="thinking-badge">{{ msg.thinkingSteps.length }} 步骤</span>
                            </div>
                            <div class="thinking-steps">
                                <div
                                    v-for="(step, stepIndex) in msg.thinkingSteps"
                                    :key="stepIndex"
                                    class="thinking-step"
                                    :class="step.status"
                                >
                                    <div class="step-indicator">
                                        <span class="step-number">{{ stepIndex + 1 }}</span>
                                    </div>
                                    <div class="step-content">
                                        <div class="step-title">{{ step.title }}</div>
                                        <div class="step-text">{{ step.content }}</div>
                                    </div>
                                    <div class="step-status">
                                        <Icon v-if="step.status === 'completed'" name="check-circle" :size="16" class="status-completed" />
                                        <Icon v-else-if="step.status === 'processing'" name="refresh" :size="16" class="status-processing animate-spin" />
                                        <div v-else class="status-pending"></div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Message Bubble -->
                        <div class="message-bubble">
                            <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
                        </div>

                        <!-- Message Meta -->
                        <div class="message-meta">
                            <span class="message-time">
                                {{ new Date(msg.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}
                            </span>

                            <!-- Actions -->
                            <div class="message-actions">
                                <!-- Edit (User only) -->
                                <button
                                    v-if="msg.role === 'user'"
                                    class="action-btn"
                                    @click="editMessage(msg.id)"
                                    title="编辑消息"
                                >
                                    <Icon name="pencil" :size="14" />
                                </button>

                                <!-- Regenerate (Assistant only) -->
                                <button
                                    v-if="msg.role === 'assistant'"
                                    class="action-btn action-regenerate"
                                    @click="regenerateMessage(msg.id)"
                                    :disabled="isGenerating"
                                    title="重新生成"
                                >
                                    <Icon name="refresh" :size="14" />
                                </button>

                                <!-- Copy -->
                                <button
                                    class="action-btn"
                                    :class="{ 'is-copied': copiedMessageId === msg.id }"
                                    @click="copyMessage(msg.id)"
                                    :title="copiedMessageId === msg.id ? '已复制' : '复制'"
                                >
                                    <Icon :name="copiedMessageId === msg.id ? 'check' : 'copy'" :size="14" />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </TransitionGroup>

            <!-- Typing Indicator -->
            <Transition name="fade-up">
                <div v-if="isGenerating && messages.length > 0" class="message-wrapper message-assistant">
                    <div class="message-avatar avatar-assistant">
                        <Icon name="sparkles" :size="18" class="animate-pulse" />
                    </div>
                    <div class="message-body">
                        <div class="message-bubble typing-bubble">
                            <div class="typing-indicator">
                                <span></span>
                                <span></span>
                                <span></span>
                            </div>
                        </div>
                    </div>
                </div>
            </Transition>
        </div>

        <!-- Input Area -->
        <div class="input-area" :class="{ 'is-edit-mode': isEditMode }">
            <!-- Edit Mode Banner -->
            <Transition name="slide-down">
                <div v-if="isEditMode" class="edit-banner">
                    <Icon name="pencil" :size="16" />
                    <span>编辑模式：修改后按 Enter 重新发送</span>
                    <button class="edit-cancel" @click="cancelEdit">
                        <Icon name="x" :size="14" />
                        取消
                    </button>
                </div>
            </Transition>

            <!-- Attached Files -->
            <Transition name="slide-down">
                <div v-if="attachedFiles.length > 0" class="attached-files">
                    <div v-for="(file, index) in attachedFiles" :key="index" class="attached-file">
                        <Icon name="document" :size="14" />
                        <span class="file-name">{{ file.name }}</span>
                        <span class="file-size">({{ (file.size / 1024).toFixed(1) }}KB)</span>
                        <button class="file-remove" @click="removeFile(index)">
                            <Icon name="x" :size="12" />
                        </button>
                    </div>
                </div>
            </Transition>

            <!-- Input Box -->
            <div class="input-wrapper">
                <!-- Options Panel -->
                <Transition name="slide-up">
                    <div v-show="showOptions" class="options-panel">
                        <label class="option-item">
                            <input type="checkbox" v-model="useKnowledgeBase" class="option-checkbox">
                            <Icon name="database" :size="16" />
                            <span>知识库检索</span>
                        </label>
                        <button class="option-item" @click="$refs.fileInput.click()">
                            <Icon name="attachment" :size="16" />
                            <span>上传文件</span>
                        </button>
                    </div>
                </Transition>

                <div class="input-box">
                    <button class="input-action" @click="toggleOptions" :class="{ 'is-active': showOptions }">
                        <Icon name="plus" :size="20" />
                    </button>

                    <textarea
                        v-model="messageInput"
                        @keydown="handleKeyDown"
                        placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
                        class="message-input"
                        rows="1"
                        :disabled="isLoading"
                    ></textarea>

                    <button
                        v-if="!isGenerating"
                        @click="sendMessage"
                        class="send-btn"
                        :class="{ 'is-active': messageInput.trim() }"
                        :disabled="!messageInput.trim()"
                        title="发送消息"
                    >
                        <Icon name="arrow-up" :size="18" />
                    </button>
                    <button
                        v-else
                        @click="stopGeneration"
                        class="send-btn stop-btn"
                        title="停止生成"
                    >
                        <Icon name="stop" :size="18" />
                    </button>
                </div>

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
/* ==================== LAYOUT ==================== */
.chat-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--bg-secondary);
    position: relative;
}

/* ==================== GENERATION NOTICE ==================== */
.generation-notice {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    z-index: 10;
    background: var(--gradient-primary);
    padding: var(--space-2) var(--space-4);
    box-shadow: var(--shadow-md);
}

.notice-content {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-3);
}

.notice-spinner {
    color: white;
}

.notice-text {
    color: white;
    font-size: var(--text-sm);
    font-weight: var(--font-medium);
}

.notice-stop {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-1) var(--space-3);
    background: rgba(255, 255, 255, 0.2);
    border: none;
    border-radius: var(--radius-full);
    color: white;
    font-size: var(--text-xs);
    font-weight: var(--font-medium);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.notice-stop:hover {
    background: rgba(255, 255, 255, 0.3);
}

/* ==================== MESSAGES CONTAINER ==================== */
.messages-container {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-6);
    scroll-behavior: smooth;
}

/* ==================== EMPTY STATE ==================== */
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    padding: var(--space-8);
    text-align: center;
}

.empty-icon {
    width: 80px;
    height: 80px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--gradient-primary);
    border-radius: var(--radius-2xl);
    color: white;
    margin-bottom: var(--space-6);
    animation: float 3s ease-in-out infinite;
}

@keyframes float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
}

.empty-title {
    font-family: var(--font-display);
    font-size: var(--text-2xl);
    font-weight: var(--font-semibold);
    color: var(--text-primary);
    margin: 0 0 var(--space-2);
}

.empty-subtitle {
    font-size: var(--text-base);
    color: var(--text-secondary);
    margin: 0 0 var(--space-6);
}

.empty-suggestions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    justify-content: center;
}

.suggestion-chip {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-4);
    background: var(--bg-primary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-full);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.suggestion-chip:hover {
    background: var(--bg-brand);
    border-color: var(--brand-primary-300);
    color: var(--brand-primary-600);
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}

/* ==================== MESSAGES LIST ==================== */
.messages-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
}

/* ==================== MESSAGE WRAPPER ==================== */
.message-wrapper {
    display: flex;
    gap: var(--space-3);
    animation: fadeInUp 0.4s var(--ease-out) forwards;
    animation-delay: calc(var(--index, 0) * 50ms);
}

@keyframes fadeInUp {
    from {
        opacity: 0;
        transform: translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.message-wrapper.is-editing {
    position: relative;
    z-index: 5;
}

.message-wrapper.is-editing::before {
    content: '';
    position: absolute;
    inset: -8px;
    background: var(--warning-100);
    border: 2px solid var(--warning-500);
    border-radius: var(--radius-xl);
    animation: pulseGlow 2s ease-in-out infinite;
}

@keyframes pulseGlow {
    0%, 100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.3); }
    50% { box-shadow: 0 0 20px 5px rgba(245, 158, 11, 0.2); }
}

/* ==================== AVATAR ==================== */
.message-avatar {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-xl);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: all var(--transition-fast);
}

.avatar-user {
    background: var(--gradient-secondary);
    color: white;
}

.avatar-assistant {
    background: var(--gradient-primary);
    color: white;
    box-shadow: var(--shadow-brand);
}

.avatar-system {
    background: var(--warning-100);
    color: var(--warning-600);
}

/* ==================== MESSAGE BODY ==================== */
.message-body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
}

/* ==================== THINKING PANEL ==================== */
.thinking-panel {
    background: var(--gradient-cosmic);
    border-radius: var(--radius-xl);
    overflow: hidden;
    box-shadow: var(--shadow-lg);
}

.thinking-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3) var(--space-4);
    background: rgba(255, 255, 255, 0.1);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    color: white;
}

.thinking-title {
    font-weight: var(--font-semibold);
    font-size: var(--text-sm);
    flex: 1;
}

.thinking-badge {
    background: rgba(255, 255, 255, 0.2);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-full);
    font-size: var(--text-xs);
}

.thinking-steps {
    padding: var(--space-3);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    max-height: 300px;
    overflow-y: auto;
}

.thinking-step {
    display: flex;
    gap: var(--space-3);
    padding: var(--space-3);
    background: rgba(255, 255, 255, 0.95);
    border-radius: var(--radius-lg);
    align-items: flex-start;
}

.step-indicator {
    width: 24px;
    height: 24px;
    border-radius: var(--radius-full);
    background: var(--gradient-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.step-number {
    color: white;
    font-size: var(--text-xs);
    font-weight: var(--font-bold);
}

.step-content {
    flex: 1;
    min-width: 0;
}

.step-title {
    font-weight: var(--font-semibold);
    font-size: var(--text-sm);
    color: var(--text-primary);
    margin-bottom: var(--space-1);
}

.step-text {
    font-size: var(--text-sm);
    color: var(--text-secondary);
    line-height: var(--leading-relaxed);
}

.step-status {
    flex-shrink: 0;
}

.status-completed {
    color: var(--success-500);
}

.status-processing {
    color: var(--brand-primary-500);
}

.status-pending {
    width: 16px;
    height: 16px;
    border-radius: var(--radius-full);
    border: 2px solid var(--border-secondary);
}

/* ==================== MESSAGE BUBBLE ==================== */
.message-bubble {
    background: var(--bg-primary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-2xl);
    padding: var(--space-4);
    box-shadow: var(--shadow-sm);
    transition: all var(--transition-fast);
    position: relative;
}

.message-wrapper:hover .message-bubble {
    box-shadow: var(--shadow-md);
}

.message-user .message-bubble {
    background: var(--bg-brand);
    border-color: var(--brand-primary-200);
}

.message-wrapper.is-error .message-bubble {
    background: var(--error-50);
    border-color: var(--error-200);
}

.message-wrapper.is-info .message-bubble {
    background: var(--info-50);
    border-color: var(--info-200);
}

/* ==================== MESSAGE TEXT ==================== */
.message-text {
    color: var(--text-primary);
    font-size: var(--text-base);
    line-height: var(--leading-relaxed);
    word-wrap: break-word;
}

.message-text :deep(p) {
    margin: 0 0 var(--space-3);
}

.message-text :deep(p:last-child) {
    margin-bottom: 0;
}

.message-text :deep(ul),
.message-text :deep(ol) {
    margin: var(--space-2) 0;
    padding-left: var(--space-6);
}

.message-text :deep(li) {
    margin: var(--space-1) 0;
}

.message-text :deep(code) {
    background: var(--bg-tertiary);
    padding: var(--space-0\.5) var(--space-1);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: 0.9em;
    color: var(--brand-primary-600);
}

.message-text :deep(pre) {
    background: var(--slate-900);
    color: var(--slate-100);
    padding: var(--space-4);
    border-radius: var(--radius-lg);
    overflow-x: auto;
    margin: var(--space-3) 0;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
}

.message-text :deep(pre code) {
    background: none;
    padding: 0;
    color: inherit;
}

.message-text :deep(blockquote) {
    border-left: 4px solid var(--brand-primary-400);
    padding-left: var(--space-4);
    margin: var(--space-3) 0;
    color: var(--text-secondary);
    font-style: italic;
}

.message-text :deep(a) {
    color: var(--text-link);
    text-decoration: none;
}

.message-text :deep(a:hover) {
    text-decoration: underline;
}

.message-text :deep(h1),
.message-text :deep(h2),
.message-text :deep(h3) {
    font-family: var(--font-display);
    font-weight: var(--font-semibold);
    margin: var(--space-4) 0 var(--space-2);
    color: var(--text-primary);
}

.message-text :deep(h1) { font-size: var(--text-xl); }
.message-text :deep(h2) { font-size: var(--text-lg); }
.message-text :deep(h3) { font-size: var(--text-base); }

/* ==================== MESSAGE META ==================== */
.message-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--space-1);
}

.message-time {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
}

.message-actions {
    display: flex;
    gap: var(--space-1);
    opacity: 0;
    transition: opacity var(--transition-fast);
}

.message-wrapper:hover .message-actions {
    opacity: 1;
}

.action-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
    color: var(--text-tertiary);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.action-btn:hover {
    background: var(--bg-brand);
    color: var(--brand-primary-600);
}

.action-btn.is-copied {
    background: var(--success-100);
    color: var(--success-600);
}

.action-btn.action-regenerate:hover {
    background: var(--success-100);
    color: var(--success-600);
}

.action-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

/* ==================== TYPING INDICATOR ==================== */
.typing-bubble {
    display: inline-block;
    padding: var(--space-3) var(--space-4);
}

.typing-indicator {
    display: flex;
    gap: 4px;
}

.typing-indicator span {
    width: 8px;
    height: 8px;
    border-radius: var(--radius-full);
    background: var(--brand-primary-400);
    animation: typingBounce 1.4s ease-in-out infinite;
}

.typing-indicator span:nth-child(2) {
    animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
    animation-delay: 0.4s;
}

@keyframes typingBounce {
    0%, 60%, 100% {
        transform: translateY(0);
        opacity: 0.4;
    }
    30% {
        transform: translateY(-8px);
        opacity: 1;
    }
}

/* ==================== INPUT AREA ==================== */
.input-area {
    padding: var(--space-4);
    background: var(--bg-primary);
    border-top: 1px solid var(--border-primary);
}

.input-area.is-edit-mode {
    background: var(--warning-50);
    border-color: var(--warning-300);
}

/* Edit Banner */
.edit-banner {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-4);
    background: var(--gradient-aurora);
    border-radius: var(--radius-lg);
    margin-bottom: var(--space-3);
    color: white;
    font-size: var(--text-sm);
    font-weight: var(--font-medium);
}

.edit-cancel {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    margin-left: auto;
    padding: var(--space-1) var(--space-2);
    background: rgba(255, 255, 255, 0.2);
    border: none;
    border-radius: var(--radius-md);
    color: white;
    font-size: var(--text-xs);
    cursor: pointer;
    transition: background var(--transition-fast);
}

.edit-cancel:hover {
    background: rgba(255, 255, 255, 0.3);
}

/* Attached Files */
.attached-files {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
}

.attached-file {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: var(--bg-tertiary);
    border-radius: var(--radius-lg);
    font-size: var(--text-sm);
    color: var(--text-secondary);
}

.file-name {
    color: var(--text-primary);
    font-weight: var(--font-medium);
}

.file-size {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
}

.file-remove {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    background: var(--bg-secondary);
    border: none;
    border-radius: var(--radius-full);
    color: var(--text-tertiary);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.file-remove:hover {
    background: var(--error-100);
    color: var(--error-600);
}

/* Options Panel */
.options-panel {
    display: flex;
    gap: var(--space-4);
    padding: var(--space-3);
    background: var(--bg-tertiary);
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    margin-bottom: -1px;
}

.option-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: var(--bg-primary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.option-item:hover {
    border-color: var(--brand-primary-300);
    color: var(--brand-primary-600);
}

.option-checkbox {
    accent-color: var(--brand-primary-500);
}

/* Input Box */
.input-wrapper {
    position: relative;
}

.input-box {
    display: flex;
    align-items: flex-end;
    gap: var(--space-2);
    padding: var(--space-3);
    background: var(--bg-secondary);
    border: 2px solid var(--border-primary);
    border-radius: var(--radius-2xl);
    transition: all var(--transition-fast);
}

.input-box:focus-within {
    border-color: var(--brand-primary-400);
    box-shadow: 0 0 0 4px var(--brand-primary-100);
}

.is-edit-mode .input-box {
    border-color: var(--warning-400);
}

.is-edit-mode .input-box:focus-within {
    box-shadow: 0 0 0 4px var(--warning-100);
}

.input-action {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    background: transparent;
    border: none;
    border-radius: var(--radius-lg);
    color: var(--text-tertiary);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.input-action:hover,
.input-action.is-active {
    background: var(--bg-tertiary);
    color: var(--brand-primary-600);
}

.message-input {
    flex: 1;
    min-height: 36px;
    max-height: 200px;
    padding: var(--space-2) 0;
    background: transparent;
    border: none;
    outline: none;
    font-family: var(--font-body);
    font-size: var(--text-base);
    color: var(--text-primary);
    resize: none;
    line-height: var(--leading-normal);
}

.message-input::placeholder {
    color: var(--text-tertiary);
}

.message-input:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.send-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    background: var(--bg-tertiary);
    border: none;
    border-radius: var(--radius-xl);
    color: var(--text-tertiary);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.send-btn.is-active {
    background: var(--gradient-primary);
    color: white;
    box-shadow: var(--shadow-brand);
}

.send-btn.is-active:hover {
    transform: scale(1.05);
    box-shadow: var(--shadow-brand-lg);
}

.send-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.send-btn.stop-btn {
    background: var(--error-500);
    color: white;
}

.send-btn.stop-btn:hover {
    background: var(--error-600);
}

/* ==================== ANIMATIONS ==================== */
.slide-down-enter-active,
.slide-down-leave-active {
    transition: all var(--duration-normal) var(--ease-out);
}

.slide-down-enter-from,
.slide-down-leave-to {
    opacity: 0;
    transform: translateY(-10px);
}

.slide-up-enter-active,
.slide-up-leave-active {
    transition: all var(--duration-normal) var(--ease-out);
}

.slide-up-enter-from,
.slide-up-leave-to {
    opacity: 0;
    transform: translateY(10px);
}

.fade-up-enter-active,
.fade-up-leave-active {
    transition: all var(--duration-normal) var(--ease-out);
}

.fade-up-enter-from,
.fade-up-leave-to {
    opacity: 0;
    transform: translateY(20px);
}

.message-list-enter-active {
    transition: all var(--duration-slow) var(--ease-out);
}

.message-list-leave-active {
    transition: all var(--duration-fast) var(--ease-in);
}

.message-list-enter-from {
    opacity: 0;
    transform: translateY(20px);
}

.message-list-leave-to {
    opacity: 0;
    transform: translateX(-20px);
}

/* ==================== DARK MODE ==================== */
[data-theme="dark"] .message-bubble {
    background: var(--bg-elevated);
    border-color: var(--border-primary);
}

[data-theme="dark"] .message-user .message-bubble {
    background: rgba(139, 92, 246, 0.15);
    border-color: rgba(139, 92, 246, 0.3);
}

[data-theme="dark"] .input-box {
    background: var(--bg-tertiary);
}

[data-theme="dark"] .input-box:focus-within {
    box-shadow: 0 0 0 4px rgba(139, 92, 246, 0.2);
}

[data-theme="dark"] .suggestion-chip:hover {
    background: rgba(139, 92, 246, 0.15);
}

[data-theme="dark"] .thinking-step {
    background: rgba(255, 255, 255, 0.9);
}

/* ==================== RESPONSIVE ==================== */
@media (max-width: 768px) {
    .messages-container {
        padding: var(--space-4);
    }

    .message-wrapper {
        gap: var(--space-2);
    }

    .message-avatar {
        width: 32px;
        height: 32px;
    }

    .message-bubble {
        padding: var(--space-3);
    }

    .empty-suggestions {
        flex-direction: column;
    }

    .suggestion-chip {
        width: 100%;
        justify-content: center;
    }

    .input-area {
        padding: var(--space-3);
    }

    .options-panel {
        flex-direction: column;
        gap: var(--space-2);
    }

    .message-actions {
        opacity: 1;
    }
}
</style>
