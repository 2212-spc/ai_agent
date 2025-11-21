/* JavaScript extracted from register.html */


        // 密码强度检测
        document.getElementById('password').addEventListener('input', function(e) {
            const password = e.target.value;
            const strengthBar = document.getElementById('strengthBar');
            const strengthText = document.getElementById('strengthText');
            
            let strength = 0;
            if (password.length >= 8) strength++;
            if (password.length >= 12) strength++;
            if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++;
            if (/[0-9]/.test(password)) strength++;
            if (/[^a-zA-Z0-9]/.test(password)) strength++;
            
            strengthBar.className = 'password-strength-fill';
            if (strength <= 2) {
                strengthBar.classList.add('weak');
                strengthText.textContent = '密码强度：弱';
            } else if (strength <= 3) {
                strengthBar.classList.add('medium');
                strengthText.textContent = '密码强度：中';
            } else {
                strengthBar.classList.add('strong');
                strengthText.textContent = '密码强度：强';
            }
            
            if (password.length === 0) {
                strengthText.textContent = '密码强度';
            }
        });

        // 确认密码验证
        document.getElementById('confirmPassword').addEventListener('input', function(e) {
            const password = document.getElementById('password').value;
            const confirmPassword = e.target.value;
            const errorDiv = document.getElementById('confirmPasswordError');
            
            if (confirmPassword && password !== confirmPassword) {
                e.target.classList.add('error');
                errorDiv.textContent = '两次输入的密码不一致';
                errorDiv.classList.add('show');
            } else {
                e.target.classList.remove('error');
                errorDiv.classList.remove('show');
            }
        });

        // 邮箱格式验证
        document.getElementById('email').addEventListener('blur', function(e) {
            const email = e.target.value;
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            const errorDiv = document.getElementById('emailError');
            
            if (email && !emailRegex.test(email)) {
                e.target.classList.add('error');
                errorDiv.textContent = '请输入有效的邮箱地址';
                errorDiv.classList.add('show');
            } else {
                e.target.classList.remove('error');
                errorDiv.classList.remove('show');
            }
        });

        const API_BASE_URL = 'http://localhost:8000';

        async function handleRegister(event) {
            event.preventDefault();
            
            const username = document.getElementById('username').value;
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirmPassword').value;
            const agreeTerms = document.getElementById('agreeTerms').checked;
            const btn = document.getElementById('registerBtn');
            
            // 清除之前的错误
            clearErrors();
            
            // 验证
            let hasError = false;
            
            if (!username || username.trim().length < 2) {
                showFieldError('username', '用户名至少需要2个字符');
                hasError = true;
            }
            
            if (!email || !email.includes('@')) {
                showFieldError('email', '请输入有效的邮箱地址');
                hasError = true;
            }
            
            if (password.length < 8) {
                showFieldError('password', '密码至少需要8位字符');
                hasError = true;
            }
            
            if (password !== confirmPassword) {
                showFieldError('confirmPassword', '两次输入的密码不一致');
                hasError = true;
            }
            
            if (!agreeTerms) {
                alert('请先同意服务条款和隐私政策');
                hasError = true;
            }
            
            if (hasError) {
                return;
            }
            
            // 添加注册动画
            btn.textContent = '注册中...';
            btn.disabled = true;
            
            try {
                // 调用后端注册 API
                const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, email, password })
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail || '注册失败');
                }

                // 注册成功，保存 token 和用户信息
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('refresh_token', data.refresh_token);
                localStorage.setItem('user_id', data.user_id);
                localStorage.setItem('username', data.username);
                localStorage.setItem('email', email);

                // 注册成功，跳转到聊天页面
                btn.textContent = '注册成功！';
                setTimeout(() => {
                    window.location.href = 'agent_chat.html';
                }, 500);

            } catch (error) {
                console.error('注册错误:', error);
                showFieldError('email', error.message || '注册失败，请稍后重试');
                btn.textContent = '注册';
                btn.disabled = false;
            }
        }

        function showFieldError(fieldId, message) {
            const field = document.getElementById(fieldId);
            if (field) {
                field.classList.add('error');
            }
            
            const errorId = fieldId + 'Error';
            let errorDiv = document.getElementById(errorId);
            if (!errorDiv) {
                errorDiv = document.createElement('div');
                errorDiv.id = errorId;
                errorDiv.className = 'field-error';
                errorDiv.style.cssText = 'color: #ff4444; font-size: 12px; margin-top: 4px;';
                if (field && field.parentNode) {
                    field.parentNode.appendChild(errorDiv);
                }
            }
            errorDiv.textContent = message;
            errorDiv.classList.add('show');
        }

        function clearErrors() {
            document.querySelectorAll('.error').forEach(el => el.classList.remove('error'));
            document.querySelectorAll('.field-error').forEach(el => {
                el.classList.remove('show');
                el.textContent = '';
            });
        }

        // 回车提交
        document.getElementById('confirmPassword').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                handleRegister(e);
            }
        });

        // 检查是否已登录
        window.onload = function() {
            const accessToken = localStorage.getItem('access_token');
            if (accessToken) {
                // 如果已登录，直接跳转到聊天页面
                window.location.href = 'agent_chat.html';
            }
        };
    