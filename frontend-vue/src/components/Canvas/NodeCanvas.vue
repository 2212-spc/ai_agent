<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import { useCanvasStore } from '../../stores/canvas';

const canvasStore = useCanvasStore();
const canvasRef = ref(null);
const svgRef = ref(null);
const isDragging = ref(false);
const draggedNode = ref(null);
const dragOffset = ref({ x: 0, y: 0 });

const nodes = computed(() => canvasStore.nodes);
const connections = computed(() => canvasStore.connections);
const scale = computed(() => canvasStore.scale);

// 拖拽节点
function startDrag(node, event) {
    isDragging.value = true;
    draggedNode.value = node;
    
    const nodeEl = event.currentTarget;
    const rect = nodeEl.getBoundingClientRect();
    
    dragOffset.value = {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top
    };
    
    canvasStore.selectNode(node.id);
    event.preventDefault();
}

function onDrag(event) {
    if (!isDragging.value || !draggedNode.value) return;
    
    const canvasRect = canvasRef.value.getBoundingClientRect();
    const x = (event.clientX - canvasRect.left - dragOffset.value.x) / scale.value;
    const y = (event.clientY - canvasRect.top - dragOffset.value.y) / scale.value;
    
    canvasStore.updateNode(draggedNode.value.id, {
        position: { x, y }
    });
}

function endDrag() {
    if (isDragging.value) {
        isDragging.value = false;
        draggedNode.value = null;
        canvasStore.saveState();
    }
}

// 绘制连线
function getConnectionPath(from, to) {
    const fromNode = nodes.value.find(n => n.id === from);
    const toNode = nodes.value.find(n => n.id === to);
    
    if (!fromNode || !toNode) return '';
    
    const fromX = fromNode.position.x + 75; // 节点宽度一半
    const fromY = fromNode.position.y + 40; // 节点高度一半
    const toX = toNode.position.x + 75;
    const toY = toNode.position.y + 40;
    
    const midX = (fromX + toX) / 2;
    
    return `M ${fromX} ${fromY} C ${midX} ${fromY}, ${midX} ${toY}, ${toX} ${toY}`;
}

function selectNode(node) {
    canvasStore.selectNode(node.id);
}

// 监听节点变化，重新绘制连线
watch([nodes, connections], () => {
    nextTick(() => {
        // 连线会自动重绘
    });
}, { deep: true });

onMounted(() => {
    document.addEventListener('mousemove', onDrag);
    document.addEventListener('mouseup', endDrag);
});
</script>

<template>
    <div class="node-canvas" ref="canvasRef">
        <!-- SVG Layer for Connections -->
        <svg class="connections-layer" ref="svgRef">
            <defs>
                <marker
                    id="arrowhead"
                    markerWidth="10"
                    markerHeight="10"
                    refX="9"
                    refY="3"
                    orient="auto"
                >
                    <polygon points="0 0, 10 3, 0 6" fill="#6366f1" />
                </marker>
            </defs>
            
            <path
                v-for="conn in connections"
                :key="conn.id"
                :d="getConnectionPath(conn.from, conn.to)"
                class="connection"
                marker-end="url(#arrowhead)"
            />
        </svg>

        <!-- Nodes Layer -->
        <div
            class="canvas-content"
            :style="{ transform: `scale(${scale})` }"
        >
            <div
                v-for="node in nodes"
                :key="node.id"
                class="canvas-node"
                :class="{ 'selected': canvasStore.selectedNode === node.id }"
                :style="{
                    left: node.position.x + 'px',
                    top: node.position.y + 'px'
                }"
                @mousedown="startDrag(node, $event)"
                @click="selectNode(node)"
            >
                <div class="node-header">
                    <span class="node-type">{{ node.type }}</span>
                </div>
                <div class="node-body">
                    <div class="node-label">{{ node.label }}</div>
                    <div class="node-description" v-if="node.description">
                        {{ node.description }}
                    </div>
                </div>
            </div>
        </div>

        <!-- Empty State -->
        <div v-if="nodes.length === 0" class="canvas-empty">
            <div class="empty-icon">🎨</div>
            <div class="empty-text">点击上方节点库添加节点开始构建</div>
        </div>
    </div>
</template>

<style scoped>
.node-canvas {
    width: 100%;
    height: 100%;
    position: relative;
    background: var(--bg-secondary);
    overflow: hidden;
}

.connections-layer {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 1;
}

.connection {
    fill: none;
    stroke: #6366f1;
    stroke-width: 2;
    opacity: 0.6;
    transition: opacity 0.2s;
}

.connection:hover {
    opacity: 1;
    stroke-width: 3;
}

.canvas-content {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    transform-origin: 0 0;
    transition: transform 0.2s ease;
}

.canvas-node {
    position: absolute;
    width: 150px;
    background: var(--bg-primary);
    border: 2px solid var(--border-primary);
    border-radius: 8px;
    cursor: move;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    transition: box-shadow 0.2s, border-color 0.2s;
    user-select: none;
    z-index: 10;
}

.canvas-node:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    border-color: var(--primary-color);
}

.canvas-node.selected {
    border-color: var(--primary-color);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
}

.node-header {
    padding: 8px 12px;
    background: var(--primary-light);
    border-bottom: 1px solid var(--border-primary);
    border-radius: 6px 6px 0 0;
}

.node-type {
    font-size: 11px;
    font-weight: 600;
    color: var(--primary-color);
    text-transform: uppercase;
}

.node-body {
    padding: 12px;
}

.node-label {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.node-description {
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.4;
}

.canvas-empty {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    text-align: center;
    color: var(--text-tertiary);
}

.empty-icon {
    font-size: 48px;
    margin-bottom: 12px;
}

.empty-text {
    font-size: 14px;
}
</style>
