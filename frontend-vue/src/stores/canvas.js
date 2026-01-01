import { defineStore } from 'pinia';
import { ref, computed, nextTick } from 'vue';
import { AVAILABLE_NODES, validateNodeConfig as validateNodeConfigUtil } from '../config/nodeTypes';

export const useCanvasStore = defineStore('canvas', () => {
    // State
    const nodes = ref([]);
    const connections = ref([]);
    const scale = ref(1);
    const history = ref([]);
    const historyIndex = ref(-1);
    const selectedNode = ref(null);
    const validationErrors = ref([]);

    // Computed
    const canUndo = computed(() => historyIndex.value > 0);
    const canRedo = computed(() => historyIndex.value < history.value.length - 1);
    const hasErrors = computed(() => validationErrors.value.length > 0);

    // Actions
    function addNode(node) {
        // [优化] 为新节点初始化完整的data字段
        const nodeType = AVAILABLE_NODES[node.type];
        const defaultData = nodeType?.configFields ? {} : {};

        // 填充默认值
        if (nodeType?.configFields) {
            nodeType.configFields.forEach(field => {
                if (field.default !== undefined) {
                    defaultData[field.name] = field.default;
                }
            });
        }

        nodes.value.push({
            ...node,
            id: `node-${Date.now()}`,
            position: node.position || { x: 100, y: 100 },
            data: node.data || defaultData, // [新增] 完整配置数据
            inputs: node.inputs || [],
            outputs: node.outputs || []
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
            // 更新后自动验证
            validateNode(nodeId);
            saveState();
        }
    }

    // [新增] 单个节点验证
    function validateNode(nodeId) {
        const node = nodes.value.find(n => n.id === nodeId);
        if (!node) return [];

        const errors = validateNodeConfigUtil(node.type, node.data || {});
        return errors;
    }

    // [新增] 全量验证 - 改进版
    function validateConfig() {
        const errors = [];
        const warnings = [];

        // 1. 基本检查：至少有一个节点
        if (nodes.value.length === 0) {
            errors.push('❌ 画布为空，请至少添加一个节点');
            validationErrors.value = errors;
            return errors;
        }

        // 2. 验证每个节点的配置
        nodes.value.forEach((node, idx) => {
            const nodeErrors = validateNode(node.id);
            if (nodeErrors.length > 0) {
                errors.push(`❌ 节点"${node.label || node.type}"配置不完整：${nodeErrors.join('; ')}`);
            }
        });

        // 3. 验证连接的有效性
        connections.value.forEach((conn, idx) => {
            const fromNode = nodes.value.find(n => n.id === conn.from);
            const toNode = nodes.value.find(n => n.id === conn.to);

            if (!fromNode) {
                errors.push(`❌ 连接 #${idx + 1}: 起点节点不存在，请删除无效连接`);
            }
            if (!toNode) {
                errors.push(`❌ 连接 #${idx + 1}: 终点节点不存在，请删除无效连接`);
            }
        });

        // 4. 检查图形连通性
        if (nodes.value.length > 0) {
            // 检查是否有起始节点
            const startNodes = nodes.value.filter(n => AVAILABLE_NODES[n.type]?.isStartNode);
            if (startNodes.length === 0) {
                errors.push('❌ 缺少起始节点：请添加至少一个起始节点（如：规划器）');
            } else if (startNodes.length > 1) {
                warnings.push('⚠️ 检测到多个起始节点，请确保工作流逻辑正确');
            }

            // 检查是否有结束节点
            const endNodes = nodes.value.filter(n => AVAILABLE_NODES[n.type]?.isEndNode);
            if (endNodes.length === 0) {
                errors.push('❌ 缺少结束节点：请添加至少一个结束节点（如：合成器）');
            }

            // 检查节点是否孤立（没有连接）
            const connectedNodes = new Set();
            connections.value.forEach(conn => {
                connectedNodes.add(conn.from);
                connectedNodes.add(conn.to);
            });
            
            const isolatedNodes = nodes.value.filter(n => !connectedNodes.has(n.id));
            if (isolatedNodes.length > 0 && connections.value.length > 0) {
                warnings.push(`⚠️ 发现 ${isolatedNodes.length} 个孤立节点，请检查是否需要连接`);
            }

            // 检查是否有连接
            if (connections.value.length === 0 && nodes.value.length > 1) {
                warnings.push('⚠️ 节点之间没有连接，请双击节点建立连接');
            }
        }

        // 5. 检查是否有循环依赖（简单检查）
        if (connections.value.length > 0) {
            const visited = new Set();
            const recStack = new Set();
            
            function hasCycle(nodeId) {
                if (recStack.has(nodeId)) return true;
                if (visited.has(nodeId)) return false;
                
                visited.add(nodeId);
                recStack.add(nodeId);
                
                const outgoing = connections.value.filter(c => c.from === nodeId);
                for (const conn of outgoing) {
                    if (hasCycle(conn.to)) return true;
                }
                
                recStack.delete(nodeId);
                return false;
            }
            
            for (const node of nodes.value) {
                if (!visited.has(node.id) && hasCycle(node.id)) {
                    warnings.push('⚠️ 检测到可能的循环连接，请检查工作流逻辑');
                    break;
                }
            }
        }

        // 合并错误和警告
        const allMessages = [...errors, ...warnings];
        validationErrors.value = allMessages;
        return errors; // 只返回错误，警告不影响保存/执行
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

    // [优化] 导出完整配置，匹配后端期望格式
    function exportConfig() {
        if (nodes.value.length === 0) {
            throw new Error('画布为空，无法导出配置');
        }
        
        // 创建节点ID映射：内部ID -> 导出索引（字符串）
        const nodeIdToIndex = new Map();
        nodes.value.forEach((node, index) => {
            nodeIdToIndex.set(node.id, index);
        });
        
        // 导出节点：ID必须是字符串（LangGraph要求）
        const exportedNodes = nodes.value.map((node, index) => {
            const nodeId = String(index); // 确保是字符串
            
            return {
                id: nodeId,
                type: node.type,
                label: node.label || '',
                description: node.description || '',
                position: node.position || { x: 0, y: 0 },
                data: node.data || {},
                inputs: node.inputs || [],
                outputs: node.outputs || []
            };
        });
        
        // 导出边：字段名必须是 source 和 target（后端期望），ID必须是字符串
        const exportedEdges = connections.value.map((conn, idx) => {
            const fromIndex = nodeIdToIndex.get(conn.from);
            const toIndex = nodeIdToIndex.get(conn.to);
            
            if (fromIndex === undefined || toIndex === undefined) {
                console.warn(`无效连接 ${idx}:`, conn, 'fromIndex:', fromIndex, 'toIndex:', toIndex);
                return null;
            }
            
            return {
                source: String(fromIndex), // 确保是字符串
                target: String(toIndex),   // 确保是字符串
                id: conn.id || `edge-${fromIndex}-${toIndex}`
            };
        }).filter(edge => edge !== null);
        
        const config = {
            nodes: exportedNodes,
            edges: exportedEdges, // 使用 edges 而不是 connections
            metadata: {
                created: new Date().toISOString(),
                version: '2.0',
                nodeCount: exportedNodes.length,
                edgeCount: exportedEdges.length
            }
        };
        
        // 验证配置
        console.log('导出配置验证:');
        console.log('- 节点数:', config.nodes.length);
        console.log('- 边数:', config.edges.length);
        console.log('- 节点ID类型:', config.nodes.map(n => typeof n.id));
        console.log('- 边source/target类型:', config.edges.map(e => ({ source: typeof e.source, target: typeof e.target })));
        
        return config;
    }

    // [新增] 导入配置 - 支持 edges 和 connections 两种格式
    function importConfig(config) {
        if (!config || !config.nodes || config.nodes.length === 0) {
            throw new Error('无效的配置文件：缺少节点');
        }

        // 先清空画布
        nodes.value = [];
        connections.value = [];
        selectedNode.value = null;

        // 导入节点
        const nodeIdMap = new Map();
        const baseTime = Date.now();

        config.nodes.forEach((nodeConfig, idx) => {
            const nodeType = AVAILABLE_NODES[nodeConfig.type];

            if (!nodeType) {
                console.error(`未知的节点类型: ${nodeConfig.type}`);
                throw new Error(`未知的节点类型: ${nodeConfig.type}`);
            }

            const defaultData = {};
            if (nodeType.configFields) {
                nodeType.configFields.forEach(field => {
                    if (field.default !== undefined) {
                        defaultData[field.name] = field.default;
                    }
                });
            }

            const mergedData = { ...defaultData, ...(nodeConfig.data || {}) };
            const newInternalId = `node-${baseTime}-${idx}`;

            const newNode = {
                id: newInternalId,
                type: nodeConfig.type,
                label: nodeConfig.label || nodeType.label,
                description: nodeConfig.description || nodeType.description || '',
                position: nodeConfig.position || { x: 100 + idx * 200, y: 100 },
                data: mergedData,
                inputs: nodeConfig.inputs || nodeType.inputs || [],
                outputs: nodeConfig.outputs || nodeType.outputs || []
            };

            nodes.value.push(newNode);

            const originalId = String(nodeConfig.id !== undefined ? nodeConfig.id : idx);
            nodeIdMap.set(originalId, newInternalId);
        });

        // 导入连接
        const edges = config.edges || config.connections || [];
        edges.forEach((edge, edgeIdx) => {
            const sourceId = String(edge.source !== undefined ? edge.source : edge.from);
            const targetId = String(edge.target !== undefined ? edge.target : edge.to);

            const fromId = nodeIdMap.get(sourceId);
            const toId = nodeIdMap.get(targetId);

            if (fromId && toId) {
                connections.value.push({
                    from: fromId,
                    to: toId,
                    id: edge.id || `conn-${baseTime}-${edgeIdx}`
                });
            }
        });

        saveState();
    }

    function selectNode(nodeId) {
        selectedNode.value = nodeId;
    }

    function deselectNode() {
        selectedNode.value = null;
    }

    return {
        // State
        nodes,
        connections,
        scale,
        selectedNode,
        validationErrors,

        // Computed
        canUndo,
        canRedo,
        hasErrors,

        // Actions
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
        importConfig,
        validateConfig,
        validateNode,
        selectNode,
        deselectNode
    };
});
