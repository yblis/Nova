/**
 * Chat App — Multi-LLM Debate Mode Mixin
 * Methods for debate mode with multiple participants/providers.
 * Merged into chatApp via spread operator.
 */
window.ChatDebateMixin = {

    async toggleDebateMode() {
        console.log('toggleDebateMode called! Current state:', this.debateMode);
        this.debateMode = !this.debateMode;
        console.log('debateMode is now:', this.debateMode);
        if (this.debateMode) {
            if (this.availableProviders.length === 0) {
                await this.loadDebateProviders();
            }
            if (this.participants.length === 0) {
                await this.loadDebateDefaults();
            }
            this.showParticipantSelector = true;
        } else {
            this.showParticipantSelector = false;
            // Don't clear participants immediately to allow toggling back
        }
    },

    async loadDebateProviders() {
        try {
            const r = await fetch('/api/chat/debate/providers');
            if (r.ok) {
                const data = await r.json();
                this.availableProviders = data.providers || [];
            }
        } catch (e) {
            console.error('Error loading debate providers:', e);
            this.availableProviders = [];
        }
    },

    async loadDebateDefaults() {
        try {
            const r = await fetch('/api/chat/debate/defaults');
            if (r.ok) {
                const data = await r.json();
                if (Array.isArray(data) && data.length > 0) {
                    this.participants = data.map(p => ({
                        ...p,
                        // Ensure ID is unique if not present
                        id: p.id || crypto.randomUUID()
                    }));
                }
            }
        } catch (e) {
            console.error('Error loading debate defaults:', e);
        }
    },

    async saveDebateDefaults() {
        if (this.participants.length === 0) {
            showToast('Aucun participant à sauvegarder');
            return;
        }
        try {
            const r = await fetch('/api/chat/debate/defaults', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.participants)
            });
            if (r.ok) {
                showToast('Configuration par défaut sauvegardée');
            } else {
                showToast('Erreur lors de la sauvegarde');
            }
        } catch (e) {
            showToast('Erreur réseau');
        }
    },

    async loadProviderModels(providerId) {
        try {
            const r = await fetch(`/api/settings/providers/${providerId}/models`);
            if (r.ok) {
                const data = await r.json();
                return data.models || [];
            }
        } catch (e) {
            console.error('Error loading provider models:', e);
        }
        return [];
    },

    addParticipant(provider, model) {
        if (this.participants.length >= 4) {
            showToast('Maximum 4 participants');
            return;
        }
        // Check if already added
        const exists = this.participants.some(p =>
            p.provider_id === provider.id && p.model === model
        );
        if (exists) {
            showToast('Participant déjà ajouté');
            return;
        }
        this.participants.push({
            id: crypto.randomUUID(),
            provider_id: provider.id,
            model: model,
            name: `${provider.name} (${model.split(':')[0]})`,
            color: provider.color || 'zinc'
        });
    },

    removeParticipant(participantId) {
        this.participants = this.participants.filter(p => p.id !== participantId);
    },

    async sendDebateMessage() {
        if (this.debateLoading || !this.input.trim() || this.participants.length < 2) {
            if (this.participants.length < 2) {
                showToast('Sélectionnez au moins 2 participants');
            }
            return;
        }

        const userMsg = this.input.trim();
        this.input = '';

        // Add user message to display
        this.messages.push({ role: 'user', content: userMsg });
        this.debateLoading = true;
        this.loading = true;
        this.scrollToBottom();

        try {
            this.abortController = new AbortController();
            const response = await fetch('/api/chat/debate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.currentSessionId,
                    message: userMsg,
                    participants: this.participants.map(p => ({
                        provider_id: p.provider_id,
                        model: p.model,
                        name: p.name
                    })),
                    mode: this.debateModeOption
                }),
                signal: this.abortController.signal
            });

            if (!response.ok) throw new Error('Debate request failed');

            // Track responses per participant
            const participantMsgs = {};

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const json = JSON.parse(line.substring(6));

                            // Handle session ID
                            if (json.session_id && !this.currentSessionId) {
                                this.currentSessionId = json.session_id;
                                this.loadSessions();
                            }

                            // Handle participant response
                            if (json.participant_id && json.content) {
                                if (!participantMsgs[json.participant_id]) {
                                    // New participant message
                                    const msg = {
                                        role: 'assistant',
                                        content: '',
                                        participant_id: json.participant_id,
                                        participant_name: json.name,
                                        color: json.color
                                    };
                                    this.messages.push(msg);
                                    participantMsgs[json.participant_id] = this.messages.length - 1;
                                }
                                // Append content
                                const idx = participantMsgs[json.participant_id];
                                this.messages[idx].content += json.content;
                                this.scrollToBottom();
                            }

                            // Handle start marker for sequential mode
                            if (json.start && json.participant_id) {
                                const msg = {
                                    role: 'assistant',
                                    content: '',
                                    participant_id: json.participant_id,
                                    participant_name: json.name,
                                    color: json.color
                                };
                                this.messages.push(msg);
                                participantMsgs[json.participant_id] = this.messages.length - 1;
                                this.scrollToBottom();
                            }

                            if (json.error) {
                                showToast('Erreur: ' + json.error);
                            }

                            if (json.complete) {
                                this.loadSessions();
                            }
                        } catch (e) { }
                    }
                }
            }
        } catch (e) {
            if (e.name !== 'AbortError') {
                console.error('Debate error:', e);
                showToast('Erreur lors du débat');
            }
        } finally {
            this.debateLoading = false;
            this.loading = false;
            this.abortController = null;
        }
    }
};
