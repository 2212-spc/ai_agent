import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import axios from 'axios';

export const useChatStore = defineStore('chat', () => {
    // State
    const messages = ref([]);
    const currentSessionId = ref(null);
    const isLoading = ref(false);
    const apiBase = 'http://127.0.0.1:8000';

    // Computed
    const hasMessages = computed(() => messages.value.length > 0);

    // Actions
    function addMessage(message) {
        messages.value.push({
            ...message,
            id: Date.now(),
            timestamp: new Date().toISOString()
        });
    }

    function clearMessages() {
        messages.value = [];
    }

    async function sendMessage(content) {
        isLoading.value = true;

        // 添加用户消息到本地
        const userMsg = {
            role: 'user',
            content,
            type: 'text'
        };
        addMessage(userMsg);

        // 构建符合后端格式的请求
        const requestMessages = messages.value
            .filter(m => m.role === 'user' || m.role === 'assistant')
            .map(m => ({
                role: m.role,
                content: m.content
            }));

        try {
            const response = await axios.post(`${apiBase}/chat`, {
                messages: requestMessages,
                model: 'deepseek-chat',
                temperature: 0.7
            });

            // 添加AI回复 (后端返回 reply 字段)
            if (response.data && response.data.reply) {
                addMessage({
                    role: 'assistant',
                    content: response.data.reply,
                    type: 'text'
                });
            } else {
                console.error('响应数据格式错误:', response.data);
            }

            return response.data;
        } catch (error) {
            console.error('发送消息失败:', error);
            
            // 显示详细错误信息
            let errorMsg = '消息发送失败，请重试';
            if (error.response) {
                errorMsg = `错误 ${error.response.status}: ${error.response.data?.detail || '未知错误'}`;
            } else if (error.request) {
                errorMsg = '无法连接到服务器，请检查后端是否启动';
            }
            
            addMessage({
                role: 'system',
                content: errorMsg,
                type: 'error'
            });
            throw error;
        } finally {
            isLoading.value = false;
        }
    }

    function setSessionId(id) {
        currentSessionId.value = id;
    }

    return {
        messages,
        currentSessionId,
        isLoading,
        hasMessages,
        addMessage,
        clearMessages,
        sendMessage,
        setSessionId
    };
});
