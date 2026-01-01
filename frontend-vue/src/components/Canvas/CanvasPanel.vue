<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useCanvasStore } from '../../stores/canvas';
import { useChatStore } from '../../stores/chat';
import NodeCanvas from './NodeCanvas.vue';
import NodeConfig from './NodeConfig.vue';
import BuilderTutorial from './BuilderTutorial.vue';
import { getAllNodeTypes, NODE_CATEGORIES } from '../../config/nodeTypes';
import { AGENT_TEMPLATES, getAllTemplates } from '../../config/agentTemplates';

const router = useRouter();
const canvasStore = useCanvasStore();
const chatStore = useChatStore();

// 新增状态
const configNode = ref(null);
const showNodeConfig = ref(false);
const saveLoading = ref(false);
const executeLoading = ref(false);
const showErrorModal = ref(false);
const agentName = ref('');
const agentDescription = ref('');
const testMessage = ref('');
const showTutorial = ref(false);
const showTemplateModal = ref(false);
const templates = computed(() => getAllTemplates());
const paletteHeight = ref(40); // vh单位
const showSettingsModal = ref(false);
const lastError = ref(null);

// 获取所有节点按分类分组
const nodesByCategory = computed(() => {
  const groups = {};
  getAllNodeTypes().forEach(node => {
    if (!groups[node.category]) {
      groups[node.category] = [];
    }
    groups[node.category].push(node);
  });
  return groups;
});

function addNodeToCanvas(nodeType) {
  canvasStore.addNode({
    type: nodeType.type,
    label: nodeType.label,
    description: nodeType.description
  });
  
  // 显示操作提示
  showOperationHint(`✅ 已添加节点"${nodeType.label}"，双击节点开始连接`);
}

function getNodeTooltip(node) {
  return `${node.description}\n\n输入: ${node.inputs?.join(', ') || '无'}\n输出: ${node.outputs?.join(', ') || '无'}`;
}

const operationHint = ref(null);
const operationHintTimer = ref(null);

function showOperationHint(message, duration = 3000) {
  if (operationHintTimer.value) {
    clearTimeout(operationHintTimer.value);
  }
  
  operationHint.value = message;
  operationHintTimer.value = setTimeout(() => {
    operationHint.value = null;
  }, duration);
}

function handleNodeClick(node) {
  // node 参数已经是完整的节点对象，不需要再查找
  if (node) {
    configNode.value = { ...node };
    showNodeConfig.value = true;
  }
}

function handleUpdateNode(updatedNode) {
  canvasStore.updateNode(updatedNode.id, {
    label: updatedNode.label,
    description: updatedNode.description,
    data: updatedNode.data
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
    showErrorModal.value = false;
  }
}

// [优化] 保存前验证
async function handleSave() {
  const errors = canvasStore.validateConfig();

  if (errors.length > 0) {
    showErrorModal.value = true;
    return;
  }

  const config = canvasStore.exportConfig();

  if (!agentName.value.trim()) {
    agentName.value = `Agent-${new Date().toLocaleString()}`;
  }

  saveLoading.value = true;

  try {
    const response = await fetch('http://127.0.0.1:8000/agents', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        name: agentName.value,
        description: agentDescription.value || '通过构建器创建的Agent',
        config: config
      })
    });

    if (response.ok) {
      const agent = await response.json();
      showSuccessMessage(`✅ Agent保存成功！(ID: ${agent.id})`);

      // 导出JSON副本
      const blob = new Blob([JSON.stringify(config, null, 2)], {
        type: 'application/json'
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${agentName.value}-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } else {
      const errorData = await response.json();
      alert(`❌ 保存失败: ${errorData.detail || '未知错误'}`);
    }
  } catch (error) {
    alert(`❌ 错误: ${error.message}`);
  } finally {
    saveLoading.value = false;
  }
}

// [优化] 执行前验证 - 流式执行
async function handleExecute() {
  const errors = canvasStore.validateConfig();

  if (errors.length > 0) {
    showErrorModal.value = true;
    return;
  }

  if (!testMessage.value.trim()) {
    alert('请输入测试消息');
    return;
  }

  const config = canvasStore.exportConfig();
  executeLoading.value = true;

  try {
    // 先临时保存Agent配置
    console.log('正在保存Agent配置:', JSON.stringify(config, null, 2));
    console.log('节点数量:', config.nodes.length, '边数量:', config.edges?.length || 0);
    console.log('节点ID类型检查:', config.nodes.map(n => ({ id: n.id, type: typeof n.id })));
    
    const saveResponse = await fetch('http://127.0.0.1:8000/agents', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        name: `TempAgent-${Date.now()}`,
        description: '临时测试Agent',
        config: config
      })
    });

    if (!saveResponse.ok) {
      const errorText = await saveResponse.text();
      console.error('保存失败响应:', errorText);
      throw new Error(`无法保存Agent配置: ${saveResponse.status} ${errorText}`);
    }

    const agent = await saveResponse.json();
    console.log('Agent保存成功:', agent);
    const userMessage = testMessage.value;
    testMessage.value = ''; // 清空输入框

    // 创建临时会话用于显示执行结果
    const sessionId = `builder-exec-${Date.now()}`;
    chatStore.ensureSession(sessionId);
    chatStore.setCurrentSession(sessionId);
    
    // 添加用户消息
    chatStore.addMessage({
      role: 'user',
      content: userMessage
    }, sessionId);

    // 添加助手消息占位符
    let assistantMessageId = chatStore.addMessage({
      role: 'assistant',
      content: '',
      isStreaming: true
    }, sessionId);
    
    // 如果addMessage返回null，使用时间戳作为ID
    if (!assistantMessageId) {
      assistantMessageId = Date.now();
    }

    // 使用流式API执行Agent
    console.log('开始执行Agent:', agent.id);
    
    const execResponse = await fetch(`http://127.0.0.1:8000/agents/${agent.id}/execute/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        agent_id: agent.id,
        messages: [{ role: 'user', content: userMessage }],
        use_knowledge_base: false,
        use_tools: true
      })
    });

    if (!execResponse.ok) {
      const errorText = await execResponse.text();
      console.error('执行失败响应:', errorText);
      throw new Error(`执行失败: ${execResponse.status} ${errorText}`);
    }

    const reader = execResponse.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let fullResponse = '';

    while (true) {
      const { done, value } = await reader.read();

      if (value) {
        buffer += decoder.decode(value, { stream: true });
      }

      const events = buffer.split('\n\n');

      if (!done) {
        buffer = events.pop() || '';
      } else {
        buffer = '';
      }

      for (const eventText of events) {
        if (!eventText.trim()) continue;

        const lines = eventText.split('\n');
        let eventType = '';
        let eventData = null;

        // 解析事件块中的event和data行
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              console.log('📨 收到[DONE]标记');
              break;
            }
            try {
              eventData = JSON.parse(data);
            } catch (e) {
              console.error('JSON解析失败:', e, 'Data:', data);
            }
          }
        }

        if (eventData) {
          const finalEventType = eventType || eventData.type || eventData.event;
          console.log('🔍 处理事件类型:', finalEventType, '数据:', eventData);

          // 处理内容事件
          if (finalEventType === 'assistant_final' || finalEventType === 'content' || finalEventType === 'message' || finalEventType === 'assistant_draft') {
            const content = eventData.content || eventData.message || eventData.data || '';
            if (content) {
              fullResponse = content; // 完整内容，直接替换
              chatStore.updateMessage(assistantMessageId, {
                content: fullResponse,
                isStreaming: true
              }, sessionId);
              console.log('📝 更新内容，长度:', content.length);
            }
          } else if (finalEventType === 'token') {
            // 流式追加内容
            const chunk = eventData.data || eventData.chunk || eventData.content || '';
            if (chunk) {
              fullResponse += chunk;
              chatStore.updateMessage(assistantMessageId, {
                content: fullResponse,
                isStreaming: true
              }, sessionId);
            }
          } else if (finalEventType === 'agent_node' || finalEventType === 'node') {
            // 节点状态信息
            const nodeData = eventData.data || eventData;
            const text = nodeData.reply || nodeData.response || nodeData.content || '';
            if (text) {
              fullResponse += text + '\n';
              chatStore.updateMessage(assistantMessageId, {
                content: fullResponse,
                isStreaming: true
              }, sessionId);
            }
          } else if (finalEventType === 'agent_thought' || finalEventType === 'thought') {
            const thought = eventData.thought || eventData.content || '';
            if (thought) {
              fullResponse += `💭 ${thought}\n`;
              chatStore.updateMessage(assistantMessageId, {
                content: fullResponse,
                isStreaming: true
              }, sessionId);
            }
          } else if (finalEventType === 'tool_result' || finalEventType === 'tool' || finalEventType === 'tool_call') {
            const result = eventData.result || eventData.content || '';
            if (result) {
              fullResponse += `🔧 ${typeof result === 'object' ? JSON.stringify(result) : result}\n`;
              chatStore.updateMessage(assistantMessageId, {
                content: fullResponse,
                isStreaming: true
              }, sessionId);
            }
          } else if (eventData.content) {
            // 其他包含content字段的事件
            fullResponse += eventData.content + '\n';
            chatStore.updateMessage(assistantMessageId, {
              content: fullResponse,
              isStreaming: true
            }, sessionId);
          }
        }
      }

      if (done) {
        // 处理最后的缓冲区
        if (buffer.trim()) {
          const lines = buffer.split('\n');
          let eventType = '';
          let eventData = null;

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data !== '[DONE]') {
                try {
                  eventData = JSON.parse(data);
                } catch (e) {
                  console.error('最终缓冲JSON解析失败:', e);
                }
              }
            }
          }

          if (eventData) {
            const finalEventType = eventType || eventData.type || eventData.event;
            const content = eventData.content || eventData.message || eventData.data || eventData.reply || '';
            if (content && finalEventType !== '[DONE]') {
              fullResponse += content;
            }
          }
        }
        break;
      }
    }

    chatStore.updateMessage(assistantMessageId, {
      content: fullResponse || '✅ 执行完成（无输出）',
      isStreaming: false
    }, sessionId);

    // 执行完成后自动跳转到聊天页面
    console.log('✅ Agent执行完成，自动跳转到聊天页面');
    setTimeout(() => {
      chatStore.setCurrentSession(sessionId);
      router.push('/chat');
    }, 1000);

  } catch (error) {
    console.error('执行错误:', error);
    lastError.value = error.message;

    // 添加错误消息到聊天会话
    chatStore.addMessage({
      role: 'assistant',
      content: `❌ 执行失败: ${error.message}`
    }, sessionId);

    console.error('执行失败详情:', error);
  } finally {
    executeLoading.value = false;
  }
}

// 打开设置模态框
function openSettings() {
  showSettingsModal.value = true;
}

// 关闭设置模态框
function closeSettings() {
  showSettingsModal.value = false;
}

function showSuccessMessage(msg) {
  alert(msg);
}

function handleZoomIn() {
  canvasStore.setScale(canvasStore.scale + 0.1);
}

function handleZoomOut() {
  canvasStore.setScale(canvasStore.scale - 0.1);
}

function downloadConfig() {
  const config = canvasStore.exportConfig();
  const blob = new Blob([JSON.stringify(config, null, 2)], {
    type: 'application/json'
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `agent-config-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// 新手引导
function startTutorial() {
  showTutorial.value = true;
}

function closeTutorial() {
  showTutorial.value = false;
}

// 检查是否需要显示引导
onMounted(() => {
  const tutorialCompleted = localStorage.getItem('builder_tutorial_completed');
  if (!tutorialCompleted) {
    // 延迟显示，让界面先加载
    setTimeout(() => {
      showTutorial.value = true;
    }, 500);
  }
});

// 监听模态框状态，控制body滚动
watch(showTemplateModal, (show) => {
  if (show) {
    document.body.style.overflow = 'hidden';
  } else {
    document.body.style.overflow = '';
  }
});

// 调整侧边栏高度
function startResizePalette(event) {
  const startY = event.clientY;
  const startHeight = paletteHeight.value;

  function onMouseMove(e) {
    const deltaY = e.clientY - startY;
    const viewportHeight = window.innerHeight;
    const newHeight = Math.max(20, Math.min(70, startHeight + (deltaY / viewportHeight) * 100));
    paletteHeight.value = newHeight;
  }

  function onMouseUp() {
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  }

  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

// 模板加载
function loadTemplate(template) {
  if (confirm(`确定要加载模板"${template.name}"吗？这将清空当前画布。`)) {
    try {
      canvasStore.importConfig(template.config);
      agentName.value = template.name;
      agentDescription.value = template.description || '';
      showTemplateModal.value = false;
      showSuccessMessage(`✅ 模板"${template.name}"加载成功！`);
    } catch (error) {
      alert(`❌ 加载模板失败: ${error.message}`);
    }
  }
}
</script>

<template>
  <div class="canvas-panel">
    <!-- 工具栏 -->
      <div class="canvas-toolbar">
      <div class="toolbar-section">
        <button
          class="btn-icon"
          @click="handleUndo"
          :disabled="!canvasStore.canUndo"
          title="撤销 (Ctrl+Z)"
        >
          ↶
        </button>
        <button
          class="btn-icon"
          @click="handleRedo"
          :disabled="!canvasStore.canRedo"
          title="重做 (Ctrl+Y)"
        >
          ↷
        </button>
      </div>

      <div class="toolbar-section">
        <button class="btn-icon" @click="handleZoomOut" title="缩小">🔍−</button>
        <span class="zoom-level">{{ Math.round(canvasStore.scale * 100) }}%</span>
        <button class="btn-icon" @click="handleZoomIn" title="放大">🔍+</button>
      </div>

      <div class="toolbar-separator"></div>

      <div class="toolbar-section">
        <button class="btn btn-secondary btn-small" @click="startTutorial" title="新手引导">
          📖 引导
        </button>
        <button class="btn btn-secondary btn-small" @click="showTemplateModal = true" title="加载模板">
          📋 模板
        </button>
        <button class="btn btn-secondary btn-small" @click="handleClear" title="清空画布">
          🗑️ 清空
        </button>
        <button class="btn btn-primary btn-small" @click="handleSave" :disabled="saveLoading">
          {{ saveLoading ? '保存中...' : '💾 保存' }}
        </button>
        <button
          class="btn btn-success btn-small"
          @click="handleExecute"
          :disabled="executeLoading"
          title="测试执行Agent"
        >
          {{ executeLoading ? '执行中...' : '▶️ 执行' }}
        </button>
        <button class="btn btn-secondary btn-small" @click="downloadConfig" title="下载配置JSON">
          📥 导出
        </button>
      </div>
    </div>

    <!-- 节点库面板 -->
    <div class="node-palette" :style="{ maxHeight: `${paletteHeight}vh` }">
      <h4 class="palette-title">📚 节点库</h4>
      <div class="usage-hint">💡 点击节点添加到画布，点击画布上的节点进行配置</div>

      <!-- 按分类显示节点 -->
      <div class="categories-container">
        <div v-for="(category, catName) in nodesByCategory" :key="catName" class="category-group">
          <h5 class="category-name">
            {{ NODE_CATEGORIES[catName]?.icon }} {{ NODE_CATEGORIES[catName]?.label }}
          </h5>
          <div class="node-list">
            <div
              v-for="node in category"
              :key="node.type"
              class="node-item"
              :title="getNodeTooltip(node)"
              @click="addNodeToCanvas(node)"
            >
              <div class="node-item-content">
                <span class="node-icon">{{ node.icon }}</span>
                <span class="node-label">{{ node.label }}</span>
              </div>
              <div class="node-io-badges" v-if="node.inputs?.length || node.outputs?.length">
                <span class="io-badge input-badge" v-if="node.inputs?.length" :title="`输入: ${node.inputs.join(', ')}`">
                  ↓{{ node.inputs.length }}
                </span>
                <span class="io-badge output-badge" v-if="node.outputs?.length" :title="`输出: ${node.outputs.join(', ')}`">
                  ↑{{ node.outputs.length }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Agent信息输入 -->
      <div class="agent-info-section">
        <h4 class="palette-title">⚙️ Agent信息</h4>
        <div class="form-group">
          <label>Agent名称</label>
          <input v-model="agentName" type="text" placeholder="输入Agent名称" class="form-input" />
        </div>
        <div class="form-group">
          <label>Agent描述</label>
          <textarea
            v-model="agentDescription"
            rows="2"
            placeholder="输入Agent描述（可选）"
            class="form-input"
          ></textarea>
        </div>

        <h4 class="palette-title">🧪 测试执行</h4>
        <div class="form-group">
          <label>输入消息</label>
          <input
            v-model="testMessage"
            type="text"
            placeholder="输入测试消息..."
            class="form-input"
            @keyup.enter="handleExecute"
          />
        </div>
      </div>
    </div>

    <!-- 调整大小分隔条 -->
    <div class="palette-resizer" @mousedown="startResizePalette">
      <div class="resizer-handle"></div>
    </div>

    <!-- 画布 -->
    <div class="canvas-container">
      <NodeCanvas
        @node-click="handleNodeClick"
        @operation-hint="showOperationHint"
      />
    </div>

    <!-- 节点配置模态框 -->
    <NodeConfig
      v-if="configNode"
      :node="configNode"
      :show="showNodeConfig"
      @update:node="handleUpdateNode"
      @close="showNodeConfig = false"
    />
    
    <!-- 新手引导 -->
    <BuilderTutorial
      :show="showTutorial"
      @close="closeTutorial"
    />
    
    <!-- 模板选择模态框 -->
    <div v-if="showTemplateModal" class="modal-overlay" @click.self="showTemplateModal = false">
      <div class="modal-content template-modal">
        <div class="modal-header">
          <h3>📋 选择模板</h3>
          <button class="btn-close" @click="showTemplateModal = false">✕</button>
        </div>
        <div class="modal-body template-list">
          <div
            v-for="template in templates"
            :key="template.id"
            class="template-item"
            @click="loadTemplate(template)"
          >
            <div class="template-icon">{{ template.icon }}</div>
            <div class="template-info">
              <h4>{{ template.name }}</h4>
              <p>{{ template.description }}</p>
              <div class="template-meta">
                <span class="template-difficulty">{{ template.difficulty }}</span>
                <span class="template-time">⏱️ {{ template.estimatedTime }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 错误提示模态框 -->
        <div v-if="showErrorModal" class="error-modal" @click.self="showErrorModal = false">
      <div class="error-content">
        <div class="error-header">
          <h3>⚠️ 配置验证结果</h3>
          <button class="btn-close" @click="showErrorModal = false">✕</button>
        </div>

        <div class="error-list">
          <div 
            v-for="(error, idx) in canvasStore.validationErrors" 
            :key="idx" 
            :class="['error-item', error.startsWith('❌') ? 'error' : 'warning']"
          >
            {{ error }}
          </div>
        </div>

        <div class="error-footer">
          <p class="error-tip">💡 请修复以上错误后再进行保存或执行。警告不影响操作，但建议检查。</p>
          <button class="btn btn-primary" @click="showErrorModal = false">返回编辑</button>
        </div>
      </div>
    </div>
    
    <!-- 操作提示 -->
    <div v-if="operationHint" class="operation-hint">
      {{ operationHint }}
    </div>
    
    <!-- 设置模态框 -->
    <div v-if="showSettingsModal" class="modal-overlay" @click.self="closeSettings">
      <div class="modal-content settings-modal">
        <div class="modal-header">
          <h3>⚙️ 设置与信息</h3>
          <button class="btn-close" @click="closeSettings">✕</button>
        </div>
        <div class="modal-body">
          <!-- 错误信息 -->
          <div v-if="lastError" class="settings-section">
            <h4>❌ 最近执行错误</h4>
            <div class="error-detail">
              <pre>{{ lastError }}</pre>
            </div>
            <button class="btn btn-secondary btn-small" @click="lastError = null">清除错误信息</button>
          </div>
          
          <!-- 配置验证信息 -->
          <div class="settings-section">
            <h4>📋 配置验证</h4>
            <div v-if="canvasStore.validationErrors.length > 0" class="error-list">
              <div 
                v-for="(error, idx) in canvasStore.validationErrors" 
                :key="idx" 
                :class="['error-item', error.startsWith('❌') ? 'error' : 'warning']"
              >
                {{ error }}
              </div>
            </div>
            <div v-else class="success-message">
              ✅ 配置验证通过
            </div>
          </div>
          
          <!-- Agent信息 -->
          <div class="settings-section">
            <h4>🤖 Agent信息</h4>
            <div class="info-item">
              <label>名称:</label>
              <span>{{ agentName || '未设置' }}</span>
            </div>
            <div class="info-item">
              <label>描述:</label>
              <span>{{ agentDescription || '未设置' }}</span>
            </div>
            <div class="info-item">
              <label>节点数:</label>
              <span>{{ canvasStore.nodes.length }}</span>
            </div>
            <div class="info-item">
              <label>连接数:</label>
              <span>{{ canvasStore.connections.length }}</span>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-primary" @click="closeSettings">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.canvas-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--bg-secondary);
    min-height: 400px;
    overflow: auto;
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
    background: var(--bg-primary);
    overflow-y: auto;
    transition: max-height 0.1s;
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

.node-item-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
}

.node-icon {
    font-size: 24px;
}

.node-label {
    font-size: 12px;
    color: var(--text-primary);
    text-align: center;
}

.node-io-badges {
    display: flex;
    gap: 4px;
    margin-top: 4px;
    font-size: 10px;
}

.io-badge {
    padding: 2px 4px;
    border-radius: 3px;
    font-weight: 600;
}

.input-badge {
    background: #d1fae5;
    color: #065f46;
}

.output-badge {
    background: #ddd6fe;
    color: #5b21b6;
}

.canvas-container {
    flex: 1;
    overflow: hidden;
    position: relative;
}

/* 新增样式 */

.toolbar-separator {
    width: 1px;
    height: 24px;
    background: var(--border-primary);
    margin: 0 8px;
}

.palette-resizer {
    height: 8px;
    background: var(--bg-secondary);
    cursor: ns-resize;
    display: flex;
    align-items: center;
    justify-content: center;
    border-bottom: 1px solid var(--border-primary);
    transition: background 0.2s;
}

.palette-resizer:hover {
    background: var(--bg-tertiary);
}

.resizer-handle {
    width: 40px;
    height: 3px;
    background: var(--border-primary);
    border-radius: 2px;
}

.categories-container {
    margin-bottom: 16px;
}

.category-group {
    margin-bottom: 12px;
}

.category-name {
    font-size: 12px;
    font-weight: 600;
    color: var(--primary-color);
    margin: 8px 0 6px 0;
    padding: 0 4px;
}

.agent-info-section {
    background: var(--bg-secondary);
    padding: 12px;
    border-radius: 8px;
    margin-top: 12px;
    border: 1px solid var(--border-secondary);
}

.form-group {
    margin-bottom: 10px;
}

.form-group label {
    display: block;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.form-input {
    width: 100%;
    padding: 6px 8px;
    border: 1px solid var(--border-secondary);
    border-radius: 4px;
    font-size: 12px;
    background: var(--bg-primary);
    color: var(--text-primary);
    transition: border-color 0.2s;
}

.form-input:focus {
    outline: none;
    border-color: var(--primary-color);
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

/* 错误模态框 */
.error-modal {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 999;
}

.error-content {
    background: white;
    border-radius: 12px;
    width: 90%;
    max-width: 500px;
    max-height: 70vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
}

.error-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 24px;
    border-bottom: 1px solid #e5e7eb;
}

.error-header h3 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: #dc2626;
}

.btn-close {
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #6b7280;
    padding: 4px 8px;
    line-height: 1;
}

.btn-close:hover {
    color: #1f2937;
}

.error-list {
    flex: 1;
    overflow-y: auto;
    padding: 16px 24px;
}

.error-item {
    padding: 10px 12px;
    border-radius: 4px;
    margin-bottom: 8px;
    font-size: 13px;
    line-height: 1.4;
}

.error-item.error {
    background: #fee2e2;
    color: #991b1b;
    border-left: 3px solid #dc2626;
}

.error-item.warning {
    background: #fef3c7;
    color: #92400e;
    border-left: 3px solid #f59e0b;
}

.operation-hint {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: rgba(0, 0, 0, 0.85);
    color: white;
    padding: 12px 20px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    font-size: 14px;
    font-weight: 500;
    z-index: 1000;
    animation: slideIn 0.3s;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

@keyframes slideIn {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

.error-footer {
    padding: 16px 24px;
    border-top: 1px solid #e5e7eb;
    text-align: center;
}

.error-tip {
    margin: 0 0 12px 0;
    font-size: 13px;
    color: #6b7280;
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
    background: #f3f4f6;
    color: #374151;
}

.btn-secondary:hover {
    background: #e5e7eb;
}

.btn-primary {
    background: #3b82f6;
    color: white;
}

.btn-primary:hover {
    background: #2563eb;
}

.btn-primary:disabled {
    background: #9ca3af;
    cursor: not-allowed;
}

.btn-success {
    background: #10b981;
    color: white;
}

.btn-success:hover {
    background: #059669;
}

.btn-success:disabled {
    background: #9ca3af;
    cursor: not-allowed;
}

.btn-small {
    padding: 6px 12px;
    font-size: 12px;
}

.btn-icon {
    background: none;
    border: none;
    font-size: 16px;
    cursor: pointer;
    color: var(--text-primary);
    padding: 4px 8px;
    border-radius: 4px;
    transition: background 0.2s;
}

.btn-icon:hover:not(:disabled) {
    background: var(--bg-secondary);
}

.btn-icon:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

/* 模板模态框 */
.template-modal,
.settings-modal {
    max-width: 600px;
    max-height: 80vh;
    z-index: 10001;
}

.settings-modal {
    max-width: 700px;
}

.settings-section {
    margin-bottom: 24px;
    padding-bottom: 24px;
    border-bottom: 1px solid var(--border-primary);
}

.settings-section:last-child {
    border-bottom: none;
    margin-bottom: 0;
    padding-bottom: 0;
}

.settings-section h4 {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 12px 0;
}

.error-detail {
    background: var(--bg-secondary);
    border: 1px solid var(--border-primary);
    border-radius: 6px;
    padding: 12px;
    margin: 12px 0;
    max-height: 200px;
    overflow-y: auto;
}

.error-detail pre {
    margin: 0;
    font-size: 12px;
    color: var(--text-primary);
    white-space: pre-wrap;
    word-break: break-all;
}

.success-message {
    color: #10b981;
    font-size: 14px;
    padding: 8px 0;
}

.info-item {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
    font-size: 14px;
}

.info-item label {
    font-weight: 500;
    color: var(--text-secondary);
    min-width: 80px;
    margin-right: 12px;
}

.info-item span {
    color: var(--text-primary);
    flex: 1;
}

.template-list {
    max-height: 60vh;
    overflow-y: auto;
}

.template-item {
    display: flex;
    gap: 16px;
    padding: 16px;
    border: 1px solid var(--border-secondary);
    border-radius: 8px;
    margin-bottom: 12px;
    cursor: pointer;
    transition: all 0.2s;
}

.template-item:hover {
    border-color: var(--primary-color);
    background: var(--bg-secondary);
    transform: translateY(-2px);
}

.template-icon {
    font-size: 32px;
    flex-shrink: 0;
}

.template-info {
    flex: 1;
}

.template-info h4 {
    margin: 0 0 8px 0;
    font-size: 16px;
    color: var(--text-primary);
}

.template-info p {
    margin: 0 0 8px 0;
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.5;
}

.template-meta {
    display: flex;
    gap: 12px;
    font-size: 12px;
    color: var(--text-tertiary);
}

.template-difficulty {
    padding: 2px 8px;
    background: var(--bg-tertiary);
    border-radius: 4px;
}

.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
}

.template-modal .modal-content {
    background: var(--bg-primary);
    border-radius: 12px;
    width: 90%;
    max-width: 600px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
    display: flex;
    flex-direction: column;
    max-height: 80vh;
    z-index: 10001;
    position: relative;
}
</style>
