import { createApp } from 'vue';
import { createPinia } from 'pinia';
import router from './router';
import App from './App.vue';

// 导入全局样式
import './assets/styles/variables.css';
import './assets/styles/base.css';
import './assets/styles/components.css';
import './assets/styles/responsive.css';

const app = createApp(App);

app.use(createPinia());
app.use(router);

app.mount('#app');
