<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useCanvasStore } from '../stores/canvas';
import { getAllTemplates, TEMPLATE_CATEGORIES, DIFFICULTY_LEVELS } from '../config/agentTemplates';

const router = useRouter();

// 状态
const activeTab = ref('welcome'); // welcome, templates, wizard, advanced
const selectedTemplate = ref(null);
const showTemplateDetail = ref(false);

const templates = getAllTemplates();

// 处理模板选择
function selectTemplate(template) {
  selectedTemplate.value = template;
  showTemplateDetail.value = true;
}

// 使用模板
function useTemplate(template) {
  // 保存模板配置到 store，然后跳转到编辑器
  const canvasStore = useCanvasStore();

  if (template.config?.nodes) {
    // 导入模板配置
    canvasStore.importConfig(template.config);
  }

  // 设置 Agent 信息
  canvasStore.agentName = template.name;
  canvasStore.agentDescription = template.description;

  // 跳转到编辑器
  router.push('/agent/edit');
}

// 打开智能向导
function openWizard() {
  activeTab.value = 'wizard';
}

// 打开高级编辑
function openAdvanced() {
  router.push('/agent/edit');
}

// 导入自定义配置
function importConfig() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.json';
  input.onchange = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const config = JSON.parse(event.target.result);
          const canvasStore = useCanvasStore();
          canvasStore.importConfig(config);
          router.push('/agent/edit');
        } catch (error) {
          alert('配置文件格式错误: ' + error.message);
        }
      };
      reader.readAsText(file);
    }
  };
  input.click();
}
</script>

<template>
  <div class="agent-builder-home">
    <!-- 头部 -->
    <div class="home-header">
      <div class="header-content">
        <h1>🤖 Agent 构建器</h1>
        <p class="tagline">创建属于你的智能 Agent，让工作更高效</p>
      </div>
    </div>

    <!-- 主容器 -->
    <div class="home-container">
      <!-- Welcome 标签页 -->
      <div v-show="activeTab === 'welcome'" class="tab-content">
        <div class="three-entry-grid">
          <!-- 入口1：模板库 -->
          <div class="entry-card">
            <div class="entry-icon">📚</div>
            <h3>快速开始</h3>
            <p class="entry-description">从 5 个预设模板中选择</p>
            <ul class="entry-features">
              <li>✓ 零配置，开箱即用</li>
              <li>✓ 5 分钟完成第一个 Agent</li>
              <li>✓ 预设示例和演示</li>
            </ul>
            <button class="btn btn-primary" @click="activeTab = 'templates'">
              浏览模板 →
            </button>
          </div>

          <!-- 入口2：智能向导 -->
          <div class="entry-card coming-soon">
            <div class="entry-icon">🤖</div>
            <h3>智能向导</h3>
            <p class="entry-description">描述需求，AI 自动生成配置</p>
            <ul class="entry-features">
              <li>✓ 对话式引导</li>
              <li>✓ AI 推荐最佳方案</li>
              <li>✓ 自动优化配置</li>
            </ul>
            <button class="btn btn-secondary" disabled>
              敬请期待 (第2阶段)
            </button>
          </div>

          <!-- 入口3：高级编辑 -->
          <div class="entry-card">
            <div class="entry-icon">🎨</div>
            <h3>高级编辑</h3>
            <p class="entry-description">完全自定义，所有功能可用</p>
            <ul class="entry-features">
              <li>✓ 10 种节点类型</li>
              <li>✓ 完全自由配置</li>
              <li>✓ 适合专家用户</li>
            </ul>
            <button class="btn btn-secondary" @click="openAdvanced">
              开始编辑 →
            </button>
          </div>
        </div>

        <!-- 其他选项 -->
        <div class="other-options">
          <h4>其他选项</h4>
          <button class="btn btn-outline" @click="importConfig">
            📥 导入配置文件
          </button>
        </div>
      </div>

      <!-- Templates 标签页 -->
      <div v-show="activeTab === 'templates'" class="tab-content">
        <div class="templates-header">
          <button class="btn-back" @click="activeTab = 'welcome'">← 返回</button>
          <h2>📚 预设模板库</h2>
        </div>

        <!-- 模板网格 -->
        <div class="templates-grid">
          <div
            v-for="template in templates"
            :key="template.id"
            class="template-card"
            @click="selectTemplate(template)"
          >
            <div class="template-header">
              <span class="template-icon">{{ template.icon }}</span>
              <span class="difficulty-badge" :style="{ backgroundColor: DIFFICULTY_LEVELS[template.difficulty]?.color }">
                {{ DIFFICULTY_LEVELS[template.difficulty]?.label }}
              </span>
            </div>

            <h3>{{ template.name }}</h3>
            <p class="template-description">{{ template.description }}</p>

            <div class="template-features">
              <div v-for="feature in template.features" :key="feature" class="feature-item">
                ✓ {{ feature }}
              </div>
            </div>

            <div class="template-footer">
              <span class="time-estimate">⏱️ {{ template.estimatedTime }}</span>
              <button class="btn btn-small btn-primary">选择模板</button>
            </div>
          </div>
        </div>

        <!-- 模板详情模态框 -->
        <div v-if="showTemplateDetail && selectedTemplate" class="modal-overlay" @click="showTemplateDetail = false">
          <div class="modal-content" @click.stop>
            <div class="modal-header">
              <h2>
                <span class="modal-icon">{{ selectedTemplate.icon }}</span>
                {{ selectedTemplate.name }}
              </h2>
              <button class="btn-close" @click="showTemplateDetail = false">✕</button>
            </div>

            <div class="modal-body">
              <!-- 模板信息 -->
              <div class="detail-section">
                <h4>📋 模板说明</h4>
                <p>{{ selectedTemplate.description }}</p>
              </div>

              <!-- 功能特性 -->
              <div class="detail-section">
                <h4>✨ 功能特性</h4>
                <ul class="features-list">
                  <li v-for="feature in selectedTemplate.features" :key="feature">
                    {{ feature }}
                  </li>
                </ul>
              </div>

              <!-- 演示 -->
              <div class="detail-section">
                <h4>🎬 实时演示</h4>
                <div class="demo-box">
                  <div class="demo-item">
                    <label>📝 用户输入：</label>
                    <div class="demo-content">{{ selectedTemplate.demoInput }}</div>
                  </div>
                  <div class="demo-item">
                    <label>💬 Agent 回复：</label>
                    <div class="demo-content">{{ selectedTemplate.demoOutput }}</div>
                  </div>
                </div>
              </div>

              <!-- 难度和时间 -->
              <div class="detail-section">
                <div class="info-grid">
                  <div class="info-item">
                    <span class="label">难度</span>
                    <span class="value">{{ DIFFICULTY_LEVELS[selectedTemplate.difficulty]?.label }}</span>
                  </div>
                  <div class="info-item">
                    <span class="label">预计时间</span>
                    <span class="value">{{ selectedTemplate.estimatedTime }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="modal-footer">
              <button class="btn btn-secondary" @click="showTemplateDetail = false">
                返回
              </button>
              <button class="btn btn-primary" @click="useTemplate(selectedTemplate)">
                使用此模板 →
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Wizard 标签页 (placeholder) -->
      <div v-show="activeTab === 'wizard'" class="tab-content">
        <div class="wizard-placeholder">
          <button class="btn-back" @click="activeTab = 'welcome'">← 返回</button>
          <div class="coming-soon-box">
            <h2>🤖 AI 智能向导</h2>
            <p>这个功能正在开发中...</p>
            <p class="coming-soon-text">即将推出对话式 Agent 创建体验</p>
            <button class="btn btn-primary" @click="activeTab = 'welcome'">返回首页</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-builder-home {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  flex-direction: column;
}

.home-header {
  padding: 60px 20px 40px;
  text-align: center;
  color: white;
}

.header-content h1 {
  font-size: 48px;
  margin: 0 0 12px 0;
  font-weight: 700;
}

.tagline {
  font-size: 18px;
  margin: 0;
  opacity: 0.9;
}

.home-container {
  flex: 1;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
  padding: 40px 20px;
}

.tab-content {
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 三个入口 */
.three-entry-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 24px;
  margin-bottom: 40px;
}

.entry-card {
  background: white;
  border-radius: 16px;
  padding: 32px 24px;
  text-align: center;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
  position: relative;
}

.entry-card:hover:not(.coming-soon) {
  transform: translateY(-8px);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.2);
}

.entry-card.coming-soon {
  opacity: 0.7;
}

.entry-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.entry-card h3 {
  font-size: 24px;
  margin: 0 0 8px 0;
  color: #1f2937;
}

.entry-description {
  color: #6b7280;
  font-size: 14px;
  margin: 0 0 20px 0;
}

.entry-features {
  list-style: none;
  padding: 0;
  margin: 0 0 24px 0;
  text-align: left;
}

.entry-features li {
  color: #4b5563;
  margin: 10px 0;
  font-size: 14px;
}

.btn {
  padding: 10px 24px;
  border-radius: 8px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: #3b82f6;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
  transform: translateY(-2px);
}

.btn-secondary {
  background: #f3f4f6;
  color: #374151;
}

.btn-secondary:hover:not(:disabled) {
  background: #e5e7eb;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-outline {
  background: transparent;
  color: white;
  border: 2px solid white;
}

.btn-outline:hover {
  background: rgba(255, 255, 255, 0.1);
}

/* 其他选项 */
.other-options {
  text-align: center;
  color: white;
  margin-top: 40px;
}

.other-options h4 {
  margin: 0 0 16px 0;
  opacity: 0.9;
}

/* 模板列表 */
.templates-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 32px;
  color: white;
}

.btn-back {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.btn-back:hover {
  background: rgba(255, 255, 255, 0.3);
}

.templates-header h2 {
  margin: 0;
  flex: 1;
}

.templates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.template-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.template-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.15);
}

.template-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.template-icon {
  font-size: 32px;
}

.difficulty-badge {
  color: white;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 12px;
  font-weight: 600;
}

.template-card h3 {
  font-size: 18px;
  margin: 0 0 8px 0;
  color: #1f2937;
}

.template-description {
  color: #6b7280;
  font-size: 13px;
  margin: 0 0 16px 0;
}

.template-features {
  text-align: left;
  margin: 16px 0;
}

.feature-item {
  color: #4b5563;
  font-size: 13px;
  margin: 6px 0;
}

.template-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
}

.time-estimate {
  font-size: 12px;
  color: #9ca3af;
}

.btn-small {
  padding: 6px 16px;
  font-size: 12px;
}

/* 模态框 */
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
  padding: 20px;
}

.modal-content {
  background: white;
  border-radius: 16px;
  max-width: 600px;
  width: 100%;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px;
  border-bottom: 1px solid #e5e7eb;
}

.modal-header h2 {
  margin: 0;
  font-size: 24px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.modal-icon {
  font-size: 28px;
}

.btn-close {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #6b7280;
  padding: 4px 8px;
}

.btn-close:hover {
  color: #1f2937;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.detail-section {
  margin-bottom: 24px;
}

.detail-section h4 {
  margin: 0 0 12px 0;
  color: #1f2937;
  font-size: 16px;
}

.detail-section p {
  margin: 0;
  color: #6b7280;
  line-height: 1.6;
}

.features-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.features-list li {
  padding: 8px 0;
  color: #4b5563;
}

.demo-box {
  background: #f9fafb;
  border-radius: 8px;
  padding: 16px;
}

.demo-item {
  margin-bottom: 12px;
}

.demo-item:last-child {
  margin-bottom: 0;
}

.demo-item label {
  display: block;
  font-weight: 600;
  color: #374151;
  margin-bottom: 6px;
  font-size: 13px;
}

.demo-content {
  background: white;
  padding: 12px;
  border-radius: 6px;
  color: #4b5563;
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.info-item {
  background: #f9fafb;
  padding: 12px;
  border-radius: 8px;
  text-align: center;
}

.info-item .label {
  display: block;
  color: #6b7280;
  font-size: 12px;
  margin-bottom: 4px;
}

.info-item .value {
  display: block;
  color: #1f2937;
  font-weight: 600;
  font-size: 16px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 20px 24px;
  border-top: 1px solid #e5e7eb;
}

/* 向导占位符 */
.wizard-placeholder {
  color: white;
}

.coming-soon-box {
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 60px 40px;
  text-align: center;
  margin-top: 40px;
}

.coming-soon-box h2 {
  font-size: 36px;
  margin: 0 0 16px 0;
}

.coming-soon-box p {
  font-size: 16px;
  margin: 0 0 8px 0;
}

.coming-soon-text {
  opacity: 0.8;
  margin-bottom: 32px !important;
}

/* 响应式 */
@media (max-width: 768px) {
  .header-content h1 {
    font-size: 36px;
  }

  .three-entry-grid {
    grid-template-columns: 1fr;
  }

  .templates-grid {
    grid-template-columns: 1fr;
  }

  .modal-content {
    max-height: 90vh;
  }
}
</style>
