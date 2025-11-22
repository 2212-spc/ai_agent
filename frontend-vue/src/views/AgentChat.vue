<script setup>
import { ref, onMounted } from 'vue';
import { useChatStore } from '../stores/chat';
import { useCanvasStore } from '../stores/canvas';
import ChatPanel from '../components/Chat/ChatPanel.vue';
import CanvasPanel from '../components/Canvas/CanvasPanel.vue';
import TimelinePanel from '../components/Chat/TimelinePanel.vue';

const chatStore = useChatStore();
const canvasStore = useCanvasStore();

const showBuilder = ref(false);
const showTimeline = ref(false);
const isSidebarOpen = ref(true);

function toggleBuilder() {
    showBuilder.value = !showBuilder.value;
}

function toggleTimeline() {
    showTimeline.value = !showTimeline.value;
}

function toggleSidebar() {
    isSidebarOpen.value = !isSidebarOpen.value;
}

function openSettings() {
    window.open('/settings', '_blank');
}

function clearChat() {
    if (confirm('确定要清空当前对话吗？')) {
        chatStore.clearMessages();
    }
}

function startNewChat() {
    chatStore.clearMessages();
    chatStore.setSessionId(null);
}

function onModeChange() {
    const mode = chatStore.isMultiAgentMode ? '多智能体' : '单智能体';
    console.log(`切换到 ${mode} 模式`);
    // 可选：添加通知提示
    chatStore.addMessage({
        role: 'system',
        content: `已切换到${mode}模式`,
        type: 'info'
    });
}

onMounted(() => {
    console.log('AgentChat mounted');
});
</script>

<template>
    <div class="agent-chat-container">
        <!-- Header -->
        <div class="header">
            <div class="header-left">
                <button class="menu-toggle-btn" @click="toggleSidebar">
                    {{ isSidebarOpen ? '◀' : '▶' }}
                </button>
                <div class="logo">🤖</div>
                <div class="header-title">
                    <h1>AI Agent Studio</h1>
                    <div class="header-title-sub">多智能体对话与知识工作台</div>
                </div>
                <!-- 导航链接 -->
                <div class="header-nav">
                    <router-link to="/chat" class="nav-link active">💬 对话工作台</router-link>
                    <router-link to="/prompts" class="nav-link">📝 Prompt模板</router-link>
                    <router-link to="/knowledge" class="nav-link">📁 知识库</router-link>
                    <router-link to="/history" class="nav-link">📚 会话历史</router-link>
                </div>
            </div>
            
            <div class="header-right">
                <!-- 模式切换 -->
                <div class="mode-switch-container">
                    <span class="mode-switch-label">模式:</span>
                    <label class="mode-switch">
                        <input type="checkbox" v-model="chatStore.isMultiAgentMode" @change="onModeChange">
                        <span class="mode-slider"></span>
                    </label>
                    <span class="mode-indicator">{{ chatStore.isMultiAgentMode ? '多智能体' : '单智能体' }}</span>
                </div>
                <button class="btn-icon" @click="openSettings" title="会话设置">⚙️</button>
                <button class="btn-icon" @click="toggleBuilder" title="Agent构建器">🛠️</button>
                <button class="btn btn-secondary btn-small" @click="toggleTimeline">
                    {{ showTimeline ? '← 收起过程' : '展开过程 →' }}
                </button>
                <button class="btn-icon" @click="clearChat" title="清空对话">🗑️</button>
            </div>
        </div>

        <!-- Main Content -->
        <div class="main-content" :class="{ 'sidebar-closed': !isSidebarOpen }">
            <!-- Sidebar -->
            <aside class="sidebar" v-show="isSidebarOpen">
                <button class="btn btn-primary btn-small new-chat-btn" @click="startNewChat">
                    ➕ 新建对话
                </button>
                <div class="sidebar-section">
                    <div class="sidebar-header">
                        <h3 class="section-title">📚 历史记录</h3>
                        <button class="btn-icon" title="刷新">🔄</button>
                    </div>
                    <div class="empty-state">
                        <div class="empty-state-icon">💭</div>
                        <div class="empty-state-text">暂无历史会话</div>
                    </div>
                </div>
            </aside>

            <!-- Chat Panel -->
            <div class="content-area">
                <ChatPanel />
            </div>

            <!-- Builder Panel -->
            <aside class="builder-panel" v-show="showBuilder">
                <CanvasPanel />
            </aside>

            <!-- Timeline Panel -->
            <aside class="timeline-panel-container" v-show="showTimeline">
                <TimelinePanel />
            </aside>
        </div>
    </div>
</template>

<style scoped>
.agent-chat-container {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: var(--bg-secondary);
}

.main-content {
    display: flex;
    flex: 1;
    overflow: hidden;
    transition: all 0.3s ease;
}

.sidebar {
    width: 280px;
    background: var(--bg-primary);
    border-right: 1px solid var(--border-primary);
    padding: 16px;
    overflow-y: auto;
    transition: transform 0.3s ease;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.new-chat-btn {
    width: 100%;
}

.sidebar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.main-content.sidebar-closed .sidebar {
    transform: translateX(-100%);
}

.content-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.builder-panel {
    width: 400px;
    background: var(--bg-primary);
    border-left: 1px solid var(--border-primary);
    overflow: hidden;
}

.timeline-panel-container {
    width: 320px;
    background: var(--bg-primary);
    border-left: 1px solid var(--border-primary);
    overflow: hidden;
}

.section-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 12px;
}

.empty-state {
    text-align: center;
    padding: 32px 16px;
    color: var(--text-tertiary);
}

.empty-state-icon {
    font-size: 32px;
    margin-bottom: 8px;
}

.empty-state-text {
    font-size: 13px;
}

.menu-toggle-btn {
    width: 32px;
    height: 32px;
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: 16px;
    border-radius: 6px;
    transition: background 0.2s;
}

.menu-toggle-btn:hover {
    background: var(--bg-tertiary);
}

.header-nav {
    display: flex;
    gap: 8px;
    margin-left: 24px;
}

.nav-link {
    padding: 6px 12px;
    border-radius: 6px;
    text-decoration: none;
    font-size: 13px;
    color: var(--text-secondary);
    transition: all 0.2s;
}

.nav-link:hover {
    background: var(--bg-tertiary);
    color: var(--text-primary);
}

.nav-link.active {
    background: var(--primary-light);
    color: var(--primary-color);
    font-weight: 500;
}

.mode-switch-container {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-right: 12px;
}

.mode-switch-label {
    font-size: 13px;
    color: var(--text-secondary);
}

.mode-switch {
    position: relative;
    display: inline-block;
    width: 44px;
    height: 24px;
}

.mode-switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.mode-slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #ccc;
    transition: 0.3s;
    border-radius: 24px;
}

.mode-slider:before {
    position: absolute;
    content: "";
    height: 18px;
    width: 18px;
    left: 3px;
    bottom: 3px;
    background-color: white;
    transition: 0.3s;
    border-radius: 50%;
}

input:checked + .mode-slider {
    background-color: var(--primary-color);
}

input:checked + .mode-slider:before {
    transform: translateX(20px);
}

.mode-indicator {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
    min-width: 60px;
}

.header-right {
    display: flex;
    align-items: center;
    gap: 8px;
}
</style>
