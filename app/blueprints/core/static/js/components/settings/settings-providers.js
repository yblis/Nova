/**
 * Settings Page — Providers & Servers Mixin
 * Methods for managing LLM providers and legacy Ollama servers.
 * Merged into settingsPage via spread operator.
 */
window.SettingsProvidersMixin = {

    // ============== Legacy Servers ==============

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

    // ============== LLM Providers ==============

    // Helper function to safely get models for a provider
    getModelsForProvider(providerId) {
        return this.providerModels[providerId] || [];
    },

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
            // Use spread operator to force Alpine.js reactivity on nested object updates
            this.providerModels = { ...this.providerModels, [id]: data.models || [] };
        } catch (e) {
            this.providerModels = { ...this.providerModels, [id]: [] };
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
};
