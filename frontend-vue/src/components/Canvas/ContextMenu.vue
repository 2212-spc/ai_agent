<script setup>
import { ref, onMounted, onUnmounted } from 'vue';

const props = defineProps({
  show: { type: Boolean, default: false },
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 }
});

const emit = defineEmits(['close', 'delete', 'configure']);

function handleDelete() {
  emit('delete');
  emit('close');
}

function handleConfigure() {
  emit('configure');
  emit('close');
}

function handleClickOutside(event) {
  if (props.show && !event.target.closest('.context-menu')) {
    emit('close');
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
});
</script>

<template>
  <div
    v-if="show"
    class="context-menu"
    :style="{ left: x + 'px', top: y + 'px' }"
    @click.stop
  >
    <div class="menu-item" @click="handleConfigure">
      <span class="menu-icon">⚙️</span>
      <span>配置节点</span>
    </div>
    <div class="menu-item danger" @click="handleDelete">
      <span class="menu-icon">🗑️</span>
      <span>删除节点</span>
    </div>
  </div>
</template>

<style scoped>
.context-menu {
  position: fixed;
  background: var(--bg-primary);
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 2000;
  min-width: 160px;
  padding: 4px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-primary);
  border-radius: 4px;
  transition: background 0.2s;
}

.menu-item:hover {
  background: var(--bg-secondary);
}

.menu-item.danger {
  color: #ef4444;
}

.menu-item.danger:hover {
  background: #fee2e2;
}

.menu-icon {
  font-size: 14px;
}
</style>



