<script setup>
import { ref, computed, watch } from 'vue';
import { useChatStore } from '../../stores/chat';

const chatStore = useChatStore();

// 时间线步骤
const steps = ref([]);
const filters = ref({
    thoughts: true,
    observations: true,
    tools: true
});

// 从store中获取timeline数据
const timelineData = computed(() => {
    if (chatStore.timelineSteps.length > 0) {
        return chatStore.timelineSteps;
    }
    
    // 如果没有真实数据，显示示例
    if (chatStore.isLoading) {
        return [
            { icon: '🤔', title: '理解问题', content: '分析用户输入，确定意图...', status: 'completed', type: 'thoughts' },
            { icon: '🔍', title: '检索知识', content: '从知识库中搜索相关信息...', status: chatStore.isLoading ? 'running' : 'completed', type: 'observations' },
            { icon: '🤖', title: 'AI推理', content: '使用DeepSeek模型生成回复...', status: 'pending', type: 'tools' }
        ];
    }
    
    return [];
});

// 过滤后的步骤
const filteredSteps = computed(() => {
    return timelineData.value.filter(step => {
        return filters.value[step.type];
    });
});

function toggleFilter(filterName) {
    filters.value[filterName] = !filters.value[filterName];
}

// 监听消息变化，更新时间线
watch(() => chatStore.messages, (newMessages) => {
    // 可以从最新消息中提取时间线数据
    // 这里暂时使用默认行为
}, { deep: true });
</script>

<template>
    <div class="timeline-panel">
        <div class="timeline-header">
            <h3>执行过程</h3>
            <span class="timeline-count">{{ filteredSteps.length }}步骤</span>
        </div>
        
        <!-- 过滤器 -->
        <div class="timeline-filters">
            <button
                class="filter-chip"
                :class="{ active: filters.thoughts }"
                @click="toggleFilter('thoughts')"
            >
                思维
            </button>
            <button
                class="filter-chip"
                :class="{ active: filters.observations }"
                @click="toggleFilter('observations')"
            >
                观察
            </button>
            <button
                class="filter-chip"
                :class="{ active: filters.tools }"
                @click="toggleFilter('tools')"
            >
                工具调用
            </button>
        </div>
        
        <div class="timeline-content">
            <div 
                v-for="(step, index) in filteredSteps" 
                :key="index"
                class="timeline-step"
                :class="step.status"
            >
                <div class="step-icon">{{ step.icon }}</div>
                <div class="step-content">
                    <div class="step-title">{{ step.title }}</div>
                    <div class="step-description">{{ step.content }}</div>
                </div>
                <div class="step-status">
                    <span v-if="step.status === 'completed'">✓</span>
                    <span v-else-if="step.status === 'running'" class="spinner">⚙️</span>
                    <span v-else>○</span>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.timeline-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--bg-secondary);
}

.timeline-header {
    padding: 16px;
    background: var(--bg-primary);
    border-bottom: 1px solid var(--border-primary);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.timeline-header h3 {
    font-size: 14px;
    font-weight: 600;
    margin: 0;
}

.timeline-count {
    font-size: 12px;
    color: var(--text-tertiary);
    background: var(--bg-tertiary);
    padding: 2px 8px;
    border-radius: 10px;
}

.timeline-filters {
    display: flex;
    gap: 8px;
    padding: 12px 16px;
    background: var(--bg-primary);
    border-bottom: 1px solid var(--border-primary);
}

.filter-chip {
    padding: 6px 12px;
    border-radius: 16px;
    border: 1px solid var(--border-secondary);
    background: var(--bg-secondary);
    color: var(--text-secondary);
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s;
}

.filter-chip:hover {
    border-color: var(--primary-color);
    color: var(--text-primary);
}

.filter-chip.active {
    background: var(--primary-light);
    border-color: var(--primary-color);
    color: var(--primary-color);
    font-weight: 500;
}

.timeline-content {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
}

.timeline-step {
    display: flex;
    gap: 12px;
    padding: 12px;
    margin-bottom: 12px;
    background: var(--bg-primary);
    border-radius: 8px;
    border: 1px solid var(--border-primary);
    transition: all 0.2s;
}

.timeline-step.running {
    border-color: var(--primary-color);
    background: var(--primary-light);
}

.timeline-step.completed {
    opacity: 0.8;
}

.step-icon {
    font-size: 24px;
    flex-shrink: 0;
}

.step-content {
    flex: 1;
}

.step-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.step-description {
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.4;
}

.step-status {
    flex-shrink: 0;
    font-size: 16px;
}

.spinner {
    display: inline-block;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}
</style>
