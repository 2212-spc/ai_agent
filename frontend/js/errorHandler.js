/* ===== 全局错误处理模块 ===== */

/**
 * 错误处理器 - 统一管理所有错误
 */
class ErrorHandler {
    constructor() {
        this.errorLog = [];
        this.maxLogSize = 100;
        this.setupGlobalHandlers();
    }

    /**
     * 设置全局错误处理器
     */
    setupGlobalHandlers() {
        // 捕获未处理的JavaScript错误
        window.addEventListener('error', (event) => {
            this.handleError({
                type: 'JavaScript Error',
                message: event.message,
                filename: event.filename,
                line: event.lineno,
                column: event.colno,
                error: event.error,
                timestamp: new Date().toISOString()
            });
        });

        // 捕获未处理的Promise rejection
        window.addEventListener('unhandledrejection', (event) => {
            this.handleError({
                type: 'Unhandled Promise Rejection',
                message: event.reason?.message || event.reason,
                error: event.reason,
                timestamp: new Date().toISOString()
            });
        });

        // 捕获资源加载错误
        window.addEventListener('error', (event) => {
            if (event.target !== window) {
                this.handleError({
                    type: 'Resource Load Error',
                    message: `Failed to load: ${event.target.src || event.target.href}`,
                    element: event.target.tagName,
                    timestamp: new Date().toISOString()
                }, false); // 资源错误不显示通知
            }
        }, true);
    }

    /**
     * 处理错误
     * @param {Object} errorInfo - 错误信息
     * @param {boolean} showNotification - 是否显示通知
     */
    handleError(errorInfo, showNotification = true) {
        // 记录到控制台
        console.error('❌ Error:', errorInfo);

        // 添加到错误日志
        this.errorLog.push(errorInfo);
        if (this.errorLog.length > this.maxLogSize) {
            this.errorLog.shift();
        }

        // 显示用户友好的错误提示
        if (showNotification && typeof notificationManager !== 'undefined') {
            const userMessage = this.getUserFriendlyMessage(errorInfo);
            notificationManager.show(userMessage, 'error', 5000);
        }

        // 上报到监控系统（如果配置了）
        this.reportError(errorInfo);
    }

    /**
     * 获取用户友好的错误消息
     */
    getUserFriendlyMessage(errorInfo) {
        const { type, message } = errorInfo;

        // 网络错误
        if (message?.includes('fetch') || message?.includes('network')) {
            return '网络连接失败，请检查网络后重试';
        }

        // 超时错误
        if (message?.includes('timeout')) {
            return '请求超时，请稍后重试';
        }

        // 权限错误
        if (message?.includes('permission') || message?.includes('denied')) {
            return '权限不足，请检查权限设置';
        }

        // 默认消息
        return '操作失败，请刷新页面后重试';
    }

    /**
     * 上报错误到监控系统
     */
    reportError(errorInfo) {
        // 这里可以集成第三方监控服务，如 Sentry
        // 示例：
        // if (typeof Sentry !== 'undefined') {
        //     Sentry.captureException(errorInfo.error);
        // }
        
        // 或者发送到自己的后端
        // fetch('/api/log-error', {
        //     method: 'POST',
        //     headers: { 'Content-Type': 'application/json' },
        //     body: JSON.stringify(errorInfo)
        // }).catch(() => {}); // 静默失败
    }

    /**
     * 获取错误日志
     */
    getErrorLog() {
        return [...this.errorLog];
    }

    /**
     * 清空错误日志
     */
    clearErrorLog() {
        this.errorLog = [];
    }

    /**
     * 手动记录错误
     */
    logError(message, error = null) {
        this.handleError({
            type: 'Manual Log',
            message,
            error,
            timestamp: new Date().toISOString()
        });
    }
}

/**
 * API错误处理器
 */
class APIErrorHandler {
    /**
     * 处理API响应
     */
    static async handleResponse(response) {
        if (!response.ok) {
            const error = await this.parseError(response);
            throw error;
        }
        return response;
    }

    /**
     * 解析错误响应
     */
    static async parseError(response) {
        let message = '请求失败';
        let details = null;

        try {
            const data = await response.json();
            message = data.message || data.error || message;
            details = data.details || data;
        } catch (e) {
            // 无法解析JSON，使用状态文本
            message = response.statusText || message;
        }

        const error = new Error(message);
        error.status = response.status;
        error.details = details;
        error.response = response;

        return error;
    }

    /**
     * 包装fetch请求，自动处理错误
     */
    static async fetch(url, options = {}) {
        try {
            // 添加超时控制
            const timeout = options.timeout || 30000; // 默认30秒
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), timeout);

            const response = await fetch(url, {
                ...options,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            return await this.handleResponse(response);
        } catch (error) {
            // 处理不同类型的错误
            if (error.name === 'AbortError') {
                throw new Error('请求超时，请稍后重试');
            }
            
            if (!navigator.onLine) {
                throw new Error('网络连接已断开，请检查网络');
            }

            throw error;
        }
    }
}

/**
 * 重试机制
 */
class RetryHandler {
    /**
     * 带重试的执行函数
     * @param {Function} fn - 要执行的函数
     * @param {number} maxRetries - 最大重试次数
     * @param {number} delay - 重试延迟(ms)
     */
    static async withRetry(fn, maxRetries = 3, delay = 1000) {
        let lastError;
        
        for (let i = 0; i <= maxRetries; i++) {
            try {
                return await fn();
            } catch (error) {
                lastError = error;
                
                if (i < maxRetries) {
                    console.log(`重试 ${i + 1}/${maxRetries}...`);
                    await this.sleep(delay * Math.pow(2, i)); // 指数退避
                }
            }
        }
        
        throw lastError;
    }

    static sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// 创建全局实例
const errorHandler = new ErrorHandler();

// 导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        ErrorHandler,
        APIErrorHandler,
        RetryHandler,
        errorHandler
    };
}
