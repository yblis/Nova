/**
 * Settings Page Component
 * Alpine.js component for the /settings page
 */
(function () {
    const registerSettingsPage = () => {
        Alpine.data('settingsPage', () => ({
            // Load active tab from URL hash, localStorage, or default
            activeTab: (() => {
                const hash = window.location.hash.slice(1);
                const validTabs = ['general', 'providers', 'shortcuts', 'rag', 'llm', 'about', 'websearch', 'textprompts', 'audio'];
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
                    const validTabs = ['general', 'providers', 'shortcuts', 'rag', 'llm', 'about', 'websearch', 'textprompts', 'audio'];
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
                }
            },

            setTab(tab) {
                this.activeTab = tab;
            },

            async loadServers() {
                try {
                    const r = await fetch('/api/settings/servers');
                    if (r.ok) {
                        const data = await r.json();
                        this.servers = data.servers;
                        this.activeServerId = data.active_server_id;
                    }
                } catch (e) {
                    console.error("Failed to load servers", e);
                }
            },

            updateTheme(val) {
                this.theme = val;
                window.dispatchEvent(new CustomEvent('theme-change', { detail: val }));
            },

            editServer(server) {
                this.editingId = server.id;
                this.formServer = { name: server.name, url: server.url };
            },

            cancelEdit() {
                this.editingId = null;
                this.formServer = { name: '', url: '' };
            },

            async saveServer() {
                const name = this.formServer.name.trim();
                const url = this.formServer.url.trim();
                if (!name || !url) return;
                try {
                    let r;
                    if (this.editingId) {
                        r = await fetch(`/api/settings/servers/${this.editingId}`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ name, url })
                        });
                    } else {
                        r = await fetch('/api/settings/servers', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ name, url })
                        });
                    }
                    if (r.ok) {
                        await r.json();
                        this.cancelEdit();
                        await this.loadServers();
                        showToast(this.editingId ? 'Server updated!' : 'Server added!');
                        window.dispatchEvent(new CustomEvent('servers-changed'));
                    } else {
                        showToast((await r.json()).error || 'Failed to save server');
                    }
                } catch (e) {
                    showToast('Error saving server');
                }
            },

            async deleteServer(id) {
                if (!confirm('Delete this server?')) return;
                try {
                    const r = await fetch(`/api/settings/servers/${id}`, { method: 'DELETE' });
                    if (r.ok) {
                        await this.loadServers();
                        window.dispatchEvent(new CustomEvent('servers-changed'));
                    }
                } catch (e) {
                    showToast('Error deleting server');
                }
            },

            async setActiveServer(id) {
                try {
                    const r = await fetch('/api/settings/servers/active', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ server_id: id })
                    });
                    if (r.ok) {
                        this.activeServerId = id;
                        window.dispatchEvent(new CustomEvent('servers-changed'));
                        showToast('Active server switched!');
                    }
                } catch (e) {
                    showToast('Error switching server');
                }
            },

            async loadRagConfig() {
                this.ragLoading = true;
                try {
                    const r = await fetch('/api/rag/config');
                    if (r.ok) {
                        const data = await r.json();
                        this.ragConfig = {
                            embedding_model: data.embedding_model || '',
                            embedding_provider_id: data.embedding_provider_id || '',
                            embedding_providers: data.embedding_providers || [],
                            available_models: data.available_models || [],
                            chunk_size: data.chunk_size || 500,
                            chunk_overlap: data.chunk_overlap || 50,
                            top_k: data.top_k || 5,
                            // OCR
                            ocr_provider: data.ocr_provider || '',
                            ocr_model: data.ocr_model || '',
                            ocr_threshold: data.ocr_threshold || 50,
                            ocr_models_available: [],
                            ocr_configured_providers: [],
                            // Qdrant
                            use_qdrant: data.use_qdrant !== undefined ? data.use_qdrant : true,
                            qdrant_available: data.qdrant_available || false,
                            qdrant_stats: data.qdrant_stats || null
                        };
                        // Load OCR providers
                        await this.loadOcrProviders();
                        // If a provider is already selected, load its models
                        if (this.ragConfig.ocr_provider) {
                            this.loadOcrModels(this.ragConfig.ocr_provider);
                        }
                    }
                } catch (e) {
                    console.error('Failed to load RAG config', e);
                } finally {
                    this.ragLoading = false;
                }
            },

            async saveRagConfig() {
                this.ragSaving = true;
                try {
                    const r = await fetch('/api/rag/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            embedding_model: this.ragConfig.embedding_model,
                            embedding_provider_id: this.ragConfig.embedding_provider_id,
                            chunk_size: this.ragConfig.chunk_size,
                            chunk_overlap: this.ragConfig.chunk_overlap,
                            top_k: this.ragConfig.top_k,
                            ocr_provider: this.ragConfig.ocr_provider,
                            ocr_model: this.ragConfig.ocr_model,
                            ocr_threshold: this.ragConfig.ocr_threshold,
                            use_qdrant: this.ragConfig.use_qdrant
                        })
                    });
                    if (r.ok) {
                        showToast('Configuration RAG enregistrée !');
                    } else {
                        showToast((await r.json()).error || 'Erreur lors de l\'enregistrement');
                    }
                } catch (e) {
                    console.error('Failed to save RAG config', e);
                    showToast('Erreur lors de l\'enregistrement');
                } finally {
                    this.ragSaving = false;
                }
            },

            async loadOcrProviders() {
                // Load configured providers list
                try {
                    const r = await fetch('/api/rag/ocr-providers');
                    if (r.ok) {
                        const data = await r.json();
                        this.ragConfig.ocr_configured_providers = data.providers || [];
                    }
                } catch (e) {
                    console.error('Failed to load OCR providers', e);
                }
            },

            async loadEmbeddingModels(providerId) {
                // Load embedding models for a specific provider
                try {
                    const url = providerId 
                        ? `/api/rag/embedding-models?provider_id=${encodeURIComponent(providerId)}`
                        : '/api/rag/embedding-models';
                    const r = await fetch(url);
                    if (r.ok) {
                        const data = await r.json();
                        this.ragConfig.available_models = data.models || [];
                        // Reset model selection if the current model is not in the list
                        if (this.ragConfig.available_models.length > 0) {
                            const currentModelExists = this.ragConfig.available_models.some(
                                m => m.name === this.ragConfig.embedding_model
                            );
                            if (!currentModelExists) {
                                this.ragConfig.embedding_model = '';
                            }
                        }
                    }
                } catch (e) {
                    console.error('Failed to load embedding models', e);
                }
            },

            async loadOcrModels(providerKey) {
                // providerKey format: "provider_type:provider_id"
                if (!providerKey) {
                    this.ragConfig.ocr_models_available = [];
                    return;
                }
                this.ocrModelsLoading = true;
                try {
                    const r = await fetch(`/api/rag/ocr-models?provider=${encodeURIComponent(providerKey)}`);
                    if (r.ok) {
                        const data = await r.json();
                        this.ragConfig.ocr_models_available = data.models || [];
                    }
                } catch (e) {
                    console.error('Failed to load OCR models', e);
                } finally {
                    this.ocrModelsLoading = false;
                }
            },

            // Web Search Methods
            async loadWebSearchConfig() {
                this.webSearchLoading = true;
                this.webSearchTestMessage = '';
                try {
                    const r = await fetch('/api/settings/web_search/config');
                    if (r.ok) {
                        const data = await r.json();
                        this.webSearchConfig = {
                            searxng_url: data.searxng_url || '',
                            max_results: data.max_results || 5,
                            timeout: data.timeout || 10,
                            is_available: data.is_available || false
                        };
                    }
                } catch (e) {
                    console.error('Failed to load web search config', e);
                } finally {
                    this.webSearchLoading = false;
                }
            },

            async saveWebSearchConfig() {
                this.webSearchSaving = true;
                try {
                    const r = await fetch('/api/settings/web_search/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            searxng_url: this.webSearchConfig.searxng_url,
                            max_results: this.webSearchConfig.max_results,
                            timeout: this.webSearchConfig.timeout
                        })
                    });
                    if (r.ok) {
                        showToast('Configuration recherche web enregistrée !');
                        // Reload to update is_available
                        await this.loadWebSearchConfig();
                    } else {
                        const data = await r.json();
                        showToast(data.error || 'Erreur lors de l\'enregistrement');
                    }
                } catch (e) {
                    console.error('Failed to save web search config', e);
                    showToast('Erreur lors de l\'enregistrement');
                } finally {
                    this.webSearchSaving = false;
                }
            },

            async testWebSearch() {
                this.webSearchTesting = true;
                this.webSearchTestMessage = '';
                try {
                    // First save the URL
                    const saveR = await fetch('/api/settings/web_search/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ searxng_url: this.webSearchConfig.searxng_url })
                    });
                    if (!saveR.ok) {
                        const data = await saveR.json();
                        this.webSearchTestMessage = data.error || 'URL invalide';
                        this.webSearchTestSuccess = false;
                        return;
                    }
                    // Then test
                    const r = await fetch('/api/settings/web_search/test', { method: 'POST' });
                    const data = await r.json();
                    if (r.ok && data.ok) {
                        this.webSearchTestMessage = data.message;
                        this.webSearchTestSuccess = true;
                        this.webSearchConfig.is_available = true;
                    } else {
                        this.webSearchTestMessage = data.error || 'Échec du test';
                        this.webSearchTestSuccess = false;
                        this.webSearchConfig.is_available = false;
                    }
                } catch (e) {
                    console.error('Failed to test web search', e);
                    this.webSearchTestMessage = 'Erreur de connexion';
                    this.webSearchTestSuccess = false;
                } finally {
                    this.webSearchTesting = false;
                }
            },

            // LLM Config Methods
            async loadLlmConfig() {
                this.llmLoading = true;
                try {
                    const r = await fetch('/api/settings/llm/config');
                    if (r.ok) {
                        const data = await r.json();
                        this.llmConfig = {
                            default_system_prompt: data.default_system_prompt || '',
                            temperature: data.temperature !== undefined ? data.temperature : 0.7,
                            top_p: data.top_p !== undefined ? data.top_p : 0.9,
                            top_k: data.top_k !== undefined ? data.top_k : 40,
                            repeat_penalty: data.repeat_penalty !== undefined ? data.repeat_penalty : 1.1,
                            num_ctx: data.num_ctx !== undefined ? data.num_ctx : 4096,
                            auto_generate_title: data.auto_generate_title !== undefined ? data.auto_generate_title : true
                        };
                    }
                } catch (e) {
                    console.error('Failed to load LLM config', e);
                } finally {
                    this.llmLoading = false;
                }
            },

            async saveLlmConfig() {
                this.llmSaving = true;
                try {
                    const r = await fetch('/api/settings/llm/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(this.llmConfig)
                    });
                    if (r.ok) {
                        showToast('Configuration LLM enregistrée !');
                    } else {
                        const data = await r.json();
                        showToast(data.error || 'Erreur lors de l\'enregistrement');
                    }
                } catch (e) {
                    console.error('Failed to save LLM config', e);
                    showToast('Erreur lors de l\'enregistrement');
                } finally {
                    this.llmSaving = false;
                }
            },

            // Text Prompts Methods
            async loadTextPromptsConfig() {
                this.textPromptsLoading = true;
                try {
                    const r = await fetch('/api/texts/prompts');
                    if (r.ok) {
                        const data = await r.json();
                        this.textPrompts = data.prompts || {};
                    }
                } catch (e) {
                    console.error('Failed to load textual prompts', e);
                    showToast('Erreur lors du chargement des prompts');
                } finally {
                    this.textPromptsLoading = false;
                }
            },

            async saveTextPromptsConfig() {
                this.textPromptsSaving = true;
                try {
                    const r = await fetch('/api/texts/prompts', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ prompts: this.textPrompts })
                    });
                    if (r.ok) {
                        showToast('Prompts enregistrés !');
                    } else {
                        showToast((await r.json()).error || 'Erreur lors de l\'enregistrement');
                    }
                } catch (e) {
                    console.error('Failed to save textual prompts', e);
                    showToast('Erreur lors de l\'enregistrement');
                } finally {
                    this.textPromptsSaving = false;
                }
            },

            async resetTextPrompts() {
                if (!confirm('Voulez-vous vraiment réinitialiser tous les prompts aux valeurs par défaut ?')) return;
                this.textPromptsSaving = true;
                try {
                    const r = await fetch('/api/texts/prompts/reset', { method: 'POST' });
                    if (r.ok) {
                        showToast('Prompts réinitialisés !');
                        await this.loadTextPromptsConfig();
                    } else {
                        showToast((await r.json()).error || 'Erreur');
                    }
                } catch (e) {
                    showToast('Erreur lors de la réinitialisation');
                } finally {
                    this.textPromptsSaving = false;
                }
            },

            // Audio Config Methods
            async loadAudioConfig() {
                this.audioLoading = true;
                try {
                    const r = await fetch('/api/settings/audio/config');
                    if (r.ok) {
                        const data = await r.json();
                        this.audioConfig = {
                            stt_provider_id: data.stt_provider_id || '',
                            stt_model: data.stt_model || '',
                            tts_provider_id: data.tts_provider_id || '',
                            tts_model: data.tts_model || '',
                            tts_voice: data.tts_voice || '',
                            tts_speed: data.tts_speed !== undefined ? data.tts_speed : 1.0,
                            play_start_sound: data.play_start_sound !== undefined ? data.play_start_sound : false
                        };

                        // Load models if providers are selected
                        if (this.audioConfig.stt_provider_id) {
                            this.loadProviderModels(this.audioConfig.stt_provider_id);
                        }
                        if (this.audioConfig.tts_provider_id) {
                            this.loadProviderModels(this.audioConfig.tts_provider_id);
                        }
                    }
                } catch (e) {
                    console.error('Failed to load audio config', e);
                } finally {
                    this.audioLoading = false;
                }
            },

            async saveAudioConfig() {
                this.audioSaving = true;
                try {
                    const r = await fetch('/api/settings/audio/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(this.audioConfig)
                    });
                    if (r.ok) {
                        showToast('Configuration audio sauvegardée !');
                    } else {
                        const data = await r.json();
                        showToast(data.error || 'Erreur lors de la sauvegarde');
                    }
                } catch (e) {
                    console.error('Failed to save audio config', e);
                    showToast('Erreur lors de la sauvegarde');
                } finally {
                    this.audioSaving = false;
                }
            },

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

            // Provider type info with colors and icons
            getProviderTypeInfo(type) {
                const info = this.providerTypes[type] || {};
                const colors = {
                    ollama: 'blue', lmstudio: 'teal', openai: 'emerald', anthropic: 'amber',
                    gemini: 'purple', mistral: 'orange', groq: 'cyan', openrouter: 'pink',
                    deepseek: 'indigo', qwen: 'rose', openai_compatible: 'slate'
                };
                return { ...info, color: colors[type] || 'gray' };
            },

            async loadProviders() {
                this.providersLoading = true;
                try {
                    const [providersRes, typesRes] = await Promise.all([
                        fetch('/api/settings/providers'),
                        fetch('/api/settings/provider-types')
                    ]);
                    if (providersRes.ok) {
                        const data = await providersRes.json();
                        this.providers = data.providers || [];
                        this.activeProviderId = data.active_provider_id;
                    }
                    if (typesRes.ok) {
                        const data = await typesRes.json();
                        this.providerTypes = data.types || {};
                    }
                } catch (e) {
                    console.error('Failed to load providers', e);
                } finally {
                    this.providersLoading = false;
                }
            },

            editProvider(provider) {
                this.editingProviderId = provider.id;
                this.formProvider = {
                    name: provider.name,
                    type: provider.type,
                    url: provider.url || '',
                    api_key: '', // Never prefill API key for security
                    extra_headers: provider.extra_headers || {}
                };
                this.showApiKey = false;
            },

            cancelProviderEdit() {
                this.editingProviderId = null;
                this.formProvider = { name: '', type: 'ollama', url: '', api_key: '', extra_headers: {} };
                this.showApiKey = false;
            },

            async saveProvider() {
                const { name, type, url, api_key, extra_headers } = this.formProvider;
                if (!name.trim()) {
                    showToast('Le nom est requis');
                    return;
                }

                this.providersSaving = true;
                try {
                    let r;
                    const payload = { name: name.trim(), type, url: url.trim(), extra_headers };
                    if (api_key.trim()) {
                        payload.api_key = api_key.trim();
                    }

                    if (this.editingProviderId) {
                        r = await fetch(`/api/settings/providers/${this.editingProviderId}`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(payload)
                        });
                    } else {
                        r = await fetch('/api/settings/providers', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(payload)
                        });
                    }

                    if (r.ok) {
                        this.cancelProviderEdit();
                        await this.loadProviders();
                        showToast(this.editingProviderId ? 'Fournisseur modifié !' : 'Fournisseur ajouté !');
                        window.dispatchEvent(new CustomEvent('providers-changed'));
                    } else {
                        const data = await r.json();
                        showToast(data.error || 'Erreur lors de la sauvegarde');
                    }
                } catch (e) {
                    console.error('Failed to save provider', e);
                    showToast('Erreur lors de la sauvegarde');
                } finally {
                    this.providersSaving = false;
                }
            },

            async deleteProvider(id) {
                if (!confirm('Supprimer ce fournisseur ?')) return;
                try {
                    const r = await fetch(`/api/settings/providers/${id}`, { method: 'DELETE' });
                    if (r.ok) {
                        await this.loadProviders();
                        window.dispatchEvent(new CustomEvent('providers-changed'));
                        showToast('Fournisseur supprimé');
                    } else {
                        showToast('Erreur lors de la suppression');
                    }
                } catch (e) {
                    showToast('Erreur lors de la suppression');
                }
            },

            async setActiveProvider(id) {
                try {
                    const r = await fetch('/api/settings/providers/active', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ provider_id: id })
                    });
                    if (r.ok) {
                        this.activeProviderId = id;
                        window.dispatchEvent(new CustomEvent('providers-changed'));
                        showToast('Fournisseur activé !');
                    } else {
                        showToast('Erreur lors du changement');
                    }
                } catch (e) {
                    showToast('Erreur lors du changement');
                }
            },

            async testProvider(id) {
                this.testingProviderId = id;
                this.testResult = null;
                try {
                    const r = await fetch(`/api/settings/providers/${id}/test`, { method: 'POST' });
                    const data = await r.json();
                    this.testResult = { id, ok: data.ok, message: data.message };
                    if (data.ok) {
                        showToast('Connexion réussie !');
                        // Load models for the default model selector
                        await this.loadProviderModels(id);
                    } else {
                        showToast(data.message || 'Échec du test');
                    }
                } catch (e) {
                    this.testResult = { id, ok: false, message: 'Erreur de connexion' };
                    showToast('Erreur lors du test');
                } finally {
                    this.testingProviderId = null;
                }
            },

            async loadProviderModels(id) {
                try {
                    const r = await fetch(`/api/settings/providers/${id}/models`);
                    const data = await r.json();
                    this.providerModels[id] = data.models || [];
                } catch (e) {
                    this.providerModels[id] = [];
                }
            },

            async migrateFromServers() {
                try {
                    const r = await fetch('/api/settings/providers/migrate', { method: 'POST' });
                    const data = await r.json();
                    if (r.ok) {
                        showToast(data.message);
                        await this.loadProviders();
                    } else {
                        showToast(data.error || 'Erreur de migration');
                    }
                } catch (e) {
                    showToast('Erreur de migration');
                }
            },

            async setProviderDefaultModel(providerId, modelName) {
                try {
                    const r = await fetch(`/api/settings/providers/${providerId}/default-model`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ model: modelName })
                    });
                    if (r.ok) {
                        // Update local state
                        const provider = this.providers.find(p => p.id === providerId);
                        if (provider) {
                            provider.default_model = modelName;
                        }
                        showToast(modelName ? 'Modèle par défaut défini !' : 'Modèle par défaut supprimé');
                    } else {
                        const data = await r.json();
                        showToast(data.error || 'Erreur');
                    }
                } catch (e) {
                    showToast('Erreur lors de la mise à jour');
                }
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
