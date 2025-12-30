/**
 * Theme initialization - Prevents flash of unstyled content (FOUC)
 * This script must be loaded synchronously in the <head> section
 */
(function () {
    try {
        const savedTheme = localStorage.getItem('theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

        if (savedTheme === 'dark' || ((!savedTheme || savedTheme === 'system') && prefersDark)) {
            document.documentElement.classList.add('dark');
        }
    } catch (e) {
        // localStorage unavailable, fall back to system preference
    }
})();
