/**
 * 前端应用初始化脚本
 * 作用：解决代码脑裂问题，统一使用模块化代码
 * 创建时间：2024-11-21
 */

(function() {
    'use strict';
    
    console.log('🚀 初始化应用...');
    
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
        console.error('❌ 缺少必要模块:', missingModules);
        alert('应用初始化失败：缺少必要模块 ' + missingModules.join(', '));
        return;
    }
    
    console.log('✅ 所有必要模块已加载');
    
    // 2. 创建全局单例实例
    window.chatManager = new ChatManager();
    window.canvasManager = new CanvasManager();
    window.errorHandler = new ErrorHandler();
    window.notificationManager = new NotificationManager();
    
    console.log('✅ 全局实例创建完成');
    
    // 3. 设置全局错误处理
    window.errorHandler.setupGlobalHandlers();
    
    // 4. 兼容层：将旧的全局函数调用映射到新模块
    // 这样可以保持向后兼容，逐步迁移
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
    
    // 5. DOM Ready 时初始化应用
    function initializeApp() {
        console.log('📱 初始化应用组件...');
        
        try {
            // 初始化聊天管理器
            if (window.chatManager && typeof window.chatManager.init === 'function') {
                window.chatManager.init();
                console.log('✅ ChatManager 初始化成功');
            }
            
            // 初始化画布管理器
            if (window.canvasManager && typeof window.canvasManager.init === 'function') {
                window.canvasManager.init();
                console.log('✅ CanvasManager 初始化成功');
            }
            
            console.log('🎉 应用初始化完成！');
            
        } catch (error) {
            console.error('❌ 应用初始化失败:', error);
            window.errorHandler.handleError({
                type: 'Initialization Error',
                message: error.message,
                error: error,
                timestamp: new Date().toISOString()
            });
        }
    }
    
    // 6. 等待 DOM 加载完成
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeApp);
        console.log('⏳ 等待 DOM 加载完成...');
    } else {
        // DOM 已经加载完成，立即初始化
        initializeApp();
    }
    
})();
