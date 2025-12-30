/**
 * i18n.js - Internationalization service for Nova
 * 
 * Uses Alpine.js store for reactivity.
 */

(function () {
    'use strict';

    const SUPPORTED_LOCALES = ['fr', 'en'];
    const DEFAULT_LOCALE = 'fr';
    const STORAGE_KEY = 'locale';

    // Use the path provided by Flask, or fallback
    const getLocalesPath = () => window.LOCALES_PATH || '/static/locales/';

    // Define the store logic
    const i18nStore = {
        locale: DEFAULT_LOCALE,
        translations: {},
        loaded: false,

        async init() {
            const savedLocale = localStorage.getItem(STORAGE_KEY);
            const browserLocale = navigator.language?.split('-')[0];

            let targetLocale = DEFAULT_LOCALE;
            if (savedLocale && SUPPORTED_LOCALES.includes(savedLocale)) {
                targetLocale = savedLocale;
            } else if (browserLocale && SUPPORTED_LOCALES.includes(browserLocale)) {
                targetLocale = browserLocale;
            }

            await this.loadLocale(targetLocale);
        },

        async loadLocale(locale) {
            if (!SUPPORTED_LOCALES.includes(locale)) locale = DEFAULT_LOCALE;

            try {
                const basePath = getLocalesPath();
                const url = `${basePath}${locale}.json`;
                console.log(`[i18n] Loading: ${url}`);

                const response = await fetch(url);
                if (!response.ok) throw new Error(response.statusText);

                const data = await response.json();

                // Update state - Alpine will react to this
                this.translations = data;
                this.locale = locale;
                this.loaded = true;

                localStorage.setItem(STORAGE_KEY, locale);
                document.documentElement.lang = locale;

                console.log(`[i18n] Loaded: ${locale}`);
            } catch (error) {
                console.error('[i18n] Error:', error);
            }
        },

        t(key, fallback = null, params = {}) {
            // Accessing this.translations makes it reactive
            const currentTranslations = this.translations || {};

            if (!key) return fallback || '';

            const keys = key.split('.');
            let value = currentTranslations;

            for (const k of keys) {
                if (value && typeof value === 'object' && k in value) {
                    value = value[k];
                } else {
                    value = fallback !== null ? fallback : key;
                    break;
                }
            }

            let result = typeof value === 'string' ? value : (fallback || key);

            // Interpolation
            if (params && typeof params === 'object') {
                Object.keys(params).forEach(p => {
                    result = result.replace(new RegExp(`{${p}}`, 'g'), params[p]);
                });
            }

            return result;
        }
    };

    // Helper to expose t() globally
    window.t = function (key, fallback, params) {
        // If Alpine is ready and store exists, use it
        if (window.Alpine && window.Alpine.store('i18n')) {
            return window.Alpine.store('i18n').t(key, fallback, params);
        }
        return fallback || key; // Fallback before Alpine loads
    };

    // Register with Alpine
    document.addEventListener('alpine:init', () => {
        Alpine.store('i18n', i18nStore);
        // Initialize the store
        Alpine.store('i18n').init();
    });

    // Also expose setLocale globally for the settings page usage
    window.i18n = {
        setLocale: async (code) => {
            if (window.Alpine && window.Alpine.store('i18n')) {
                await window.Alpine.store('i18n').loadLocale(code);
                // Reload to be sure everything is clean (optional but requested)
                window.location.reload();
            }
        },
        getLocale: () => localStorage.getItem(STORAGE_KEY) || DEFAULT_LOCALE
    };

})();
