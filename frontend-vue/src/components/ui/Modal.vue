<script setup>
/**
 * Modal Component - Beautiful, accessible overlay dialog
 * Features: backdrop blur, staggered animations, keyboard support
 */

import { onMounted, onUnmounted, watch } from 'vue';
import Icon from './Icon.vue';

const props = defineProps({
    open: {
        type: Boolean,
        required: true
    },
    title: {
        type: String,
        default: ''
    },
    size: {
        type: String,
        default: 'md', // 'sm', 'md', 'lg', 'xl'
        validator: (value) => ['sm', 'md', 'lg', 'xl', 'full'].includes(value)
    },
    showClose: {
        type: Boolean,
        default: true
    },
    closeOnBackdrop: {
        type: Boolean,
        default: true
    },
    closeOnEsc: {
        type: Boolean,
        default: true
    }
});

const emit = defineEmits(['close', 'opened', 'closed']);

function handleBackdropClick() {
    if (props.closeOnBackdrop) {
        emit('close');
    }
}

function handleEscape(e) {
    if (e.key === 'Escape' && props.closeOnEsc && props.open) {
        emit('close');
    }
}

watch(() => props.open, (isOpen) => {
    if (isOpen) {
        document.body.style.overflow = 'hidden';
        emit('opened');
    } else {
        document.body.style.overflow = '';
        emit('closed');
    }
});

onMounted(() => {
    document.addEventListener('keydown', handleEscape);
    if (props.open) {
        document.body.style.overflow = 'hidden';
    }
});

onUnmounted(() => {
    document.removeEventListener('keydown', handleEscape);
    document.body.style.overflow = '';
});
</script>

<template>
    <Teleport to="body">
        <!-- Backdrop -->
        <Transition name="fade">
            <div
                v-if="open"
                class="modal-backdrop"
                @click="handleBackdropClick"
                aria-hidden="true"
            ></div>
        </Transition>

        <!-- Modal Content -->
        <Transition name="modal">
            <div
                v-if="open"
                role="dialog"
                aria-modal="true"
                :aria-labelledby="title ? 'modal-title' : undefined"
                class="modal-container"
                @click.stop
            >
                <div :class="['modal-content', `modal-${size}`]" @click.stop>
                    <!-- Header -->
                    <div v-if="title || showClose || $slots.header" class="modal-header">
                        <slot name="header">
                            <h2 v-if="title" id="modal-title" class="modal-title">{{ title }}</h2>
                        </slot>
                        <button
                            v-if="showClose"
                            type="button"
                            class="modal-close"
                            @click="emit('close')"
                            aria-label="Close modal"
                        >
                            <Icon name="x" :size="20" />
                        </button>
                    </div>

                    <!-- Body -->
                    <div class="modal-body">
                        <slot />
                    </div>

                    <!-- Footer -->
                    <div v-if="$slots.footer" class="modal-footer">
                        <slot name="footer" />
                    </div>
                </div>
            </div>
        </Transition>
    </Teleport>
</template>

<style scoped>
/* Backdrop with blur */
.modal-backdrop {
    position: fixed;
    inset: 0;
    background: var(--bg-overlay);
    backdrop-filter: blur(var(--blur-md));
    -webkit-backdrop-filter: blur(var(--blur-md));
    z-index: var(--z-modal-backdrop);
}

/* Modal Container - Flex centered */
.modal-container {
    position: fixed;
    inset: 0;
    z-index: var(--z-modal);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-4);
    overflow-y: auto;
}

/* Modal Content */
.modal-content {
    position: relative;
    background: var(--bg-primary);
    border-radius: var(--radius-2xl);
    box-shadow: var(--shadow-2xl), 0 0 0 1px rgba(0, 0, 0, 0.05);
    max-height: calc(100vh - 2rem);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    width: 100%;
}

/* Sizes */
.modal-sm { max-width: 400px; }
.modal-md { max-width: 600px; }
.modal-lg { max-width: 800px; }
.modal-xl { max-width: 1200px; }
.modal-full {
    max-width: calc(100vw - 2rem);
    max-height: calc(100vh - 2rem);
}

/* Header */
.modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-6);
    border-bottom: 1px solid var(--border-primary);
    background: var(--bg-secondary);
    border-radius: var(--radius-2xl) var(--radius-2xl) 0 0;
}

.modal-title {
    font-size: var(--text-xl);
    font-weight: var(--font-semibold);
    font-family: var(--font-display);
    color: var(--text-primary);
    margin: 0;
}

.modal-close {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    border: none;
    background: transparent;
    border-radius: var(--radius-lg);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
}

.modal-close:hover {
    background: var(--hover-bg);
    color: var(--text-primary);
}

.modal-close:active {
    transform: scale(0.95);
}

/* Body */
.modal-body {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-6);
    color: var(--text-primary);
    line-height: var(--leading-relaxed);
}

/* Footer */
.modal-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--space-3);
    padding: var(--space-6);
    border-top: 1px solid var(--border-primary);
    background: var(--bg-secondary);
}

/* Animations */
.fade-enter-active,
.fade-leave-active {
    transition: opacity var(--duration-slow) var(--ease-out);
}

.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}

.modal-enter-active {
    transition: all var(--duration-slow) var(--ease-out);
    transition-delay: 50ms;
}

.modal-leave-active {
    transition: all var(--duration-normal) var(--ease-in);
}

.modal-enter-from {
    opacity: 0;
    transform: scale(0.95) translateY(20px);
}

.modal-enter-to {
    opacity: 1;
    transform: scale(1) translateY(0);
}

.modal-leave-from {
    opacity: 1;
    transform: scale(1);
}

.modal-leave-to {
    opacity: 0;
    transform: scale(0.95);
}

/* Responsive */
@media (max-width: 640px) {
    .modal-container {
        padding: var(--space-2);
        align-items: flex-end;
    }

    .modal-content {
        max-height: calc(100vh - 1rem);
        border-radius: var(--radius-2xl) var(--radius-2xl) 0 0;
    }

    .modal-header,
    .modal-body,
    .modal-footer {
        padding: var(--space-4);
    }

    .modal-title {
        font-size: var(--text-lg);
    }
}

/* Dark mode enhancements */
[data-theme="dark"] .modal-backdrop {
    background: rgba(0, 0, 0, 0.8);
}

[data-theme="dark"] .modal-content {
    box-shadow: var(--shadow-2xl), 0 0 0 1px rgba(255, 255, 255, 0.05);
}
</style>
