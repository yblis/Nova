/**
 * Toast Notification Utility
 * Provides global showToast function for user notifications
 */
window.showToast = function (message, duration = 4000) {
    const container = document.getElementById('toast-container');
    if (!container) {
        console.warn('Toast container not found');
        return;
    }

    const toast = document.createElement('div');
    toast.className = 'pointer-events-auto rounded-xl bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 px-4 py-3 shadow-xl font-medium text-sm flex items-center gap-3 self-end';
    toast.innerHTML = `
    <span>${message}</span>
    <button onclick="this.parentElement.remove()" class="text-zinc-500 hover:text-zinc-300 dark:text-zinc-400 dark:hover:text-zinc-600">
      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
      </svg>
    </button>
  `;

    container.appendChild(toast);
    setTimeout(() => toast.remove(), duration);
};
