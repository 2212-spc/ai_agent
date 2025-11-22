<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import { useCanvasStore } from '../../stores/canvas';

const canvasStore = useCanvasStore();
const canvasRef = ref(null);
const svgRef = ref(null);
const isDragging = ref(false);
const draggedNode = ref(null);
const dragOffset = ref({ x: 0, y: 0 });
const isConnecting = ref(false);
const connectingFrom = ref(null);
const showNodeConfig = ref(false);
const configNode = ref(null);
const isPanning = ref(false);
const panStart = ref({ x: 0, y: 0 });
const panOffset = ref({ x: 0, y: 0 });

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

function selectNode(node, event) {
    // 如果正在连线模式
    if (isConnecting.value && connectingFrom.value) {
        if (connectingFrom.value !== node.id) {
            // 完成连线
            canvasStore.addConnection(connectingFrom.value, node.id);
        }
        // 退出连线模式
        isConnecting.value = false;
        connectingFrom.value = null;
        event.stopPropagation();
        return;
    }
    
    canvasStore.selectNode(node.id);
}

function openNodeConfig(node, event) {
    event.stopPropagation();
    configNode.value = { ...node };
    showNodeConfig.value = true;
}

function saveNodeConfig() {
    if (configNode.value) {
        canvasStore.updateNode(configNode.value.id, {
            label: configNode.value.label,
            description: configNode.value.description
        });
    }
    closeNodeConfig();
}

function closeNodeConfig() {
    showNodeConfig.value = false;
    configNode.value = null;
}

function startConnection(node, event) {
    event.stopPropagation();
    isConnecting.value = true;
    connectingFrom.value = node.id;
    canvasStore.selectNode(node.id);
}

// 监听节点变化，重新绘制连线
watch([nodes, connections], () => {
    nextTick(() => {
        // 连线会自动重绘
    });
}, { deep: true });

function cancelConnection() {
    if (isConnecting.value) {
        isConnecting.value = false;
        connectingFrom.value = null;
    }
}

// 画布平移
function startPan(event) {
    // 只有中键或空白区域+左键才能平移
    if (event.button === 1 || (event.button === 0 && event.target === canvasRef.value)) {
        isPanning.value = true;
        panStart.value = { x: event.clientX, y: event.clientY };
        event.preventDefault();
    }
}

function onPan(event) {
    if (isPanning.value) {
        const dx = event.clientX - panStart.value.x;
        const dy = event.clientY - panStart.value.y;
        panOffset.value = { x: dx, y: dy };
    }
}

function endPan() {
    if (isPanning.value) {
        isPanning.value = false;
    }
}

// 鼠标滚轮缩放
function onWheel(event) {
    event.preventDefault();
    const delta = event.deltaY > 0 ? -0.1 : 0.1;
    const newScale = Math.max(0.1, Math.min(2, scale.value + delta));
    canvasStore.setScale(newScale);
}

onMounted(() => {
    document.addEventListener('mousemove', onDrag);
    document.addEventListener('mouseup', endDrag);
    document.addEventListener('mousemove', onPan);
    document.addEventListener('mouseup', endPan);
    
    if (canvasRef.value) {
        canvasRef.value.addEventListener('wheel', onWheel, { passive: false });
    }
});
</script>

<template>
    <div 
        class="node-canvas" 
        ref="canvasRef" 
        @click="cancelConnection"
        @mousedown="startPan"
        :style="{ cursor: isPanning ? 'grabbing' : 'default' }"
    >
        <!-- SVG Layer for Connections -->
        <svg 
            class="connections-layer" 
            ref="svgRef"
            :style="{ transform: `translate(${panOffset.x}px, ${panOffset.y}px)` }"
        >
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
            :style="{ 
                transform: `translate(${panOffset.x}px, ${panOffset.y}px) scale(${scale})` 
            }"
        >
            <div
                v-for="node in nodes"
                :key="node.id"
                class="canvas-node"
                :class="{ 
                    'selected': canvasStore.selectedNode === node.id,
                    'connecting': isConnecting && connectingFrom === node.id
                }"
                :style="{
                    left: node.position.x + 'px',
                    top: node.position.y + 'px'
                }"
                @mousedown="startDrag(node, $event)"
                @click="selectNode(node, $event)"
                @dblclick="startConnection(node, $event)"
            >
                <div class="node-header">
                    <span class="node-type">{{ node.type }}</span>
                    <button class="node-config-btn" @click="openNodeConfig(node, $event)" title="配置">
                        ⚙️
                    </button>
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
        
        <!-- Node Config Modal -->
        <div v-if="showNodeConfig" class="modal-overlay" @click="closeNodeConfig">
            <div class="modal-content" @click.stop>
                <div class="modal-header">
                    <h3>节点配置</h3>
                    <button class="modal-close" @click="closeNodeConfig">×</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label>节点类型</label>
                        <input type="text" v-model="configNode.type" disabled />
                    </div>
                    <div class="form-group">
                        <label>节点标签</label>
                        <input type="text" v-model="configNode.label" />
                    </div>
                    <div class="form-group">
                        <label>描述</label>
                        <textarea v-model="configNode.description" rows="3"></textarea>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" @click="closeNodeConfig">取消</button>
                    <button class="btn btn-primary" @click="saveNodeConfig">保存</button>
                </div>
            </div>
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

.canvas-node.connecting {
    border-color: #10a37f;
    box-shadow: 0 0 0 3px rgba(16, 163, 127, 0.3);
    animation: pulse 1s infinite;
}

@keyframes pulse {
    0%, 100% {
        box-shadow: 0 0 0 3px rgba(16, 163, 127, 0.3);
    }
    50% {
        box-shadow: 0 0 0 6px rgba(16, 163, 127, 0.5);
    }
}

.node-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    background: var(--bg-tertiary);
    border-bottom: 1px solid var(--border-primary);
    border-radius: 6px 6px 0 0;
}

.node-config-btn {
    background: none;
    border: none;
    font-size: 14px;
    cursor: pointer;
    padding: 2px 4px;
    opacity: 0.6;
    transition: opacity 0.2s;
}

.node-config-btn:hover {
    opacity: 1;
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

/* Modal Styles */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.modal-content {
    background: var(--bg-primary);
    border-radius: 12px;
    width: 90%;
    max-width: 500px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
}

.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    border-bottom: 1px solid var(--border-primary);
}

.modal-header h3 {
    margin: 0;
    font-size: 18px;
}

.modal-close {
    background: none;
    border: none;
    font-size: 24px;
    color: var(--text-tertiary);
    cursor: pointer;
    padding: 0;
    width: 28px;
    height: 28px;
}

.modal-close:hover {
    color: var(--text-primary);
}

.modal-body {
    padding: 20px;
}

.form-group {
    margin-bottom: 16px;
}

.form-group label {
    display: block;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 6px;
}

.form-group input,
.form-group textarea {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid var(--border-secondary);
    border-radius: 6px;
    background: var(--bg-secondary);
    color: var(--text-primary);
    font-size: 14px;
    font-family: inherit;
}

.form-group input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.form-group input:focus,
.form-group textarea:focus {
    outline: none;
    border-color: var(--primary-color);
}

.modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    padding: 16px 20px;
    border-top: 1px solid var(--border-primary);
}
</style>
