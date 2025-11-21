/* JavaScript extracted from knowledge_base.html */


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
            
            showToast('success', newTheme === 'dark' ? '🌙 已切换到暗色模式' : '☀️ 已切换到亮色模式');
        }
        
        function updateThemeIcon(theme) {
            const icon = document.getElementById('themeIcon');
            if (icon) {
                icon.textContent = theme === 'dark' ? '☀️' : '🌙';
            }
        }
        
        // 页面加载时初始化主题
        initTheme();

        const API_BASE = 'http://localhost:8000';
        let allDocuments = [];

        // 加载文档列表
        async function loadDocuments() {
            try {
                const response = await fetch(`${API_BASE}/documents`);
                if (!response.ok) throw new Error('加载失败');
                
                allDocuments = await response.json();
                renderDocuments(allDocuments);
                updateStats();
            } catch (error) {
                showToast('error', '加载文档列表失败');
                document.getElementById('documentsList').innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">❌</div>
                        <div>加载失败，请刷新重试</div>
                    </div>
                `;
            }
        }

        // 渲染文档列表
        function renderDocuments(documents) {
            const container = document.getElementById('documentsList');
            
            if (documents.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">📭</div>
                        <div>还没有上传任何文档</div>
                        <div style="margin-top: 8px; font-size: 13px;">点击上方按钮或拖拽文件上传</div>
                    </div>
                `;
                return;
            }

            container.innerHTML = documents.map(doc => `
                <div class="document-item card card-hoverable" data-id="${doc.id}">
                    <div class="document-info">
                        <div class="document-name">📄 ${doc.original_name}</div>
                        <div class="document-meta">
                            <span>📦 ${doc.chunk_count} 个片段</span>
                            <span>📏 ${formatSize(doc.file_size)}</span>
                            <span>📅 ${formatDate(doc.created_at)}</span>
                        </div>
                    </div>
                    <div class="document-actions">
                        <button class="btn-icon btn-delete" onclick="deleteDocument('${doc.id}', '${doc.original_name}')" title="删除">
                            🗑️
                        </button>
                    </div>
                </div>
            `).join('');
        }

        // 更新统计信息
        function updateStats() {
            const totalDocs = allDocuments.length;
            const totalChunks = allDocuments.reduce((sum, doc) => sum + doc.chunk_count, 0);
            const totalSize = allDocuments.reduce((sum, doc) => sum + doc.file_size, 0);

            document.getElementById('totalDocs').textContent = totalDocs;
            document.getElementById('totalChunks').textContent = totalChunks;
            document.getElementById('totalSize').textContent = formatSize(totalSize);
        }

        // 过滤文档
        function filterDocuments() {
            const keyword = document.getElementById('searchInput').value.toLowerCase();
            const filtered = allDocuments.filter(doc => 
                doc.original_name.toLowerCase().includes(keyword)
            );
            renderDocuments(filtered);
        }

        // 处理文件上传
        async function handleFileUpload(event) {
            const files = event.target.files;
            if (!files || files.length === 0) return;

            for (const file of files) {
                await uploadFile(file);
            }

            // 重置文件输入
            event.target.value = '';
            
            // 重新加载列表
            await loadDocuments();
        }

        // 上传单个文件
        async function uploadFile(file) {
            const formData = new FormData();
            formData.append('file', file);

            try {
                showToast('info', `正在上传 ${file.name}...`);
                
                const response = await fetch(`${API_BASE}/documents/upload`, {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) throw new Error('上传失败');
                
                showToast('success', `✅ ${file.name} 上传成功`);
            } catch (error) {
                showToast('error', `❌ ${file.name} 上传失败`);
            }
        }

        // 删除文档
        async function deleteDocument(id, name) {
            if (!confirm(`确定要删除文档「${name}」吗？\n删除后无法恢复。`)) {
                return;
            }

            try {
                const response = await fetch(`${API_BASE}/documents/${id}`, {
                    method: 'DELETE'
                });

                if (!response.ok) throw new Error('删除失败');
                
                showToast('success', '文档已删除');
                await loadDocuments();
            } catch (error) {
                showToast('error', '删除失败');
            }
        }

        // 显示提示
        function showToast(type, message) {
            const toast = document.getElementById('toast');
            const icon = document.getElementById('toastIcon');
            const msg = document.getElementById('toastMessage');

            toast.className = `toast ${type}`;
            icon.textContent = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
            msg.textContent = message;

            toast.classList.add('show');
            setTimeout(() => {
                toast.classList.remove('show');
            }, 3000);
        }

        // 格式化大小
        function formatSize(bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / 1024 / 1024).toFixed(1) + ' MB';
        }

        // 格式化日期
        function formatDate(dateStr) {
            const date = new Date(dateStr);
            const now = new Date();
            const diff = now - date;

            if (diff < 60000) return '刚刚';
            if (diff < 3600000) return Math.floor(diff / 60000) + ' 分钟前';
            if (diff < 86400000) return Math.floor(diff / 3600000) + ' 小时前';
            
            return date.toLocaleDateString('zh-CN', { 
                year: 'numeric', 
                month: '2-digit', 
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        }

        // 拖拽上传
        const uploadBox = document.getElementById('uploadBox');
        
        uploadBox.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadBox.classList.add('dragover');
        });

        uploadBox.addEventListener('dragleave', () => {
            uploadBox.classList.remove('dragover');
        });

        uploadBox.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadBox.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileUpload({ target: { files } });
            }
        });

        // 刷新文档列表
        async function refreshDocuments() {
            console.log('🔄 手动刷新文档列表...');
            showToast('info', '正在刷新...');
            await loadDocuments();
            showToast('success', '✅ 刷新完成');
        }

        // 页面加载时初始化
        document.addEventListener('DOMContentLoaded', () => {
            loadDocuments();
            
            // 添加自动刷新（每30秒）
            setInterval(() => {
                console.log('🔄 自动刷新文档列表...');
                loadDocuments();
            }, 30000); // 30秒
            
            console.log('✅ 知识库页面已初始化（自动刷新已启用）');
        });
    