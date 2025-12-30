/**
 * Copy Code Block Utility
 * Provides global copyCodeBlock function for copying code snippets
 */
window.copyCodeBlock = function (button) {
    const wrapper = button.closest('.code-block-wrapper');
    const codeBlock = wrapper.querySelector('pre code') || wrapper.querySelector('pre');
    const text = codeBlock ? codeBlock.textContent : '';

    navigator.clipboard.writeText(text).then(() => {
        // Visual feedback: change icon to checkmark
        const originalSvg = button.innerHTML;
        button.innerHTML = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>';
        button.classList.add('copied');

        setTimeout(() => {
            button.innerHTML = originalSvg;
            button.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
        showToast('Erreur lors de la copie');
    });
};
