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

        // 添加用户消息
        addMessage({
            role: 'user',
            content,
            type: 'text'
        });

        try {
            const response = await axios.post(`${apiBase}/chat`, {
                message: content,
                session_id: currentSessionId.value
            });

            // 添加AI回复
            addMessage({
                role: 'assistant',
                content: response.data.message,
                type: 'text'
            });

            if (response.data.session_id) {
                currentSessionId.value = response.data.session_id;
            }

            return response.data;
        } catch (error) {
            console.error('发送消息失败:', error);
            addMessage({
                role: 'system',
                content: '消息发送失败，请重试',
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
