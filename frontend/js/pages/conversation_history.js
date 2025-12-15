/* JavaScript extracted from conversation_history.html */


        // ========== 主题切换功能 ==========
        function initTheme() {
            const savedTheme = localStorage.getItem('theme') || 'light';
            document.documentElement.setAttribute('data-theme', savedTheme);
            updateThemeIcon(savedTheme);
        }
        
        function toggleTheme() {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            
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
        
        // 页面加载时初始化主题
        initTheme();

        const API_BASE = 'http://127.0.0.1:8000';
        let allConversations = [];
        let currentPage = 0;
        const pageSize = 20;
        let selectedSessions = new Set();

        // 获取用户信息
        function getUserInfo() {
            const userInfo = localStorage.getItem('userInfo');
            return userInfo ? JSON.parse(userInfo) : null;
        }

        // 加载会话列表
        async function loadConversations(searchQuery = '') {
            const userInfo = getUserInfo();
            const userId = userInfo?.user_id || null;

            const listEl = document.getElementById('conversationList');
            listEl.innerHTML = '<div class="loading">加载中...</div>';

            try {
                let url;
                if (searchQuery) {
                    url = `${API_BASE}/conversations/search?q=${encodeURIComponent(searchQuery)}&limit=${pageSize}`;
                    if (userId) url += `&user_id=${userId}`;
                } else {
                    url = `${API_BASE}/conversations?limit=${pageSize}&offset=${currentPage * pageSize}`;
                    if (userId) url += `&user_id=${userId}`;
                }

                const response = await fetch(url);
                if (!response.ok) throw new Error('加载失败');

                const conversations = await response.json();
                allConversations = conversations;
                selectedSessions.clear();
                updateBulkActions();
                renderConversations(conversations);
            } catch (error) {
                console.error('加载会话失败:', error);
                listEl.innerHTML = '<div class="empty-state">加载失败，请刷新重试</div>';
            }
        }

        // 渲染会话列表
        function renderConversations(conversations) {
            const listEl = document.getElementById('conversationList');

            if (conversations.length === 0) {
                listEl.innerHTML = '<div class="empty-state">暂无对话记录</div>';
                return;
            }

            listEl.innerHTML = conversations.map(conv => {
                const checked = selectedSessions.has(conv.session_id) ? 'checked' : '';
                const selectedClass = selectedSessions.has(conv.session_id) ? 'selected' : '';
                return `
                <div class="conversation-item card card-hoverable ${selectedClass}" onclick="openConversation('${conv.session_id}')">
                    <div class="conversation-select" onclick="event.stopPropagation();">
                        <input type="checkbox" ${checked} onchange="toggleSelection('${conv.session_id}', this.checked)">
                    </div>
                    <div class="conversation-info">
                        <div class="conversation-title">${escapeHtml(conv.title)}</div>
                        <div class="conversation-preview">${escapeHtml(conv.preview)}</div>
                        <div class="conversation-meta">
                            <span>💬 ${conv.message_count} 条消息</span>
                            <span>🕐 ${formatTime(conv.last_message_time)}</span>
                        </div>
                    </div>
                    <div class="conversation-actions" onclick="event.stopPropagation()">
                        <button class="btn-icon" onclick="openConversation('${conv.session_id}')" title="继续对话">
                            ▶️
                        </button>
                        <button class="btn-icon" onclick="deleteConversation('${conv.session_id}')" title="删除">
                            🗑️
                        </button>
                    </div>
                </div>
                `;
            }).join('');
        }

        // 打开对话（继续对话）
        function openConversation(sessionId) {
            window.location.href = `agent_chat.html?session_id=${sessionId}`;
        }

        // 打开设置
        // 设置功能已移除，记忆管理请访问导航栏的"记忆管理"

        // 删除对话（单个）
        async function deleteConversation(sessionId) {
            if (!confirm('确定要删除这个对话吗？删除后将无法恢复。')) {
                return;
            }

            const userInfo = getUserInfo();
            const userId = userInfo?.user_id || null;

            try {
                let url = `${API_BASE}/conversation/${sessionId}`;
                if (userId) url += `?user_id=${userId}`;

                const response = await fetch(url, {
                    method: 'DELETE',
                });

                if (!response.ok) throw new Error('删除失败');

                alert('删除成功');
                loadConversations();
            } catch (error) {
                console.error('删除失败:', error);
                alert('删除失败，请重试');
            }
        }

        // 批量删除
        async function deleteSelected() {
            if (selectedSessions.size === 0) {
                alert('请先选择要删除的会话');
                return;
            }
            if (!confirm(`确定要删除选中的 ${selectedSessions.size} 条会话吗？此操作不可恢复。`)) {
                return;
            }

            const userInfo = getUserInfo();
            const userId = userInfo?.user_id || null;
            let success = 0;
            let failed = 0;

            for (const sessionId of Array.from(selectedSessions)) {
                try {
                    let url = `${API_BASE}/conversation/${sessionId}`;
                    if (userId) url += `?user_id=${userId}`;
                    const res = await fetch(url, { method: 'DELETE' });
                    if (!res.ok) throw new Error();
                    success += 1;
                } catch (e) {
                    failed += 1;
                }
            }

            alert(`删除完成：成功 ${success} 条${failed ? `，失败 ${failed} 条` : ''}`);
            loadConversations();
        }

        // 选择逻辑
        function toggleSelection(sessionId, checked) {
            if (checked) {
                selectedSessions.add(sessionId);
            } else {
                selectedSessions.delete(sessionId);
            }
            updateBulkActions();
            // 重新渲染以更新选中样式
            renderConversations(allConversations);
        }

        function toggleSelectAll() {
            const selectAll = document.getElementById('selectAllCheckbox');
            if (selectAll.checked) {
                allConversations.forEach(c => selectedSessions.add(c.session_id));
            } else {
                selectedSessions.clear();
            }
            updateBulkActions();
            renderConversations(allConversations);
        }

        function updateBulkActions() {
            const bar = document.getElementById('bulkActions');
            const countText = document.getElementById('selectedCountText');
            const selectAll = document.getElementById('selectAllCheckbox');
            const total = allConversations.length;
            const selectedCount = selectedSessions.size;

            if (bar) {
                bar.style.display = selectedCount > 0 ? 'flex' : 'none';
            }
            if (countText) {
                countText.textContent = `已选 ${selectedCount} 条`;
            }
            if (selectAll) {
                selectAll.checked = total > 0 && selectedCount === total;
                selectAll.indeterminate = selectedCount > 0 && selectedCount < total;
            }
        }

        // 搜索处理
        let searchTimeout;
        function handleSearch(event) {
            if (event.key === 'Enter') {
                const query = event.target.value.trim();
                currentPage = 0;
                loadConversations(query);
            }
        }

        // 工具函数
        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function formatTime(timeStr) {
            if (!timeStr) return '未知时间';
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
            return date.toLocaleDateString('zh-CN');
        }

        // 页面加载时初始化
        window.addEventListener('load', () => {
            loadConversations();
        });
    