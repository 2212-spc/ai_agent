import { ref, onMounted, watch } from 'vue';

export function useTheme() {
    const currentTheme = ref('light');

    function toggleTheme() {
        const newTheme = currentTheme.value === 'light' ? 'dark' : 'light';
        setTheme(newTheme);
    }

    function setTheme(theme) {
        currentTheme.value = theme;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    }

    function initTheme() {
        const savedTheme = localStorage.getItem('theme') || 'light';
        setTheme(savedTheme);
    }

    onMounted(() => {
        initTheme();
    });

    watch(currentTheme, (newTheme) => {
        console.log(`主题切换到: ${newTheme}`);
    });

    return {
        currentTheme,
        toggleTheme,
        setTheme
    };
}
