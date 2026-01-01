<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { useCanvasStore } from '../../stores/canvas';
import ContextMenu from './ContextMenu.vue';
import { getNodeType } from '../../config/nodeTypes';

const canvasStore = useCanvasStore();
const emit = defineEmits(['node-click', 'operation-hint']);
const canvasRef = ref(null);
const svgRef = ref(null);
const isDragging = ref(false);
const draggedNode = ref(null);
const dragOffset = ref({ x: 0, y: 0 });
const isConnecting = ref(false);
const connectingFrom = ref(null);
const connectingTo = ref(null); // 用于显示临时连接线
const isPanning = ref(false);
const panStart = ref({ x: 0, y: 0 });
const panOffset = ref({ x: 0, y: 0 });
const mousePos = ref({ x: 0, y: 0 }); // 鼠标位置，用于临时连接线
const contextMenu = ref({ show: false, x: 0, y: 0, nodeId: null }); // 右键菜单
const hoveredNode = ref(null); // 悬停的节点
const tooltipPosition = ref({ x: 0, y: 0 }); // 工具提示位置
let tooltipTimer = null; // 工具提示定时器

const nodes = computed(() => canvasStore.nodes);
const connections = computed(() => canvasStore.connections);
const scale = computed(() => canvasStore.scale);

// 拖拽节点
function startDrag(node, event) {
    // 检查是否点击了按钮或其他交互元素
    const target = event.target;
    if (target.closest('.node-config-btn') || 
        target.classList.contains('node-config-btn') ||
        target.closest('.port') ||
        target.classList.contains('port') ||
        target.classList.contains('port-dot')) {
        return; // 完全跳过拖拽逻辑
    }
    
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
    // 修复：考虑平移偏移量
    const x = (event.clientX - canvasRect.left - panOffset.value.x - dragOffset.value.x) / scale.value;
    const y = (event.clientY - canvasRect.top - panOffset.value.y - dragOffset.value.y) / scale.value;
    
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

// 绘制连线（考虑缩放和平移）
function getConnectionPath(from, to) {
    const fromNode = nodes.value.find(n => n.id === from);
    const toNode = nodes.value.find(n => n.id === to);
    
    if (!fromNode || !toNode) return '';
    
    // 应用缩放和平移
    const s = scale.value;
    const px = panOffset.value.x;
    const py = panOffset.value.y;
    
    const fromX = (fromNode.position.x + 75) * s + px;
    const fromY = (fromNode.position.y + 40) * s + py;
    const toX = (toNode.position.x + 75) * s + px;
    const toY = (toNode.position.y + 40) * s + py;
    
    const midX = (fromX + toX) / 2;
    
    return `M ${fromX} ${fromY} C ${midX} ${fromY}, ${midX} ${toY}, ${toX} ${toY}`;
}

// 获取临时连接线路径（从节点到鼠标位置）
function getTempConnectionPath() {
    if (!connectingFrom.value) return '';
    
    const fromNode = nodes.value.find(n => n.id === connectingFrom.value);
    if (!fromNode) return '';
    
    const s = scale.value;
    const px = panOffset.value.x;
    const py = panOffset.value.y;
    
    const fromX = (fromNode.position.x + 75) * s + px;
    const fromY = (fromNode.position.y + 40) * s + py;
    const toX = mousePos.value.x;
    const toY = mousePos.value.y;
    
    const midX = (fromX + toX) / 2;
    
    return `M ${fromX} ${fromY} C ${midX} ${fromY}, ${midX} ${toY}, ${toX} ${toY}`;
}

// 连接线交互
const highlightedConnection = ref(null);

function highlightConnection(connId) {
    highlightedConnection.value = connId;
}

function handleConnectionClick(conn) {
    if (confirm('确定要删除这条连接吗？')) {
        canvasStore.removeConnection(conn.id);
    }
}

// 右键菜单
function showContextMenu(node, event) {
    contextMenu.value = {
        show: true,
        x: event.clientX,
        y: event.clientY,
        nodeId: node.id
    };
    canvasStore.selectNode(node.id);
}

function closeContextMenu() {
    contextMenu.value.show = false;
}

function handleDeleteNode() {
    if (contextMenu.value.nodeId) {
        canvasStore.removeNode(contextMenu.value.nodeId);
        closeContextMenu();
    }
}

function handleConfigureNode() {
    if (contextMenu.value.nodeId) {
        const node = canvasStore.nodes.find(n => n.id === contextMenu.value.nodeId);
        if (node) {
            emit('node-click', node);
        }
        closeContextMenu();
    }
}

// 键盘删除
function handleKeyDown(event) {
    // 防止在输入框中触发
    if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
        return;
    }
    
    // Delete 或 Backspace 删除选中节点
    if ((event.key === 'Delete' || event.key === 'Backspace') && canvasStore.selectedNode) {
        event.preventDefault();
        if (confirm('确定要删除选中的节点吗？')) {
            canvasStore.removeNode(canvasStore.selectedNode);
        }
    }
    
    // Escape 取消连接或关闭菜单
    if (event.key === 'Escape') {
        cancelConnection();
        closeContextMenu();
        canvasStore.deselectNode();
    }
}

// 节点悬停工具提示
function handleNodeHover(node, event) {
    // 检查是否悬停在配置按钮或端口上，如果是则不显示tooltip
    const target = event.target;
    if (target.closest('.node-config-btn') ||
        target.classList.contains('node-config-btn') ||
        target.closest('.port') ||
        target.classList.contains('port')) {
        hideTooltip();
        return;
    }

    if (tooltipTimer) clearTimeout(tooltipTimer);

    tooltipTimer = setTimeout(() => {
        hoveredNode.value = node;
        const rect = event.currentTarget.getBoundingClientRect();
        const canvasRect = canvasRef.value.getBoundingClientRect();

        // 计算工具提示位置（显示在节点右侧）
        tooltipPosition.value = {
            x: rect.right - canvasRect.left + 10,
            y: rect.top - canvasRect.top
        };
    }, 500); // 延迟显示
}

function hideTooltip() {
    if (tooltipTimer) clearTimeout(tooltipTimer);
    hoveredNode.value = null;
}

function selectNode(node, event) {
    // 如果正在连线模式
    if (isConnecting.value && connectingFrom.value) {
        if (connectingFrom.value !== node.id) {
            // 验证连接：防止自连接、重复连接、循环连接
            const canConnect = validateConnection(connectingFrom.value, node.id);
            if (canConnect.valid) {
                // 完成连线
                canvasStore.addConnection(connectingFrom.value, node.id);
                showConnectionHint('连接成功！', 'success');
            } else {
                showConnectionHint(canConnect.message, 'error');
            }
        }
        // 退出连线模式
        isConnecting.value = false;
        connectingFrom.value = null;
        event.stopPropagation();
        return;
    }
    
    canvasStore.selectNode(node.id);
}

// 验证连接
function validateConnection(from, to) {
    // 防止自连接
    if (from === to) {
        return { valid: false, message: '不能连接节点到自身' };
    }
    
    // 检查是否已存在连接
    const exists = canvasStore.connections.some(
        c => c.from === from && c.to === to
    );
    if (exists) {
        return { valid: false, message: '连接已存在' };
    }
    
    // 检查循环连接（简单检查：如果to节点已经有路径回到from节点）
    const hasPath = checkPath(to, from, new Set());
    if (hasPath) {
        return { valid: false, message: '不能创建循环连接' };
    }
    
    return { valid: true };
}

// 检查路径是否存在（用于检测循环）
function checkPath(from, to, visited) {
    if (from === to) return true;
    if (visited.has(from)) return false;
    
    visited.add(from);
    const outgoing = canvasStore.connections.filter(c => c.from === from);
    for (const conn of outgoing) {
        if (checkPath(conn.to, to, visited)) {
            return true;
        }
    }
    return false;
}

// 显示连接提示
const connectionHint = ref(null);
const connectionHintType = ref('info');

function showConnectionHint(message, type = 'info') {
    connectionHint.value = message;
    connectionHintType.value = type;
    setTimeout(() => {
        connectionHint.value = null;
    }, 2000);
}

function openNodeConfig(node, event) {
    event.stopPropagation();
    // 发送事件给父组件 (CanvasPanel)
    emit('node-click', node);
}

function startConnection(node, event) {
    event.stopPropagation();
    isConnecting.value = true;
    connectingFrom.value = node.id;
    connectingTo.value = null;
    canvasStore.selectNode(node.id);
    showConnectionHint('点击目标节点完成连接', 'info');
    // 发送事件给父组件显示提示
    emit('operation-hint', `💡 已选择节点"${node.label}"，点击目标节点完成连接`);
}

// 监听节点变化，重新绘制连线
watch([nodes, connections], () => {
    nextTick(() => {
        // 连线会自动重绘
    });
}, { deep: true });

// 监听节点数组变化，确保事件正确绑定
watch(() => nodes.value.length, () => {
    nextTick(() => {
        // 强制重新渲染，确保事件监听器正确绑定
        console.log('节点数量变化:', nodes.value.length);
    });
});

function cancelConnection() {
    if (isConnecting.value) {
        isConnecting.value = false;
        connectingFrom.value = null;
        connectingTo.value = null;
    }
}

// 更新鼠标位置（用于临时连接线）
function updateMousePos(event) {
    if (isConnecting.value && connectingFrom.value) {
        const canvasRect = canvasRef.value.getBoundingClientRect();
        mousePos.value = {
            x: event.clientX - canvasRect.left,
            y: event.clientY - canvasRect.top
        };
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
    document.addEventListener('mousemove', updateMousePos);
    document.addEventListener('keydown', handleKeyDown);
    
    if (canvasRef.value) {
        canvasRef.value.addEventListener('wheel', onWheel, { passive: false });
    }
});

onUnmounted(() => {
    document.removeEventListener('mousemove', onDrag);
    document.removeEventListener('mouseup', endDrag);
    document.removeEventListener('mousemove', onPan);
    document.removeEventListener('mouseup', endPan);
    document.removeEventListener('mousemove', updateMousePos);
    document.removeEventListener('keydown', handleKeyDown);
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
                :class="['connection', { 'highlighted': highlightedConnection === conn.id }]"
                marker-end="url(#arrowhead)"
                @click.stop="handleConnectionClick(conn)"
                @mouseenter="highlightConnection(conn.id)"
                @mouseleave="highlightConnection(null)"
            />
            <!-- 临时连接线（正在连接时显示） -->
            <path
                v-if="isConnecting && connectingFrom"
                :d="getTempConnectionPath()"
                class="connection temp-connection"
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
                @contextmenu.prevent="showContextMenu(node, $event)"
                @mouseenter="handleNodeHover(node, $event)"
                @mouseleave="hideTooltip"
            >
                <!-- 输入端口 -->
                <div v-if="getNodeType(node.type)?.inputs?.length > 0" class="node-ports input-ports">
                    <div 
                        v-for="input in getNodeType(node.type).inputs" 
                        :key="input"
                        class="port input-port"
                        :title="`输入: ${input}`"
                    >
                        <div class="port-dot"></div>
                    </div>
                </div>
                
                <div class="node-header">
                    <span class="node-type">{{ node.type }}</span>
                    <button
                        class="node-config-btn"
                        @click.stop="openNodeConfig(node, $event)"
                        @mousedown.stop
                        @mouseup.stop
                        @dblclick.stop
                        title="配置节点"
                    >
                        ⚙️
                    </button>
                </div>
                <div class="node-body">
                    <div class="node-label">{{ node.label }}</div>
                    <div class="node-description" v-if="node.description">
                        {{ node.description }}
                    </div>
                </div>
                
                <!-- 输出端口 -->
                <div v-if="getNodeType(node.type)?.outputs?.length > 0" class="node-ports output-ports">
                    <div 
                        v-for="output in getNodeType(node.type).outputs" 
                        :key="output"
                        class="port output-port"
                        :title="`输出: ${output}`"
                    >
                        <div class="port-dot"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Empty State -->
        <div v-if="nodes.length === 0" class="canvas-empty">
            <div class="empty-icon">🎨</div>
            <div class="empty-text">点击上方节点库添加节点开始构建</div>
        </div>
        
        <!-- 连接提示 -->
        <div v-if="connectionHint" :class="['connection-hint', `hint-${connectionHintType}`]">
            {{ connectionHint }}
        </div>
        
        <!-- 节点悬停工具提示 -->
        <div 
            v-if="hoveredNode" 
            class="node-tooltip"
            :style="{ 
                left: tooltipPosition.x + 'px', 
                top: tooltipPosition.y + 'px' 
            }"
        >
            <div class="tooltip-header">
                <span class="tooltip-icon">{{ getNodeType(hoveredNode.type)?.icon }}</span>
                <span class="tooltip-title">{{ hoveredNode.label }}</span>
            </div>
            <div class="tooltip-body">
                <p class="tooltip-description">{{ getNodeType(hoveredNode.type)?.description }}</p>
                <div class="tooltip-io">
                    <div class="tooltip-section" v-if="getNodeType(hoveredNode.type)?.inputs?.length">
                        <strong>输入:</strong>
                        <ul>
                            <li v-for="input in getNodeType(hoveredNode.type)?.inputs" :key="input">
                                {{ input }}
                            </li>
                        </ul>
                    </div>
                    <div class="tooltip-section" v-if="getNodeType(hoveredNode.type)?.outputs?.length">
                        <strong>输出:</strong>
                        <ul>
                            <li v-for="output in getNodeType(hoveredNode.type)?.outputs" :key="output">
                                {{ output }}
                            </li>
                        </ul>
                    </div>
                </div>
                <div class="tooltip-hint">
                    💡 双击节点开始连接
                </div>
            </div>
        </div>
        
        <!-- 右键菜单 -->
        <ContextMenu
            :show="contextMenu.show"
            :x="contextMenu.x"
            :y="contextMenu.y"
            @close="closeContextMenu"
            @delete="handleDeleteNode"
            @configure="handleConfigureNode"
        />
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

.connection {
    cursor: pointer;
}

.connection:hover {
    opacity: 1;
    stroke-width: 3;
}

.connection.highlighted {
    stroke: #10a37f;
    stroke-width: 3;
    opacity: 1;
}

.temp-connection {
    stroke: #10a37f;
    stroke-width: 2;
    stroke-dasharray: 5,5;
    opacity: 0.8;
    pointer-events: none;
}

.connection-hint {
    position: absolute;
    top: 20px;
    left: 50%;
    transform: translateX(-50%);
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    z-index: 1000;
    pointer-events: none;
    animation: fadeInOut 2s;
}

.hint-success {
    background: #10b981;
    color: white;
}

.hint-error {
    background: #ef4444;
    color: white;
}

.hint-info {
    background: #3b82f6;
    color: white;
}

@keyframes fadeInOut {
    0%, 100% { opacity: 0; transform: translateX(-50%) translateY(-10px); }
    10%, 90% { opacity: 1; transform: translateX(-50%) translateY(0); }
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
    background: var(--bg-secondary);
    border: 1px solid var(--border-secondary);
    border-radius: 4px;
    font-size: 14px;
    cursor: pointer;
    padding: 4px 6px;
    opacity: 0.8;
    transition: all 0.2s;
    position: relative;
    z-index: 10;
    pointer-events: auto;
}

.node-config-btn:hover {
    opacity: 1;
    background: var(--primary-color);
    border-color: var(--primary-color);
    transform: scale(1.1);
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
