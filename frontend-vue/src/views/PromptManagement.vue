<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';

const router = useRouter();
const prompts = ref([]);
const agents = ref([]);
const isLoading = ref(false);
const selectedAgent = ref('');
const apiBase = 'http://127.0.0.1:8000';

async function loadPrompts() {
    isLoading.value = true;
    try {
        const response = await axios.get(`${apiBase}/prompts?include_inactive=true`);
        prompts.value = response.data;
    } catch (error) {
        console.error('加载Prompts失败:', error);
    } finally {
        isLoading.value = false;
    }
}

async function loadAgents() {
    try {
        const response = await axios.get(`${apiBase}/agents/list`);
        agents.value = response.data;
    } catch (error) {
        console.error('加载Agents失败:', error);
    }
}

async function activatePrompt(promptId) {
    try {
        await axios.post(`${apiBase}/prompts/${promptId}/activate`);
        loadPrompts();
    } catch (error) {
        console.error('激活Prompt失败:', error);
    }
}

onMounted(() => {
    loadPrompts();
    loadAgents();
});
</script>

<template>
    <div class="page-container">
        <div class="header">
            <div class="header-left">
                <button class="btn-icon" @click="router.push('/chat')">←</button>
                <div>
                    <h1>Prompt模板管理</h1>
                    <p class="subtitle">管理智能体的Prompt模板</p>
                </div>
            </div>
            <button class="btn btn-primary" @click="loadPrompts">🔄 刷新</button>
        </div>

        <div class="content">
            <!-- Agent选择 -->
            <div class="filter-section">
                <label>筛选智能体:</label>
                <select v-model="selectedAgent" class="select">
                    <option value="">全部</option>
                    <option v-for="agent in agents" :key="agent.name" :value="agent.name">
                        {{ agent.display_name }}
                    </option>
                </select>
            </div>

            <!-- Prompt列表 -->
            <div v-if="isLoading" class="loading">加载中...</div>
            <div v-else-if="prompts.length === 0" class="empty-state">
                <div class="empty-state-icon">📝</div>
                <h3>暂无Prompt模板</h3>
            </div>
            <div v-else class="prompts-grid">
                <div
                    v-for="prompt in prompts"
                    :key="prompt.id"
                    class="prompt-card"
                    :class="{ active: prompt.is_active }"
                    v-show="!selectedAgent || prompt.agent_name === selectedAgent"
                >
                    <div class="prompt-header">
                        <h3>{{ prompt.name }}</h3>
                        <span class="badge" :class="prompt.is_active ? 'badge-success' : 'badge-default'">
                            {{ prompt.is_active ? '激活' : '未激活' }}
                        </span>
                    </div>
                    <div class="prompt-meta">
                        <span>🤖 {{ prompt.agent_name }}</span>
                        <span>📅 {{ new Date(prompt.created_at).toLocaleDateString() }}</span>
                    </div>
                    <p class="prompt-description">{{ prompt.description }}</p>
                    <div class="prompt-actions">
                        <button
                            v-if="!prompt.is_active"
                            @click="activatePrompt(prompt.id)"
                            class="btn btn-primary btn-small"
                        >
                            激活
                        </button>
                        <button class="btn btn-secondary btn-small">查看</button>
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

.filter-section {
    margin-bottom: 20px;
    display: flex;
    gap: 12px;
    align-items: center;
}

.select {
    padding: 8px 12px;
    border: 1px solid var(--border-secondary);
    border-radius: 6px;
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 14px;
}

.prompts-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
}

.prompt-card {
    background: var(--bg-primary);
    border: 1px solid var(--border-primary);
    border-radius: 12px;
    padding: 16px;
    transition: all 0.2s;
}

.prompt-card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
}

.prompt-card.active {
    border-color: var(--primary-color);
    background: var(--primary-light);
}

.prompt-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.prompt-header h3 {
    margin: 0;
    font-size: 16px;
}

.badge {
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
}

.badge-success {
    background: #d4edda;
    color: #155724;
}

.badge-default {
    background: var(--bg-tertiary);
    color: var(--text-tertiary);
}

.prompt-meta {
    display: flex;
    gap: 16px;
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 12px;
}

.prompt-description {
    color: var(--text-secondary);
    font-size: 14px;
    line-height: 1.5;
    margin-bottom: 16px;
}

.prompt-actions {
    display: flex;
    gap: 8px;
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
</style>
