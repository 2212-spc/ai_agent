/* ===== 工具函数模块 ===== */

/**
 * 通知管理器 - 单例模式
 */
class NotificationManager {
    constructor() {
        if (NotificationManager.instance) {
            return NotificationManager.instance;
        }
        this.notifications = [];
        NotificationManager.instance = this;
    }

    /**
     * 显示通知
     * @param {string} message - 消息内容
     * @param {string} type - 类型: success, error, warning, info
     * @param {number} duration - 持续时间(ms)，0表示不自动关闭
     */
    show(message, type = 'info', duration = 3000) {
        const id = `notification-${Date.now()}-${Math.random()}`;
        const notification = this.createNotification(id, message, type);
        
        document.body.appendChild(notification);
        this.notifications.push({ id, element: notification });
        
        // 自动关闭
        if (duration > 0) {
            setTimeout(() => this.close(id), duration);
        }
        
        return id;
    }

    createNotification(id, message, type) {
        const div = document.createElement('div');
        div.id = id;
        div.className = `notification ${type}`;
        
        const icons = {
            success: '✅',
            error: '❌',
            warning: '⚠️',
            info: 'ℹ️'
        };
        
        div.innerHTML = `
            <div class="notification-icon">${icons[type] || icons.info}</div>
            <div class="notification-content">
                <div class="notification-message">${this.escapeHtml(message)}</div>
            </div>
            <button class="notification-close" onclick="notificationManager.close('${id}')" aria-label="关闭">×</button>
        `;
        
        return div;
    }

    close(id) {
        const index = this.notifications.findIndex(n => n.id === id);
        if (index !== -1) {
            const notification = this.notifications[index];
            notification.element.style.animation = 'fadeOut 0.3s';
            setTimeout(() => {
                notification.element.remove();
                this.notifications.splice(index, 1);
            }, 300);
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

/**
 * 输入验证器
 */
class InputValidator {
    /**
     * 验证消息内容
     */
    static validateMessage(message) {
        if (!message || message.trim().length === 0) {
            return { valid: false, error: '消息不能为空' };
        }
        
        if (message.length > 10000) {
            return { valid: false, error: '消息过长（最多10000字符）' };
        }
        
        // 基础XSS防护（后端也应该做）
        const sanitized = this.sanitizeInput(message);
        
        return { valid: true, value: sanitized };
    }

    /**
     * 验证文件
     */
    static validateFile(file, options = {}) {
        const {
            maxSize = 100 * 1024 * 1024, // 100MB
            allowedTypes = ['application/pdf', 'image/*', 'text/*']
        } = options;

        if (file.size > maxSize) {
            return { 
                valid: false, 
                error: `文件过大（最大${Math.round(maxSize / 1024 / 1024)}MB）` 
            };
        }

        const isAllowed = allowedTypes.some(type => {
            if (type.endsWith('/*')) {
                const prefix = type.split('/')[0];
                return file.type.startsWith(prefix + '/');
            }
            return file.type === type;
        });

        if (!isAllowed) {
            return { valid: false, error: '不支持的文件类型' };
        }

        return { valid: true, file };
    }

    /**
     * 基础输入清理
     */
    static sanitizeInput(input) {
        // 使用DOMPurify如果可用
        if (typeof DOMPurify !== 'undefined') {
            return DOMPurify.sanitize(input);
        }
        
        // 简单的HTML转义
        return input
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#x27;');
    }
}

/**
 * 状态管理器 - 支持撤销/重做
 */
class StateManager {
    constructor(initialState = {}) {
        this.history = [JSON.parse(JSON.stringify(initialState))];
        this.currentIndex = 0;
        this.maxHistory = 50; // 最多保存50个历史状态
    }

    get state() {
        return this.history[this.currentIndex];
    }

    setState(newState) {
        // 删除当前位置之后的所有历史
        this.history = this.history.slice(0, this.currentIndex + 1);
        
        // 添加新状态
        this.history.push(JSON.parse(JSON.stringify(newState)));
        
        // 限制历史记录数量
        if (this.history.length > this.maxHistory) {
            this.history.shift();
        } else {
            this.currentIndex++;
        }
    }

    undo() {
        if (this.canUndo()) {
            this.currentIndex--;
            return true;
        }
        return false;
    }

    redo() {
        if (this.canRedo()) {
            this.currentIndex++;
            return true;
        }
        return false;
    }

    canUndo() {
        return this.currentIndex > 0;
    }

    canRedo() {
        return this.currentIndex < this.history.length - 1;
    }

    clear() {
        const current = this.state;
        this.history = [JSON.parse(JSON.stringify(current))];
        this.currentIndex = 0;
    }
}

/**
 * 本地存储管理器
 */
class StorageManager {
    /**
     * 保存数据
     */
    static set(key, value) {
        try {
            const data = JSON.stringify(value);
            localStorage.setItem(key, data);
            return true;
        } catch (error) {
            console.error('保存数据失败:', error);
            return false;
        }
    }

    /**
     * 获取数据
     */
    static get(key, defaultValue = null) {
        try {
            const data = localStorage.getItem(key);
            return data ? JSON.parse(data) : defaultValue;
        } catch (error) {
            console.error('读取数据失败:', error);
            return defaultValue;
        }
    }

    /**
     * 删除数据
     */
    static remove(key) {
        try {
            localStorage.removeItem(key);
            return true;
        } catch (error) {
            console.error('删除数据失败:', error);
            return false;
        }
    }

    /**
     * 清空所有数据
     */
    static clear() {
        try {
            localStorage.clear();
            return true;
        } catch (error) {
            console.error('清空数据失败:', error);
            return false;
        }
    }
}

/**
 * 防抖函数
 */
function debounce(func, wait = 300) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * 节流函数
 */
function throttle(func, limit = 300) {
    let inThrottle;
    return function executedFunction(...args) {
        if (!inThrottle) {
            func(...args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * 格式化日期
 */
function formatDate(date, format = 'YYYY-MM-DD HH:mm:ss') {
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    const seconds = String(d.getSeconds()).padStart(2, '0');
    
    return format
        .replace('YYYY', year)
        .replace('MM', month)
        .replace('DD', day)
        .replace('HH', hours)
        .replace('mm', minutes)
        .replace('ss', seconds);
}

/**
 * 生成唯一ID
 */
function generateId(prefix = 'id') {
    return `${prefix}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * 深拷贝
 */
function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

// 导出（如果使用模块系统）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        NotificationManager,
        InputValidator,
        StateManager,
        StorageManager,
        debounce,
        throttle,
        formatDate,
        generateId,
        deepClone
    };
}

// 创建全局实例
const notificationManager = new NotificationManager();
