<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';
import { API_BASE_URL } from '../config/api';

const router = useRouter();
const prompts = ref([]);
const agents = ref([]);
const isLoading = ref(false);
const selectedAgent = ref('');
const showDetailModal = ref(false);
const selectedPrompt = ref(null);
const showCreateModal = ref(false);
const newPrompt = ref({
    name: '',
    description: '',
    content: '',
    agent_id: ''
});
const apiBase = API_BASE_URL;

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

function viewPrompt(prompt) {
    selectedPrompt.value = prompt;
    showDetailModal.value = true;
}

function closeModal() {
    showDetailModal.value = false;
    selectedPrompt.value = null;
}

async function openCreateModal() {
    // 确保agents已加载
    if (agents.value.length === 0) {
        await loadAgents();
    }
    
    newPrompt.value = {
        name: '',
        description: '',
        content: '',
        agent_id: agents.value[0]?.id || ''
    };
    showCreateModal.value = true;
}

function closeCreateModal() {
    showCreateModal.value = false;
}

async function createPrompt() {
    try {
        await axios.post(`${apiBase}/prompts`, newPrompt.value);
        alert('Prompt创建成功！');
        closeCreateModal();
        loadPrompts();
    } catch (error) {
        console.error('创建Prompt失败:', error);
        alert('创建失败: ' + (error.response?.data?.detail || error.message));
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
            <div class="header-actions">
                <button class="btn btn-secondary" @click="loadPrompts">🔄 刷新</button>
                <button class="btn btn-primary" @click="openCreateModal">➕ 新建Prompt</button>
            </div>
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
                        <button class="btn btn-secondary btn-small" @click="viewPrompt(prompt)">查看</button>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Prompt详情Modal -->
        <div v-if="showDetailModal" class="modal-overlay" @click="closeModal">
            <div class="modal-content" @click.stop>
                <div class="modal-header">
                    <h2>{{ selectedPrompt?.name }}</h2>
                    <button class="modal-close" @click="closeModal">×</button>
                </div>
                <div class="modal-body">
                    <div class="detail-section">
                        <label>智能体:</label>
                        <p>{{ selectedPrompt?.agent_name }}</p>
                    </div>
                    <div class="detail-section">
                        <label>描述:</label>
                        <p>{{ selectedPrompt?.description }}</p>
                    </div>
                    <div class="detail-section">
                        <label>内容:</label>
                        <pre class="prompt-content">{{ selectedPrompt?.content }}</pre>
                    </div>
                    <div class="detail-section">
                        <label>创建时间:</label>
                        <p>{{ new Date(selectedPrompt?.created_at).toLocaleString() }}</p>
                    </div>
                    <div class="detail-section">
                        <label>状态:</label>
                        <p>{{ selectedPrompt?.is_active ? '激活' : '未激活' }}</p>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 创建Prompt Modal -->
        <div v-if="showCreateModal" class="modal-overlay" @click="closeCreateModal">
            <div class="modal-content" @click.stop>
                <div class="modal-header">
                    <h2>新建Prompt模板</h2>
                    <button class="modal-close" @click="closeCreateModal">×</button>
                </div>
                <div class="modal-body">
                    <div class="detail-section">
                        <label>名称:</label>
                        <input type="text" v-model="newPrompt.name" placeholder="输入Prompt名称" />
                    </div>
                    <div class="detail-section">
                        <label>智能体:</label>
                        <select v-model="newPrompt.agent_id" class="select">
                            <option v-for="agent in agents" :key="agent.id" :value="agent.id">
                                {{ agent.display_name }}
                            </option>
                        </select>
                    </div>
                    <div class="detail-section">
                        <label>描述:</label>
                        <input type="text" v-model="newPrompt.description" placeholder="简要描述" />
                    </div>
                    <div class="detail-section">
                        <label>内容:</label>
                        <textarea 
                            v-model="newPrompt.content" 
                            placeholder="输入Prompt内容..."
                            rows="10"
                            class="prompt-content-editor"
                        ></textarea>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" @click="closeCreateModal">取消</button>
                    <button class="btn btn-primary" @click="createPrompt">创建</button>
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

/* Modal样式 */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.modal-content {
    background: var(--bg-primary);
    border-radius: 12px;
    max-width: 800px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
}

.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    border-bottom: 1px solid var(--border-primary);
}

.modal-header h2 {
    margin: 0;
    font-size: 20px;
}

.modal-close {
    background: none;
    border: none;
    font-size: 28px;
    color: var(--text-tertiary);
    cursor: pointer;
    line-height: 1;
    padding: 0;
    width: 32px;
    height: 32px;
}

.modal-close:hover {
    color: var(--text-primary);
}

.modal-body {
    padding: 20px;
}

.detail-section {
    margin-bottom: 20px;
}

.detail-section label {
    display: block;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 8px;
    font-size: 13px;
}

.detail-section p {
    margin: 0;
    color: var(--text-primary);
    line-height: 1.6;
}

.detail-section input[type="text"],
.detail-section textarea {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid var(--border-secondary);
    border-radius: 6px;
    background: var(--bg-secondary);
    color: var(--text-primary);
    font-size: 14px;
    font-family: inherit;
}

.detail-section input:focus,
.detail-section textarea:focus {
    outline: none;
    border-color: var(--primary-color);
}

.prompt-content-editor {
    font-family: var(--font-mono);
    resize: vertical;
}

.modal-footer {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
    padding: 16px 20px;
    border-top: 1px solid var(--border-primary);
}

.prompt-content {
    background: var(--bg-tertiary);
    padding: 16px;
    border-radius: 8px;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-wrap: break-word;
    color: var(--text-primary);
    font-family: var(--font-mono);
    max-height: 400px;
    overflow-y: auto;
}
</style>
