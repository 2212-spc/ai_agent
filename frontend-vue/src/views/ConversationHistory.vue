<script setup>
import { useRouter } from 'vue-router';
const router = useRouter();
</script>

<template>
    <div class="page-container">
        <div class="header">
            <h1>对话历史</h1>
            <button class="btn btn-primary" @click="router.push('/chat')">返回聊天</button>
        </div>
        <div class="content">
            <div class="empty-state">
                <div class="empty-state-icon">💭</div>
                <h3 class="empty-state-title">暂无历史记录</h3>
                <p class="empty-state-subtitle">开始对话后会显示在这里</p>
            </div>
        </div>
    </div>
</template>

<style scoped>
.page-container {
    padding: 20px;
    height: 100vh;
}
.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}
.content {
    display: flex;
    align-items: center;
    justify-content: center;
    height: calc(100% - 80px);
}
</style>
