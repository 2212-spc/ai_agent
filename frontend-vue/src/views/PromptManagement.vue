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

// AI 辅助生成相关状态
const showAiPanel = ref(false);
const aiRequirement = ref('');
const generatedKeywords = ref([]);
const selectedKeywords = ref([]);
const isExtracting = ref(false);
const isGenerating = ref(false);

const apiBase = API_BASE_URL;

async function extractKeywords() {
    if (!aiRequirement.value) return;
    
    isExtracting.value = true;
    try {
        const response = await axios.post(`${apiBase}/prompts/extract-keywords`, {
            user_requirement: aiRequirement.value
        });
        generatedKeywords.value = response.data.keywords;
        selectedKeywords.value = [...response.data.keywords]; // 默认全选
    } catch (error) {
        console.error('提取关键词失败:', error);
        alert('提取关键词失败: ' + (error.response?.data?.detail || error.message));
    } finally {
        isExtracting.value = false;
    }
}

function toggleKeyword(keyword) {
    const index = selectedKeywords.value.indexOf(keyword);
    if (index === -1) {
        selectedKeywords.value.push(keyword);
    } else {
        selectedKeywords.value.splice(index, 1);
    }
}

async function generatePromptWithKeywords() {
    if (!newPrompt.value.agent_id) {
        alert('请先选择一个智能体');
        return;
    }
    
    isGenerating.value = true;
    try {
        const response = await axios.post(`${apiBase}/prompts/generate`, {
            agent_id: newPrompt.value.agent_id,
            user_requirement: aiRequirement.value,
            keywords: selectedKeywords.value
        });
        
        if (response.data.success) {
            newPrompt.value.content = response.data.generated_prompt;
            // 如果名称为空，自动填充建议名称
            if (!newPrompt.value.name) {
                newPrompt.value.name = response.data.suggested_name;
            }
            if (!newPrompt.value.description) {
                newPrompt.value.description = response.data.suggested_description;
            }
        }
    } catch (error) {
        console.error('生成Prompt失败:', error);
        alert('生成失败: ' + (error.response?.data?.detail || error.message));
    } finally {
        isGenerating.value = false;
    }
}

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
        alert('激活失败: ' + (error.response?.data?.detail || error.message));
    }
}

async function deactivatePrompt(promptId) {
    try {
        await axios.post(`${apiBase}/prompts/${promptId}/deactivate`);
        loadPrompts();
    } catch (error) {
        console.error('停用Prompt失败:', error);
        alert('停用失败: ' + (error.response?.data?.detail || error.message));
    }
}

async function deletePrompt(promptId) {
    if (confirm('确定要删除这个Prompt模板吗？此操作不可恢复。')) {
        try {
            await axios.delete(`${apiBase}/prompts/${promptId}`);
            loadPrompts();
            alert('Prompt删除成功！');
        } catch (error) {
            console.error('删除Prompt失败:', error);
            alert('删除失败: ' + (error.response?.data?.detail || error.message));
        }
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
                    <h1>Prompt模板管理 (v2.2)</h1>
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
                        {{ agent.name }}
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
                        <button
                            v-if="prompt.is_active"
                            @click="deactivatePrompt(prompt.id)"
                            class="btn btn-warning btn-small"
                        >
                            停用
                        </button>
                        <button class="btn btn-secondary btn-small" @click="viewPrompt(prompt)">查看</button>
                        <button
                            v-if="!prompt.is_default"
                            @click="deletePrompt(prompt.id)"
                            class="btn btn-danger btn-small"
                        >
                            删除
                        </button>
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
                    <h2>新建Prompt模板 (v2.0 AI增强版)</h2>
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
                                {{ agent.name }}
                            </option>
                        </select>
                    </div>
                    <div class="detail-section">
                        <label>描述:</label>
                        <input type="text" v-model="newPrompt.description" placeholder="简要描述" />
                    </div>

                    <!-- AI 智能辅助面板 -->
                    <div class="ai-helper-panel">
                        <div class="ai-helper-header" @click="showAiPanel = !showAiPanel">
                            <span>✨ AI 智能辅助生成</span>
                            <span class="toggle-icon">{{ showAiPanel ? '▼' : '▶' }}</span>
                        </div>
                        
                        <div v-if="showAiPanel" class="ai-helper-content">
                            <div class="helper-step">
                                <label>1. 描述您的需求:</label>
                                <textarea 
                                    v-model="aiRequirement" 
                                    placeholder="例如：帮我写一个能分析财报并提取风险点的助手..."
                                    rows="3"
                                ></textarea>
                                <button 
                                    class="btn btn-secondary btn-small full-width" 
                                    @click="extractKeywords"
                                    :disabled="isExtracting || !aiRequirement"
                                >
                                    {{ isExtracting ? '分析中...' : '🔍 提取关键词' }}
                                </button>
                            </div>

                            <div v-if="generatedKeywords.length > 0" class="helper-step">
                                <label>2. 选择核心关键词 (点击切换):</label>
                                <div class="keywords-cloud">
                                    <span 
                                        v-for="kw in generatedKeywords" 
                                        :key="kw"
                                        class="keyword-tag"
                                        :class="{ active: selectedKeywords.includes(kw) }"
                                        @click="toggleKeyword(kw)"
                                    >
                                        {{ kw }}
                                        <span class="check-mark" v-if="selectedKeywords.includes(kw)">✓</span>
                                    </span>
                                </div>
                                <button 
                                    class="btn btn-primary btn-small full-width" 
                                    @click="generatePromptWithKeywords"
                                    :disabled="isGenerating || selectedKeywords.length === 0"
                                >
                                    {{ isGenerating ? '生成中...' : '✨ 生成 Prompt 内容' }}
                                </button>
                            </div>
                        </div>
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

.btn-warning {
    background: #ffc107;
    color: #212529;
    border: none;
}

.btn-warning:hover {
    background: #e0a800;
}

.btn-danger {
    background: #dc3545;
    color: white;
    border: none;
}

.btn-danger:hover {
    background: #c82333;
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

/* AI 辅助面板样式 */
.ai-helper-panel {
    border: 1px solid var(--border-primary);
    border-radius: 8px;
    margin-bottom: 20px;
    overflow: hidden;
    background: var(--bg-secondary);
}

.ai-helper-header {
    padding: 12px 16px;
    background: var(--bg-tertiary);
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    color: var(--primary-color);
    user-select: none;
}

.ai-helper-content {
    padding: 16px;
    border-top: 1px solid var(--border-primary);
}

.helper-step {
    margin-bottom: 16px;
}

.helper-step:last-child {
    margin-bottom: 0;
}

.helper-step label {
    display: block;
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 8px;
}

.helper-step textarea {
    width: 100%;
    padding: 8px;
    border: 1px solid var(--border-secondary);
    border-radius: 6px;
    margin-bottom: 8px;
    background: var(--bg-primary);
    color: var(--text-primary);
    font-size: 13px;
}

.full-width {
    width: 100%;
}

.keywords-cloud {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 12px;
}

.keyword-tag {
    padding: 4px 12px;
    border-radius: 16px;
    background: var(--bg-primary);
    border: 1px solid var(--border-secondary);
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s;
    user-select: none;
    color: var(--text-primary);
}

.keyword-tag:hover {
    border-color: var(--primary-color);
}

.keyword-tag.active {
    background: var(--primary-light);
    border-color: var(--primary-color);
    color: var(--primary-color);
    font-weight: 500;
}

.check-mark {
    margin-left: 4px;
    font-size: 10px;
}
</style>
