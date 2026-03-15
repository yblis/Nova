/**
 * Settings Page Component
 * Alpine.js component for the /settings page
 *
 * Methods are split into mixins loaded before this file:
 * - SettingsProvidersMixin  (settings-providers.js)
 * - SettingsIntegrationsMixin (settings-integrations.js)
 * - SettingsLlmMixin (settings-llm.js)
 */
(function () {
    const registerSettingsPage = () => {
        Alpine.data('settingsPage', () => ({
            // Load active tab from URL hash, localStorage, or default
            activeTab: (() => {
                const hash = window.location.hash.slice(1);
                const validTabs = ['general', 'providers', 'shortcuts', 'rag', 'llm', 'about', 'websearch', 'prompts', 'audio', 'email', 'bookstack'];
                if (hash && validTabs.includes(hash)) return hash;
                const stored = localStorage.getItem('settings_active_tab');
                if (stored && validTabs.includes(stored)) return stored;
                return 'providers';
            })(),
            theme: localStorage.getItem('theme') || 'system',
            mobileMenuOpen: false,  // Mobile sidebar toggle
            analytics: true,
            servers: [],
            activeServerId: null,
            formServer: { name: '', url: '' },
            editingId: null,
            ragConfig: {
                embedding_model: '',
                embedding_provider_id: '',
                embedding_providers: [],
                available_models: [],
                chunk_size: 500,
                chunk_overlap: 50,
                top_k: 5,
                // OCR Configuration
                ocr_provider: '',  // Format: "provider_type:provider_id"
                ocr_model: '',
                ocr_threshold: 50,
                ocr_models_available: [],
                ocr_configured_providers: [],
                // Qdrant Configuration
                use_qdrant: true,
                qdrant_available: false,
                qdrant_stats: null
            },
            ragLoading: false,
            ragSaving: false,
            ocrModelsLoading: false,
            // Web Search Config
            webSearchConfig: { searxng_url: '', max_results: 5, timeout: 10, is_available: false },
            webSearchLoading: false,
            webSearchSaving: false,
            webSearchTesting: false,
            webSearchTestMessage: '',
            webSearchTestSuccess: false,
            // LLM Config
            llmConfig: {
                default_system_prompt: '',
                temperature: 0.7,
                top_p: 0.9,
                top_k: 40,
                repeat_penalty: 1.1,
                num_ctx: 4096,
                auto_generate_title: true
            },
            llmLoading: false,
            llmSaving: false,
            // Text Prompts Config
            textPromptsSaving: false,
            textPromptsLoading: false,
            textPrompts: {},
            // Audio Config
            audioConfig: {
                stt_enabled: true,
                stt_provider_id: '',
                stt_model: '',
                tts_enabled: true,
                tts_provider_id: '',
                tts_model: '',
                tts_voice: '',
                tts_speed: 1.0,
                play_start_sound: false
            },
            audioLoading: false,
            audioSaving: false,
            // Email Config
            emailConfig: {
                reception_protocol: 'imap',
                imap_host: '', imap_port: 993, imap_encryption: 'ssl',
                pop3_host: '', pop3_port: 995, pop3_encryption: 'tls',
                smtp_host: '', smtp_port: 587, smtp_encryption: 'starttls',
                email_address: '', auth_type: 'password', password: '',
                oauth2_client_id: '', oauth2_client_secret: '',
                default_folder: 'INBOX', max_emails: 10, timeout: 30,
                auto_summarize: false, include_attachments_info: true,
                is_available: false
            },
            emailPresets: [],
            emailLoading: false,
            emailSaving: false,
            emailTesting: false,
            emailTestMessage: '',
            emailTestSuccess: false,
            emailTestResults: null,
            // Bookstack Config
            bookstackConfig: { url: '', token_id: '', token_secret: '', token_secret_masked: '', max_results: 5, timeout: 15, is_available: false },
            bookstackLoading: false,
            bookstackSaving: false,
            bookstackTesting: false,
            bookstackTestMessage: '',
            bookstackTestSuccess: false,
            showBookstackSecret: false,

            // ============== LLM Providers Management ==============
            providers: [],
            activeProviderId: null,
            providerTypes: {},
            formProvider: { name: '', type: 'ollama', url: '', api_key: '', extra_headers: {} },
            editingProviderId: null,
            testingProviderId: null,
            testResult: null,
            providerModels: {},
            providersLoading: false,
            providersSaving: false,
            showApiKey: false,

            // ============== Mixins ==============
            ...window.SettingsProvidersMixin,
            ...window.SettingsIntegrationsMixin,
            ...window.SettingsLlmMixin,

            // ============== Core Methods ==============

            async init() {
                await this.loadProviders();

                // Update URL hash to match current tab
                if (window.location.hash.slice(1) !== this.activeTab) {
                    history.replaceState(null, '', '#' + this.activeTab);
                }

                // Load data for the current tab
                this.loadTabData(this.activeTab);

                // Watch activeTab changes - persist and sync with URL
                this.$watch('activeTab', (newTab) => {
                    localStorage.setItem('settings_active_tab', newTab);
                    history.replaceState(null, '', '#' + newTab);
                    this.loadTabData(newTab);
                });

                // Listen for hash changes (browser back/forward)
                window.addEventListener('hashchange', () => {
                    const hash = window.location.hash.slice(1);
                    const validTabs = ['general', 'providers', 'shortcuts', 'rag', 'llm', 'about', 'websearch', 'prompts', 'audio', 'email', 'bookstack'];
                    if (hash && validTabs.includes(hash) && hash !== this.activeTab) {
                        this.activeTab = hash;
                    }
                });
            },

            // Load data based on tab
            loadTabData(tab) {
                switch (tab) {
                    case 'providers': this.loadProviders(); break;
                    case 'rag': this.loadRagConfig(); break;
                    case 'llm': this.loadLlmConfig(); break;
                    case 'websearch': this.loadWebSearchConfig(); break;
                    case 'textprompts': this.loadTextPromptsConfig(); break;
                    case 'audio': this.loadAudioConfig(); break;
                    case 'email': this.loadEmailConfig(); break;
                    case 'bookstack': this.loadBookstackConfig(); break;
                }
            },

            setTab(tab) {
                this.activeTab = tab;
            },

            updateTheme(val) {
                this.theme = val;
                window.dispatchEvent(new CustomEvent('theme-change', { detail: val }));
            }
        }));
    };

    // Register immediately if Alpine is already initialized (SPA navigation)
    // Otherwise register on alpine:init event (fresh page load)
    if (typeof Alpine !== 'undefined' && Alpine.version) {
        registerSettingsPage();
        console.log('[settings-page.js] Registered immediately (SPA navigation)');
    } else {
        document.addEventListener('alpine:init', () => {
            registerSettingsPage();
            console.log('[settings-page.js] Registered via alpine:init event');
        });
    }
})();
