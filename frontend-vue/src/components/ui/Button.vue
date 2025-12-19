<script setup>
/**
 * Button Component - Premium, animated buttons with multiple variants
 * Features: Loading states, sizes, variants, icons, animations
 */

import { computed } from 'vue';
import Icon from './Icon.vue';

const props = defineProps({
    variant: {
        type: String,
        default: 'primary',
        validator: (v) => ['primary', 'secondary', 'ghost', 'danger', 'success', 'gradient'].includes(v)
    },
    size: {
        type: String,
        default: 'md',
        validator: (v) => ['xs', 'sm', 'md', 'lg', 'xl'].includes(v)
    },
    loading: {
        type: Boolean,
        default: false
    },
    disabled: {
        type: Boolean,
        default: false
    },
    icon: {
        type: String,
        default: ''
    },
    iconPosition: {
        type: String,
        default: 'left',
        validator: (v) => ['left', 'right'].includes(v)
    },
    iconOnly: {
        type: Boolean,
        default: false
    },
    type: {
        type: String,
        default: 'button'
    },
    block: {
        type: Boolean,
        default: false
    }
});

defineEmits(['click']);

const buttonClasses = computed(() => [
    'btn',
    `btn-${props.variant}`,
    `btn-${props.size}`,
    {
        'btn-loading': props.loading,
        'btn-disabled': props.disabled,
        'btn-icon-only': props.iconOnly,
        'btn-block': props.block
    }
]);

const iconSize = computed(() => {
    const sizes = { xs: 14, sm: 16, md: 18, lg: 20, xl: 22 };
    return sizes[props.size] || 18;
});
</script>

<template>
    <button
        :type="type"
        :class="buttonClasses"
        :disabled="disabled || loading"
        @click="$emit('click', $event)"
    >
        <!-- Loading Spinner -->
        <span v-if="loading" class="btn-spinner">
            <svg viewBox="0 0 24 24" fill="none" :width="iconSize" :height="iconSize">
                <circle
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    stroke-width="3"
                    stroke-linecap="round"
                    class="spinner-track"
                />
                <path
                    d="M12 2a10 10 0 0 1 10 10"
                    stroke="currentColor"
                    stroke-width="3"
                    stroke-linecap="round"
                    class="spinner-head"
                />
            </svg>
        </span>

        <!-- Left Icon -->
        <Icon
            v-else-if="icon && iconPosition === 'left'"
            :name="icon"
            :size="iconSize"
            class="btn-icon"
        />

        <!-- Content -->
        <span v-if="!iconOnly" class="btn-content">
            <slot />
        </span>

        <!-- Right Icon -->
        <Icon
            v-if="icon && iconPosition === 'right' && !loading"
            :name="icon"
            :size="iconSize"
            class="btn-icon"
        />
    </button>
</template>

<style scoped>
/* Base Button */
.btn {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    font-family: var(--font-body);
    font-weight: var(--font-medium);
    line-height: 1;
    white-space: nowrap;
    border: none;
    border-radius: var(--radius-lg);
    cursor: pointer;
    user-select: none;
    transition: all var(--transition-fast);
    outline: none;
}

.btn:focus-visible {
    box-shadow: 0 0 0 3px var(--brand-primary-200);
}

.btn:active:not(:disabled) {
    transform: scale(0.98);
}

/* Sizes */
.btn-xs {
    height: 28px;
    padding: 0 var(--space-2);
    font-size: var(--text-xs);
    border-radius: var(--radius-md);
}

.btn-sm {
    height: 32px;
    padding: 0 var(--space-3);
    font-size: var(--text-sm);
}

.btn-md {
    height: 40px;
    padding: 0 var(--space-4);
    font-size: var(--text-sm);
}

.btn-lg {
    height: 48px;
    padding: 0 var(--space-6);
    font-size: var(--text-base);
}

.btn-xl {
    height: 56px;
    padding: 0 var(--space-8);
    font-size: var(--text-lg);
    border-radius: var(--radius-xl);
}

/* Icon Only */
.btn-icon-only {
    padding: 0;
}

.btn-icon-only.btn-xs { width: 28px; }
.btn-icon-only.btn-sm { width: 32px; }
.btn-icon-only.btn-md { width: 40px; }
.btn-icon-only.btn-lg { width: 48px; }
.btn-icon-only.btn-xl { width: 56px; }

/* Block */
.btn-block {
    display: flex;
    width: 100%;
}

/* Variants */
.btn-primary {
    background: var(--brand-primary-500);
    color: white;
    box-shadow: var(--shadow-sm), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.btn-primary:hover:not(:disabled) {
    background: var(--brand-primary-600);
    box-shadow: var(--shadow-md), var(--shadow-brand);
    transform: translateY(-1px);
}

.btn-secondary {
    background: var(--bg-tertiary);
    color: var(--text-primary);
    border: 1px solid var(--border-primary);
}

.btn-secondary:hover:not(:disabled) {
    background: var(--hover-bg);
    border-color: var(--border-secondary);
}

.btn-ghost {
    background: transparent;
    color: var(--text-secondary);
}

.btn-ghost:hover:not(:disabled) {
    background: var(--hover-bg);
    color: var(--text-primary);
}

.btn-danger {
    background: var(--error-500);
    color: white;
}

.btn-danger:hover:not(:disabled) {
    background: var(--error-600);
    box-shadow: var(--shadow-error);
}

.btn-success {
    background: var(--success-500);
    color: white;
}

.btn-success:hover:not(:disabled) {
    background: var(--success-600);
    box-shadow: var(--shadow-success);
}

.btn-gradient {
    background: var(--gradient-primary);
    color: white;
    box-shadow: var(--shadow-brand);
}

.btn-gradient:hover:not(:disabled) {
    box-shadow: var(--shadow-brand-lg);
    transform: translateY(-2px);
}

/* Disabled State */
.btn-disabled,
.btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    pointer-events: none;
}

/* Loading State */
.btn-loading {
    position: relative;
    cursor: wait;
}

.btn-spinner {
    display: flex;
    align-items: center;
    justify-content: center;
}

.spinner-track {
    opacity: 0.25;
}

.spinner-head {
    animation: spin 0.75s linear infinite;
    transform-origin: center;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* Content */
.btn-content {
    display: inline-flex;
    align-items: center;
}

/* Icon */
.btn-icon {
    flex-shrink: 0;
}

/* Dark Mode */
[data-theme="dark"] .btn-primary {
    box-shadow: var(--shadow-sm), inset 0 1px 0 rgba(255, 255, 255, 0.15);
}

[data-theme="dark"] .btn-secondary {
    background: var(--slate-800);
    border-color: var(--slate-600);
}

[data-theme="dark"] .btn-secondary:hover:not(:disabled) {
    background: var(--slate-700);
}
</style>
