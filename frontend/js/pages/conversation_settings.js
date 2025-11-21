/* JavaScript extracted from conversation_settings.html */


        const API_BASE = 'http://127.0.0.1:8000';
        const urlParams = new URLSearchParams(window.location.search);
        const sessionId = urlParams.get('session_id');

        // 如果没有会话ID，使用localStorage存储全局设置
        const isGlobalSettings = !sessionId;

        // 加载配置
        async function loadConfig() {
            if (isGlobalSettings) {
                // 从localStorage加载全局设置
                const globalSettings = localStorage.getItem('globalSettings');
                if (globalSettings) {
                    try {
                        const settings = JSON.parse(globalSettings);
                        document.getElementById('shareMemoryToggle').checked = settings.share_memory_across_sessions !== false;
                    } catch (e) {
                        // 默认开启
                        document.getElementById('shareMemoryToggle').checked = true;
                    }
                } else {
                    // 默认开启
                    document.getElementById('shareMemoryToggle').checked = true;
                }
            } else {
                // 从API加载会话设置
                try {
                    const response = await fetch(`${API_BASE}/conversation/${sessionId}/config`);
                    if (!response.ok) throw new Error('加载配置失败');

                    const config = await response.json();
                    document.getElementById('shareMemoryToggle').checked = config.share_memory_across_sessions;
                } catch (error) {
                    console.error('加载配置失败:', error);
                    // 默认开启
                    document.getElementById('shareMemoryToggle').checked = true;
                }
            }
        }

        // 保存配置
        let saveTimeout;
        async function saveConfig() {
            const shareMemory = document.getElementById('shareMemoryToggle').checked;
            const statusEl = document.getElementById('saveStatus');

            if (isGlobalSettings) {
                // 保存到localStorage
                try {
                    const settings = {
                        share_memory_across_sessions: shareMemory,
                        updated_at: new Date().toISOString()
                    };
                    localStorage.setItem('globalSettings', JSON.stringify(settings));
                    
                    // 显示成功提示
                    statusEl.innerHTML = '<div class="save-status success">✅ 全局设置已保存</div>';
                    setTimeout(() => {
                        statusEl.innerHTML = '';
                    }, 2000);
                } catch (error) {
                    console.error('保存配置失败:', error);
                    statusEl.innerHTML = '<div class="save-status error">❌ 保存失败</div>';
                }
            } else {
                // 保存到API
                const userInfo = localStorage.getItem('userInfo');
                const userId = userInfo ? JSON.parse(userInfo).user_id : null;

                try {
                    const url = `${API_BASE}/conversation/${sessionId}/config`;
                    const response = await fetch(url, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            session_id: sessionId,
                            share_memory_across_sessions: shareMemory,
                            user_id: userId,
                        }),
                    });

                    if (!response.ok) throw new Error('保存失败');

                    const config = await response.json();
                    
                    // 显示成功提示
                    statusEl.innerHTML = '<div class="save-status success">✅ 设置已保存</div>';
                    setTimeout(() => {
                        statusEl.innerHTML = '';
                    }, 2000);

                } catch (error) {
                    console.error('保存配置失败:', error);
                    statusEl.innerHTML = '<div class="save-status error">❌ 保存失败，请重试</div>';
                }
            }
        }

        // 切换处理（防抖）
        function handleToggleChange() {
            clearTimeout(saveTimeout);
            saveTimeout = setTimeout(() => {
                saveConfig();
            }, 500);
        }

        // 返回
        function goBack() {
            if (document.referrer) {
                window.history.back();
            } else {
                window.location.href = 'conversation_history.html';
            }
        }

        // 页面加载时初始化
        window.addEventListener('load', () => {
            loadConfig();
        });
    