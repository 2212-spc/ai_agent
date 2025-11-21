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
    
    // 清空消息
    const messagesContainer = document.getElementById('messagesContainer');
    if (messagesContainer) {
        messagesContainer.innerHTML = '';
    }
    
    // 生成新会话ID
    if (window.chatManager) {
        window.chatManager.currentSessionId = window.chatManager.generateSessionId();
        console.log('新会话ID:', window.chatManager.currentSessionId);
    }
    
    // 清空时间线
    const timelineContent = document.getElementById('timelineContent');
    if (timelineContent) {
        timelineContent.innerHTML = '';
    }
    
    if (window.notificationManager) {
        window.notificationManager.show('✅ 新会话已创建', 'success', 2000);
    }
}

// startNewChat 别名（兼容旧代码）
function startNewChat() {
    newChat();
}

// ========== 设置面板 ==========
function openSettings() {
    if (window.notificationManager) {
        window.notificationManager.show('设置功能开发中...', 'info', 2000);
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
    
    if (window.notificationManager) {
        window.notificationManager.show('💾 配置保存功能开发中...', 'info', 2000);
    }
    
    // TODO: 实现配置保存逻辑
    // 1. 收集所有节点信息
    // 2. 生成配置JSON
    // 3. 调用API保存
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
    
    if (window.notificationManager) {
        window.notificationManager.show('↩️ 撤销功能开发中...', 'info', 2000);
    }
    
    // TODO: 实现撤销功能
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
function refreshHistoryList() {
    if (window.notificationManager) {
        window.notificationManager.show('🔄 刷新历史记录...', 'info', 1000);
    }
    
    // TODO: 实现历史记录刷新逻辑
    // 这里可以调用API获取历史记录列表
    console.log('刷新历史记录列表');
}

function loadHistorySession(sessionId) {
    if (!sessionId) {
        console.warn('会话ID为空');
        return;
    }
    
    console.log('加载历史会话:', sessionId);
    
    if (window.chatManager && typeof window.chatManager.loadHistoryMessages === 'function') {
        window.chatManager.currentSessionId = sessionId;
        window.chatManager.loadHistoryMessages(sessionId);
    }
    
    // 关闭侧边栏
    closeSidebar();
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
});

// 暴露到全局作用域
window.toggleSidebar = toggleSidebar;
window.closeSidebar = closeSidebar;
window.toggleTimeline = toggleTimeline;
window.toggleMultiAgentMode = toggleMultiAgentMode;
window.exportChat = exportChat;
window.clearChat = clearChat;
window.stopGeneration = stopGeneration;
window.toggleTheme = toggleTheme;
window.closeImageModal = closeImageModal;
window.closeMermaidModal = closeMermaidModal;
window.newChat = newChat;
window.startNewChat = startNewChat;
window.openSettings = openSettings;
window.sendQuickExample = sendQuickExample;
window.toggleBuilder = toggleBuilder;
window.closeBuilder = closeBuilder;
window.refreshHistoryList = refreshHistoryList;
window.loadHistorySession = loadHistorySession;
window.deleteHistorySession = deleteHistorySession;
// 构建器管理
window.clearBuilder = clearBuilder;
window.saveAgentConfig = saveAgentConfig;
window.testAgentConfig = testAgentConfig;
window.autoLayout = autoLayout;
window.undoBuilder = undoBuilder;
// 画布节点管理
window.addNode = addNode;
window.resetZoom = resetZoom;
window.deleteSelectedNode = deleteSelectedNode;
window.duplicateNode = duplicateNode;
window.closeContextMenu = closeContextMenu;
// 时间线过滤
window.toggleTimelineFilter = toggleTimelineFilter;
