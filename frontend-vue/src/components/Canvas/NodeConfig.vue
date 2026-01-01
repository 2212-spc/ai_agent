<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { getNodeType } from '../../config/nodeTypes';

const props = defineProps({
  node: {
    type: Object,
    required: true
  },
  show: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:node', 'close']);

// 本地配置副本
const localConfig = ref({});
const localLabel = ref('');
const localDescription = ref('');

// 节点类型定义
const nodeType = computed(() => getNodeType(props.node.type));

// 可用工具列表（运行时从API加载）
const availableTools = ref([]);

// 加载可用工具
onMounted(async () => {
  try {
    const response = await fetch('http://127.0.0.1:8000/tools');
    if (response.ok) {
      const tools = await response.json();
      availableTools.value = tools.map(tool => ({
        value: tool.id,
        label: tool.name
      }));
    }
  } catch (error) {
    console.error('加载工具列表失败:', error);
  }
});

// 初始化本地数据
watch(() => props.node, (newNode) => {
  if (newNode) {
    localConfig.value = { ...(newNode.data || {}) };
    localLabel.value = newNode.label || '';
    localDescription.value = newNode.description || '';
  }
}, { immediate: true });

// 处理保存
function handleSave() {
  emit('update:node', {
    ...props.node,
    label: localLabel.value,
    description: localDescription.value,
    data: { ...localConfig.value }
  });
  emit('close');
}

// 处理取消
function handleCancel() {
  emit('close');
}

// 动态获取字段选项（为tool_executor加载工具列表）
function getFieldOptions(field) {
  if (field.name === 'toolId' && props.node.type === 'tool_executor') {
    return availableTools.value.length > 0 ? availableTools.value : field.options;
  }
  return field.options || [];
}

// JSON验证
function validateJSON(value) {
  try {
    JSON.parse(value);
    return true;
  } catch {
    return false;
  }
}
</script>

<template>
  <div v-if="show" class="node-config-modal" @click.self="handleCancel">
    <div class="node-config-content">
      <!-- 头部 -->
      <div class="node-config-header">
        <h3>
          <span class="node-icon">{{ nodeType?.icon }}</span>
          配置节点: {{ nodeType?.label }}
        </h3>
        <button class="btn-close" @click="handleCancel">✕</button>
      </div>

      <!-- 描述 -->
      <p class="node-description">{{ nodeType?.description }}</p>

      <!-- 表单 -->
      <div class="node-config-body">
        <!-- 基础信息 -->
        <div class="form-section">
          <h4>基础信息</h4>

          <div class="form-group">
            <label>节点名称</label>
            <input
              v-model="localLabel"
              type="text"
              placeholder="输入节点名称"
              class="form-input"
            />
          </div>

          <div class="form-group">
            <label>描述</label>
            <textarea
              v-model="localDescription"
              rows="2"
              placeholder="输入节点描述（可选）"
              class="form-textarea"
            ></textarea>
          </div>
        </div>

        <!-- 节点特定配置 -->
        <div v-if="nodeType?.configFields && nodeType.configFields.length > 0" class="form-section">
          <h4>节点配置</h4>

          <div
            v-for="field in nodeType.configFields"
            :key="field.name"
            class="form-group"
          >
            <label>
              {{ field.label }}
              <span v-if="field.required" class="required">*</span>
            </label>
            <small v-if="field.description" class="field-description">
              {{ field.description }}
            </small>

            <!-- 文本输入 -->
            <input
              v-if="field.fieldType === 'text'"
              v-model="localConfig[field.name]"
              type="text"
              :placeholder="field.placeholder"
              :required="field.required"
              class="form-input"
            />

            <!-- 数字输入 -->
            <input
              v-else-if="field.fieldType === 'number'"
              v-model.number="localConfig[field.name]"
              type="number"
              :placeholder="field.placeholder"
              :required="field.required"
              class="form-input"
            />

            <!-- 多行文本 -->
            <textarea
              v-else-if="field.fieldType === 'textarea'"
              v-model="localConfig[field.name]"
              rows="4"
              :placeholder="field.placeholder"
              :required="field.required"
              class="form-textarea"
            ></textarea>

            <!-- 代码编辑器 -->
            <textarea
              v-else-if="field.fieldType === 'code'"
              v-model="localConfig[field.name]"
              rows="3"
              :placeholder="field.placeholder"
              :required="field.required"
              class="form-code"
              spellcheck="false"
            ></textarea>

            <!-- JSON编辑器 -->
            <div v-else-if="field.fieldType === 'json'">
              <textarea
                v-model="localConfig[field.name]"
                rows="4"
                :placeholder="field.placeholder"
                :required="field.required"
                class="form-code"
                spellcheck="false"
              ></textarea>
              <small
                v-if="localConfig[field.name] && !validateJSON(localConfig[field.name])"
                class="error-text"
              >
                无效的JSON格式
              </small>
            </div>

            <!-- 下拉选择 -->
            <select
              v-else-if="field.fieldType === 'select'"
              v-model="localConfig[field.name]"
              :required="field.required"
              class="form-select"
            >
              <option value="">-- 请选择 --</option>
              <option
                v-for="option in getFieldOptions(field)"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </option>
            </select>

            <!-- 复选框 -->
            <label v-else-if="field.fieldType === 'checkbox'" class="checkbox-label">
              <input
                v-model="localConfig[field.name]"
                type="checkbox"
                class="form-checkbox"
              />
              <span>{{ field.description || '启用' }}</span>
            </label>
          </div>
        </div>

        <!-- 输入输出提示 -->
        <div class="form-section info-section">
          <div class="io-info">
            <div>
              <strong>输入:</strong>
              <span class="io-tags">
                <span v-for="input in nodeType?.inputs" :key="input" class="io-tag">
                  {{ input }}
                </span>
                <span v-if="!nodeType?.inputs || nodeType.inputs.length === 0" class="text-muted">
                  无
                </span>
              </span>
            </div>
            <div>
              <strong>输出:</strong>
              <span class="io-tags">
                <span v-for="output in nodeType?.outputs" :key="output" class="io-tag">
                  {{ output }}
                </span>
                <span v-if="!nodeType?.outputs || nodeType.outputs.length === 0" class="text-muted">
                  无
                </span>
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部按钮 -->
      <div class="node-config-footer">
        <button class="btn btn-secondary" @click="handleCancel">取消</button>
        <button class="btn btn-primary" @click="handleSave">保存</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.node-config-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.node-config-content {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 600px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
}

.node-config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
}

.node-config-header h3 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-icon {
  font-size: 24px;
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

.node-description {
  padding: 12px 24px;
  margin: 0;
  background: #f9fafb;
  color: #6b7280;
  font-size: 14px;
  border-bottom: 1px solid #e5e7eb;
}

.node-config-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.form-section {
  margin-bottom: 24px;
}

.form-section h4 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-weight: 500;
  color: #374151;
  font-size: 14px;
}

.required {
  color: #ef4444;
  margin-left: 2px;
}

.field-description {
  display: block;
  margin-top: -4px;
  margin-bottom: 6px;
  color: #6b7280;
  font-size: 12px;
}

.form-input,
.form-textarea,
.form-select,
.form-code {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.2s;
  font-family: inherit;
}

.form-input:focus,
.form-textarea:focus,
.form-select:focus,
.form-code:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-code {
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
  background: #f9fafb;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-weight: 400;
}

.form-checkbox {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

.error-text {
  display: block;
  margin-top: 4px;
  color: #ef4444;
  font-size: 12px;
}

.info-section {
  background: #f9fafb;
  padding: 16px;
  border-radius: 8px;
}

.io-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
  font-size: 14px;
}

.io-tags {
  display: inline-flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-left: 8px;
}

.io-tag {
  background: #e0e7ff;
  color: #4338ca;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.text-muted {
  color: #9ca3af;
  font-style: italic;
}

.node-config-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid #e5e7eb;
}

.btn {
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 14px;
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
</style>
