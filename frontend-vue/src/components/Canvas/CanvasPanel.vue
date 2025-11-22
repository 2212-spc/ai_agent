<script setup>
import { ref } from 'vue';
import { useCanvasStore } from '../../stores/canvas';
import NodeCanvas from './NodeCanvas.vue';

const canvasStore = useCanvasStore();

const nodeTypes = [
    { type: 'router', label: '路由节点', icon: '🔀' },
    { type: 'executor', label: '执行节点', icon: '⚙️' },
    { type: 'tool', label: '工具节点', icon: '🔧' },
    { type: 'llm', label: 'LLM节点', icon: '🤖' },
    { type: 'knowledge', label: '知识库', icon: '📚' }
];

function addNodeToCanvas(type, label) {
    canvasStore.addNode({
        type,
        label,
        description: ''
    });
}

function handleUndo() {
    canvasStore.undo();
}

function handleRedo() {
    canvasStore.redo();
}

function handleClear() {
    if (confirm('确定要清空画布吗？')) {
        canvasStore.clearCanvas();
    }
}

function handleSave() {
    const config = canvasStore.exportConfig();
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `agent-config-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

function handleZoomIn() {
    canvasStore.setScale(canvasStore.scale + 0.1);
}

function handleZoomOut() {
    canvasStore.setScale(canvasStore.scale - 0.1);
}
</script>

<template>
    <div class="canvas-panel">
        <!-- Toolbar -->
        <div class="canvas-toolbar">
            <div class="toolbar-section">
                <button class="btn-icon" @click="handleUndo" :disabled="!canvasStore.canUndo" title="撤销">
                    ↶
                </button>
                <button class="btn-icon" @click="handleRedo" :disabled="!canvasStore.canRedo" title="重做">
                    ↷
                </button>
            </div>

            <div class="toolbar-section">
                <button class="btn-icon" @click="handleZoomOut" title="缩小">🔍-</button>
                <span class="zoom-level">{{ Math.round(canvasStore.scale * 100) }}%</span>
                <button class="btn-icon" @click="handleZoomIn" title="放大">🔍+</button>
            </div>

            <div class="toolbar-section">
                <button class="btn btn-secondary btn-small" @click="handleClear">清空</button>
                <button class="btn btn-primary btn-small" @click="handleSave">保存</button>
            </div>
        </div>

        <!-- Node Palette -->
        <div class="node-palette">
            <h4 class="palette-title">节点库</h4>
            <div class="usage-hint">
                💡 双击节点开始连线，点击目标节点完成连线
            </div>
            <div class="node-list">
                <div
                    v-for="node in nodeTypes"
                    :key="node.type"
                    class="node-item"
                    @click="addNodeToCanvas(node.type, node.label)"
                >
                    <span class="node-icon">{{ node.icon }}</span>
                    <span class="node-label">{{ node.label }}</span>
                </div>
            </div>
        </div>

        <!-- Canvas -->
        <div class="canvas-container">
            <NodeCanvas />
        </div>
    </div>
</template>

<style scoped>
.canvas-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--bg-secondary);
}

.canvas-toolbar {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 12px 16px;
    background: var(--bg-primary);
    border-bottom: 1px solid var(--border-primary);
}

.toolbar-section {
    display: flex;
    align-items: center;
    gap: 8px;
}

.zoom-level {
    font-size: 13px;
    color: var(--text-secondary);
    min-width: 50px;
    text-align: center;
}

.node-palette {
    padding: 16px;
    border-bottom: 1px solid var(--border-primary);
    background: var(--bg-primary);
}

.palette-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 8px;
}

.usage-hint {
    font-size: 11px;
    color: var(--text-tertiary);
    background: var(--bg-tertiary);
    padding: 6px 10px;
    border-radius: 4px;
    margin-bottom: 12px;
}

.node-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    gap: 8px;
}

.node-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    padding: 12px 8px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-secondary);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
}

.node-item:hover {
    border-color: var(--primary-color);
    background: var(--primary-light);
    transform: translateY(-2px);
}

.node-icon {
    font-size: 24px;
}

.node-label {
    font-size: 12px;
    color: var(--text-primary);
    text-align: center;
}

.canvas-container {
    flex: 1;
    overflow: hidden;
    position: relative;
}
</style>
