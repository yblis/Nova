/**
 * Settings Page — Integrations Mixin
 * Methods for RAG, Web Search, Email, and Bookstack configuration.
 * Merged into settingsPage via spread operator.
 */
window.SettingsIntegrationsMixin = {

    // ============== RAG Configuration ==============

    async loadRagConfig() {
        this.ragLoading = true;
        try {
            const r = await fetch('/api/rag/config');
            if (r.ok) {
                const data = await r.json();
                // Sauvegarder les valeurs OCR avant réinitialisation
                const savedOcrProvider = data.ocr_provider || '';
                const savedOcrModel = data.ocr_model || '';
                
                this.ragConfig = {
                    embedding_model: data.embedding_model || '',
                    embedding_provider_id: data.embedding_provider_id || '',
                    embedding_providers: data.embedding_providers || [],
                    available_models: data.available_models || [],
                    chunk_size: data.chunk_size || 500,
                    chunk_overlap: data.chunk_overlap || 50,
                    top_k: data.top_k || 5,
                    // OCR - initialiser avec valeurs sauvegardées
                    ocr_provider: savedOcrProvider,
                    ocr_model: savedOcrModel,
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
                
                // If a provider is already selected, load its models AND WAIT
                if (savedOcrProvider) {
                    await this.loadOcrModels(savedOcrProvider);
                }
                
                // IMPORTANT: Restaurer les valeurs OCR APRÈS que les options soient rendues
                // Utiliser setTimeout car $nextTick ne suffit pas pour x-for
                setTimeout(() => {
                    this.ragConfig.ocr_provider = savedOcrProvider;
                    this.ragConfig.ocr_model = savedOcrModel;
                }, 100);
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

    // ============== Web Search ==============

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

    // ============== Email ==============

    async loadEmailConfig() {
        this.emailLoading = true;
        this.emailTestMessage = '';
        try {
            const [configR, presetsR] = await Promise.all([
                fetch('/api/settings/email/config'),
                fetch('/api/settings/email/presets')
            ]);
            if (configR.ok) {
                const data = await configR.json();
                this.emailConfig = { ...this.emailConfig, ...data };
            }
            if (presetsR.ok) {
                this.emailPresets = await presetsR.json();
            }
        } catch (e) {
            console.error('Failed to load email config', e);
        } finally {
            this.emailLoading = false;
        }
    },

    async saveEmailConfig() {
        this.emailSaving = true;
        try {
            const r = await fetch('/api/settings/email/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.emailConfig)
            });
            if (r.ok) {
                showToast('Configuration email enregistrée !');
                await this.loadEmailConfig();
            } else {
                const data = await r.json();
                showToast(data.error || 'Erreur lors de l\'enregistrement');
            }
        } catch (e) {
            console.error('Failed to save email config', e);
            showToast('Erreur lors de l\'enregistrement');
        } finally {
            this.emailSaving = false;
        }
    },

    async testEmailConnection() {
        this.emailTesting = true;
        this.emailTestMessage = '';
        this.emailTestResults = null;
        try {
            // Save first
            await fetch('/api/settings/email/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.emailConfig)
            });
            // Test
            const r = await fetch('/api/settings/email/test', { method: 'POST' });
            const data = await r.json();
            this.emailTestResults = data;
            this.emailTestMessage = data.message;
            this.emailTestSuccess = data.ok;
            if (data.ok) this.emailConfig.is_available = true;
        } catch (e) {
            console.error('Failed to test email', e);
            this.emailTestMessage = 'Erreur de connexion';
            this.emailTestSuccess = false;
        } finally {
            this.emailTesting = false;
        }
    },

    applyEmailPreset(presetName) {
        const presets = this.emailPresets;
        const preset = presets[presetName];
        if (preset) {
            this.emailConfig.imap_host = preset.imap_host || '';
            this.emailConfig.imap_port = preset.imap_port || 993;
            this.emailConfig.imap_encryption = preset.imap_encryption || 'tls';
            this.emailConfig.pop3_host = preset.pop3_host || '';
            this.emailConfig.pop3_port = preset.pop3_port || 995;
            this.emailConfig.pop3_encryption = preset.pop3_encryption || 'tls';
            this.emailConfig.smtp_host = preset.smtp_host || '';
            this.emailConfig.smtp_port = preset.smtp_port || 587;
            this.emailConfig.smtp_encryption = preset.smtp_encryption || 'starttls';
            showToast(`Préset ${preset.label || presetName} appliqué`);
        }
    },

    // ============== Bookstack ==============

    async loadBookstackConfig() {
        this.bookstackLoading = true;
        this.bookstackTestMessage = '';
        try {
            const r = await fetch('/api/settings/bookstack/config');
            if (r.ok) {
                const data = await r.json();
                this.bookstackConfig = {
                    url: data.url || '',
                    token_id: data.token_id || '',
                    token_secret: '',
                    token_secret_masked: data.token_secret_masked || '',
                    max_results: data.max_results || 5,
                    timeout: data.timeout || 15,
                    is_available: data.is_available || false
                };
            }
        } catch (e) {
            console.error('Failed to load Bookstack config', e);
        } finally {
            this.bookstackLoading = false;
        }
    },

    async saveBookstackConfig() {
        this.bookstackSaving = true;
        try {
            const payload = {
                url: this.bookstackConfig.url,
                token_id: this.bookstackConfig.token_id,
                max_results: this.bookstackConfig.max_results,
                timeout: this.bookstackConfig.timeout
            };
            // Only send token_secret if user typed a new one
            if (this.bookstackConfig.token_secret) {
                payload.token_secret = this.bookstackConfig.token_secret;
            }
            const r = await fetch('/api/settings/bookstack/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (r.ok) {
                showToast('Configuration Bookstack enregistrée !');
                await this.loadBookstackConfig();
            } else {
                const data = await r.json();
                showToast(data.error || 'Erreur lors de l\'enregistrement');
            }
        } catch (e) {
            console.error('Failed to save Bookstack config', e);
            showToast('Erreur lors de l\'enregistrement');
        } finally {
            this.bookstackSaving = false;
        }
    },

    async testBookstack() {
        this.bookstackTesting = true;
        this.bookstackTestMessage = '';
        try {
            // Save config first
            const payload = {
                url: this.bookstackConfig.url,
                token_id: this.bookstackConfig.token_id
            };
            if (this.bookstackConfig.token_secret) {
                payload.token_secret = this.bookstackConfig.token_secret;
            }
            const saveR = await fetch('/api/settings/bookstack/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!saveR.ok) {
                const data = await saveR.json();
                this.bookstackTestMessage = data.error || 'Configuration invalide';
                this.bookstackTestSuccess = false;
                return;
            }
            // Then test
            const r = await fetch('/api/settings/bookstack/test', { method: 'POST' });
            const data = await r.json();
            if (data.ok) {
                this.bookstackTestMessage = data.message;
                this.bookstackTestSuccess = true;
                this.bookstackConfig.is_available = true;
            } else {
                this.bookstackTestMessage = data.message || data.error || 'Échec du test';
                this.bookstackTestSuccess = false;
                this.bookstackConfig.is_available = false;
            }
        } catch (e) {
            console.error('Failed to test Bookstack', e);
            this.bookstackTestMessage = 'Erreur de connexion';
            this.bookstackTestSuccess = false;
        } finally {
            this.bookstackTesting = false;
        }
    }
};
