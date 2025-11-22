<script setup>
import { ref, onMounted } from 'vue';
import { useChatStore } from '../stores/chat';
import { useCanvasStore } from '../stores/canvas';
import ChatPanel from '../components/Chat/ChatPanel.vue';
import CanvasPanel from '../components/Canvas/CanvasPanel.vue';

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
                    <div class="header-title-sub">智能体工作台</div>
                </div>
            </div>
            
            <div class="header-right">
                <button class="btn-icon" @click="openSettings" title="设置">⚙️</button>
                <button class="btn btn-primary" @click="toggleBuilder">
                    {{ showBuilder ? '关闭' : '打开' }}Agent构建器
                </button>
            </div>
        </div>

        <!-- Main Content -->
        <div class="main-content" :class="{ 'sidebar-closed': !isSidebarOpen }">
            <!-- Sidebar -->
            <aside class="sidebar" v-show="isSidebarOpen">
                <div class="sidebar-section">
                    <h3 class="section-title">会话历史</h3>
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
</style>
