/**
 * Confirmation Modal Component
 * Provides confirmModal Alpine component and global showConfirmDialog helper
 */

// Global Confirmation Modal Component for Alpine.js
function confirmModal() {
    return {
        isOpen: false,
        title: 'Confirmer',
        message: '',
        type: 'danger',
        confirmText: 'Confirmer',
        onConfirm: null,
        onCancel: null,

        open(detail) {
            this.title = detail.title || 'Confirmer';
            this.message = detail.message || 'Êtes-vous sûr ?';
            this.type = detail.type || 'danger';
            this.confirmText = detail.confirmText || 'Confirmer';
            this.onConfirm = detail.onConfirm || null;
            this.onCancel = detail.onCancel || null;
            this.isOpen = true;
        },

        confirm() {
            this.isOpen = false;
            if (this.onConfirm) this.onConfirm();
        },

        cancel() {
            this.isOpen = false;
            if (this.onCancel) this.onCancel();
        }
    };
}

// Helper function to show confirmation dialog
window.showConfirmDialog = function (options) {
    window.dispatchEvent(new CustomEvent('confirm-dialog', { detail: options }));
};
