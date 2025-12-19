/**
 * UI交互函数集合
 * 从原内联代码中提取的各种UI交互功能
 * 创建时间：2024-11-21
 */

// ========== 侧边栏控制 ==========
function toggleSidebar() {
    const sidebar = document.getElementById('historySidebar');
    const toggleBtn = document.getElementById('toggleSidebarBtn');
    
    if (!sidebar) {
        console.warn('侧边栏元素未找到');
        return;
    }
    
    // 桌面视图使用 collapsed 类控制
    if (sidebar.classList.contains('collapsed')) {
        sidebar.classList.remove('collapsed');
        if (toggleBtn) toggleBtn.textContent = '◀';
    } else {
        sidebar.classList.add('collapsed');
        if (toggleBtn) toggleBtn.textContent = '▶';
    }
}

// 关闭侧边栏
function closeSidebar() {
    const sidebar = document.getElementById('historySidebar');
    const toggleBtn = document.getElementById('toggleSidebarBtn');
    
    if (sidebar) {
        sidebar.classList.add('collapsed');
        if (toggleBtn) toggleBtn.textContent = '▶';
    }
}

// ========== 时间线控制 ==========
function toggleTimeline() {
    const timeline = document.querySelector('.agent-timeline');
    const toggleText = document.getElementById('timelineToggleText');
    
    if (!timeline) {
        console.warn('时间线元素未找到');
        return;
    }
    
    // 切换 open 类来显示/隐藏时间线
    if (timeline.classList.contains('open')) {
        timeline.classList.remove('open');
        if (toggleText) toggleText.textContent = '展开过程 →';
    } else {
        timeline.classList.add('open');
        if (toggleText) toggleText.textContent = '← 收起过程';
    }
}

// ========== 全局记忆模式切换 ==========
function toggleGlobalMemory() {
    const checkbox = document.getElementById('globalMemoryToggle');
    const isEnabled = checkbox?.checked || false;
    const memoryIndicator = document.getElementById('memoryIndicator');
    
    console.log('全局记忆模式:', isEnabled ? '开启' : '关闭');
    
    // 更新chatManager状态
    if (window.chatManager && typeof window.chatManager.toggleGlobalMemory === 'function') {
        window.chatManager.toggleGlobalMemory(isEnabled);
    }
    
    // 更新记忆模式指示器
    if (memoryIndicator) {
        if (isEnabled) {
            memoryIndicator.textContent = '全局记忆🌐';
            memoryIndicator.classList.add('global-memory');
        } else {
            memoryIndicator.textContent = '独立记忆';
            memoryIndicator.classList.remove('global-memory');
        }
    }
    
    // 显示系统消息
    const message = isEnabled 
        ? '🌐 已启用全局记忆！AI将记住所有对话的内容，可以跨对话引用信息。'
        : '🔒 已切换到独立记忆模式！每个对话拥有独立的记忆，互不干扰。';
    
    if (window.notificationManager) {
        window.notificationManager.show(message, 'success', 3000);
    }
    
    console.log(`记忆模式切换: ${isEnabled ? '全局记忆' : '独立记忆'}`);
}

// ========== 深度思考模式切换 ==========
function toggleDeepThink() {
    const checkbox = document.getElementById('deepThinkToggle');
    const isEnabled = checkbox?.checked || false;
    const thinkIndicator = document.getElementById('thinkIndicator');
    
    console.log('深度思考模式:', isEnabled ? '开启' : '关闭');
    
    // 更新chatManager状态
    if (window.chatManager && typeof window.chatManager.toggleDeepThink === 'function') {
        window.chatManager.toggleDeepThink(isEnabled);
    }
    
    // 更新思考模式指示器
    if (thinkIndicator) {
        if (isEnabled) {
            thinkIndicator.textContent = '深度思考💭';
            thinkIndicator.classList.add('deep-thinking');
        } else {
            thinkIndicator.textContent = '标准模式';
            thinkIndicator.classList.remove('deep-thinking');
        }
    }
    
    // 显示系统消息
    const message = isEnabled 
        ? '🧠 已启用深度思考模式！AI将展示完整的思考过程，帮助您理解推理步骤。'
        : '✨ 已切换到标准模式。AI将直接给出答案。';
    
    if (window.notificationManager) {
        window.notificationManager.show(message, 'success', 3000);
    }
    
    console.log(`思考模式切换: ${isEnabled ? '深度思考' : '标准模式'}`);
}

// ========== 多智能体模式切换 ==========
function toggleMultiAgentMode() {
    const checkbox = document.getElementById('multiAgentToggle');
    const isEnabled = checkbox?.checked || false;
    const modeIndicator = document.getElementById('modeIndicator');
    
    console.log('多智能体模式:', isEnabled ? '开启' : '关闭');
    
    // 更新chatManager状态
    if (window.chatManager && typeof window.chatManager.toggleMultiAgentMode === 'function') {
        window.chatManager.toggleMultiAgentMode(isEnabled);
    }
    
    // 更新模式指示器
    if (modeIndicator) {
        if (isEnabled) {
            modeIndicator.textContent = '多智能体🤖🤖🤖';
            modeIndicator.classList.add('multi-agent');
        } else {
            modeIndicator.textContent = '单智能体';
            modeIndicator.classList.remove('multi-agent');
        }
    }
    
    // 显示系统消息
    const message = isEnabled 
        ? '✨ 已切换到多智能体模式！将由多个专家智能体协作处理您的问题。'
        : '✨ 已切换到单智能体模式。';
    
    if (window.notificationManager) {
        window.notificationManager.show(message, 'success', 3000);
    }
    
    console.log(`模式切换: ${isEnabled ? '多智能体' : '单智能体'}`);
}

// ========== 聊天导出 ==========
function exportChat() {
    const messagesContainer = document.getElementById('messagesContainer');
    if (!messagesContainer) {
        console.warn('消息容器未找到');
        return;
    }
    
    const messages = messagesContainer.querySelectorAll('.message');
    let exportText = '# AI Agent 聊天记录\n\n';
    exportText += `导出时间: ${new Date().toLocaleString('zh-CN')}\n\n`;
    exportText += '---\n\n';
    
    messages.forEach((msg, index) => {
        const role = msg.classList.contains('user-message') ? '用户' : 'AI Agent';
        const content = msg.querySelector('.message-content')?.textContent || '';
        const time = msg.querySelector('.message-time')?.textContent || '';
        
        exportText += `### ${role} [${time}]\n\n`;
        exportText += `${content}\n\n`;
        exportText += '---\n\n';
    });
    
    // 创建下载链接
    const blob = new Blob([exportText], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat_${Date.now()}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    if (window.notificationManager) {
        window.notificationManager.show('✅ 聊天记录已导出', 'success', 2000);
    }
}

// ========== 清空聊天 ==========
function clearChat() {
    if (!confirm('确定要清空所有聊天记录吗？此操作不可恢复。')) {
        return;
    }
    
    const messagesContainer = document.getElementById('messagesContainer');
    if (messagesContainer) {
        messagesContainer.innerHTML = '';
    }
    
    // 清空时间线
    const timelineContent = document.getElementById('timelineContent');
    if (timelineContent) {
        timelineContent.innerHTML = '';
    }
    
    // 重置会话ID
    if (window.chatManager) {
        window.chatManager.currentSessionId = window.chatManager.generateSessionId();
    }
    
    if (window.notificationManager) {
        window.notificationManager.show('✅ 聊天记录已清空', 'success', 2000);
    }
}

// ========== 停止生成 ==========
function stopGeneration() {
    if (window.chatManager && typeof window.chatManager.stopCurrentRequest === 'function') {
        window.chatManager.stopCurrentRequest();
    }
    
    // 切换按钮显示
    const sendBtn = document.getElementById('sendBtn');
    const stopBtn = document.getElementById('stopBtn');
    
    if (sendBtn) sendBtn.style.display = 'flex';
    if (stopBtn) stopBtn.style.display = 'none';
}

// ========== 主题切换 ==========
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    // 更新图标
    const themeIcon = document.querySelector('.theme-toggle-btn');
    if (themeIcon) {
        themeIcon.textContent = newTheme === 'dark' ? '🌙' : '☀️';
    }
    
    if (window.notificationManager) {
        const message = newTheme === 'dark' ? '已切换到暗色主题' : '已切换到亮色主题';
        window.notificationManager.show(message, 'info', 2000);
    }
}

// 初始化主题
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    const themeIcon = document.querySelector('.theme-toggle-btn');
    if (themeIcon) {
        themeIcon.textContent = savedTheme === 'dark' ? '🌙' : '☀️';
    }
}

// ========== 图片/Mermaid模态框 ==========
function closeImageModal() {
    const modal = document.getElementById('imageModal');
    if (modal) {
        modal.classList.remove('active');
    }
}

function closeMermaidModal() {
    const modal = document.getElementById('mermaidModal');
    if (modal) {
        modal.classList.remove('active');
    }
}

// 点击模态框背景关闭
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('active');
    }
});

// ========== 新建会话 ==========
function newChat() {
    if (!confirm('确定要创建新会话吗？当前聊天记录将被保存。')) {
        return;
    }
    
    if (!window.chatManager) {
        console.error('chatManager 未初始化');
        return;
    }
    
    // 生成新会话ID
    const newSessionId = window.chatManager.generateSessionId();
    console.log('🆕 新建会话ID:', newSessionId);
    
    // 保存当前会话的滚动位置
    if (window.chatManager.currentSessionId && window.chatManager.mainContainer) {
        const currentSession = window.chatManager.sessions.get(window.chatManager.currentSessionId);
        if (currentSession) {
            currentSession.scrollPosition = window.chatManager.mainContainer.scrollTop;
        }
    }
    
    // 隐藏当前会话的容器
    if (window.chatManager.currentSessionId) {
        const currentSession = window.chatManager.sessions.get(window.chatManager.currentSessionId);
        if (currentSession && currentSession.containerDiv) {
            currentSession.containerDiv.style.display = 'none';
        }
    }
    
    // 创建新会话
    window.chatManager.ensureSession(newSessionId);
    window.chatManager.currentSessionId = newSessionId;
    
    // 显示新会话的容器（空的）
    const newSession = window.chatManager.sessions.get(newSessionId);
    if (newSession && newSession.containerDiv) {
        newSession.containerDiv.style.display = 'block';
        console.log('📂 已显示新会话容器（空）');
    }
    
    // 清空时间线（新会话没有节点）
    const timelineContent = document.getElementById('timelineContent');
    if (timelineContent) {
        timelineContent.innerHTML = '';
    }
    
    // 移除历史记录项的高亮状态（新会话没有对应的历史记录）
    const historyItems = document.querySelectorAll('.history-item');
    historyItems.forEach(item => {
        item.classList.remove('active');
    });
    
    // 显示空状态（欢迎界面）
    window.chatManager.showEmptyState();
    
    // 更新UI按钮状态
    window.chatManager.updateSendButton(newSessionId);
    
    if (window.notificationManager) {
        window.notificationManager.show('✅ 新会话已创建', 'success', 2000);
    }
}

// startNewChat 别名（兼容旧代码）
function startNewChat() {
    newChat();
}

// ========== 设置面板（已移除，请使用导航栏的"记忆管理"） ==========
// function openSettings() {
//     // 打开设置页面（新标签页）
//     window.open('conversation_settings.html', '_blank');
//     console.log('打开设置页面');
// }

// ========== 输入选项面板 ==========
function toggleInputOptions() {
    const panel = document.getElementById('inputOptionsPanel');
    if (panel) {
        panel.classList.toggle('open');
    }
}

// ========== 文件选择处理 ==========
function handleFileSelect(event) {
    const files = event.target.files;
    if (!files || files.length === 0) {
        return;
    }
    
    const attachedFilesDiv = document.getElementById('attachedFiles');
    if (!attachedFilesDiv) {
        console.warn('附件容器未找到');
        return;
    }
    
    // 显示选中的文件
    attachedFilesDiv.innerHTML = '';
    
    Array.from(files).forEach((file, index) => {
        const fileTag = document.createElement('div');
        fileTag.className = 'attached-file-tag';
        fileTag.innerHTML = `
            <span>📎 ${escapeHtml(file.name)}</span>
            <button onclick="removeFile(${index})" title="移除">×</button>
        `;
        attachedFilesDiv.appendChild(fileTag);
    });
    
    if (window.notificationManager) {
        window.notificationManager.show(`已选择 ${files.length} 个文件`, 'success', 2000);
    }
}

function removeFile(index) {
    const fileInput = document.getElementById('fileInput');
    if (fileInput) {
        // 清空文件输入
        fileInput.value = '';
    }
    
    const attachedFilesDiv = document.getElementById('attachedFiles');
    if (attachedFilesDiv) {
        attachedFilesDiv.innerHTML = '';
    }
}

// ========== 退出登录 ==========
function logout() {
    if (!confirm('确定要退出登录吗？')) {
        return;
    }
    
    // 清除本地存储的用户信息
    localStorage.removeItem('userInfo');
    localStorage.removeItem('token');
    
    if (window.notificationManager) {
        window.notificationManager.show('👋 已退出登录', 'success', 2000);
    }
    
    // 跳转到登录页面
    setTimeout(() => {
        window.location.href = 'login.html';
    }, 1000);
}

// ========== 画布视图控制 ==========
function resetCanvasView() {
    if (window.canvasManager && typeof window.canvasManager.resetView === 'function') {
        window.canvasManager.resetView();
        console.log('重置画布视图');
    }
}

function centerCanvas() {
    if (window.canvasManager && typeof window.canvasManager.centerView === 'function') {
        window.canvasManager.centerView();
        console.log('居中画布');
    } else {
        // 如果没有centerView方法，使用resetView
        resetCanvasView();
    }
}

// ========== 画布示例加载 ==========
function loadExample(exampleType) {
    if (window.notificationManager) {
        window.notificationManager.show(`加载示例: ${exampleType}`, 'info', 2000);
    }
    
    // TODO: 实现示例加载逻辑
    console.log('加载示例:', exampleType);
    
    if (window.canvasManager && typeof window.canvasManager.loadExample === 'function') {
        window.canvasManager.loadExample(exampleType);
    } else {
        if (window.notificationManager) {
            window.notificationManager.show('示例功能开发中...', 'info', 2000);
        }
    }
}

// ========== 快捷示例 ==========
function sendQuickExample(example) {
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.value = example;
        messageInput.focus();
        
        // 自动调整高度
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
    }
}

// useExample 别名（用于HTML中的快捷按钮）
function useExample(example) {
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.value = example;
        messageInput.focus();
        
        // 自动调整高度
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
        
        // 隐藏空状态，显示消息容器
        const emptyState = document.querySelector('.empty-state');
        if (emptyState) {
            emptyState.style.display = 'none';
        }
    }
}

// ========== 构建器面板控制 ==========
function toggleBuilder() {
    const builderPanel = document.getElementById('builderPanel');
    const overlay = document.getElementById('builderOverlay');
    
    if (!builderPanel) {
        console.warn('构建器面板未找到');
        if (window.notificationManager) {
            window.notificationManager.show('构建器功能开发中...', 'info', 2000);
        }
        return;
    }
    
    if (builderPanel.classList.contains('open')) {
        builderPanel.classList.remove('open');
        if (overlay) overlay.classList.remove('active');
    } else {
        builderPanel.classList.add('open');
        if (overlay) overlay.classList.add('active');
    }
}

function closeBuilder() {
    const builderPanel = document.getElementById('builderPanel');
    const overlay = document.getElementById('builderOverlay');
    
    if (builderPanel) builderPanel.classList.remove('open');
    if (overlay) overlay.classList.remove('active');
}

function clearBuilder() {
    if (!confirm('确定要清空构建器吗？所有节点将被删除。')) {
        return;
    }
    
    console.log('清空构建器');
    
    const canvas = document.getElementById('canvasContentLayer');
    if (canvas) {
        canvas.innerHTML = '';
    }
    
    if (window.canvasManager && typeof window.canvasManager.clear === 'function') {
        window.canvasManager.clear();
    }
    
    if (window.notificationManager) {
        window.notificationManager.show('✅ 构建器已清空', 'success', 2000);
    }
}

function saveAgentConfig() {
    console.log('保存Agent配置');
    
    if (!window.canvasManager) {
        if (window.notificationManager) {
            window.notificationManager.show('⚠️ 画布管理器未初始化', 'warning', 2000);
        }
        return;
    }
    
    try {
        // 导出配置
        const config = window.canvasManager.exportConfig();
        
        // 转换为JSON字符串
        const json = JSON.stringify(config, null, 2);
        
        // 创建Blob并下载
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `agent-config-${Date.now()}.json`;
        link.click();
        URL.revokeObjectURL(url);
        
        console.log('配置已导出:', config);
        
        if (window.notificationManager) {
            window.notificationManager.show('💾 配置已保存为JSON文件', 'success', 2000);
        }
    } catch (error) {
        console.error('保存配置失败:', error);
        if (window.notificationManager) {
            window.notificationManager.show('❌ 保存失败', 'error', 2000);
        }
    }
}

function testAgentConfig() {
    console.log('测试Agent配置');
    
    if (window.notificationManager) {
        window.notificationManager.show('▶️ 配置测试功能开发中...', 'info', 2000);
    }
    
    // TODO: 实现配置测试逻辑
}

function autoLayout() {
    console.log('自动布局');
    
    if (window.canvasManager && typeof window.canvasManager.autoLayout === 'function') {
        window.canvasManager.autoLayout();
    } else {
        if (window.notificationManager) {
            window.notificationManager.show('📐 自动布局功能开发中...', 'info', 2000);
        }
    }
}

function undoBuilder() {
    console.log('撤销操作');
    
    if (window.canvasManager && typeof window.canvasManager.undo === 'function') {
        window.canvasManager.undo();
    } else {
        if (window.notificationManager) {
            window.notificationManager.show('⚠️ 画布管理器未初始化', 'warning', 2000);
        }
    }
}

function redoBuilder() {
    console.log('重做操作');
    
    if (window.canvasManager && typeof window.canvasManager.redo === 'function') {
        window.canvasManager.redo();
    } else {
        if (window.notificationManager) {
            window.notificationManager.show('⚠️ 画布管理器未初始化', 'warning', 2000);
        }
    }
}

// ========== 画布节点管理 ==========
function addNode(type, label) {
    console.log(`添加节点: ${type} - ${label}`);
    
    if (window.canvasManager && typeof window.canvasManager.addNode === 'function') {
        window.canvasManager.addNode(type, label);
    } else {
        if (window.notificationManager) {
            window.notificationManager.show(`添加${label}节点`, 'info', 2000);
        }
    }
}

function resetZoom() {
    console.log('重置画布缩放');
    
    if (window.canvasManager && typeof window.canvasManager.resetZoom === 'function') {
        window.canvasManager.resetZoom();
    } else {
        if (window.notificationManager) {
            window.notificationManager.show('画布已重置', 'info', 2000);
        }
    }
}

function zoomIn() {
    console.log('放大画布');
    
    if (window.canvasManager && typeof window.canvasManager.zoomIn === 'function') {
        window.canvasManager.zoomIn();
    } else {
        if (window.notificationManager) {
            window.notificationManager.show('🔍 放大', 'info', 1000);
        }
    }
}

function zoomOut() {
    console.log('缩小画布');
    
    if (window.canvasManager && typeof window.canvasManager.zoomOut === 'function') {
        window.canvasManager.zoomOut();
    } else {
        if (window.notificationManager) {
            window.notificationManager.show('🔍 缩小', 'info', 1000);
        }
    }
}

function deleteSelectedNode() {
    console.log('删除选中节点');
    
    if (window.canvasManager && typeof window.canvasManager.deleteSelected === 'function') {
        window.canvasManager.deleteSelected();
    }
}

function duplicateNode() {
    console.log('复制节点');
    
    if (window.notificationManager) {
        window.notificationManager.show('复制节点功能开发中', 'info', 2000);
    }
}

function closeContextMenu() {
    const contextMenu = document.getElementById('contextMenu');
    if (contextMenu) {
        contextMenu.style.display = 'none';
    }
}

// ========== 时间线过滤 ==========
function toggleTimelineFilter(filter, element) {
    console.log(`切换时间线过滤: ${filter}`);
    
    // 切换当前元素的active状态
    if (element) {
        element.classList.toggle('active');
    }
    
    // 根据过滤器显示/隐藏时间线内容
    const timelineContent = document.getElementById('timelineContent');
    if (timelineContent) {
        const items = timelineContent.querySelectorAll(`[data-type="${filter}"]`);
        items.forEach(item => {
            if (element && element.classList.contains('active')) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    }
    
    console.log(`时间线过滤已切换: ${filter}`);
}

// ========== 历史记录管理 ==========
async function refreshHistoryList() {
    const API_BASE = window.chatManager?.API_BASE || 'http://127.0.0.1:8000';
    const sidebarContent = document.getElementById('sidebarHistoryList');
    
    if (!sidebarContent) {
        console.warn('侧边栏内容容器未找到');
        return;
    }
    
    // 显示加载状态
    sidebarContent.innerHTML = '<div class="history-loading">🔄 加载中...</div>';
    
    try {
        // 获取用户信息
        const userInfo = localStorage.getItem('userInfo');
        const userId = userInfo ? JSON.parse(userInfo).user_id : null;
        
        // 构建API URL
        let url = `${API_BASE}/conversations?limit=50&offset=0`;
        if (userId) {
            url += `&user_id=${userId}`;
        }
        
        console.log('加载历史记录:', url);
        
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const conversations = await response.json();
        console.log('获取到历史记录:', conversations.length, '条');
        
        // 渲染历史记录
        if (conversations.length === 0) {
            sidebarContent.innerHTML = '<div class="history-empty">📭 暂无历史记录</div>';
        } else {
            sidebarContent.innerHTML = conversations.map(conv => {
                const time = formatHistoryTime(conv.last_message_time);
                const preview = escapeHtml(conv.preview || '').substring(0, 40);
                
                // 检查是否是当前会话
                const isActive = window.chatManager?.currentSessionId === conv.session_id;
                const activeClass = isActive ? ' active' : '';
                
                return `
                    <div class="history-item${activeClass}" 
                         data-session-id="${conv.session_id}"
                         onclick="loadHistorySession('${conv.session_id}')">
                        <div class="history-item-title">${escapeHtml(conv.title || '未命名对话')}</div>
                        <div class="history-item-preview">${preview}...</div>
                        <div class="history-item-time">💬 ${conv.message_count} · 🕐 ${time}</div>
                    </div>
                `;
            }).join('');
        }
        
        if (window.notificationManager) {
            window.notificationManager.show('✅ 历史记录已更新', 'success', 1000);
        }
        
    } catch (error) {
        console.error('加载历史记录失败:', error);
        sidebarContent.innerHTML = '<div class="history-error">❌ 加载失败<br><button onclick="refreshHistoryList()">重试</button></div>';
        
        if (window.notificationManager) {
            window.notificationManager.show('加载历史记录失败', 'error', 2000);
        }
    }
}

// 格式化历史记录时间
function formatHistoryTime(timeStr) {
    if (!timeStr) return '未知';
    
    const date = new Date(timeStr);
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (minutes < 1) return '刚刚';
    if (minutes < 60) return `${minutes}分钟前`;
    if (hours < 24) return `${hours}小时前`;
    if (days < 7) return `${days}天前`;
    
    return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
}

// HTML转义
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function loadHistorySession(sessionId) {
    if (!sessionId) {
        console.warn('会话ID为空');
        return;
    }
    
    console.log('加载历史会话:', sessionId);
    
    if (window.chatManager) {
        // 使用新的 switchToSession 方法（支持多会话并发）
        // switchToSession 会自动加载历史消息（如果需要）
        if (typeof window.chatManager.switchToSession === 'function') {
            window.chatManager.switchToSession(sessionId);
        }
    }
    
    // 保持侧边栏打开状态，方便切换对话
    // closeSidebar(); // 已注释：用户希望保留历史记录面板
    
    // 高亮当前激活的历史记录项
    const historyItems = document.querySelectorAll('.history-item');
    historyItems.forEach(item => {
        item.classList.remove('active');
    });
    
    // 找到当前会话的项并高亮（使用 data-session-id 属性）
    const activeItem = document.querySelector(`.history-item[data-session-id="${sessionId}"]`);
    if (activeItem) {
        activeItem.classList.add('active');
        
        // 可选：滚动到可见区域
        activeItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

function deleteHistorySession(sessionId) {
    if (!confirm('确定要删除这个会话吗？')) {
        return;
    }
    
    console.log('删除会话:', sessionId);
    
    // TODO: 调用API删除会话
    if (window.notificationManager) {
        window.notificationManager.show('会话删除功能开发中...', 'info', 2000);
    }
}

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', () => {
    console.log('✅ UI交互函数已加载');
    
    // 初始化主题
    initTheme();
    
    // 绑定构建器覆盖层点击事件
    const builderOverlay = document.getElementById('builderOverlay');
    if (builderOverlay) {
        builderOverlay.addEventListener('click', closeBuilder);
    }
    
    // 自动加载历史记录
    setTimeout(() => {
        if (typeof refreshHistoryList === 'function') {
            refreshHistoryList();
        }
    }, 500);
});

// 暴露到全局作用域
window.toggleSidebar = toggleSidebar;
window.closeSidebar = closeSidebar;
window.toggleTimeline = toggleTimeline;
window.toggleGlobalMemory = toggleGlobalMemory;
window.toggleDeepThink = toggleDeepThink;
window.toggleMultiAgentMode = toggleMultiAgentMode;
window.exportChat = exportChat;
window.clearChat = clearChat;
window.stopGeneration = stopGeneration;
window.toggleTheme = toggleTheme;
window.closeImageModal = closeImageModal;
window.closeMermaidModal = closeMermaidModal;
window.newChat = newChat;
window.startNewChat = startNewChat;
// window.openSettings = openSettings; // 已移除
window.sendQuickExample = sendQuickExample;
window.useExample = useExample; // 添加这个！
window.toggleBuilder = toggleBuilder;
window.closeBuilder = closeBuilder;
window.refreshHistoryList = refreshHistoryList;
window.loadHistorySession = loadHistorySession;
window.deleteHistorySession = deleteHistorySession;
window.formatHistoryTime = formatHistoryTime;
window.escapeHtml = escapeHtml;
window.toggleInputOptions = toggleInputOptions;
window.handleFileSelect = handleFileSelect;
window.removeFile = removeFile;
window.logout = logout;
window.resetCanvasView = resetCanvasView;
window.centerCanvas = centerCanvas;
window.loadExample = loadExample;
// 构建器管理
window.clearBuilder = clearBuilder;
window.saveAgentConfig = saveAgentConfig;
window.testAgentConfig = testAgentConfig;
window.autoLayout = autoLayout;
window.undoBuilder = undoBuilder;
window.redoBuilder = redoBuilder;
// 画布节点管理
window.addNode = addNode;
window.resetZoom = resetZoom;
window.zoomIn = zoomIn;
window.zoomOut = zoomOut;
window.deleteSelectedNode = deleteSelectedNode;
window.duplicateNode = duplicateNode;
window.closeContextMenu = closeContextMenu;
// 时间线过滤
window.toggleTimelineFilter = toggleTimelineFilter;
