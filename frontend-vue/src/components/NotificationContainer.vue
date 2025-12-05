<script setup>
import { useNotification } from '../composables/useNotification';

const { notifications, close } = useNotification();

function getIcon(type) {
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };
    return icons[type] || icons.info;
}

// 不需要truncateText，因为已经在AgentChat.vue中截取了
function truncateText(text, maxLength = 200) {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}
</script>

<template>
    <div class="notification-container">
        <transition-group name="notification-list" tag="div">
            <div
                v-for="notification in notifications"
                :key="notification.id"
                class="notification"
                :class="notification.type"
                @click="close(notification.id)"
            >
                <div class="notification-icon">{{ getIcon(notification.type) }}</div>
                <div class="notification-content">
                    <div v-if="notification.isRich">
                        <div class="notification-title">{{ notification.title }}</div>
                        <div class="notification-body">{{ notification.content }}</div>
                    </div>
                    <div v-else class="notification-message">{{ notification.message }}</div>
                </div>
                <button class="notification-close" @click.stop="close(notification.id)" aria-label="关闭">×</button>
            </div>
        </transition-group>
    </div>
</template>

<style scoped>
.notification-container {
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 9999;
    display: flex;
    flex-direction: column-reverse;
    gap: 10px;
    max-width: 400px;
    pointer-events: none;
}

.notification {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 14px 16px;
    border-radius: 8px;
    background: white;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    cursor: pointer;
    pointer-events: auto;
    min-width: 300px;
    max-width: 400px;
    border-left: 4px solid;
    transition: all 0.3s ease;
}

.notification:hover {
    transform: translateX(-5px);
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
}

.notification.success {
    border-left-color: #4CAF50;
    background: #f1f8f4;
}

.notification.error {
    border-left-color: #f44336;
    background: #fef1f0;
}

.notification.warning {
    border-left-color: #ff9800;
    background: #fff8f0;
}

.notification.info {
    border-left-color: #2196F3;
    background: #f0f7ff;
}

.notification-icon {
    font-size: 20px;
    flex-shrink: 0;
}

.notification-content {
    flex: 1;
    min-width: 0;
}

.notification-title {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary, #1a1a1a);
    margin-bottom: 6px;
    line-height: 1.4;
    word-break: break-word;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', 'PingFang SC', sans-serif;
}

.notification-body {
    font-size: 13px;
    font-weight: 400;
    color: var(--text-secondary, #666);
    line-height: 1.6;
    word-break: break-word;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', 'PingFang SC', sans-serif;
}

.notification-message {
    font-size: 13px;
    color: var(--text-secondary, #666);
    line-height: 1.5;
    word-break: break-word;
}

.notification-close {
    background: none;
    border: none;
    color: var(--text-tertiary, #999);
    cursor: pointer;
    font-size: 20px;
    padding: 0;
    width: 20px;
    height: 20px;
    line-height: 1;
    flex-shrink: 0;
    transition: color 0.2s;
}

.notification-close:hover {
    color: var(--text-primary, #333);
}

/* Transition animations */
.notification-list-enter-active {
    animation: slideIn 0.3s ease-out;
}

.notification-list-leave-active {
    animation: slideOut 0.3s ease-in;
}

@keyframes slideIn {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

@keyframes slideOut {
    from {
        transform: translateX(0);
        opacity: 1;
    }
    to {
        transform: translateX(100%);
        opacity: 0;
    }
}
</style>

