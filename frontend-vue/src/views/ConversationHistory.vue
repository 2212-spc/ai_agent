<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';

const router = useRouter();
const conversations = ref([]);
const isLoading = ref(false);
const searchQuery = ref('');
const apiBase = 'http://127.0.0.1:8000';

async function loadConversations() {
    isLoading.value = true;
    try {
        const response = await axios.get(`${apiBase}/conversations`);
        conversations.value = response.data;
    } catch (error) {
        console.error('加载会话失败:', error);
    } finally {
        isLoading.value = false;
    }
}

async function deleteConversation(sessionId) {
    if (!confirm('确定要删除这个会话吗？')) return;
    
    try {
        await axios.delete(`${apiBase}/conversation/${sessionId}`);
        loadConversations();
    } catch (error) {
        console.error('删除会话失败:', error);
    }
}

function openConversation(sessionId) {
    router.push({ path: '/chat', query: { session_id: sessionId } });
}

onMounted(() => {
    loadConversations();
});
</script>

<template>
    <div class="page-container">
        <div class="header">
            <div class="header-left">
                <button class="btn-icon" @click="router.push('/chat')">←</button>
                <div>
                    <h1>对话历史</h1>
                    <p class="subtitle">查看和管理历史会话</p>
                </div>
            </div>
            <button class="btn btn-primary" @click="loadConversations">🔄 刷新</button>
        </div>

        <div class="content">
            <!-- 搜索框 -->
            <div class="search-box">
                <input
                    v-model="searchQuery"
                    type="text"
                    placeholder="🔍 搜索会话..."
                    class="search-input"
                />
            </div>

            <!-- 会话列表 -->
            <div v-if="isLoading" class="loading">加载中...</div>
            <div v-else-if="conversations.length === 0" class="empty-state">
                <div class="empty-state-icon">💭</div>
                <h3>暂无历史记录</h3>
                <p>开始对话后会显示在这里</p>
            </div>
            <div v-else class="conversations-list">
                <div
                    v-for="conv in conversations"
                    :key="conv.session_id"
                    class="conversation-card"
                    @click="openConversation(conv.session_id)"
                    v-show="!searchQuery || conv.title?.includes(searchQuery)"
                >
                    <div class="conv-header">
                        <h3>{{ conv.title || '未命名会话' }}</h3>
                        <span class="conv-date">
                            {{ new Date(conv.created_at).toLocaleDateString() }}
                        </span>
                    </div>
                    <p class="conv-preview">{{ conv.last_message || '暂无消息' }}</p>
                    <div class="conv-footer">
                        <span class="conv-count">💬 {{ conv.message_count || 0 }} 条消息</span>
                        <button
                            class="btn-icon btn-danger"
                            @click.stop="deleteConversation(conv.session_id)"
                            title="删除"
                        >
                            🗑️
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.page-container {
    height: 100vh;
    display: flex;
    flex-direction: column;
    background: var(--bg-secondary);
}

.header {
    background: var(--bg-primary);
    padding: 20px;
    border-bottom: 1px solid var(--border-primary);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header-left {
    display: flex;
    gap: 16px;
    align-items: center;
}

.header h1 {
    margin: 0;
    font-size: 24px;
}

.subtitle {
    color: var(--text-secondary);
    margin: 4px 0 0 0;
    font-size: 14px;
}

.content {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
}

.search-box {
    margin-bottom: 20px;
}

.search-input {
    width: 100%;
    padding: 12px 16px;
    border: 1px solid var(--border-secondary);
    border-radius: 8px;
    background: var(--bg-primary);
    font-size: 14px;
    color: var(--text-primary);
}

.search-input:focus {
    outline: none;
    border-color: var(--primary-color);
}

.conversations-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
}

.conversation-card {
    background: var(--bg-primary);
    border: 1px solid var(--border-primary);
    border-radius: 12px;
    padding: 16px;
    cursor: pointer;
    transition: all 0.2s;
}

.conversation-card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
    border-color: var(--primary-color);
}

.conv-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.conv-header h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
}

.conv-date {
    font-size: 12px;
    color: var(--text-tertiary);
}

.conv-preview {
    color: var(--text-secondary);
    font-size: 14px;
    line-height: 1.5;
    margin-bottom: 12px;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
}

.conv-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 12px;
    border-top: 1px solid var(--border-secondary);
}

.conv-count {
    font-size: 13px;
    color: var(--text-tertiary);
}

.btn-danger:hover {
    color: #dc2626;
}

.loading, .empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-tertiary);
}

.empty-state-icon {
    font-size: 48px;
    margin-bottom: 16px;
}

.empty-state h3 {
    margin: 0 0 8px 0;
}
</style>
