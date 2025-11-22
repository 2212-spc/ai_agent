<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';

const router = useRouter();
const memories = ref([]);
const isLoading = ref(false);
const showCreateModal = ref(false);
const newMemory = ref({
    content: '',
    importance: 'medium',
    tags: '',
    metadata: {}
});
const apiBase = 'http://127.0.0.1:8000';

async function loadMemories() {
    isLoading.value = true;
    try {
        const response = await axios.get(`${apiBase}/memory/list`);
        memories.value = response.data;
    } catch (error) {
        console.error('加载记忆失败:', error);
    } finally {
        isLoading.value = false;
    }
}

async function createMemory() {
    try {
        const tags = newMemory.value.tags.split(',').map(t => t.trim()).filter(t => t);
        
        await axios.post(`${apiBase}/memory`, {
            content: newMemory.value.content,
            importance: newMemory.value.importance,
            tags: tags,
            metadata: {}
        });
        
        alert('记忆创建成功！');
        closeCreateModal();
        loadMemories();
    } catch (error) {
        console.error('创建记忆失败:', error);
        alert('创建失败: ' + (error.response?.data?.detail || error.message));
    }
}

async function deleteMemory(memoryId) {
    if (!confirm('确定要删除这条记忆吗？')) return;
    
    try {
        await axios.delete(`${apiBase}/memory/${memoryId}`);
        loadMemories();
    } catch (error) {
        console.error('删除记忆失败:', error);
    }
}

function openCreateModal() {
    newMemory.value = {
        content: '',
        importance: 'medium',
        tags: '',
        metadata: {}
    };
    showCreateModal.value = true;
}

function closeCreateModal() {
    showCreateModal.value = false;
}

onMounted(() => {
    loadMemories();
});
</script>

<template>
    <div class="page-container">
        <div class="header">
            <div class="header-left">
                <button class="btn-icon" @click="router.push('/chat')">←</button>
                <div>
                    <h1>记忆管理</h1>
                    <p class="subtitle">管理AI的长期记忆</p>
                </div>
            </div>
            <div class="header-actions">
                <button class="btn btn-secondary" @click="loadMemories">🔄 刷新</button>
                <button class="btn btn-primary" @click="openCreateModal">➕ 新建记忆</button>
            </div>
        </div>

        <div class="content">
            <div v-if="isLoading" class="loading">加载中...</div>
            <div v-else-if="memories.length === 0" class="empty-state">
                <div class="empty-state-icon">🧠</div>
                <h3>暂无记忆</h3>
                <p>创建记忆让AI记住重要信息</p>
            </div>
            <div v-else class="memories-grid">
                <div
                    v-for="memory in memories"
                    :key="memory.id"
                    class="memory-card"
                >
                    <div class="memory-header">
                        <span class="importance-badge" :class="`importance-${memory.importance}`">
                            {{ memory.importance === 'high' ? '重要' : memory.importance === 'medium' ? '中等' : '一般' }}
                        </span>
                        <button class="btn-icon-small" @click="deleteMemory(memory.id)">🗑️</button>
                    </div>
                    <p class="memory-content">{{ memory.content }}</p>
                    <div class="memory-tags" v-if="memory.tags && memory.tags.length > 0">
                        <span v-for="tag in memory.tags" :key="tag" class="tag">{{ tag }}</span>
                    </div>
                    <div class="memory-meta">
                        <span>📅 {{ new Date(memory.created_at).toLocaleString() }}</span>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 创建记忆Modal -->
        <div v-if="showCreateModal" class="modal-overlay" @click="closeCreateModal">
            <div class="modal-content" @click.stop>
                <div class="modal-header">
                    <h2>新建记忆</h2>
                    <button class="modal-close" @click="closeCreateModal">×</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label>内容:</label>
                        <textarea v-model="newMemory.content" rows="4" placeholder="输入要记住的内容..."></textarea>
                    </div>
                    <div class="form-group">
                        <label>重要性:</label>
                        <select v-model="newMemory.importance">
                            <option value="low">一般</option>
                            <option value="medium">中等</option>
                            <option value="high">重要</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>标签 (逗号分隔):</label>
                        <input type="text" v-model="newMemory.tags" placeholder="例如: 工作, 个人, 重要" />
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" @click="closeCreateModal">取消</button>
                    <button class="btn btn-primary" @click="createMemory">创建</button>
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

.header-actions {
    display: flex;
    gap: 12px;
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

.memories-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
}

.memory-card {
    background: var(--bg-primary);
    border: 1px solid var(--border-primary);
    border-radius: 12px;
    padding: 16px;
    transition: all 0.2s;
}

.memory-card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
}

.memory-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.importance-badge {
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
}

.importance-high {
    background: #fee;
    color: #c00;
}

.importance-medium {
    background: #fef3c7;
    color: #92400e;
}

.importance-low {
    background: var(--bg-tertiary);
    color: var(--text-tertiary);
}

.memory-content {
    color: var(--text-primary);
    line-height: 1.6;
    margin-bottom: 12px;
}

.memory-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 12px;
}

.tag {
    background: var(--primary-light);
    color: var(--primary-color);
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
}

.memory-meta {
    font-size: 12px;
    color: var(--text-tertiary);
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
    max-width: 600px;
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

.form-group {
    margin-bottom: 16px;
}

.form-group label {
    display: block;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 8px;
    font-size: 13px;
}

.form-group input,
.form-group textarea,
.form-group select {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--border-secondary);
    border-radius: 6px;
    background: var(--bg-secondary);
    color: var(--text-primary);
    font-size: 14px;
    font-family: inherit;
}

.form-group input:focus,
.form-group textarea:focus,
.form-group select:focus {
    outline: none;
    border-color: var(--primary-color);
}

.modal-footer {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
    padding: 16px 20px;
    border-top: 1px solid var(--border-primary);
}
</style>
