import { createApp } from 'vue';
import { createPinia } from 'pinia';
import router from './router';
import App from './App.vue';

// 导入全局样式 - Cosmic Tech Design System
import './assets/styles/variables.css';      // Design tokens
import './assets/styles/animations.css';     // Animation system
import './assets/styles/base.css';           // Base styles
import './assets/styles/components.css';     // Component styles
import './assets/styles/responsive.css';     // Responsive design

const app = createApp(App);

app.use(createPinia());
app.use(router);

app.mount('#app');
