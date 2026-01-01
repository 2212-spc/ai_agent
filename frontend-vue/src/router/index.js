import { createRouter, createWebHistory } from 'vue-router';

const routes = [
    {
        path: '/',
        redirect: '/chat'
    },
    {
        path: '/chat',
        name: 'AgentChat',
        component: () => import('../views/AgentChat.vue')
    },
    {
        path: '/history',
        name: 'History',
        component: () => import('../views/ConversationHistory.vue')
    },
    {
        path: '/settings',
        name: 'Settings',
        component: () => import('../views/ConversationSettings.vue')
    },
    {
        path: '/knowledge',
        name: 'Knowledge',
        component: () => import('../views/KnowledgeBase.vue')
    },
    {
        path: '/prompts',
        name: 'Prompts',
        component: () => import('../views/PromptManagement.vue')
    },
    {
        path: '/memory',
        name: 'Memory',
        component: () => import('../views/Memory.vue')
    },
    {
        path: '/login',
        name: 'Login',
        component: () => import('../views/Login.vue')
    },
    {
        path: '/register',
        name: 'Register',
        component: () => import('../views/Register.vue')
    },
    {
        path: '/agent/builder',
        name: 'AgentBuilder',
        component: () => import('../views/AgentBuilderHome.vue')
    },
    {
        path: '/agent/edit',
        name: 'AgentEditor',
        component: () => import('../views/AgentEditor.vue')
    }
];

const router = createRouter({
    history: createWebHistory(),
    routes
});

export default router;
