<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const username = ref('');
const password = ref('');
const confirmPassword = ref('');

function handleRegister() {
    if (password.value !== confirmPassword.value) {
        alert('两次密码不一致');
        return;
    }
    if (username.value && password.value) {
        router.push('/login');
    }
}
</script>

<template>
    <div class="login-page">
        <div class="login-card">
            <h1>🤖 AI Agent Studio</h1>
            <h2>注册</h2>
            
            <form @submit.prevent="handleRegister">
                <input v-model="username" type="text" placeholder="用户名" class="input" />
                <input v-model="password" type="password" placeholder="密码" class="input" />
                <input v-model="confirmPassword" type="password" placeholder="确认密码" class="input" />
                <button type="submit" class="btn btn-primary full-width">注册</button>
            </form>
            
            <p class="register-link">
                已有账号？<router-link to="/login">登录</router-link>
            </p>
        </div>
    </div>
</template>

<style scoped>
.login-page {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background: var(--bg-secondary);
}

.login-card {
    width: 400px;
    padding: 40px;
    background: var(--bg-primary);
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.login-card h1 {
    text-align: center;
    font-size: 32px;
    margin-bottom: 8px;
}

.login-card h2 {
    text-align: center;
    font-size: 24px;
    margin-bottom: 32px;
    color: var(--text-primary);
}

.input {
    width: 100%;
    padding: 12px;
    margin-bottom: 16px;
    border: 1px solid var(--border-secondary);
    border-radius: 6px;
    font-size: 14px;
}

.full-width {
    width: 100%;
}

.register-link {
    text-align: center;
    margin-top: 16px;
    font-size: 14px;
    color: var(--text-secondary);
}

.register-link a {
    color: var(--primary-color);
    text-decoration: none;
}
</style>
