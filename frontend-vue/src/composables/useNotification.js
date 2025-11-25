import { ref } from 'vue';

// 通知类型
export const NOTIFICATION_TYPES = {
    SUCCESS: 'success',
    ERROR: 'error',
    WARNING: 'warning',
    INFO: 'info'
};

// 通知状态管理
const notifications = ref([]);
let notificationId = 0;

/**
 * 通知系统 Composable
 */
export function useNotification() {
    /**
     * 显示普通通知
     * @param {string} message - 消息内容
     * @param {string} type - 类型
     * @param {number} duration - 持续时间(ms)
     */
    function show(message, type = NOTIFICATION_TYPES.INFO, duration = 3000) {
        const id = ++notificationId;
        const notification = {
            id,
            message,
            type,
            isRich: false,
            createdAt: Date.now()
        };
        
        notifications.value.push(notification);
        
        if (duration > 0) {
            setTimeout(() => close(id), duration);
        }
        
        return id;
    }
    
    /**
     * 显示富文本通知
     * @param {string} title - 标题
     * @param {string} content - 内容
     * @param {string} type - 类型
     * @param {number} duration - 持续时间(ms)
     */
    function showRich(title, content, type = NOTIFICATION_TYPES.INFO, duration = 5000) {
        const id = ++notificationId;
        const notification = {
            id,
            title,
            content,
            type,
            isRich: true,
            createdAt: Date.now()
        };
        
        notifications.value.push(notification);
        
        if (duration > 0) {
            setTimeout(() => close(id), duration);
        }
        
        return id;
    }
    
    /**
     * 关闭通知
     * @param {number} id - 通知ID
     */
    function close(id) {
        const index = notifications.value.findIndex(n => n.id === id);
        if (index !== -1) {
            notifications.value.splice(index, 1);
        }
    }
    
    /**
     * 清空所有通知
     */
    function clearAll() {
        notifications.value = [];
    }
    
    return {
        notifications,
        show,
        showRich,
        close,
        clearAll
    };
}

