/**
 * UI Components - Cosmic Tech Design System
 * Export all UI components for easy imports
 *
 * Usage:
 * import { Icon, Modal, Button } from '@/components/ui';
 */

export { default as Icon } from './Icon.vue';
export { default as Modal } from './Modal.vue';
export { default as Button } from './Button.vue';

// Default export for convenience
export default {
    Icon: () => import('./Icon.vue'),
    Modal: () => import('./Modal.vue'),
    Button: () => import('./Button.vue'),
};
