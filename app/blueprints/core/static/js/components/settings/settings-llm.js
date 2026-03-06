/**
 * Settings Page — LLM, Text Prompts & Audio Mixin
 * Methods for LLM parameters, text prompts, and audio configuration.
 * Merged into settingsPage via spread operator.
 */
window.SettingsLlmMixin = {

    // ============== LLM Configuration ==============

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

    // ============== Text Prompts ==============

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

    // ============== Audio Configuration ==============

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
    }
};
