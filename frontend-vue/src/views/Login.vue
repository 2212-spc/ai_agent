<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';
import { API_BASE_URL } from '../config/api';

const router = useRouter();
const email = ref('');
const password = ref('');
const isLoading = ref(false);
const error = ref('');

async function handleLogin() {
    if (!email.value || !password.value) {
        error.value = '请输入邮箱和密码';
        return;
    }
    
    isLoading.value = true;
    error.value = '';
    
    try {
        const response = await axios.post(`${API_BASE_URL}/api/auth/login`, {
            email: email.value,
            password: password.value
        });
        
        // 保存token
        localStorage.setItem('access_token', response.data.access_token);
        localStorage.setItem('refresh_token', response.data.refresh_token);
        localStorage.setItem('user', email.value);
        
        // 跳转到聊天页面
        router.push('/chat');
    } catch (err) {
        console.error('登录失败:', err);
        error.value = err.response?.data?.detail || '登录失败，请检查邮箱和密码';
    } finally {
        isLoading.value = false;
    }
}

function goToRegister() {
    router.push('/register');
}

function skipLogin() {
    router.push('/chat');
}
</script>

<template>
    <div class="login-container">
        <div class="login-box">
            <div class="login-header">
                <h1>🤖 AI Agent Studio</h1>
                <p class="login-subtitle">登录您的账户</p>
            </div>
            
            <form @submit.prevent="handleLogin" class="login-form">
                <div class="form-group">
                    <label>邮箱</label>
                    <input 
                        type="email" 
                        v-model="email" 
                        placeholder="请输入注册时的邮箱"
                        :disabled="isLoading"
                        class="form-input"
                        autocomplete="email"
                    />
                </div>
                
                <div class="form-group">
                    <label>密码</label>
                    <input 
                        type="password" 
                        v-model="password" 
                        placeholder="请输入密码"
                        :disabled="isLoading"
                        class="form-input"
                    />
                </div>
                
                <div v-if="error" class="error-message">
                    {{ error }}
                </div>
                
                <button type="submit" class="btn btn-primary btn-block" :disabled="isLoading">
                    {{ isLoading ? '登录中...' : '登录' }}
                </button>
                
                <div class="login-footer">
                    <span>还没有账户？</span>
                    <button type="button" class="btn-link" @click="goToRegister">立即注册</button>
                </div>
                
                <div class="login-skip">
                    <button type="button" class="btn-link" @click="skipLogin">
                        跳过登录 →
                    </button>
                </div>
            </form>
        </div>
    </div>
</template>

<style scoped>
.login-container {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px;
}

.login-box {
    background: var(--bg-primary);
    padding: 40px;
    border-radius: 16px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
    width: 100%;
    max-width: 420px;
    border: 1px solid var(--border-primary);
}

.login-header {
    text-align: center;
    margin-bottom: 32px;
}

.login-header h1 {
    font-size: 28px;
    margin-bottom: 8px;
    color: var(--text-primary);
}

.login-subtitle {
    color: var(--text-secondary);
    font-size: 14px;
}

.login-form {
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

.btn-block {
    width: 100%;
    padding: 12px;
    font-size: 15px;
    font-weight: 600;
}

.login-footer {
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

.login-skip {
    text-align: center;
    padding-top: 12px;
    border-top: 1px solid var(--border-primary);
}
</style>
