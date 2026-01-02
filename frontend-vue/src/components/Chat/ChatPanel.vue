<script setup>
/**
 * ChatPanel - Redesigned with Cosmic Tech Design System
 * Features: Premium message bubbles, animations, modern UI
 */

import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue';
import { useChatStore } from '../../stores/chat';
import { marked } from 'marked';
import axios from 'axios';
import Icon from '../ui/Icon.vue';
import { API_BASE_URL } from '../../config/api';

const chatStore = useChatStore();
const messageInput = ref('');
const chatContainer = ref(null);
const inputAreaRef = ref(null);
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

            const response = await axios.post(`${API_BASE_URL}/documents/upload`, formData, {
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

onMounted(() => {
    scrollToBottom();
    
    // Mobile Fluid Layout Observer
    if (inputAreaRef.value && chatContainer.value) {
        const observer = new ResizeObserver(entries => {
            for (const entry of entries) {
                // Add padding to chat container to match input height + extra space
                // Use CSS variable for performance if needed, or direct style
                const height = entry.contentRect.height;
                chatContainer.value.style.paddingBottom = `${height + 20}px`;
            }
        });
        observer.observe(inputAreaRef.value);
        
        onUnmounted(() => {
            observer.disconnect();
        });
    }
});
</script>

<template>
    <div class="chat-panel chat-panel-immersive">
        <!-- 1. Dynamic Nebula Background -->
        <div class="nebula-background">
            <div class="nebula-layer layer-1"></div>
            <div class="nebula-layer layer-2"></div>
            <div class="stars"></div>
        </div>

        <!-- 2. HUD Overlay (Tactical Border) -->
        <div class="hud-overlay">
            <svg class="hud-corner top-left" viewBox="0 0 100 100">
                <path d="M0 40 V0 H40" fill="none" stroke="var(--brand-primary-500)" stroke-width="2" />
                <rect x="0" y="0" width="10" height="10" fill="var(--brand-primary-500)" opacity="0.5" />
            </svg>
            <svg class="hud-corner top-right" viewBox="0 0 100 100">
                <path d="M100 40 V0 H60" fill="none" stroke="var(--brand-primary-500)" stroke-width="2" />
                <rect x="90" y="0" width="10" height="10" fill="var(--brand-primary-500)" opacity="0.5" />
            </svg>
            <svg class="hud-corner bottom-left" viewBox="0 0 100 100">
                <path d="M0 60 V100 H40" fill="none" stroke="var(--brand-primary-500)" stroke-width="2" />
            </svg>
            <svg class="hud-corner bottom-right" viewBox="0 0 100 100">
                <path d="M100 60 V100 H60" fill="none" stroke="var(--brand-primary-500)" stroke-width="2" />
            </svg>
            <div class="hud-status">SYSTEM ONLINE // QUANTUM LINK ESTABLISHED</div>
        </div>

        <!-- 3. Holographic Thinking Core (3D Data Sphere) -->
        <Transition name="fade">
            <div v-if="isGenerating" class="holographic-core-container">
                <div class="holographic-core">
                    <div class="core-sphere-outer"></div>
                    <div class="core-sphere-inner"></div>
                    <div class="core-ring-x"></div>
                    <div class="core-ring-y"></div>
                    <div class="core-particles"></div>
                </div>
                <div class="holographic-status">
                    <span class="status-text">NEURAL PROCESSING</span>
                    <span class="status-dots">...</span>
                </div>
            </div>
        </Transition>

        <!-- Generation Notice -->
        <Transition name="slide-down">
            <div v-if="isGenerating" class="generation-notice glass-panel">
                <div class="notice-content">
                    <span class="notice-text">Thinking...</span>
                    <button class="notice-stop" @click="stopGeneration">
                        <Icon name="stop" :size="14" />
                    </button>
                </div>
            </div>
        </Transition>

        <!-- Messages Area -->
        <div class="messages-container" ref="chatContainer">
            <!-- Empty State -->
            <div v-if="messages.length === 0" class="empty-state">
                <div class="empty-visual">
                    <div class="holo-planet"></div>
                    <div class="holo-rings"></div>
                </div>
                <h3 class="empty-title">A.I. AGENT READY</h3>
                <p class="empty-subtitle">Quantum Core Initialized. Awaiting Input.</p>
                <div class="empty-suggestions">
                    <button class="suggestion-chip neon-chip" @click="messageInput = '帮我分析一下...'">
                        <Icon name="sparkles" :size="14" />
                        深度分析
                    </button>
                    <button class="suggestion-chip neon-chip" @click="messageInput = '请解释...'">
                        <Icon name="light-bulb" :size="14" />
                        概念解析
                    </button>
                    <button class="suggestion-chip neon-chip" @click="messageInput = '如何实现...'">
                        <Icon name="cpu-chip" :size="14" />
                        代码实现
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
                    <!-- Avatar (Neon Style) -->
                    <div class="message-avatar" :class="`avatar-${msg.role}`">
                        <Icon v-if="msg.role === 'user'" name="user" :size="18" />
                        <Icon v-else-if="msg.role === 'assistant'" name="sparkles" :size="18" />
                        <Icon v-else name="exclamation-circle" :size="18" />
                    </div>

                    <!-- Content -->
                    <div class="message-body">
                        <!-- Thinking Steps (Neural Stream) -->
                        <div v-if="msg.thinkingSteps && msg.thinkingSteps.length > 0" class="thinking-panel neon-panel">
                            <div class="thinking-header">
                                <Icon name="brain" :size="16" />
                                <span class="thinking-title">NEURAL STREAM</span>
                                <span class="thinking-badge">{{ msg.thinkingSteps.length }} NODES</span>
                            </div>
                            <div class="thinking-steps">
                                <div class="step-line"></div> <!-- Vertical Line -->
                                <div
                                    v-for="(step, stepIndex) in msg.thinkingSteps"
                                    :key="stepIndex"
                                    class="thinking-step"
                                    :class="step.status"
                                >
                                    <div class="step-dot"></div>
                                    <div class="step-content">
                                        <div class="step-title">{{ step.title }}</div>
                                        <div class="step-text">{{ step.content }}</div>
                                    </div>
                                    <div class="step-status-icon">
                                         <Icon v-if="step.status === 'completed'" name="check" :size="14" />
                                         <Icon v-else-if="step.status === 'processing'" name="refresh" :size="14" class="animate-spin" />
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Message Bubble (Glass) -->
                        <div class="message-bubble glass-bubble" :class="{ 'generating': isGenerating && index === messages.length - 1 && msg.role === 'assistant' }">
                            <div v-if="!msg.content && isGenerating && index === messages.length - 1 && msg.role === 'assistant'" class="typing-indicator">
                                <span></span><span></span><span></span>
                            </div>
                            <div v-else class="message-text" v-html="renderMarkdown(msg.content)"></div>
                        </div>

                        <!-- Meta -->
                        <div class="message-meta">
                            <span class="message-time">{{ new Date(msg.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}</span>
                            <div class="message-actions">
                                <button v-if="msg.role === 'user'" class="action-btn" @click="editMessage(msg.id)">
                                    <Icon name="pencil" :size="14" />
                                </button>
                                <button v-if="msg.role === 'assistant'" class="action-btn" @click="regenerateMessage(msg.id)" :disabled="isGenerating">
                                    <Icon name="refresh" :size="14" />
                                </button>
                                <button class="action-btn" @click="copyMessage(msg.id)">
                                    <Icon :name="copiedMessageId === msg.id ? 'check' : 'copy'" :size="14" />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </TransitionGroup>
        </div>

        <!-- Input Area (Quantum Field) -->
        <div class="input-area-container" ref="inputAreaRef">
            <div class="input-area glass-panel" :class="{ 'is-edit-mode': isEditMode }">
                <!-- Edit Banner -->
                <Transition name="slide-down">
                    <div v-if="isEditMode" class="edit-banner">
                        <Icon name="pencil" :size="16" />
                        <span>EDIT MODE</span>
                        <button class="edit-cancel" @click="cancelEdit">
                            <Icon name="x" :size="14" />
                        </button>
                    </div>
                </Transition>

                <!-- Files -->
                <Transition name="slide-down">
                    <div v-if="attachedFiles.length > 0" class="attached-files">
                        <div v-for="(file, index) in attachedFiles" :key="index" class="attached-file">
                            <Icon name="document" :size="14" />
                            <span class="file-name">{{ file.name }}</span>
                            <button class="file-remove" @click="removeFile(index)">
                                <Icon name="x" :size="12" />
                            </button>
                        </div>
                    </div>
                </Transition>

                <!-- Input Box Wrapper -->
                <div class="input-wrapper">
                    <!-- Options -->
                    <Transition name="slide-up">
                        <div v-show="showOptions" class="options-panel glass-panel">
                             <div class="option-item" :class="{ 'is-active': useKnowledgeBase }" @click="useKnowledgeBase = !useKnowledgeBase">
                                <Icon name="database" :size="20" />
                                <span>Knowledge</span>
                            </div>
                            <div class="option-item" @click="$refs.fileInput.click()">
                                <Icon name="attachment" :size="20" />
                                <span>Upload</span>
                            </div>
                        </div>
                    </Transition>

                    <!-- Quantum Input Box -->
                    <div class="input-box quantum-box">
                        <button class="input-action" @click="toggleOptions" :class="{ 'is-active': showOptions }">
                            <Icon name="plus" :size="20" />
                        </button>

                        <textarea
                            v-model="messageInput"
                            @keydown="handleKeyDown"
                            @focus="isInputFocused = true"
                            @blur="isInputFocused = false"
                            placeholder="Enter command..."
                            class="message-input"
                            rows="1"
                            :disabled="isLoading"
                        ></textarea>

                        <button
                            v-if="!isGenerating"
                            @click="sendMessage"
                            class="send-btn neon-send"
                            :class="{ 'is-active': messageInput.trim() }"
                            :disabled="!messageInput.trim()"
                        >
                            <Icon name="arrow-up" :size="18" />
                        </button>
                        <button
                            v-else
                            @click="stopGeneration"
                            class="send-btn stop-btn"
                        >
                            <Icon name="stop" :size="18" />
                        </button>
                    </div>

                    <input ref="fileInput" type="file" multiple style="display: none;" @change="handleFileSelect" />
                </div>
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

.chat-panel-immersive {
    position: relative;
    overflow: hidden;
}

.nebula-background {
    position: absolute;
    inset: 0;
    z-index: 0;
    pointer-events: none;
}

.nebula-layer {
    position: absolute;
    inset: 0;
    background: var(--gradient-mesh);
    background-size: 200% 200%;
    filter: blur(40px);
    opacity: 0.5;
    animation: gradientShift 22s ease-in-out infinite;
}

.nebula-layer.layer-2 {
    opacity: 0.35;
    animation-duration: 30s;
    mix-blend-mode: screen;
}

.stars {
    position: absolute;
    inset: 0;
    background-image: radial-gradient(rgba(255,255,255,0.15) 1px, transparent 1px);
    background-size: 2px 2px;
    opacity: 0.2;
}

.hud-overlay {
    position: absolute;
    inset: 0;
    z-index: 1;
    pointer-events: none;
}

.hud-corner {
    position: absolute;
    width: 100px;
    height: 100px;
    opacity: 0.6;
}

.hud-corner.top-left { top: 8px; left: 8px; }
.hud-corner.top-right { top: 8px; right: 8px; }
.hud-corner.bottom-left { bottom: 8px; left: 8px; }
.hud-corner.bottom-right { bottom: 8px; right: 8px; }

.hud-status {
    position: absolute;
    top: 8px;
    left: 50%;
    transform: translateX(-50%);
    font-size: var(--text-xs);
    color: var(--brand-primary-400);
    letter-spacing: 1px;
}

.glass-panel {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border-radius: var(--radius-xl);
}

.glass-bubble {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    box-shadow: var(--shadow-md);
}

.neon-chip {
    box-shadow: var(--shadow-brand);
    transition: transform var(--transition-fast), box-shadow var(--transition-fast);
}

.neon-chip:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-brand-lg);
}

.neon-panel {
    box-shadow: var(--shadow-brand);
}

.messages-container {
    position: relative;
    z-index: 2;
}

.input-area-container {
    position: relative;
    z-index: 3;
}

/* ==================== HOLOGRAPHIC CORE ==================== */
.holographic-core-container {
    position: absolute;
    top: 40%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 20;
    display: flex;
    flex-direction: column;
    align-items: center;
    pointer-events: none;
}

.holographic-core {
    width: 120px;
    height: 120px;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
}

.core-inner {
    position: absolute;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: radial-gradient(circle at 30% 30%, #fff, var(--brand-primary-400));
    box-shadow: 0 0 30px var(--brand-primary-500);
    animation: pulse 2s ease-in-out infinite;
    z-index: 3;
}

.core-outer {
    position: absolute;
    width: 100%;
    height: 100%;
    border: 2px solid rgba(139, 92, 246, 0.3);
    border-radius: 50%;
    border-top-color: var(--brand-primary-400);
    border-bottom-color: var(--brand-primary-400);
    animation: spin 4s linear infinite;
    z-index: 2;
}

.core-ring {
    position: absolute;
    width: 140%;
    height: 140%;
    border: 1px dashed rgba(139, 92, 246, 0.2);
    border-radius: 50%;
    animation: spin 10s linear infinite reverse;
    z-index: 1;
}

.holographic-status {
    margin-top: 40px;
    font-family: 'Courier New', monospace;
    color: var(--brand-primary-400);
    letter-spacing: 2px;
    font-size: 12px;
    text-shadow: 0 0 10px var(--brand-primary-500);
    animation: blink 1s steps(2) infinite;
    background: rgba(0, 0, 0, 0.5);
    padding: 4px 12px;
    border-radius: 4px;
    border: 1px solid rgba(139, 92, 246, 0.3);
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

@keyframes pulse {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(0.8); opacity: 0.7; }
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

.empty-visual {
    position: relative;
    width: 200px;
    height: 200px;
    margin-bottom: var(--space-6);
    display: flex;
    align-items: center;
    justify-content: center;
}

.planet {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    background: linear-gradient(135deg, #6366f1, #a855f7);
    box-shadow: 
        inset -10px -10px 20px rgba(0,0,0,0.5),
        0 0 30px rgba(139, 92, 246, 0.4);
    position: relative;
    z-index: 2;
    animation: float 6s ease-in-out infinite;
}

.orbit {
    position: absolute;
    width: 160px;
    height: 160px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 50%;
    animation: spin 20s linear infinite;
}

.orbit::before {
    content: '';
    position: absolute;
    top: 14px;
    left: 85%;
    width: 8px;
    height: 8px;
    background: #fff;
    border-radius: 50%;
    box-shadow: 0 0 10px #fff;
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

/* Cursor effect for generating message */
.message-bubble.generating .message-text::after {
    content: '▋';
    display: inline-block;
    vertical-align: middle;
    margin-left: 2px;
    animation: blink 1s step-end infinite;
    color: var(--brand-primary-500);
}

@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
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
    flex-direction: column; /* Vertical on all screens for consistency */
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    padding: var(--space-2);
    min-width: 64px;
    height: 64px;
    background: var(--bg-primary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-lg);
    font-size: var(--text-xs);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.option-item:hover {
    border-color: var(--brand-primary-300);
    color: var(--brand-primary-600);
    transform: translateY(-2px);
}

.option-item.is-active {
    background: var(--bg-brand);
    border-color: var(--brand-primary-500);
    color: var(--brand-primary-600);
}

.option-item.disabled {
    opacity: 0.5;
    cursor: not-allowed;
    background: var(--bg-secondary);
}

.option-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
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

.core-sphere-outer {
    position: absolute;
    width: 130px;
    height: 130px;
    border-radius: 50%;
    background: radial-gradient(circle at 30% 30%, rgba(255,255,255,0.85), var(--brand-primary-400));
    box-shadow: var(--shadow-brand-glow);
    animation: pulse 2.5s ease-in-out infinite;
    z-index: 2;
}

.core-sphere-inner {
    position: absolute;
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: radial-gradient(circle at 70% 70%, var(--brand-secondary-400), transparent 60%);
    animation: spin 6s linear infinite;
    opacity: 0.75;
    z-index: 3;
}

.core-ring-x {
    position: absolute;
    width: 160px;
    height: 160px;
    border: 2px solid rgba(139,92,246,0.3);
    border-radius: 50%;
    animation: spin 8s linear infinite;
    z-index: 1;
}

.core-ring-y {
    position: absolute;
    width: 160px;
    height: 160px;
    border: 2px dashed rgba(6,182,212,0.3);
    border-radius: 50%;
    transform: rotateX(60deg);
    animation: spinReverse 12s linear infinite;
    z-index: 1;
}

.core-particles {
    position: absolute;
    width: 180px;
    height: 180px;
    border-radius: 50%;
    box-shadow: 0 0 20px rgba(139, 92, 246, 0.3);
    animation: cosmicGlow 3s ease-in-out infinite;
    z-index: 0;
}

.holo-planet {
    width: 90px;
    height: 90px;
    border-radius: 50%;
    background: linear-gradient(135deg, #6366f1, #a855f7);
    box-shadow: inset -10px -10px 20px rgba(0,0,0,0.5), 0 0 30px rgba(139, 92, 246, 0.4);
    position: relative;
    z-index: 2;
    animation: float 6s ease-in-out infinite;
}

.holo-rings {
    position: absolute;
    width: 180px;
    height: 180px;
    border: 1px dashed rgba(255, 255, 255, 0.2);
    border-radius: 50%;
    animation: spin 20s linear infinite;
}

.input-area {
    position: relative;
    z-index: 3;
}

.input-box.quantum-box {
    position: relative;
    border: 2px solid rgba(139,92,246,0.3);
}

.input-box.quantum-box::before {
    content: "";
    position: absolute;
    inset: -2px;
    border-radius: var(--radius-2xl);
    background: conic-gradient(from 0deg, rgba(139,92,246,0.5), rgba(6,182,212,0.5), rgba(236,72,153,0.5), rgba(139,92,246,0.5));
    filter: blur(8px);
    opacity: 0.6;
    z-index: -1;
}

.send-btn.neon-send {
    box-shadow: var(--shadow-brand);
}

.send-btn.neon-send.is-active {
    background: var(--gradient-primary);
    color: #fff;
    box-shadow: var(--shadow-brand-lg);
}

.thinking-panel.neon-panel .thinking-steps {
    position: relative;
}

.thinking-panel.neon-panel .step-line {
    position: absolute;
    left: 10px;
    top: 10px;
    bottom: 10px;
    width: 2px;
    background: linear-gradient(180deg, rgba(139,92,246,0.4), rgba(6,182,212,0.4));
}

.thinking-panel.neon-panel .thinking-step {
    position: relative;
    padding-left: 24px;
}

.thinking-panel.neon-panel .step-dot {
    position: absolute;
    left: 4px;
    top: 18px;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--brand-primary-500);
    box-shadow: 0 0 12px rgba(139,92,246,0.5);
}

/* ==================== RESPONSIVE ==================== */
@media (max-width: 768px) {
    .messages-container {
        padding: var(--space-4);
        padding-bottom: var(--space-20); /* Ensure space for bottom input */
        -webkit-overflow-scrolling: touch; /* Smooth scrolling on iOS */
    }

    .message-wrapper {
        gap: var(--space-2);
        margin-bottom: var(--space-2);
    }

    .message-avatar {
        display: none; /* Hide avatars on mobile like iMessage */
    }

    /* iOS Style Bubbles */
    .message-bubble {
        padding: 10px 16px;
        border-radius: 20px;
        max-width: 75%;
        font-size: 16px;
        line-height: 1.4;
        position: relative;
        box-shadow: none; /* Flat style */
    }

    /* User Bubble (Right - Blue) */
    .message-user {
        justify-content: flex-end;
    }

    .message-user .message-bubble {
        background: var(--ios-blue);
        color: white;
        border: none;
        border-bottom-right-radius: 4px; /* Tail effect */
    }

    /* Assistant Bubble (Left - Gray) */
    .message-assistant .message-bubble {
        background: var(--ios-gray);
        color: black;
        border: none;
        border-bottom-left-radius: 4px; /* Tail effect */
    }
    
    [data-theme="dark"] .message-assistant .message-bubble {
        background: var(--ios-gray-dark);
        color: white;
    }

    /* Input Area - iOS Style */
    .input-area-container {
        position: fixed; /* Fixed to bottom */
        bottom: 0;
        left: 0;
        right: 0;
        z-index: 100;
        background: rgba(255, 255, 255, 0.95); /* More opaque to prevent overlap visibility */
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-top: 1px solid rgba(0,0,0,0.1);
        padding-bottom: env(safe-area-inset-bottom);
        display: flex;
        flex-direction: column;
    }

    [data-theme="dark"] .input-area-container {
        background: rgba(30, 30, 30, 0.95);
        border-top: 1px solid rgba(255,255,255,0.1);
    }

    .input-area {
        padding: 8px 12px;
        background: transparent;
        border: none;
        order: 1; /* Input stays above options */
    }

    .input-wrapper {
        display: flex;
        align-items: flex-end;
        gap: 8px;
        position: relative; /* Context for children */
    }
    
    /* Move Options Panel OUT of input-wrapper flow visually */
    .options-panel {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 8px; /* Reduce gap to fit screen */
        padding: 12px; /* Reduce padding */
        padding-top: 0;
        background: transparent;
        order: 2; /* Below input */
        border: none;
        margin: 0;
        width: 100%;
        box-sizing: border-box; /* Ensure padding doesn't increase width */
        overflow-x: hidden; /* Prevent horizontal scroll bar */
    }
    
    .option-item {
        background: rgba(242, 242, 247, 0.8); /* iOS System Gray 6 */
        border-radius: 12px;
        /* Remove aspect-ratio: 1 to allow height to adapt to content if needed, but keep square-ish */
        height: auto;
        min-height: 70px;
        box-shadow: none;
        border: none;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 8px 4px; /* Reduce internal padding */
    }
    
    .option-item span {
        font-size: 10px; /* Smaller text */
        white-space: nowrap; /* Prevent wrapping */
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 100%;
    }
    
    [data-theme="dark"] .option-item {
        background: rgba(44, 44, 46, 0.8); /* iOS Dark Gray 6 */
    }

    .input-box {
        flex: 1;
        background: white;
        border: 1px solid #c6c6c8; /* iOS Border Gray */
        border-radius: 20px; /* Capsule shape */
        padding: 6px 12px; /* Slim padding */
        display: flex;
        align-items: center;
        min-height: 36px;
    }
    
    [data-theme="dark"] .input-box {
        background: #1c1c1e;
        border-color: #38383a;
    }
}
</style>
