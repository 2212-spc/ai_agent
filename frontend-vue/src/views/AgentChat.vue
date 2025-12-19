<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { useChatStore } from '../stores/chat';
import { useCanvasStore } from '../stores/canvas';
import { useTheme } from '../composables/useTheme';
import { useNotification, NOTIFICATION_TYPES } from '../composables/useNotification';
import ChatPanel from '../components/Chat/ChatPanel.vue';
import CanvasPanel from '../components/Canvas/CanvasPanel.vue';
import TimelinePanel from '../components/Chat/TimelinePanel.vue';
import NotificationContainer from '../components/NotificationContainer.vue';

const chatStore = useChatStore();
const canvasStore = useCanvasStore();
const { currentTheme, toggleTheme } = useTheme();
const { showRich } = useNotification();

const showBuilder = ref(false);
const showTimeline = ref(false);
const isSidebarOpen = ref(true);
const historyList = ref([]);
const isLoadingHistory = ref(false);
const sidebarWidth = ref(280);
const builderWidth = ref(500);
const timelineWidth = ref(320);

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
    if (!confirm('确定要创建新会话吗？当前聊天记录将被保存。')) {
        return;
    }
    
    // 生成新会话ID
    const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    console.log('🆕 新建会话:', newSessionId);
    
    // 创建新会话并切换
    chatStore.ensureSession(newSessionId);
    chatStore.setSessionId(newSessionId);
    
    // 清空timeline
    chatStore.clearTimelineSteps();
    
    // 提示用户
    if (window.notificationManager) {
        window.notificationManager.show('✅ 新会话已创建', 'success', 2000);
    }
    
    console.log('✅ 新会话已创建:', newSessionId);
}

function onModeChange() {
    const mode = chatStore.isMultiAgentMode ? '多智能体' : '单智能体';
    console.log(`切换到 ${mode} 模式`);
    chatStore.addMessage({
        role: 'system',
        content: `已切换到${mode}模式`,
        type: 'info'
    });
}

async function loadHistoryList() {
    isLoadingHistory.value = true;
    try {
        const response = await fetch('http://127.0.0.1:8000/conversations');
        const data = await response.json();
        historyList.value = data.slice(0, 10); // 只显示最近10条
    } catch (error) {
        console.error('加载历史记录失败:', error);
    } finally {
        isLoadingHistory.value = false;
    }
}

function refreshHistory() {
    loadHistoryList();
}

async function selectConversation(sessionId) {
    try {
        // 初始化会话状态
        const session = chatStore.ensureSession(sessionId);
        
        // 切换会话,但不关闭sidebar
        chatStore.setSessionId(sessionId);
        
        // 如果会话消息为空，从后端加载历史消息
        if (session.messages.length === 0) {
            const response = await fetch(`http://127.0.0.1:8000/conversation/${sessionId}/history?limit=100`);
            
            // 如果是404（新会话），不报错
            if (!response.ok) {
                if (response.status === 404) {
                    console.log('新会话，没有历史记录');
                    return;
                }
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            
            // 加载历史消息到会话中，并尝试恢复思考步骤
            session.messages = data.map((msg, index) => {
                const messageObj = {
                    id: msg.id || `msg_${Date.now()}_${index}`,
                    role: msg.role,
                    content: msg.content,
                    timestamp: msg.created_at,
                    type: 'text'
                };
                
                // 如果是助手消息，尝试加载思考步骤
                if (msg.role === 'assistant' && messageObj.id) {
                    const thinkingSteps = chatStore.loadThinkingSteps(sessionId, messageObj.id);
                    if (thinkingSteps) {
                        messageObj.thinkingSteps = thinkingSteps;
                        console.log('📥 恢复思考步骤:', thinkingSteps.length, '个');
                    }
                }
                
                return messageObj;
            });
            
            console.log('已加载会话:', sessionId, '消息数:', data.length);
        } else {
            console.log('切换到会话:', sessionId, '已有消息数:', session.messages.length);
        }
    } catch (error) {
        console.error('加载会话失败:', error);
        
        // 不要用alert，使用通知系统
        if (window.notificationManager) {
            window.notificationManager.show('加载历史会话失败', 'error', 3000);
        }
    }
}

function startResizeBuilder(event) {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = builderWidth.value;
    
    function onMouseMove(e) {
        const deltaX = startX - e.clientX;
        const newWidth = Math.max(300, Math.min(800, startWidth + deltaX));
        builderWidth.value = newWidth;
    }
    
    function onMouseUp() {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
    }
    
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
}

function startResizeTimeline(event) {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = timelineWidth.value;
    
    function onMouseMove(e) {
        const deltaX = startX - e.clientX;
        const newWidth = Math.max(250, Math.min(600, startWidth + deltaX));
        timelineWidth.value = newWidth;
    }
    
    function onMouseUp() {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
    }
    
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
}

// 后台生成完成事件处理
function handleBackgroundGenerationComplete(event) {
    const { sessionId, question, answer } = event.detail;
    
    // 截取问题（限制40字符）
    const truncatedQuestion = question.length > 40 
        ? question.substring(0, 40) + '...' 
        : question;
    
    // 截取答案（限制120字符）
    const truncatedAnswer = answer.length > 120 
        ? answer.substring(0, 120) + '...' 
        : answer;
    
    // 显示富文本通知
    showRich(
        truncatedQuestion,
        truncatedAnswer,
        NOTIFICATION_TYPES.SUCCESS,
        6000
    );
    
    // 刷新历史列表
    loadHistoryList();
}

onMounted(() => {
    console.log('AgentChat mounted');
    loadHistoryList();
    
    // 每30秒自动刷新历史记录
    setInterval(() => {
        loadHistoryList();
    }, 30000);
    
    // 监听后台生成完成事件
    window.addEventListener('background-generation-complete', handleBackgroundGenerationComplete);
});

onUnmounted(() => {
    // 清理事件监听
    window.removeEventListener('background-generation-complete', handleBackgroundGenerationComplete);
});
</script>

<template>
    <div class="agent-chat-container">
        <!-- Notification Container -->
        <NotificationContainer />
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
                    <router-link to="/memory" class="nav-link">🧠 记忆管理</router-link>
                    <router-link to="/history" class="nav-link">📚 会话历史</router-link>
                </div>
            </div>
            
            <div class="header-right">
                <!-- 🔒 全局记忆模式切换 -->
                <div class="mode-switch-container">
                    <label class="mode-switch">
                        <input type="checkbox" v-model="chatStore.isGlobalMemory" @change="chatStore.toggleGlobalMemory(chatStore.isGlobalMemory)">
                        <span class="mode-slider"></span>
                    </label>
                    <span class="mode-indicator" :class="{ 'global-memory': chatStore.isGlobalMemory }">
                        {{ chatStore.isGlobalMemory ? '全局记忆🌐' : '独立记忆' }}
                    </span>
                </div>
                
                <!-- 💭 深度思考模式切换 -->
                <div class="mode-switch-container">
                    <label class="mode-switch">
                        <input type="checkbox" v-model="chatStore.isDeepThinkMode" @change="chatStore.toggleDeepThink(chatStore.isDeepThinkMode)">
                        <span class="mode-slider"></span>
                    </label>
                    <span class="mode-indicator" :class="{ 'deep-think': chatStore.isDeepThinkMode }">
                        {{ chatStore.isDeepThinkMode ? '深度思考💭' : '标准模式' }}
                    </span>
                </div>
                
                <!-- 多智能体模式切换 -->
                <div class="mode-switch-container">
                    <span class="mode-switch-label">模式:</span>
                    <label class="mode-switch">
                        <input type="checkbox" v-model="chatStore.isMultiAgentMode" @change="onModeChange">
                        <span class="mode-slider"></span>
                    </label>
                    <span class="mode-indicator">{{ chatStore.isMultiAgentMode ? '多智能体' : '单智能体' }}</span>
                </div>
                <button class="btn-icon" @click="toggleTheme" title="切换主题">
                    {{ currentTheme === 'dark' ? '🌙' : '☀️' }}
                </button>
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
            <aside class="sidebar" v-show="isSidebarOpen" :style="{ width: sidebarWidth + 'px' }">
                <button class="btn btn-primary btn-small new-chat-btn" @click="startNewChat">
                    ➕ 新建对话
                </button>
                <div class="sidebar-section">
                    <div class="sidebar-header">
                        <h3 class="section-title">📚 历史记录</h3>
                        <button class="btn-icon" @click="refreshHistory" title="刷新">🔄</button>
                    </div>
                    
                    <!-- 加载中 -->
                    <div v-if="isLoadingHistory" class="history-loading">加载中...</div>
                    
                    <!-- 空状态 -->
                    <div v-else-if="historyList.length === 0" class="empty-state">
                        <div class="empty-state-icon">💭</div>
                        <div class="empty-state-text">暂无历史会话</div>
                    </div>
                    
                    <!-- 历史记录列表 -->
                    <div v-else class="history-list">
                        <div 
                            v-for="item in historyList" 
                            :key="item.session_id"
                            class="history-item"
                            :class="{ 'active': item.session_id === chatStore.currentSessionId }"
                            @click="selectConversation(item.session_id)"
                        >
                            <div class="history-title">
                                {{ item.title || '新对话' }}
                                <span 
                                    v-if="chatStore.getSessionStatus(item.session_id) === chatStore.SESSION_STATUS.GENERATING"
                                    class="generating-badge"
                                    title="后台生成中"
                                >
                                    ⚡
                                </span>
                            </div>
                            <div class="history-meta">
                                {{ item.created_at ? new Date(item.created_at).toLocaleString('zh-CN', { 
                                    month: '2-digit', 
                                    day: '2-digit', 
                                    hour: '2-digit', 
                                    minute: '2-digit' 
                                }) : '最近' }}
                            </div>
                        </div>
                    </div>
                </div>
            </aside>

            <!-- Chat Panel -->
            <div class="content-area">
                <ChatPanel />
            </div>

            <!-- Builder Panel -->
            <aside class="builder-panel" v-show="showBuilder" :style="{ width: builderWidth + 'px' }">
                <div class="resize-handle resize-handle-left" @mousedown="startResizeBuilder"></div>
                <CanvasPanel />
            </aside>

            <!-- Timeline Panel -->
            <aside class="timeline-panel-container" v-show="showTimeline" :style="{ width: timelineWidth + 'px' }">
                <div class="resize-handle resize-handle-left" @mousedown="startResizeTimeline"></div>
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

.history-loading {
    text-align: center;
    padding: 20px;
    color: var(--text-tertiary);
    font-size: 13px;
}

.history-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.history-item {
    padding: 10px 12px;
    border-radius: 8px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-primary);
    cursor: pointer;
    transition: all 0.2s;
}

.history-item:hover {
    background: var(--hover-bg);
    border-color: var(--brand-primary-500);
}

.history-item.active {
    background: var(--bg-brand);
    border-color: var(--brand-primary-500);
    box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.2);
}

.history-title {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    display: flex;
    align-items: center;
    gap: 6px;
}

.generating-badge {
    font-size: 12px;
    animation: blink 1.5s ease-in-out infinite;
}

@keyframes blink {
    0%, 100% {
        opacity: 1;
    }
    50% {
        opacity: 0.3;
    }
}

.history-meta {
    font-size: 11px;
    color: var(--text-tertiary);
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
    position: relative;
    background: var(--bg-primary);
    border-left: 1px solid var(--border-primary);
    overflow: hidden;
    min-width: 300px;
    max-width: 800px;
}

.resize-handle {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 4px;
    background: transparent;
    cursor: ew-resize;
    z-index: 10;
}

.resize-handle:hover {
    background: var(--brand-primary-500);
}

.resize-handle-left {
    left: 0;
}

.timeline-panel-container {
    position: relative;
    background: var(--bg-primary);
    border-left: 1px solid var(--border-primary);
    overflow: hidden;
    min-width: 250px;
    max-width: 600px;
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
    background: var(--bg-brand);
    color: var(--brand-primary-600);
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
    background-color: var(--brand-primary-500);
}

input:checked + .mode-slider:before {
    transform: translateX(20px);
}

.mode-indicator {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    min-width: 70px;
    background: var(--bg-tertiary);
    padding: 4px 10px;
    border-radius: 12px;
    border: 1px solid var(--border-secondary);
    transition: all 0.3s ease;
}

/* 🔒 全局记忆模式样式 */
.mode-indicator.global-memory {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-color: #667eea;
    box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

/* 💭 深度思考模式样式 */
.mode-indicator.deep-think {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    color: white;
    border-color: #f093fb;
    box-shadow: 0 2px 8px rgba(240, 147, 251, 0.3);
}

.header-right {
    display: flex;
    align-items: center;
    gap: 8px;
}
</style>
