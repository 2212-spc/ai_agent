<script setup>
import { ref, computed } from 'vue';

const props = defineProps({
  show: { type: Boolean, default: false }
});

const emit = defineEmits(['close', 'next', 'prev', 'skip']);

// 引导步骤
const steps = [
  {
    id: 1,
    title: '欢迎使用Agent构建器',
    content: '这是一个可视化工具，帮助您通过拖拽节点来构建AI Agent工作流。',
    highlight: null,
    position: 'center'
  },
  {
    id: 2,
    title: '添加节点',
    content: '点击左侧节点库中的节点，将其添加到画布上。每个节点代表一个功能模块。',
    highlight: 'node-palette',
    position: 'left'
  },
  {
    id: 3,
    title: '理解节点类型',
    content: '节点有不同类型：规划器(起点) → 工具执行器/知识检索 → 合成器(终点)。节点左侧绿点是输入端口，右侧蓝点是输出端口。',
    highlight: 'canvas-container',
    position: 'center'
  },
  {
    id: 4,
    title: '连接节点',
    content: '双击一个节点开始连接，然后点击目标节点完成连接。连接定义了数据流向。鼠标悬停在节点上可查看详细信息。',
    highlight: 'canvas-container',
    position: 'center'
  },
  {
    id: 5,
    title: '连接示例',
    content: '典型工作流：\n• 规划器 → 知识库检索 → 合成器\n• 规划器 → 工具执行器 → 合成器\n确保有起点和终点节点。',
    highlight: 'canvas-container',
    position: 'center'
  },
  {
    id: 6,
    title: '配置节点',
    content: '点击节点上的⚙️按钮或右键菜单中的"配置节点"来设置节点参数。每个节点都有特定的配置选项。',
    highlight: 'canvas-container',
    position: 'center'
  },
  {
    id: 7,
    title: '删除节点',
    content: '右键点击节点选择"删除节点"，或选中节点后按Delete/Backspace键删除。',
    highlight: 'canvas-container',
    position: 'center'
  },
  {
    id: 8,
    title: '保存和执行',
    content: '填写Agent名称和描述，点击"保存"保存配置，点击"执行"测试Agent。执行结果会实时显示在聊天界面。',
    highlight: 'canvas-toolbar',
    position: 'top'
  },
  {
    id: 9,
    title: '开始构建',
    content: '现在您已经了解了基本操作，开始构建您的第一个Agent吧！也可以点击"模板"按钮加载示例。',
    highlight: null,
    position: 'center'
  }
];

const currentStepIndex = ref(0);
const currentStep = computed(() => steps[currentStepIndex.value]);

function nextStep() {
  if (currentStepIndex.value < steps.length - 1) {
    currentStepIndex.value++;
    emit('next', currentStep.value);
  } else {
    completeTutorial();
  }
}

function prevStep() {
  if (currentStepIndex.value > 0) {
    currentStepIndex.value--;
    emit('prev', currentStep.value);
  }
}

function skipTutorial() {
  completeTutorial();
}

function completeTutorial() {
  localStorage.setItem('builder_tutorial_completed', 'true');
  emit('close');
}

const progress = computed(() => {
  return ((currentStepIndex.value + 1) / steps.length) * 100;
});
</script>

<template>
  <div v-if="show" class="tutorial-overlay" @click.self="skipTutorial">
    <!-- 遮罩层 -->
    <div class="tutorial-mask"></div>
    
    <!-- 引导内容 -->
    <div 
      class="tutorial-content"
      :class="[`tutorial-${currentStep.position}`]"
      @click.stop
    >
      <div class="tutorial-header">
        <div class="tutorial-progress">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: progress + '%' }"></div>
          </div>
          <span class="progress-text">{{ currentStepIndex + 1 }} / {{ steps.length }}</span>
        </div>
        <button class="tutorial-close" @click="skipTutorial">✕</button>
      </div>
      
      <div class="tutorial-body">
        <h3 class="tutorial-title">{{ currentStep.title }}</h3>
        <p class="tutorial-text">{{ currentStep.content }}</p>
      </div>
      
      <div class="tutorial-footer">
        <button class="btn btn-secondary" @click="skipTutorial">跳过引导</button>
        <div class="tutorial-nav">
          <button 
            class="btn btn-secondary" 
            @click="prevStep"
            :disabled="currentStepIndex === 0"
          >
            上一步
          </button>
          <button 
            class="btn btn-primary" 
            @click="nextStep"
          >
            {{ currentStepIndex === steps.length - 1 ? '完成' : '下一步' }}
          </button>
        </div>
      </div>
    </div>
    
    <!-- 高亮区域指示器 -->
    <div 
      v-if="currentStep.highlight" 
      class="tutorial-highlight"
      :data-target="currentStep.highlight"
    ></div>
  </div>
</template>

<style scoped>
.tutorial-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 10000;
  pointer-events: auto;
}

.tutorial-mask {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(3px);
  z-index: 9999;
}

.tutorial-content {
  position: absolute;
  background: white;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
  min-width: 400px;
  max-width: 500px;
  z-index: 10001;
  pointer-events: auto;
}

.tutorial-center {
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.tutorial-left {
  top: 20%;
  left: 20px;
}

.tutorial-top {
  top: 80px;
  left: 50%;
  transform: translateX(-50%);
}

.tutorial-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-primary);
}

.tutorial-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.progress-bar {
  flex: 1;
  height: 6px;
  background: var(--bg-secondary);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--primary-color);
  transition: width 0.3s;
}

.progress-text {
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 50px;
  text-align: right;
}

.tutorial-close {
  background: none;
  border: none;
  font-size: 20px;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 4px 8px;
  line-height: 1;
}

.tutorial-close:hover {
  color: var(--text-primary);
}

.tutorial-body {
  padding: 24px 20px;
}

.tutorial-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 12px 0;
}

.tutorial-text {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
}

.tutorial-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-top: 1px solid var(--border-primary);
}

.tutorial-nav {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-secondary {
  background: #e5e7eb;
  color: #374151;
  border: 1px solid #d1d5db;
}

.btn-secondary:hover:not(:disabled) {
  background: #d1d5db;
}

.btn-primary {
  background: #3b82f6;
  color: white;
  border: 1px solid #3b82f6;
}

.btn-primary:hover {
  background: #2563eb;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tutorial-highlight {
  position: absolute;
  border: 3px solid var(--primary-color);
  border-radius: 8px;
  box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.5), 0 0 20px rgba(99, 102, 241, 0.5);
  pointer-events: none;
  z-index: 10000;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% {
    box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.5), 0 0 20px rgba(99, 102, 241, 0.5);
  }
  50% {
    box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.5), 0 0 30px rgba(99, 102, 241, 0.8);
  }
}
</style>

