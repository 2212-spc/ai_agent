/* JavaScript extracted from prompt_management.html */


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
            
            showToast(newTheme === 'dark' ? '🌙 已切换到暗色模式' : '☀️ 已切换到亮色模式', 'success');
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
        let agents = [];
        let currentAgentId = null;
        let prompts = [];

        // 页面加载时初始化
        async function init() {
            // 首先初始化默认模板（如果还没有）
            await initDefaultPrompts();
            await loadAgents();
            await loadPrompts();
        }

        // 初始化默认模板
        async function initDefaultPrompts() {
            try {
                const response = await fetch(`${API_BASE}/prompts/init-defaults`, {
                    method: 'POST',
                });
                if (response.ok) {
                    const result = await response.json();
                    console.log('默认模板初始化:', result.message);
                }
            } catch (error) {
                console.warn('初始化默认模板失败:', error);
                // 不影响页面加载，继续执行
            }
        }

        // 加载智能体列表
        async function loadAgents() {
            try {
                const response = await fetch(`${API_BASE}/agents/list`);
                if (!response.ok) throw new Error('加载智能体列表失败');
                agents = await response.json();
                renderAgents();
            } catch (error) {
                showToast('error', '加载智能体列表失败: ' + error.message);
                document.getElementById('agentList').innerHTML = '<div class="empty-state">加载失败</div>';
            }
        }

        // 渲染智能体列表
        function renderAgents() {
            const container = document.getElementById('agentList');
            if (agents.length === 0) {
                container.innerHTML = '<div class="empty-state">没有可用的智能体</div>';
                return;
            }

            container.innerHTML = agents.map(agent => `
                <div class="agent-item ${currentAgentId === agent.id ? 'active' : ''}" 
                     onclick="selectAgent('${agent.id}')">
                    <div class="agent-name">${agent.name}</div>
                    <div class="agent-description">${agent.description || '无描述'}</div>
                </div>
            `).join('');
        }

        // 选择智能体
        async function selectAgent(agentId) {
            currentAgentId = agentId;
            renderAgents();
            
            const agent = agents.find(a => a.id === agentId);
            document.getElementById('selectedAgentName').textContent = agent ? agent.name : '未知智能体';
            document.getElementById('createPromptBtn').style.display = 'block';
            document.getElementById('generatePromptBtn').style.display = 'block';
            
            await loadPrompts(agentId);
        }

        // 加载Prompt模板列表
        async function loadPrompts(agentId = null) {
            try {
                const url = agentId 
                    ? `${API_BASE}/prompts/agent/${agentId}?include_inactive=true`
                    : `${API_BASE}/prompts?include_inactive=true`;
                
                const response = await fetch(url);
                if (!response.ok) throw new Error('加载Prompt模板失败');
                prompts = await response.json();
                renderPrompts();
            } catch (error) {
                showToast('error', '加载Prompt模板失败: ' + error.message);
                prompts = [];
                renderPrompts();
            }
        }

        // 渲染Prompt模板列表
        function renderPrompts() {
            const container = document.getElementById('promptList');
            
            if (!currentAgentId) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">👈</div>
                        <div>请从左侧选择一个智能体查看其Prompt模板</div>
                    </div>
                `;
                return;
            }

            const agentPrompts = prompts.filter(p => p.agent_id === currentAgentId);
            
            if (agentPrompts.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">📝</div>
                        <div>该智能体还没有Prompt模板</div>
                        <div style="margin-top: 12px;">
                            <button class="btn btn-primary" onclick="openCreateModal()">创建第一个模板</button>
                        </div>
                    </div>
                `;
                return;
            }

            container.innerHTML = agentPrompts.map(prompt => `
                <div class="prompt-card card card-hoverable ${prompt.is_default ? 'default' : ''} ${prompt.is_active ? 'active' : 'inactive'}">
                    <div class="prompt-header">
                        <div class="prompt-title">
                            <span class="prompt-name">${escapeHtml(prompt.name)}</span>
                            ${prompt.is_default ? '<span class="badge badge-default">默认模板</span>' : ''}
                            ${prompt.is_active ? '<span class="badge badge-active">已激活</span>' : '<span class="badge" style="background: #9ca3af; color: white;">已停用</span>'}
                        </div>
                        <div class="prompt-actions">
                            <label class="toggle-label">
                                <span>${prompt.is_active ? '激活' : '停用'}</span>
                                <label class="toggle-switch">
                                    <input type="checkbox" ${prompt.is_active ? 'checked' : ''} 
                                           ${prompt.is_default ? 'title="默认模板：需要先激活其他模板才能停用"' : ''}
                                           onchange="togglePromptStatus('${prompt.id}', this.checked, ${prompt.is_default})">
                                    <span class="toggle-slider"></span>
                                </label>
                            </label>
                            ${!prompt.is_default ? `<button class="btn btn-secondary btn-small" onclick="openEditModal('${prompt.id}')">编辑</button>` : ''}
                            ${!prompt.is_default ? `<button class="btn btn-danger btn-small" onclick="deletePrompt('${prompt.id}')">删除</button>` : ''}
                        </div>
                    </div>
                    ${prompt.description ? `<div class="prompt-description">${escapeHtml(prompt.description)}</div>` : ''}
                    <div class="prompt-content">${escapeHtml(prompt.content)}</div>
                    <div class="prompt-meta">
                        <span>创建时间: ${formatDate(prompt.created_at)}</span>
                        <span>更新时间: ${formatDate(prompt.updated_at)}</span>
                    </div>
                </div>
            `).join('');
        }

        // 打开创建模板模态框
        function openCreateModal() {
            document.getElementById('modalTitle').textContent = '创建Prompt模板';
            document.getElementById('templateId').value = '';
            document.getElementById('templateName').value = '';
            document.getElementById('templateDescription').value = '';
            document.getElementById('templateContent').value = '';
            
            // 设置当前选中的智能体
            const agentSelect = document.getElementById('templateAgentId');
            agentSelect.innerHTML = '<option value="">请选择智能体</option>' +
                agents.map(agent => `<option value="${agent.id}" ${agent.id === currentAgentId ? 'selected' : ''}>${agent.name}</option>`).join('');
            
            document.getElementById('promptModal').classList.add('active');
        }

        // 打开编辑模板模态框
        async function openEditModal(templateId) {
            const prompt = prompts.find(p => p.id === templateId);
            if (!prompt) {
                showToast('error', '找不到该模板');
                return;
            }

            document.getElementById('modalTitle').textContent = '编辑Prompt模板';
            document.getElementById('templateId').value = prompt.id;
            document.getElementById('templateName').value = prompt.name;
            document.getElementById('templateDescription').value = prompt.description || '';
            document.getElementById('templateContent').value = prompt.content;
            
            // 设置智能体选择（编辑时不可更改）
            const agentSelect = document.getElementById('templateAgentId');
            agentSelect.innerHTML = `<option value="${prompt.agent_id}" selected>${agents.find(a => a.id === prompt.agent_id)?.name || prompt.agent_id}</option>`;
            agentSelect.disabled = true;
            
            document.getElementById('promptModal').classList.add('active');
        }

        // 关闭模态框
        function closeModal() {
            document.getElementById('promptModal').classList.remove('active');
            document.getElementById('templateAgentId').disabled = false;
        }

        // 保存Prompt模板
        async function savePrompt() {
            const form = document.getElementById('promptForm');
            if (!form.checkValidity()) {
                form.reportValidity();
                return;
            }

            const templateId = document.getElementById('templateId').value;
            const data = {
                name: document.getElementById('templateName').value,
                agent_id: document.getElementById('templateAgentId').value,
                content: document.getElementById('templateContent').value,
                description: document.getElementById('templateDescription').value || null,
            };

            try {
                let response;
                if (templateId) {
                    // 更新
                    response = await fetch(`${API_BASE}/prompts/${templateId}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data),
                    });
                } else {
                    // 创建
                    response = await fetch(`${API_BASE}/prompts`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data),
                    });
                }

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || '保存失败');
                }

                showToast('success', templateId ? '模板更新成功' : '模板创建成功');
                closeModal();
                await loadPrompts(currentAgentId);
            } catch (error) {
                showToast('error', '保存失败: ' + error.message);
            }
        }

        // 切换Prompt模板激活状态
        async function togglePromptStatus(templateId, isActive, isDefault = false) {
            try {
                let response;
                if (isActive) {
                    // 激活模板（会自动停用其他模板）
                    const confirmMsg = isDefault 
                        ? '确定要激活默认模板吗？激活后，该智能体的其他模板将自动设为非激活状态。'
                        : '确定要激活这个模板吗？激活后，该智能体的其他模板将自动设为非激活状态。';
                    
                    if (!confirm(confirmMsg)) {
                        // 如果取消，需要恢复开关状态
                        await loadPrompts(currentAgentId);
                        return;
                    }
                    response = await fetch(`${API_BASE}/prompts/${templateId}/activate`, {
                        method: 'POST',
                    });
                } else {
                    // 停用模板
                    const confirmMsg = isDefault
                        ? '确定要停用默认模板吗？停用前请确保该智能体至少有一个其他激活的模板，否则系统将使用硬编码的默认prompt。'
                        : '确定要停用这个模板吗？停用后该模板将不会被使用。';
                    
                    if (!confirm(confirmMsg)) {
                        // 如果取消，需要恢复开关状态
                        await loadPrompts(currentAgentId);
                        return;
                    }
                    response = await fetch(`${API_BASE}/prompts/${templateId}/deactivate`, {
                        method: 'POST',
                    });
                }

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || (isActive ? '激活失败' : '停用失败'));
                }

                showToast('success', isActive ? '模板激活成功' : '模板已停用');
                await loadPrompts(currentAgentId);
            } catch (error) {
                showToast('error', (isActive ? '激活' : '停用') + '失败: ' + error.message);
                // 发生错误时重新加载以恢复正确的状态
                await loadPrompts(currentAgentId);
            }
        }

        // 激活Prompt模板（保留兼容性）
        async function activatePrompt(templateId) {
            await togglePromptStatus(templateId, true);
        }

        // 删除Prompt模板
        async function deletePrompt(templateId) {
            if (!confirm('确定要删除这个模板吗？此操作不可恢复。')) {
                return;
            }

            try {
                const response = await fetch(`${API_BASE}/prompts/${templateId}`, {
                    method: 'DELETE',
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || '删除失败');
                }

                showToast('success', '模板删除成功');
                await loadPrompts(currentAgentId);
            } catch (error) {
                showToast('error', '删除失败: ' + error.message);
            }
        }

        // 工具函数
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function formatDate(dateString) {
            if (!dateString) return '未知';
            const date = new Date(dateString);
            return date.toLocaleString('zh-CN');
        }

        function showToast(type, message) {
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            document.body.appendChild(toast);

            setTimeout(() => {
                toast.remove();
            }, 3000);
        }

        // 绑定创建按钮事件
        document.getElementById('createPromptBtn').addEventListener('click', openCreateModal);

        // ==================== 智能生成Prompt功能 ====================
        let currentGeneratedPrompt = null;

        // 打开生成模态框
        function openGenerateModal() {
            if (!currentAgentId) {
                showToast('warning', '请先选择一个智能体');
                return;
            }
            
            const agent = agents.find(a => a.id === currentAgentId);
            document.getElementById('generateAgentName').value = agent ? agent.name : '未知';
            document.getElementById('generateRequirement').value = '';
            document.getElementById('generateStyle').value = '';
            document.getElementById('generateFormat').value = '';
            document.getElementById('generateResult').style.display = 'none';
            currentGeneratedPrompt = null;
            
            document.getElementById('generateModal').style.display = 'block';
        }

        // 关闭生成模态框
        function closeGenerateModal() {
            document.getElementById('generateModal').style.display = 'none';
        }

        // 生成Prompt
        async function generatePrompt() {
            const requirement = document.getElementById('generateRequirement').value.trim();
            if (!requirement) {
                showToast('error', '请输入你的需求');
                return;
            }
            
            const generateBtn = document.getElementById('generateBtn');
            generateBtn.disabled = true;
            generateBtn.textContent = '生成中...';
            
            try {
                const response = await fetch(`${API_BASE}/prompts/generate`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        agent_id: currentAgentId,
                        user_requirement: requirement,
                        reference_style: document.getElementById('generateStyle').value || null,
                        output_format: document.getElementById('generateFormat').value || null,
                    })
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || '生成失败');
                }
                
                const result = await response.json();
                currentGeneratedPrompt = result;
                
                // 显示生成结果
                document.getElementById('generatedPromptContent').textContent = result.generated_prompt;
                document.getElementById('generateResult').style.display = 'block';
                
                // 显示验证结果
                displayValidationResult(result.validation);
                
                showToast('success', 'Prompt生成成功！');
                
            } catch (error) {
                showToast('error', '生成失败: ' + error.message);
            } finally {
                generateBtn.disabled = false;
                generateBtn.textContent = '✨ 生成Prompt';
            }
        }

        // 复制生成的Prompt
        function copyGeneratedPrompt() {
            if (!currentGeneratedPrompt) return;
            
            const text = currentGeneratedPrompt.generated_prompt;
            navigator.clipboard.writeText(text).then(() => {
                showToast('success', '已复制到剪贴板');
            }).catch(() => {
                showToast('error', '复制失败');
            });
        }

        // 保存生成的Prompt
        async function saveGeneratedPrompt() {
            if (!currentGeneratedPrompt) return;
            
            const name = prompt('请输入模板名称：', currentGeneratedPrompt.suggested_name);
            if (!name) return;
            
            const description = prompt('请输入模板描述（可选）：', currentGeneratedPrompt.suggested_description || '');
            
            try {
                const response = await fetch(`${API_BASE}/prompts`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: name,
                        agent_id: currentGeneratedPrompt.agent_id,
                        content: currentGeneratedPrompt.generated_prompt,
                        description: description || null,
                    })
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || '保存失败');
                }
                
                showToast('success', '模板保存成功！');
                closeGenerateModal();
                await loadPrompts(currentAgentId);
                
            } catch (error) {
                showToast('error', '保存失败: ' + error.message);
            }
        }

        // 重新生成
        function regeneratePrompt() {
            document.getElementById('generateResult').style.display = 'none';
            generatePrompt();
        }

        // 显示验证结果
        function displayValidationResult(validation) {
            const container = document.getElementById('validationResult');
            if (!validation) {
                container.innerHTML = '';
                return;
            }

            let html = '';
            
            // 显示问题（issues）
            if (validation.issues && validation.issues.length > 0) {
                html += `
                    <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 12px; margin-bottom: 12px;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                            <span style="color: #dc2626; font-weight: 600;">⚠️ 发现问题</span>
                        </div>
                        <ul style="margin: 0; padding-left: 20px; color: #991b1b;">
                            ${validation.issues.map(issue => `<li>${issue}</li>`).join('')}
                        </ul>
                    </div>
                `;
            }
            
            // 显示警告（warnings）
            if (validation.warnings && validation.warnings.length > 0) {
                html += `
                    <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 12px; margin-bottom: 12px;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                            <span style="color: #d97706; font-weight: 600;">💡 建议</span>
                        </div>
                        <ul style="margin: 0; padding-left: 20px; color: #92400e;">
                            ${validation.warnings.map(warning => `<li>${warning}</li>`).join('')}
                        </ul>
                    </div>
                `;
            }
            
            // 显示验证通过
            if (validation.valid && (!validation.issues || validation.issues.length === 0)) {
                html += `
                    <div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 12px; margin-bottom: 12px;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="color: #16a34a; font-weight: 600;">✅ 验证通过</span>
                        </div>
                        <div style="margin-top: 8px; color: #166534; font-size: 14px;">
                            占位符检查：${validation.placeholders_found?.length || 0} 个，格式要求：已满足
                        </div>
                    </div>
                `;
            }
            
            container.innerHTML = html;
        }

        // 初始化
        init();
    