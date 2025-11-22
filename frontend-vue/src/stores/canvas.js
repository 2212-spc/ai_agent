import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export const useCanvasStore = defineStore('canvas', () => {
    // State
    const nodes = ref([]);
    const connections = ref([]);
    const scale = ref(1);
    const history = ref([]);
    const historyIndex = ref(-1);
    const selectedNode = ref(null);

    // Computed
    const canUndo = computed(() => historyIndex.value > 0);
    const canRedo = computed(() => historyIndex.value < history.value.length - 1);

    // Actions
    function addNode(node) {
        nodes.value.push({
            ...node,
            id: `node-${Date.now()}`,
            position: node.position || { x: 100, y: 100 }
        });
        saveState();
    }

    function removeNode(nodeId) {
        nodes.value = nodes.value.filter(n => n.id !== nodeId);
        connections.value = connections.value.filter(
            c => c.from !== nodeId && c.to !== nodeId
        );
        saveState();
    }

    function updateNode(nodeId, updates) {
        const node = nodes.value.find(n => n.id === nodeId);
        if (node) {
            Object.assign(node, updates);
        }
    }

    function addConnection(from, to) {
        const exists = connections.value.some(
            c => c.from === from && c.to === to
        );
        if (!exists) {
            connections.value.push({ from, to, id: `conn-${Date.now()}` });
            saveState();
        }
    }

    function removeConnection(connId) {
        connections.value = connections.value.filter(c => c.id !== connId);
        saveState();
    }

    function setScale(newScale) {
        scale.value = Math.max(0.1, Math.min(3, newScale));
    }

    function saveState() {
        const state = {
            nodes: JSON.parse(JSON.stringify(nodes.value)),
            connections: JSON.parse(JSON.stringify(connections.value))
        };

        // 删除当前索引之后的历史
        history.value = history.value.slice(0, historyIndex.value + 1);
        history.value.push(state);

        // 限制历史记录数量
        if (history.value.length > 50) {
            history.value.shift();
        } else {
            historyIndex.value++;
        }
    }

    function undo() {
        if (canUndo.value) {
            historyIndex.value--;
            restoreState();
        }
    }

    function redo() {
        if (canRedo.value) {
            historyIndex.value++;
            restoreState();
        }
    }

    function restoreState() {
        const state = history.value[historyIndex.value];
        if (state) {
            nodes.value = JSON.parse(JSON.stringify(state.nodes));
            connections.value = JSON.parse(JSON.stringify(state.connections));
        }
    }

    function clearCanvas() {
        nodes.value = [];
        connections.value = [];
        saveState();
    }

    function exportConfig() {
        return {
            nodes: nodes.value.map((node, index) => ({
                id: index,
                type: node.type,
                label: node.label,
                description: node.description || '',
                position: node.position
            })),
            connections: connections.value.map(conn => ({
                from: nodes.value.findIndex(n => n.id === conn.from),
                to: nodes.value.findIndex(n => n.id === conn.to)
            })),
            metadata: {
                created: new Date().toISOString(),
                version: '1.0'
            }
        };
    }

    function selectNode(nodeId) {
        selectedNode.value = nodeId;
    }

    function deselectNode() {
        selectedNode.value = null;
    }

    return {
        nodes,
        connections,
        scale,
        selectedNode,
        canUndo,
        canRedo,
        addNode,
        removeNode,
        updateNode,
        addConnection,
        removeConnection,
        setScale,
        saveState,
        undo,
        redo,
        clearCanvas,
        exportConfig,
        selectNode,
        deselectNode
    };
});
