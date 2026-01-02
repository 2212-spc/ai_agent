<script setup>
import { ref, onMounted, computed } from 'vue';
import { useChatStore } from '../stores/chat';
import { useNotification, NOTIFICATION_TYPES } from '../composables/useNotification';
import { API_BASE_URL } from '../config/api';

const chatStore = useChatStore();
const { showRich } = useNotification();

// 记忆列表和搜索
const memories = ref([]);
const isLoading = ref(false);
const searchQuery = ref('');
const selectedType = ref('all');
const selectedMemories = ref(new Set());

// 用户偏好设置
const userPreferences = ref({
    default_share_memory: true,
    default_auto_extract: true,
});
const isConfigLoading = ref(false);

// 统计数据
const stats = computed(() => {
    const total = memories.value.length;
    const byType = memories.value.reduce((acc, mem) => {
        acc[mem.memory_type] = (acc[mem.memory_type] || 0) + 1;
        return acc;
    }, {});
    return { total, byType };
});

// 过滤后的记忆列表
const filteredMemories = computed(() => {
    let filtered = memories.value;
    
    // 按类型筛选
    if (selectedType.value !== 'all') {
        filtered = filtered.filter(m => m.memory_type === selectedType.value);
    }
    
    // 按关键词搜索
    if (searchQuery.value.trim()) {
        const query = searchQuery.value.toLowerCase();
        filtered = filtered.filter(m => 
            m.content.toLowerCase().includes(query)
        );
    }
    
    return filtered;
});

// 加载记忆列表
async function loadMemories() {
    isLoading.value = true;
    try {
        const params = new URLSearchParams();
        if (searchQuery.value) params.append('query', searchQuery.value);
        if (selectedType.value !== 'all') params.append('memory_type', selectedType.value);
        params.append('limit', '100');
        
        const response = await fetch(`${API_BASE_URL}/api/memories/search?${params}`);
        if (!response.ok) throw new Error('加载记忆失败');
        
        memories.value = await response.json();
        showRich('记忆加载成功', NOTIFICATION_TYPES.SUCCESS);
    } catch (error) {
        console.error('加载记忆失败:', error);
        showRich('加载记忆失败: ' + error.message, NOTIFICATION_TYPES.ERROR);
    } finally {
        isLoading.value = false;
    }
}

// 加载用户偏好设置
async function loadUserPreferences() {
    const userId = 'default'; // 使用默认用户ID
    isConfigLoading.value = true;
    try {
        const response = await fetch(`${API_BASE_URL}/api/preferences?user_id=${userId}`);
        if (!response.ok) throw new Error('加载偏好设置失败');
        
        const data = await response.json();
        userPreferences.value = {
            default_share_memory: data.default_share_memory,
            default_auto_extract: data.default_auto_extract,
        };
        
        console.log('✅ 用户偏好加载成功:', userPreferences.value);
    } catch (error) {
        console.error('加载用户偏好失败:', error);
        // 使用默认值
    } finally {
        isConfigLoading.value = false;
    }
}

// 更新用户偏好设置
async function updateUserPreferences() {
    const userId = 'default';
    isConfigLoading.value = true;
    try {
        const response = await fetch(`${API_BASE_URL}/api/preferences`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: userId,
                default_share_memory: userPreferences.value.default_share_memory,
                default_auto_extract: userPreferences.value.default_auto_extract,
            }),
        });
        
        if (!response.ok) throw new Error('更新偏好设置失败');
        
        showRich('✅ 偏好设置已保存，所有新对话将使用此设置', NOTIFICATION_TYPES.SUCCESS);
        console.log('✅ 用户偏好已更新:', userPreferences.value);
    } catch (error) {
        console.error('更新偏好设置失败:', error);
        showRich('更新偏好设置失败: ' + error.message, NOTIFICATION_TYPES.ERROR);
    } finally {
        isConfigLoading.value = false;
    }
}

// 切换跨对话记忆开关
function toggleShareMemory() {
    userPreferences.value.default_share_memory = !userPreferences.value.default_share_memory;
    updateUserPreferences();
}

// 切换自动提取开关
function toggleAutoExtract() {
    userPreferences.value.default_auto_extract = !userPreferences.value.default_auto_extract;
    updateUserPreferences();
}

// 删除单条记忆
async function deleteMemory(memoryId) {
    if (!confirm('确定要删除这条记忆吗？')) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/memories/${memoryId}`, {
            method: 'DELETE',
        });
        
        if (!response.ok) throw new Error('删除失败');
        
        memories.value = memories.value.filter(m => m.id !== memoryId);
        selectedMemories.value.delete(memoryId);
        showRich('记忆已删除', NOTIFICATION_TYPES.SUCCESS);
    } catch (error) {
        console.error('删除记忆失败:', error);
        showRich('删除记忆失败: ' + error.message, NOTIFICATION_TYPES.ERROR);
    }
}

// 批量删除记忆
async function deleteBatch() {
    if (selectedMemories.value.size === 0) {
        showRich('请先选择要删除的记忆', NOTIFICATION_TYPES.WARNING);
        return;
    }
    
    if (!confirm(`确定要删除选中的 ${selectedMemories.value.size} 条记忆吗？`)) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/memories/batch`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(Array.from(selectedMemories.value)),
        });
        
        if (!response.ok) throw new Error('批量删除失败');
        
        const result = await response.json();
        memories.value = memories.value.filter(m => !selectedMemories.value.has(m.id));
        selectedMemories.value.clear();
        showRich(`成功删除 ${result.deleted_count} 条记忆`, NOTIFICATION_TYPES.SUCCESS);
    } catch (error) {
        console.error('批量删除失败:', error);
        showRich('批量删除失败: ' + error.message, NOTIFICATION_TYPES.ERROR);
    }
}

// 切换选中状态
function toggleSelection(memoryId) {
    if (selectedMemories.value.has(memoryId)) {
        selectedMemories.value.delete(memoryId);
    } else {
        selectedMemories.value.add(memoryId);
    }
}

// 全选/取消全选
function toggleSelectAll() {
    if (selectedMemories.value.size === filteredMemories.value.length) {
        selectedMemories.value.clear();
    } else {
        filteredMemories.value.forEach(m => selectedMemories.value.add(m.id));
    }
}

// 获取记忆类型的中文名称
function getTypeLabel(type) {
    const labels = {
        fact: '事实',
        preference: '偏好',
        event: '事件',
        relationship: '关系'
    };
    return labels[type] || type;
}

// 获取记忆类型的颜色
function getTypeColor(type) {
    const colors = {
        fact: '#10a37f',
        preference: '#667eea',
        event: '#f59e0b',
        relationship: '#ec4899'
    };
    return colors[type] || '#6b7280';
}

// 格式化日期
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// 格式化重要性评分
function getImportanceLabel(score) {
    if (score >= 90) return '极高';
    if (score >= 80) return '高';
    if (score >= 70) return '中高';
    if (score >= 60) return '中';
    return '低';
}

onMounted(() => {
    loadMemories();
    loadUserPreferences();
});
</script>

<template>
    <div class="memory-page">
        <!-- 顶部导航栏 -->
        <div class="header">
            <div class="header-left">
                <h1>记忆管理</h1>
                <div class="stats">
                    <span class="stat-item">总计: {{ stats.total }}</span>
                    <span class="stat-item" v-if="stats.byType.fact">事实: {{ stats.byType.fact }}</span>
                    <span class="stat-item" v-if="stats.byType.preference">偏好: {{ stats.byType.preference }}</span>
                    <span class="stat-item" v-if="stats.byType.event">事件: {{ stats.byType.event }}</span>
                    <span class="stat-item" v-if="stats.byType.relationship">关系: {{ stats.byType.relationship }}</span>
                </div>
            </div>
            <div class="header-right">
                <button @click="loadMemories" class="btn-icon" title="刷新">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
                    </svg>
                </button>
            </div>
        </div>

        <div class="content">
            <!-- 左侧：记忆配置 -->
            <div class="config-panel">
                <div class="panel-card">
                    <h3>🌐 全局记忆设置</h3>
                    <p style="color: #6b7280; font-size: 14px; margin-bottom: 16px;">
                        这些设置将应用于所有新建的对话
                    </p>
                    
                    <div class="config-section">
                        <div class="config-item">
                            <div class="config-label">
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                                    <circle cx="9" cy="7" r="4"/>
                                    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                                    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                                </svg>
                                <div>
                                    <strong>新对话默认共享记忆</strong>
                                    <p class="config-desc">开启后，新对话可以访问历史记忆；关闭后，新对话将完全隔离</p>
                                </div>
                            </div>
                            <label class="toggle-switch">
                                <input 
                                    type="checkbox" 
                                    v-model="userPreferences.default_share_memory"
                                    @change="toggleShareMemory"
                                    :disabled="isConfigLoading"
                                />
                                <span class="slider"></span>
                            </label>
                        </div>

                        <div class="config-item">
                            <div class="config-label">
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <path d="M12 20h9"/>
                                    <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>
                                </svg>
                                <div>
                                    <strong>新对话默认自动提取记忆</strong>
                                    <p class="config-desc">开启后，新对话会自动提取重要信息作为长期记忆</p>
                                </div>
                            </div>
                            <label class="toggle-switch">
                                <input 
                                    type="checkbox" 
                                    v-model="userPreferences.default_auto_extract"
                                    @change="toggleAutoExtract"
                                    :disabled="isConfigLoading"
                                />
                                <span class="slider"></span>
                            </label>
                        </div>
                    </div>

                    <div class="info-box">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <circle cx="12" cy="12" r="10"/>
                            <path d="M12 16v-4"/>
                            <path d="M12 8h.01"/>
                        </svg>
                        <div>
                            <p><strong>💡 说明：</strong></p>
                            <ul style="margin-bottom: 12px;">
                                <li>✅ 修改这些设置后，<strong>所有新建的对话</strong>都会使用新设置</li>
                                <li>📝 已有对话的设置不会改变</li>
                                <li>🔒 关闭记忆共享后，新对话将无法访问历史记忆</li>
                            </ul>
                            <p><strong>记忆类型：</strong></p>
                            <ul>
                                <li><span class="type-badge" style="background: #10a37f">事实</span> 明确的事实信息（姓名、职业等）</li>
                                <li><span class="type-badge" style="background: #667eea">偏好</span> 用户的偏好和习惯</li>
                                <li><span class="type-badge" style="background: #f59e0b">事件</span> 重要的事件或计划</li>
                                <li><span class="type-badge" style="background: #ec4899">关系</span> 人物关系或社交信息</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 右侧：记忆列表 -->
            <div class="memory-panel">
                <!-- 搜索和筛选 -->
                <div class="toolbar">
                    <div class="search-box">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <circle cx="11" cy="11" r="8"/>
                            <path d="m21 21-4.35-4.35"/>
                        </svg>
                        <input 
                            v-model="searchQuery" 
                            type="text" 
                            placeholder="搜索记忆内容..."
                            @input="loadMemories"
                        />
                    </div>

                    <select v-model="selectedType" @change="loadMemories" class="type-filter">
                        <option value="all">所有类型</option>
                        <option value="fact">事实</option>
                        <option value="preference">偏好</option>
                        <option value="event">事件</option>
                        <option value="relationship">关系</option>
                    </select>

                    <button 
                        @click="toggleSelectAll" 
                        class="btn-secondary"
                        :disabled="filteredMemories.length === 0"
                    >
                        {{ selectedMemories.size === filteredMemories.length ? '取消全选' : '全选' }}
                    </button>

                    <button 
                        @click="deleteBatch" 
                        class="btn-danger"
                        :disabled="selectedMemories.size === 0"
                    >
                        删除选中 ({{ selectedMemories.size }})
                    </button>
                </div>

                <!-- 记忆列表 -->
                <div class="memory-list" v-if="!isLoading">
                    <div 
                        v-for="memory in filteredMemories" 
                        :key="memory.id"
                        class="memory-item"
                        :class="{ selected: selectedMemories.has(memory.id) }"
                    >
                        <div class="memory-checkbox">
                            <input 
                                type="checkbox" 
                                :checked="selectedMemories.has(memory.id)"
                                @change="toggleSelection(memory.id)"
                            />
                        </div>

                        <div class="memory-content">
                            <div class="memory-header">
                                <span 
                                    class="type-badge" 
                                    :style="{ background: getTypeColor(memory.memory_type) }"
                                >
                                    {{ getTypeLabel(memory.memory_type) }}
                                </span>
                                <span class="importance-badge" :class="'importance-' + Math.floor(memory.importance_score / 20)">
                                    {{ getImportanceLabel(memory.importance_score) }} ({{ memory.importance_score }})
                                </span>
                                <span class="access-count">访问 {{ memory.access_count }} 次</span>
                            </div>

                            <div class="memory-text">
                                {{ memory.content }}
                            </div>

                            <div class="memory-footer">
                                <span class="timestamp">
                                    创建于 {{ formatDate(memory.created_at) }}
                                </span>
                                <span v-if="memory.last_accessed_at" class="timestamp">
                                    最后访问 {{ formatDate(memory.last_accessed_at) }}
                                </span>
                            </div>
                        </div>

                        <button @click="deleteMemory(memory.id)" class="btn-delete" title="删除">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                <path d="M3 6h18"/>
                                <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>
                                <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
                            </svg>
                        </button>
                    </div>

                    <div v-if="filteredMemories.length === 0" class="empty-state">
                        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" opacity="0.3">
                            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
                            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
                        </svg>
                        <p>暂无记忆</p>
                        <p class="empty-hint">对话中的重要信息会自动保存为记忆</p>
                    </div>
                </div>

                <div v-else class="loading-state">
                    <div class="spinner"></div>
                    <p>加载中...</p>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.memory-page {
    height: 100vh;
    display: flex;
    flex-direction: column;
    background: var(--bg-primary, #f9fafb);
}

.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 30px;
    background: white;
    border-bottom: 1px solid #e5e7eb;
}

.header-left {
    display: flex;
    align-items: center;
    gap: 20px;
}

.header-left h1 {
    margin: 0;
    font-size: 24px;
    font-weight: 600;
    color: #111827;
}

.stats {
    display: flex;
    gap: 15px;
}

.stat-item {
    padding: 4px 12px;
    background: #f3f4f6;
    border-radius: 12px;
    font-size: 13px;
    color: #6b7280;
}

.header-right {
    display: flex;
    gap: 10px;
}

.btn-icon {
    padding: 8px;
    background: transparent;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    cursor: pointer;
    color: #6b7280;
    transition: all 0.2s;
}

.btn-icon:hover {
    background: #f9fafb;
    color: #111827;
}

.content {
    display: flex;
    flex: 1;
    overflow: hidden;
    gap: 20px;
    padding: 20px 30px;
}

.config-panel {
    width: 380px;
    flex-shrink: 0;
}

.memory-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.panel-card {
    background: white;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.panel-card h3 {
    margin: 0 0 20px 0;
    font-size: 18px;
    font-weight: 600;
    color: #111827;
}

.config-section {
    display: flex;
    flex-direction: column;
    gap: 20px;
    margin-bottom: 24px;
}

.config-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px;
    background: #f9fafb;
    border-radius: 8px;
}

.config-label {
    display: flex;
    gap: 12px;
    flex: 1;
}

.config-label svg {
    flex-shrink: 0;
    margin-top: 2px;
    color: #6b7280;
}

.config-label strong {
    display: block;
    font-size: 14px;
    color: #111827;
    margin-bottom: 4px;
}

.config-desc {
    font-size: 12px;
    color: #6b7280;
    margin: 0;
    line-height: 1.4;
}

.toggle-switch {
    position: relative;
    display: inline-block;
    width: 44px;
    height: 24px;
    flex-shrink: 0;
}

.toggle-switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #cbd5e1;
    transition: 0.3s;
    border-radius: 24px;
}

.slider:before {
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

input:checked + .slider {
    background-color: #10a37f;
}

input:checked + .slider:before {
    transform: translateX(20px);
}

input:disabled + .slider {
    opacity: 0.5;
    cursor: not-allowed;
}

.info-box {
    display: flex;
    gap: 12px;
    padding: 16px;
    background: #eff6ff;
    border-radius: 8px;
    border-left: 3px solid #3b82f6;
}

.info-box svg {
    flex-shrink: 0;
    color: #3b82f6;
    margin-top: 2px;
}

.info-box p {
    margin: 0 0 8px 0;
    font-size: 13px;
    color: #1e40af;
}

.info-box ul {
    margin: 0;
    padding-left: 20px;
    font-size: 12px;
    color: #1e3a8a;
    line-height: 1.8;
}

.toolbar {
    display: flex;
    gap: 12px;
    margin-bottom: 16px;
    background: white;
    padding: 16px;
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.search-box {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 12px;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
}

.search-box svg {
    color: #9ca3af;
}

.search-box input {
    flex: 1;
    border: none;
    background: transparent;
    outline: none;
    font-size: 14px;
    color: #111827;
    padding: 8px 0;
}

.type-filter {
    padding: 8px 16px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: white;
    font-size: 14px;
    color: #374151;
    cursor: pointer;
    outline: none;
}

.type-filter:hover {
    border-color: #d1d5db;
}

.btn-secondary,
.btn-danger {
    padding: 8px 16px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-secondary {
    background: #f3f4f6;
    color: #374151;
}

.btn-secondary:hover:not(:disabled) {
    background: #e5e7eb;
}

.btn-danger {
    background: #fee;
    color: #dc2626;
}

.btn-danger:hover:not(:disabled) {
    background: #fecaca;
}

.btn-secondary:disabled,
.btn-danger:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.memory-list {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 2px;
}

.memory-item {
    display: flex;
    gap: 12px;
    padding: 16px;
    background: white;
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    transition: all 0.2s;
}

.memory-item:hover {
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.memory-item.selected {
    border: 2px solid #10a37f;
    padding: 15px;
}

.memory-checkbox {
    flex-shrink: 0;
}

.memory-checkbox input[type="checkbox"] {
    width: 18px;
    height: 18px;
    cursor: pointer;
}

.memory-content {
    flex: 1;
    min-width: 0;
}

.memory-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    flex-wrap: wrap;
}

.type-badge {
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
    color: white;
}

.importance-badge {
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
}

.importance-4 {
    background: #fee;
    color: #dc2626;
}

.importance-3,
.importance-2 {
    background: #fef3c7;
    color: #d97706;
}

.importance-1,
.importance-0 {
    background: #e5e7eb;
    color: #6b7280;
}

.access-count {
    padding: 4px 10px;
    background: #f3f4f6;
    border-radius: 12px;
    font-size: 12px;
    color: #6b7280;
}

.memory-text {
    font-size: 14px;
    color: #111827;
    line-height: 1.6;
    margin-bottom: 12px;
    word-break: break-word;
}

.memory-footer {
    display: flex;
    gap: 16px;
    font-size: 12px;
    color: #9ca3af;
}

.btn-delete {
    flex-shrink: 0;
    padding: 8px;
    background: transparent;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    cursor: pointer;
    color: #dc2626;
    transition: all 0.2s;
    height: fit-content;
}

.btn-delete:hover {
    background: #fee;
    border-color: #fecaca;
}

.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #9ca3af;
}

.empty-state p {
    margin: 16px 0 4px 0;
    font-size: 16px;
    font-weight: 500;
}

.empty-hint {
    font-size: 14px !important;
    color: #d1d5db !important;
}

.loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #9ca3af;
}

.spinner {
    width: 40px;
    height: 40px;
    border: 4px solid #e5e7eb;
    border-top-color: #10a37f;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.loading-state p {
    margin-top: 16px;
    font-size: 14px;
}

/* 滚动条样式 */
.memory-list::-webkit-scrollbar {
    width: 8px;
}

.memory-list::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 4px;
}

.memory-list::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 4px;
}

.memory-list::-webkit-scrollbar-thumb:hover {
    background: #94a3b8;
}
</style>

