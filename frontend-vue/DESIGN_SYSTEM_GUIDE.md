# 🌌 AI Agent Studio - Cosmic Tech Design System

## 快速开始

### 1. 新建组件已自动集成

✅ 设计系统已自动引入到 `main.js`，无需额外配置：

```javascript
import './assets/styles/variables.css';      // 设计令牌
import './assets/styles/animations.css';     // 动画系统
import './assets/styles/base.css';           // 基础样式
import './assets/styles/components.css';     // 组件样式
import './assets/styles/responsive.css';     // 响应式设计
```

### 2. 使用UI组件

#### 方式一：单独导入
```vue
<script setup>
import Icon from '@/components/ui/Icon.vue';
import Modal from '@/components/ui/Modal.vue';
import Button from '@/components/ui/Button.vue';
</script>
```

#### 方式二：统一导入
```vue
<script setup>
import { Icon, Modal, Button } from '@/components/ui';
</script>
```

---

## 📦 可用组件

### Icon - SVG图标系统

#### 基础用法
```vue
<Icon name="sparkles" />
<Icon name="robot" :size="24" />
<Icon name="heart" :size="20" stroke-width="2" class="text-error" />
```

#### 所有可用图标
```
Navigation: menu, x, chevron-*, arrow-*
Actions: plus, minus, check, copy, clipboard, pencil, trash, refresh, stop, play
Communication: chat, chat-bubble, send, paper-airplane
Files: document, folder, attachment, upload, download
AI & Tech: sparkles, cpu-chip, bolt, light-bulb, brain, robot
Settings: cog, wrench, adjustments
Data: database, book-open, archive, clock, history
Status: check-circle, x-circle, exclamation-circle, information-circle
Theme: sun, moon, eye, eye-slash
User: user, user-circle, users
Search: search, magnifying-glass
Misc: home, star, heart, globe, link, bars-3, ellipsis-*
```

### Modal - 模态对话框

#### 基础用法
```vue
<template>
  <Button @click="open = true">打开对话框</Button>

  <Modal
    :open="open"
    @close="open = false"
    title="确认操作"
    size="md"
  >
    <p>确定要执行此操作吗？</p>

    <template #footer>
      <Button variant="secondary" @click="open = false">取消</Button>
      <Button variant="primary" @click="confirm">确认</Button>
    </template>
  </Modal>
</template>

<script setup>
import { ref } from 'vue';
import { Modal, Button } from '@/components/ui';

const open = ref(false);

function confirm() {
  // 执行操作
  open.value = false;
}
</script>
```

#### Props
- `open`: Boolean - 是否打开
- `title`: String - 标题
- `size`: String - 尺寸 ('sm', 'md', 'lg', 'xl', 'full')
- `showClose`: Boolean - 显示关闭按钮 (默认true)
- `closeOnBackdrop`: Boolean - 点击背景关闭 (默认true)
- `closeOnEsc`: Boolean - ESC键关闭 (默认true)

#### Slots
- `header`: 自定义头部
- `default`: 内容
- `footer`: 底部操作栏

### Button - 按钮组件

#### 基础用法
```vue
<!-- 变体 -->
<Button variant="primary">主要按钮</Button>
<Button variant="secondary">次要按钮</Button>
<Button variant="ghost">幽灵按钮</Button>
<Button variant="danger">危险按钮</Button>
<Button variant="success">成功按钮</Button>
<Button variant="gradient">渐变按钮</Button>

<!-- 尺寸 -->
<Button size="xs">超小</Button>
<Button size="sm">小</Button>
<Button size="md">中等</Button>
<Button size="lg">大</Button>
<Button size="xl">超大</Button>

<!-- 带图标 -->
<Button icon="sparkles">AI生成</Button>
<Button icon="send" icon-position="right">发送</Button>

<!-- 仅图标 -->
<Button icon="cog" icon-only />

<!-- 加载状态 -->
<Button :loading="isLoading">提交</Button>

<!-- 禁用状态 -->
<Button :disabled="true">禁用</Button>

<!-- 全宽 -->
<Button block>全宽按钮</Button>
```

#### Props
- `variant`: 'primary' | 'secondary' | 'ghost' | 'danger' | 'success' | 'gradient'
- `size`: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
- `icon`: String - 图标名称
- `iconPosition`: 'left' | 'right'
- `iconOnly`: Boolean - 仅显示图标
- `loading`: Boolean - 加载状态
- `disabled`: Boolean - 禁用状态
- `block`: Boolean - 全宽显示

---

## 🎨 使用设计令牌

### 颜色系统

#### Brand Colors
```css
.my-element {
  color: var(--brand-primary-500);           /* 主色 */
  background: var(--brand-secondary-100);     /* 次色浅版 */
  border-color: var(--brand-accent-400);      /* 强调色 */
}
```

#### Semantic Colors
```css
.success {
  color: var(--success-500);
  background: var(--success-50);
}

.error {
  color: var(--error-500);
  background: var(--error-50);
}

.warning {
  color: var(--warning-500);
  background: var(--warning-50);
}
```

#### Text & Background
```css
.card {
  color: var(--text-primary);                /* 主文本 */
  background: var(--bg-primary);             /* 主背景 */
  border: 1px solid var(--border-primary);   /* 边框 */
}
```

### 渐变系统
```css
.gradient-primary {
  background: var(--gradient-primary);
  /* linear-gradient(135deg, #8B5CF6 0%, #06B6D4 100%) */
}

.gradient-cosmic {
  background: var(--gradient-cosmic);
  /* 深邃宇宙渐变 */
}

.gradient-aurora {
  background: var(--gradient-aurora);
  /* 极光渐变 */
}
```

### 阴影系统
```css
.card {
  box-shadow: var(--shadow-md);              /* 中等阴影 */
}

.card:hover {
  box-shadow: var(--shadow-brand);           /* 品牌发光 */
}

.elevated {
  box-shadow: var(--shadow-xl);              /* 超大阴影 */
}
```

### 间距系统
```css
.container {
  padding: var(--space-6);                   /* 24px */
  margin-bottom: var(--space-8);             /* 32px */
  gap: var(--space-4);                       /* 16px */
}
```

### 圆角系统
```css
.button {
  border-radius: var(--radius-lg);           /* 8px */
}

.card {
  border-radius: var(--radius-2xl);          /* 16px */
}

.avatar {
  border-radius: var(--radius-full);         /* 9999px - 圆形 */
}
```

### 字体系统
```css
.heading {
  font-family: var(--font-display);          /* Satoshi */
  font-size: var(--text-2xl);                /* 24px */
  font-weight: var(--font-semibold);         /* 600 */
  line-height: var(--leading-tight);         /* 1.25 */
}

.body-text {
  font-family: var(--font-body);             /* Inter */
  font-size: var(--text-base);               /* 16px */
  line-height: var(--leading-relaxed);       /* 1.625 */
}

.code {
  font-family: var(--font-mono);             /* JetBrains Mono */
  font-size: var(--text-sm);                 /* 14px */
}
```

### 过渡与动画
```css
.button {
  transition: all var(--transition-normal);   /* 200ms ease-out */
}

.button:hover {
  transition: all var(--transition-fast);     /* 150ms ease-out */
}

.modal {
  transition: all var(--transition-slow);     /* 300ms ease-out */
}
```

---

## ✨ 动画系统

### Utility Classes
```vue
<!-- Fade Animations -->
<div class="animate-fadeIn">渐入</div>
<div class="animate-fadeInUp">向上渐入</div>
<div class="animate-fadeInLeft">从左渐入</div>

<!-- Scale Animations -->
<div class="animate-scaleIn">缩放进入</div>
<div class="animate-popIn">弹跳进入</div>
<div class="animate-bounceIn">反弹进入</div>

<!-- Slide Animations -->
<div class="animate-slideInUp">向上滑入</div>
<div class="animate-slideInRight">从右滑入</div>

<!-- Continuous Animations -->
<div class="animate-pulse">脉冲</div>
<div class="animate-spin">旋转</div>
<div class="animate-float">浮动</div>
<div class="animate-cosmicGlow">宇宙发光</div>
```

### Stagger Children
```vue
<div class="stagger-children">
  <div>Item 1</div>  <!-- 延迟 0ms -->
  <div>Item 2</div>  <!-- 延迟 50ms -->
  <div>Item 3</div>  <!-- 延迟 100ms -->
</div>
```

### Loading Skeleton
```vue
<div class="skeleton skeleton-card"></div>
<div class="skeleton skeleton-text"></div>
<div class="skeleton skeleton-avatar"></div>
```

### Typing Indicator
```vue
<div class="typing-indicator">
  <span></span>
  <span></span>
  <span></span>
</div>
```

### Hover Effects
```vue
<div class="hover-lift">悬停抬升</div>
<div class="hover-scale">悬停放大</div>
<div class="hover-glow">悬停发光</div>
<div class="hover-brighten">悬停增亮</div>
```

---

## 📱 响应式设计

### 断点
```css
/* Mobile First Approach */
@media (max-width: 640px) { /* 手机 */ }
@media (max-width: 768px) { /* 平板 */ }
@media (max-width: 1024px) { /* 小桌面 */ }
@media (min-width: 1280px) { /* 大桌面 */ }
```

### 示例
```css
.container {
  padding: var(--space-4);
}

@media (min-width: 768px) {
  .container {
    padding: var(--space-6);
  }
}

@media (min-width: 1024px) {
  .container {
    padding: var(--space-8);
  }
}
```

---

## 🌙 暗黑模式

暗黑模式自动通过 `[data-theme="dark"]` 属性切换：

```vue
<script setup>
import { useTheme } from '@/composables/useTheme';

const { currentTheme, toggleTheme } = useTheme();
</script>

<template>
  <button @click="toggleTheme">
    <Icon :name="currentTheme === 'dark' ? 'moon' : 'sun'" />
  </button>
</template>
```

所有设计令牌自动适配暗黑模式，无需额外代码。

---

## 🎯 最佳实践

### 1. 使用设计令牌而非硬编码
```css
/* ❌ 不要这样 */
.button {
  padding: 12px 16px;
  border-radius: 8px;
  color: #8B5CF6;
}

/* ✅ 应该这样 */
.button {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  color: var(--brand-primary-500);
}
```

### 2. 使用语义化颜色
```css
/* ❌ 不要这样 */
.error-message {
  color: #EF4444;
}

/* ✅ 应该这样 */
.error-message {
  color: var(--error-500);
}
```

### 3. 优先使用组件
```vue
<!-- ❌ 不要这样 -->
<button class="btn btn-primary">提交</button>

<!-- ✅ 应该这样 -->
<Button variant="primary">提交</Button>
```

### 4. 使用动画工具类
```vue
<!-- ❌ 不要这样 -->
<div class="custom-animation">...</div>

<style scoped>
.custom-animation {
  animation: fadeIn 0.3s ease-out;
}
@keyframes fadeIn { ... }
</style>

<!-- ✅ 应该这样 -->
<div class="animate-fadeIn">...</div>
```

---

## 🚀 下一步

### 待完成组件
- [ ] Dropdown - 下拉菜单
- [ ] Tabs - 选项卡
- [ ] Tooltip - 提示框
- [ ] Toast - 轻提示
- [ ] Input - 输入框
- [ ] Select - 下拉选择
- [ ] Checkbox - 复选框
- [ ] Radio - 单选框
- [ ] Switch - 开关

### 待优化页面
- [ ] ChatPanel - 消息气泡重设计
- [ ] AgentChat - 主页面布局升级
- [ ] TimelinePanel - 执行过程可视化

---

## 💡 问题与帮助

### Q: 如何自定义主色？
A: 修改 `variables.css` 中的 `--brand-primary-*` 系列变量。

### Q: 如何添加新图标？
A: 在 `Icon.vue` 的 `icons` 对象中添加新的SVG路径。

### Q: 如何自定义暗黑模式颜色？
A: 修改 `variables.css` 中的 `[data-theme="dark"]` 部分。

### Q: 动画太快/太慢？
A: 修改 `variables.css` 中的 `--duration-*` 变量。

---

**Designed with** 💜 **Cosmic Tech Design System**
