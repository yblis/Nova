/**
 * UI State Component
 * Global Alpine.js component for sidebar, theme, and provider management
 */
function uiState() {
    return {
        path: window.location.pathname,
        online: navigator.onLine,
        toast: '',
        openNav: false,
        sidebarCollapsed: localStorage.getItem('sidebarCollapsed') === 'true',
        theme: localStorage.getItem('theme') || 'system',
        providers: [],
        activeProvider: null,
        providerTypes: {},

        toggleSidebar() {
            this.sidebarCollapsed = !this.sidebarCollapsed;
            localStorage.setItem('sidebarCollapsed', this.sidebarCollapsed.toString());
        },

        applyTheme() {
            const isDark = this.theme === 'dark' || (this.theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
            document.documentElement.classList.toggle('dark', isDark);
            localStorage.setItem('theme', this.theme);
        },

        setTheme(val) {
            this.theme = val;
            this.applyTheme();
        },

        async loadProviders() {
            // Use localStorage cache to avoid repeated API calls
            const cacheKey = 'providers_cache';
            const cacheExpiry = 'providers_cache_expiry';
            const now = Date.now();

            try {
                const cached = localStorage.getItem(cacheKey);
                const expiry = localStorage.getItem(cacheExpiry);
                // Cache valid for 30 seconds
                if (cached && expiry && now < parseInt(expiry)) {
                    const data = JSON.parse(cached);
                    this.providers = data.providers || [];
                    const activeId = data.active_provider_id;
                    this.activeProvider = this.providers.find(p => p.id === activeId) ||
                        (this.providers.length > 0 ? this.providers[0] : null);
                    return;
                }
            } catch (e) { /* localStorage unavailable or quota exceeded */ }

            try {
                const [providersRes, typesRes] = await Promise.all([
                    fetch('/api/settings/providers'),
                    fetch('/api/settings/provider-types')
                ]);
                if (providersRes.ok) {
                    const data = await providersRes.json();
                    // Save to cache
                    localStorage.setItem(cacheKey, JSON.stringify(data));
                    localStorage.setItem(cacheExpiry, (now + 30000).toString());

                    this.providers = data.providers || [];
                    const activeId = data.active_provider_id;
                    this.activeProvider = this.providers.find(p => p.id === activeId) ||
                        (this.providers.length > 0 ? this.providers[0] : null);
                }
                if (typesRes.ok) {
                    const data = await typesRes.json();
                    this.providerTypes = data.types || {};
                }
            } catch (e) { }
        },

        async switchProvider(id) {
            try {
                const r = await fetch('/api/settings/providers/active', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ provider_id: id })
                });
                if (r.ok) {
                    localStorage.removeItem('providers_cache');
                    localStorage.removeItem('providers_cache_expiry');
                    window.location.reload();
                }
            } catch (e) { }
        },

        getProviderTypeName(type) {
            return this.providerTypes[type]?.name || type;
        },

        init() {
            this.path = window.location.pathname;
            this.applyTheme();

            // Listen for theme changes from other components (like settings page)
            window.addEventListener('theme-change', (e) => {
                this.setTheme(e.detail);
            });

            // Listen for provider changes - invalidate cache
            window.addEventListener('providers-changed', () => {
                localStorage.removeItem('providers_cache');
                localStorage.removeItem('providers_cache_expiry');
                this.loadProviders();
            });

            // System preference change
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
                if (this.theme === 'system') this.applyTheme();
            });

            this.loadProviders();

            // Update path after HTMX navigation
            document.body.addEventListener('htmx:afterSettle', (e) => {
                this.path = window.location.pathname;
            });
        }
    };
}
