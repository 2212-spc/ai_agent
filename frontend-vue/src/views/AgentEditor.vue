<script setup>
import { onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import CanvasPanel from '../components/Canvas/CanvasPanel.vue';
import { useCanvasStore } from '../stores/canvas';

const router = useRouter();
const canvasStore = useCanvasStore();

onMounted(() => {
  if (canvasStore.nodes.length === 0) {
    console.log('Canvas initialized');
  }

  // 添加 Escape 快捷键返回
  document.addEventListener('keydown', handleEscapeKey);
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleEscapeKey);
});

function handleBack() {
  router.push('/chat');
}

function handleEscapeKey(event) {
  if (event.key === 'Escape' && !event.target.matches('input, textarea')) {
    handleBack();
  }
}
</script>

<template>
  <div class="agent-editor">
    <!-- 返回按钮 -->
    <div class="editor-header">
      <button class="btn-back" @click="handleBack" title="返回到聊天页面 (Esc)">
        ← 返回
      </button>
      <h2 class="editor-title">Agent 构建器</h2>
      <div class="spacer"></div>
    </div>

    <!-- 画布面板 -->
    <div class="editor-content">
      <CanvasPanel />
    </div>
  </div>
</template>

<style scoped>
.agent-editor {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-secondary);
}

.editor-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-primary);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.btn-back {
  padding: 8px 14px;
  border-radius: 6px;
  border: none;
  background: linear-gradient(135deg, var(--primary-color), #5b4fdb);
  color: white;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.btn-back:hover {
  transform: translateX(-4px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.btn-back:active {
  transform: translateX(-2px);
}

.editor-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.spacer {
  flex: 1;
}

.editor-content {
  flex: 1;
  overflow: hidden;
}
</style>
