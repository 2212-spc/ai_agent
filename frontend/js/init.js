/**
 * 前端应用初始化脚本
 * 作用：解决代码脑裂问题，统一使用模块化代码
 * 创建时间：2024-11-21
 */

(function() {
    'use strict';
    
    console.log('🚀 init.js 已加载，等待其他模块...');
    
    function loadScript(src) {
        return new Promise((resolve, reject) => {
            const s = document.createElement('script');
            s.src = src;
            s.onload = () => resolve(true);
            s.onerror = () => reject(new Error('加载失败: ' + src));
            document.body.appendChild(s);
        });
    }
    
    async function ensureModules() {
        const map = {
            NotificationManager: 'js/utils.js',
            InputValidator: 'js/utils.js',
            ErrorHandler: 'js/errorHandler.js',
            CanvasManager: 'js/canvasManager.js',
            ChatManager: 'js/chatManager.js',
        };
        const order = ['NotificationManager','InputValidator','ErrorHandler','CanvasManager','ChatManager'];
        for (const name of order) {
            if (typeof window[name] === 'undefined') {
                await loadScript(map[name]);
            }
        }
    }
    
    // 延迟执行初始化，确保所有script标签都已加载
    function checkAndInitialize() {
        console.log('🔍 开始检查必要模块...');
        
        // 1. 检查必要的模块是否已加载
        const requiredModules = [
            'ChatManager',
            'CanvasManager', 
            'ErrorHandler',
            'NotificationManager',
            'InputValidator'
        ];
        
        const missingModules = requiredModules.filter(moduleName => {
            return typeof window[moduleName] === 'undefined';
        });
        
        if (missingModules.length > 0) {
            console.warn('缺少必要模块:', missingModules);
            return false;
        }
        
        console.log('✅ 所有必要模块已加载');
        return true;
    }
    
    // 2. 初始化应用的主函数
    async function initializeApp() {
        if (!checkAndInitialize()) {
            try {
                await ensureModules();
            } catch (e) {
                console.error('模块加载失败:', e);
            }
        }
        if (!checkAndInitialize()) return;
        
        try {
            // 创建全局单例实例
            window.chatManager = new ChatManager();
            window.canvasManager = new CanvasManager();
            
            // errorHandler 已经在 errorHandler.js 中创建
            // notificationManager 已经在 utils.js 中创建
            
            console.log('✅ 全局实例创建完成');
            
            // 兼容层：将旧的全局函数调用映射到新模块
            window.sendMessage = function() {
                return window.chatManager.sendMessage();
            };
            
            window.addUserMessage = function(message) {
                return window.chatManager.addUserMessage(message);
            };
            
            window.handleAgentEvent = function(eventType, eventData) {
                return window.chatManager.handleEvent(eventType, eventData);
            };
            
            console.log('✅ 兼容层设置完成');
            
            // 初始化各个组件
            console.log('📱 初始化应用组件...');
            
            if (window.chatManager && typeof window.chatManager.init === 'function') {
                window.chatManager.init();
                console.log('✅ ChatManager 初始化成功');
            }
            
            if (window.canvasManager && typeof window.canvasManager.init === 'function') {
                window.canvasManager.init();
                console.log('✅ CanvasManager 初始化成功');
            }
            
            console.log('🎉 应用初始化完成！');
            
        } catch (error) {
            console.error('❌ 应用初始化失败:', error);
            if (window.errorHandler && window.errorHandler.handleError) {
                window.errorHandler.handleError({
                    type: 'Initialization Error',
                    message: error.message,
                    error: error,
                    timestamp: new Date().toISOString()
                });
            }
        }
    }
    
    // 3. 等待 DOM 加载完成后再初始化
    // 使用 DOMContentLoaded 确保所有脚本都已加载
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeApp);
        console.log('⏳ 等待 DOM 加载完成...');
    } else {
        // DOM 已经加载完成，使用 setTimeout 确保所有脚本都执行完毕
        setTimeout(initializeApp, 0);
    }
    
})();
