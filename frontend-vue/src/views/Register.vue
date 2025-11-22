<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';

const router = useRouter();
const username = ref('');
const email = ref('');
const password = ref('');
const confirmPassword = ref('');
const isLoading = ref(false);
const error = ref('');
const success = ref('');

async function handleRegister() {
    // 清空之前的错误
    error.value = '';
    
    // 详细验证
    if (!username.value) {
        error.value = '请输入用户名';
        return;
    }
    
    if (!email.value) {
        error.value = '请输入邮箱地址';
        return;
    }
    
    // 验证邮箱格式
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email.value)) {
        error.value = '邮箱格式不正确';
        return;
    }
    
    if (!password.value) {
        error.value = '请输入密码';
        return;
    }
    
    if (password.value.length < 6) {
        error.value = '密码至少需要6个字符';
        return;
    }
    
    if (password.value !== confirmPassword.value) {
        error.value = '两次密码不一致';
        return;
    }
    
    isLoading.value = true;
    error.value = '';
    success.value = '';
    
    try {
        const response = await axios.post('http://127.0.0.1:8000/api/auth/register', {
            username: username.value,
            email: email.value,
            password: password.value
        });
        
        console.log('注册成功:', response.data);
        success.value = '注册成功！3秒后跳转到登录页面...';
        
        // 3秒后跳转到登录
        setTimeout(() => {
            router.push('/login');
        }, 3000);
    } catch (err) {
        console.error('注册失败:', err);
        error.value = err.response?.data?.detail || '注册失败，请重试';
    } finally {
        isLoading.value = false;
    }
}

function goToLogin() {
    router.push('/login');
}

function skipRegister() {
    router.push('/chat');
}
</script>

<template>
    <div class="register-container">
        <div class="register-box">
            <div class="register-header">
                <h1>🤖 AI Agent Studio</h1>
                <p class="register-subtitle">创建您的账户</p>
            </div>
            
            <form @submit.prevent="handleRegister" class="register-form">
                <div class="form-group">
                    <label>用户名 <span class="required">*</span></label>
                    <input 
                        type="text" 
                        v-model="username" 
                        placeholder="例如: zhangsan"
                        :disabled="isLoading"
                        class="form-input"
                        required
                    />
                    <small class="form-hint">用于登录的用户名</small>
                </div>
                
                <div class="form-group">
                    <label>邮箱 <span class="required">*</span></label>
                    <input 
                        type="email" 
                        v-model="email" 
                        placeholder="例如: user@example.com"
                        :disabled="isLoading"
                        class="form-input"
                        required
                    />
                    <small class="form-hint">必须是有效的邮箱地址</small>
                </div>
                
                <div class="form-group">
                    <label>密码</label>
                    <input 
                        type="password" 
                        v-model="password" 
                        placeholder="至少6个字符"
                        :disabled="isLoading"
                        class="form-input"
                    />
                </div>
                
                <div class="form-group">
                    <label>确认密码</label>
                    <input 
                        type="password" 
                        v-model="confirmPassword" 
                        placeholder="再次输入密码"
                        :disabled="isLoading"
                        class="form-input"
                    />
                </div>
                
                <div v-if="error" class="error-message">
                    {{ error }}
                </div>
                
                <div v-if="success" class="success-message">
                    {{ success }}
                </div>
                
                <button type="submit" class="btn btn-primary btn-block" :disabled="isLoading">
                    {{ isLoading ? '注册中...' : '注册' }}
                </button>
                
                <div class="register-footer">
                    <span>已有账户？</span>
                    <button type="button" class="btn-link" @click="goToLogin">立即登录</button>
                </div>
                
                <div class="register-skip">
                    <button type="button" class="btn-link" @click="skipRegister">
                        跳过注册 →
                    </button>
                </div>
            </form>
        </div>
    </div>
</template>

<style scoped>
.register-container {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
    padding: 20px;
}

.register-box {
    background: var(--bg-primary);
    padding: 40px;
    border-radius: 16px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
    width: 100%;
    max-width: 420px;
    border: 1px solid var(--border-primary);
}

.register-header {
    text-align: center;
    margin-bottom: 32px;
}

.register-header h1 {
    font-size: 28px;
    margin-bottom: 8px;
    color: var(--text-primary);
}

.register-subtitle {
    color: var(--text-secondary);
    font-size: 14px;
}

.register-form {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.form-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.form-group label {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
}

.form-input {
    padding: 12px 16px;
    border: 1px solid var(--border-secondary);
    border-radius: 8px;
    background: var(--bg-secondary);
    color: var(--text-primary);
    font-size: 14px;
    transition: all 0.2s;
}

.form-input:focus {
    outline: none;
    border-color: var(--primary-color);
    background: var(--bg-primary);
}

.form-input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.error-message {
    background: #fee;
    color: #c00;
    padding: 12px;
    border-radius: 8px;
    font-size: 13px;
    border: 1px solid #fcc;
}

.success-message {
    background: #d1fae5;
    color: #065f46;
    padding: 12px;
    border-radius: 8px;
    font-size: 13px;
    border: 1px solid #6ee7b7;
}

.btn-block {
    width: 100%;
    padding: 12px;
    font-size: 15px;
    font-weight: 600;
}

.register-footer {
    text-align: center;
    font-size: 13px;
    color: var(--text-secondary);
    display: flex;
    gap: 8px;
    align-items: center;
    justify-content: center;
}

.btn-link {
    background: none;
    border: none;
    color: var(--primary-color);
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    padding: 0;
}

.btn-link:hover {
    text-decoration: underline;
}

.register-skip {
    text-align: center;
    padding-top: 12px;
    border-top: 1px solid var(--border-primary);
}

.required {
    color: #ef4444;
    font-weight: bold;
}

.form-hint {
    display: block;
    margin-top: 4px;
    font-size: 12px;
    color: var(--text-tertiary);
    font-style: italic;
}
</style>
