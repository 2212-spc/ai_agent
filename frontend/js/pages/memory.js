// Memory Management JavaScript

const API_BASE = 'http://127.0.0.1:8000';

// State
let memories = [];
let filteredMemories = [];
let selectedMemories = new Set();
let userPreferences = {
    default_share_memory: true,
    default_auto_extract: true
};
let pendingAction = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadMemories();
    loadUserPreferences();
    initTheme();
});

// ==================== API Calls ====================

async function loadMemories() {
    try {
        showLoading();
        
        const params = new URLSearchParams();
        const searchQuery = document.getElementById('searchInput').value;
        const typeFilter = document.getElementById('typeFilter').value;
        
        if (searchQuery) params.append('query', searchQuery);
        if (typeFilter !== 'all') params.append('memory_type', typeFilter);
        params.append('limit', '100');
        
        const response = await fetch(`${API_BASE}/api/memories/search?${params}`);
        if (!response.ok) throw new Error('加载记忆失败');
        
        memories = await response.json();
        filteredMemories = [...memories];
        
        renderMemories();
        updateStats();
        showToast('记忆加载成功', 'success');
    } catch (error) {
        console.error('加载记忆失败:', error);
        showToast('加载记忆失败: ' + error.message, 'error');
        showEmptyState('加载失败');
    }
}

async function loadUserPreferences() {
    try {
        const userId = 'default'; // 使用默认用户ID
        const response = await fetch(`${API_BASE}/api/preferences?user_id=${userId}`);
        if (!response.ok) throw new Error('加载偏好设置失败');
        
        const data = await response.json();
        userPreferences = {
            default_share_memory: data.default_share_memory,
            default_auto_extract: data.default_auto_extract
        };
        
        // Update UI
        document.getElementById('shareMemoryToggle').checked = userPreferences.default_share_memory;
        document.getElementById('autoExtractToggle').checked = userPreferences.default_auto_extract;
        
        console.log('✅ 用户偏好加载成功:', userPreferences);
    } catch (error) {
        console.error('加载用户偏好失败:', error);
        // 使用默认值
        document.getElementById('shareMemoryToggle').checked = true;
        document.getElementById('autoExtractToggle').checked = true;
    }
}

async function updateUserPreferences() {
    try {
        const userId = 'default';
        const response = await fetch(`${API_BASE}/api/preferences`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: userId,
                default_share_memory: userPreferences.default_share_memory,
                default_auto_extract: userPreferences.default_auto_extract,
            }),
        });
        
        if (!response.ok) throw new Error('更新偏好设置失败');
        
        showToast('✅ 偏好设置已保存，所有新对话将使用此设置', 'success');
        console.log('✅ 用户偏好已更新:', userPreferences);
    } catch (error) {
        console.error('更新偏好设置失败:', error);
        showToast('更新偏好设置失败: ' + error.message, 'error');
    }
}

async function deleteMemoryById(memoryId) {
    try {
        const response = await fetch(`${API_BASE}/api/memories/${memoryId}`, {
            method: 'DELETE',
        });
        
        if (!response.ok) throw new Error('删除失败');
        
        memories = memories.filter(m => m.id !== memoryId);
        filteredMemories = filteredMemories.filter(m => m.id !== memoryId);
        selectedMemories.delete(memoryId);
        
        renderMemories();
        updateStats();
        showToast('记忆已删除', 'success');
    } catch (error) {
        console.error('删除记忆失败:', error);
        showToast('删除记忆失败: ' + error.message, 'error');
    }
}

async function deleteMemoriesBatch(memoryIds) {
    try {
        const response = await fetch(`${API_BASE}/api/memories/batch`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(memoryIds),
        });
        
        if (!response.ok) throw new Error('批量删除失败');
        
        const result = await response.json();
        
        memories = memories.filter(m => !memoryIds.includes(m.id));
        filteredMemories = filteredMemories.filter(m => !memoryIds.includes(m.id));
        selectedMemories.clear();
        
        renderMemories();
        updateStats();
        showToast(`成功删除 ${result.deleted_count} 条记忆`, 'success');
    } catch (error) {
        console.error('批量删除失败:', error);
        showToast('批量删除失败: ' + error.message, 'error');
    }
}

// ==================== UI Actions ====================

function toggleShareMemory() {
    userPreferences.default_share_memory = !userPreferences.default_share_memory;
    updateUserPreferences();
}

function toggleAutoExtract() {
    userPreferences.default_auto_extract = !userPreferences.default_auto_extract;
    updateUserPreferences();
}

function searchMemories() {
    filterMemories();
}

function filterMemories() {
    const searchQuery = document.getElementById('searchInput').value.toLowerCase();
    const typeFilter = document.getElementById('typeFilter').value;
    
    filteredMemories = memories.filter(memory => {
        // Type filter
        if (typeFilter !== 'all' && memory.memory_type !== typeFilter) {
            return false;
        }
        
        // Search filter
        if (searchQuery && !memory.content.toLowerCase().includes(searchQuery)) {
            return false;
        }
        
        return true;
    });
    
    renderMemories();
}

function refreshMemories() {
    selectedMemories.clear();
    loadMemories();
}

function toggleSelection(memoryId) {
    if (selectedMemories.has(memoryId)) {
        selectedMemories.delete(memoryId);
    } else {
        selectedMemories.add(memoryId);
    }
    
    updateSelectionUI();
}

function toggleSelectAll() {
    if (selectedMemories.size === filteredMemories.length && filteredMemories.length > 0) {
        selectedMemories.clear();
    } else {
        filteredMemories.forEach(m => selectedMemories.add(m.id));
    }
    
    updateSelectionUI();
}

function deleteMemory(memoryId) {
    showConfirmDialog(
        '确认删除',
        '确定要删除这条记忆吗？',
        () => deleteMemoryById(memoryId)
    );
}

function deleteBatch() {
    if (selectedMemories.size === 0) {
        showToast('请先选择要删除的记忆', 'warning');
        return;
    }
    
    showConfirmDialog(
        '批量删除',
        `确定要删除选中的 ${selectedMemories.size} 条记忆吗？`,
        () => deleteMemoriesBatch(Array.from(selectedMemories))
    );
}

// ==================== Rendering ====================

function renderMemories() {
    const listContainer = document.getElementById('memoryList');
    
    if (filteredMemories.length === 0) {
        showEmptyState(memories.length === 0 ? '暂无记忆' : '无匹配结果');
        return;
    }
    
    listContainer.innerHTML = filteredMemories.map(memory => `
        <div class="memory-item ${selectedMemories.has(memory.id) ? 'selected' : ''}" data-id="${memory.id}">
            <div class="memory-checkbox">
                <input 
                    type="checkbox" 
                    ${selectedMemories.has(memory.id) ? 'checked' : ''}
                    onchange="toggleSelection('${memory.id}')"
                />
            </div>
            
            <div class="memory-content">
                <div class="memory-header">
                    <span class="memory-type ${memory.memory_type}">
                        ${getTypeLabel(memory.memory_type)}
                    </span>
                    <span class="importance-badge ${getImportanceClass(memory.importance_score)}">
                        ${getImportanceLabel(memory.importance_score)} (${memory.importance_score})
                    </span>
                    <span class="access-count">访问 ${memory.access_count} 次</span>
                </div>
                
                <div class="memory-text">
                    ${escapeHtml(memory.content)}
                </div>
                
                <div class="memory-footer">
                    <span class="timestamp">创建于 ${formatDate(memory.created_at)}</span>
                    ${memory.last_accessed_at ? `<span class="timestamp">最后访问 ${formatDate(memory.last_accessed_at)}</span>` : ''}
                </div>
            </div>
            
            <button class="btn-delete" onclick="deleteMemory('${memory.id}')" title="删除">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path d="M3 6h18"/>
                    <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>
                    <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
                </svg>
            </button>
        </div>
    `).join('');
    
    updateSelectionUI();
}

function updateStats() {
    const stats = {
        total: memories.length,
        fact: 0,
        preference: 0,
        event: 0,
        relationship: 0
    };
    
    memories.forEach(memory => {
        if (memory.memory_type in stats) {
            stats[memory.memory_type]++;
        }
    });
    
    document.getElementById('totalMemories').textContent = stats.total;
    document.getElementById('factCount').textContent = stats.fact;
    document.getElementById('preferenceCount').textContent = stats.preference;
    document.getElementById('eventCount').textContent = stats.event;
    document.getElementById('relationshipCount').textContent = stats.relationship;
}

function updateSelectionUI() {
    const count = selectedMemories.size;
    document.getElementById('selectedCount').textContent = count;
    document.getElementById('deleteBatchBtn').disabled = count === 0;
    
    const selectAllBtn = document.getElementById('selectAllBtn');
    if (count === filteredMemories.length && filteredMemories.length > 0) {
        selectAllBtn.textContent = '取消全选';
    } else {
        selectAllBtn.textContent = '全选';
    }
    
    // Update checkboxes
    filteredMemories.forEach(memory => {
        const item = document.querySelector(`.memory-item[data-id="${memory.id}"]`);
        if (item) {
            const checkbox = item.querySelector('input[type="checkbox"]');
            if (checkbox) {
                checkbox.checked = selectedMemories.has(memory.id);
            }
            
            if (selectedMemories.has(memory.id)) {
                item.classList.add('selected');
            } else {
                item.classList.remove('selected');
            }
        }
    });
}

function showLoading() {
    const listContainer = document.getElementById('memoryList');
    listContainer.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>加载中...</p>
        </div>
    `;
}

function showEmptyState(message = '暂无记忆') {
    const listContainer = document.getElementById('memoryList');
    listContainer.innerHTML = `
        <div class="empty-state">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
                <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
            </svg>
            <p>${message}</p>
            <p class="empty-hint">对话中的重要信息会自动保存为记忆</p>
        </div>
    `;
}

// ==================== Utilities ====================

function getTypeLabel(type) {
    const labels = {
        fact: '事实',
        preference: '偏好',
        event: '事件',
        relationship: '关系'
    };
    return labels[type] || type;
}

function getImportanceLabel(score) {
    if (score >= 90) return '极高';
    if (score >= 80) return '高';
    if (score >= 70) return '中高';
    if (score >= 60) return '中';
    return '低';
}

function getImportanceClass(score) {
    if (score >= 80) return 'importance-high';
    if (score >= 60) return 'importance-medium';
    return 'importance-low';
}

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

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== Dialog ====================

function showConfirmDialog(title, message, onConfirm) {
    document.getElementById('dialogTitle').textContent = title;
    document.getElementById('dialogMessage').textContent = message;
    document.getElementById('confirmDialog').classList.add('show');
    
    pendingAction = onConfirm;
}

function closeDialog() {
    document.getElementById('confirmDialog').classList.remove('show');
    pendingAction = null;
}

function confirmAction() {
    if (pendingAction) {
        pendingAction();
        pendingAction = null;
    }
    closeDialog();
}

// ==================== Toast ====================

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    const toastIcon = document.getElementById('toastIcon');
    const toastMessage = document.getElementById('toastMessage');
    
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };
    
    toastIcon.textContent = icons[type] || icons.info;
    toastMessage.textContent = message;
    
    toast.className = 'toast show ' + type;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// ==================== Theme ====================

function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const icon = document.getElementById('themeIcon');
    if (icon) {
        icon.textContent = theme === 'dark' ? '☀️' : '🌙';
    }
}
