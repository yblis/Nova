/**
 * Chat App — Sessions Mixin
 * Methods for session CRUD, multi-selection, pin, and search.
 * Merged into chatApp via spread operator.
 */
window.ChatSessionsMixin = {

    async loadSessions() {
        const start = performance.now();
        try {
            const r = await fetch('/api/chat/sessions');
            const fetchTime = performance.now();
            this.log(`Sessions fetch took: ${(fetchTime - start).toFixed(0)}ms`);
            if (r.ok) {
                const data = await r.json();
                this.sessions = data.sessions || [];
                this.log(`Sessions parsed and assigned: ${this.sessions.length} sessions in ${(performance.now() - start).toFixed(0)}ms`);
                return true;
            }
        } catch (e) {
            this.log("Error loading sessions: " + e);
        }
        return false;
    },

    async loadSession(id) {
        if (this.selectionMode) return; // Don't load session in selection mode
        if (this.currentSessionId === id) return;
        this.currentSessionId = id;
        this.loading = true;
        if (window.innerWidth < 640) this.sidebarOpen = false;

        // Update URL hash to persist session
        if (window.location.hash.slice(1) !== id) {
            history.replaceState(null, '', '#' + id);
        }

        try {
            const r = await fetch(`/api/chat/sessions/${id}`);
            if (r.ok) {
                const data = await r.json();
                // Map messages et extraire web_sources et memory_concepts de extra_data
                this.messages = (data.messages || []).map(m => {
                    const extra = m.extra_data || {};
                    return {
                        ...m,
                        web_sources: extra.web_sources || m.web_sources,
                        memory_concepts: extra.memory_concepts || m.memory_concepts,
                        email_context: extra.email_context || m.email_context,
                        email_actions: extra.email_actions || m.email_actions,
                        bookstack_sources: extra.bookstack_sources || m.bookstack_sources
                    };
                });
                const sessionModel = data.model;
                this.currentModel = sessionModel;
                this.systemPrompt = data.system_prompt || '';
                this.modelConfig = data.model_config || { temperature: 0.7, num_ctx: 4096, top_p: 0.9, top_k: 40 };

                // Afficher immédiatement la session (scroll + loading = false)
                this.scrollToBottom();
                this.loading = false;

                // Charger les documents RAG en parallèle (non bloquant)
                this.loadRagDocuments(id);

                // Résoudre le provider en arrière-plan (non bloquant pour l'affichage)
                if (sessionModel) {
                    this._resolveProviderInBackground(sessionModel);
                }
            }
        } catch (e) {
            this.log("Error loading session: " + e);
            this.loading = false;
        }
    },

    // Résolution du provider en arrière-plan sans bloquer l'UI
    async _resolveProviderInBackground(sessionModel) {
        try {
            const providerResp = await fetch('/api/settings/providers/resolve-model', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model: sessionModel })
            });
            if (providerResp.ok) {
                const providerData = await providerResp.json();
                if (providerData.found && providerData.provider_id) {
                    // Changer le provider actif (fire-and-forget)
                    fetch('/api/settings/providers/active', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ provider_id: providerData.provider_id })
                    });
                    // Recharger les modèles en arrière-plan
                    await this.loadModels();
                    // Restaurer le modèle de la session
                    this.currentModel = sessionModel;
                    this.log(`Provider switched to ${providerData.provider_name} for model ${sessionModel}`);
                }
            }
        } catch (e) {
            this.log('Could not resolve provider for model: ' + sessionModel);
        }
    },

    newChat() {
        this.currentSessionId = null;
        this.messages = [];
        this.systemPrompt = '';
        this.modelConfig = { temperature: 0.7, num_ctx: 4096, top_p: 0.9, top_k: 40 };
        this.pendingImages = [];
        this.pendingFiles = [];
        this.ragDocuments = [];
        this.sidebarOpen = window.innerWidth >= 640;
        this.selectionMode = false;
        this.selectedSessions = [];

        // Remove hash from URL
        if (window.location.hash) {
            history.replaceState(null, '', window.location.pathname + window.location.search);
        }
    },

    async deleteSession(id) {
        showConfirmDialog({
            title: 'Supprimer la conversation',
            message: 'Voulez-vous vraiment supprimer cette conversation ?',
            type: 'danger',
            confirmText: 'Supprimer',
            onConfirm: async () => {
                try {
                    await fetch(`/api/chat/sessions/${id}`, { method: 'DELETE' });
                    this.sessions = this.sessions.filter(s => s.id !== id);
                    if (this.currentSessionId === id) this.newChat();
                } catch (e) { }
            }
        });
    },

    async togglePin(id) {
        // Optimistic update
        const session = this.sessions.find(s => s.id === id);
        if (!session) return;

        session.is_pinned = !session.is_pinned;

        // Re-sort locally: pinned first, then by date desc
        this.sortSessions();

        try {
            const r = await fetch(`/api/chat/sessions/${id}/pin`, { method: 'POST' });
            if (!r.ok) {
                // Revert on error
                session.is_pinned = !session.is_pinned;
                this.sortSessions();
                showToast('Erreur lors de l\'épinglage');
            }
        } catch (e) {
            session.is_pinned = !session.is_pinned;
            this.sortSessions();
            showToast('Erreur connexion');
        }
    },

    sortSessions() {
        this.sessions.sort((a, b) => {
            if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1;
            return (b.updated_at || 0) - (a.updated_at || 0);
        });
    },

    // Multi-selection methods
    toggleSelectionMode() {
        this.selectionMode = !this.selectionMode;
        if (!this.selectionMode) {
            this.selectedSessions = [];
        }
    },

    toggleSessionSelection(id) {
        const idx = this.selectedSessions.indexOf(id);
        if (idx > -1) {
            this.selectedSessions.splice(idx, 1);
        } else {
            this.selectedSessions.push(id);
        }
    },

    isSessionSelected(id) {
        return this.selectedSessions.includes(id);
    },

    selectAllSessions() {
        if (this.selectedSessions.length === this.sessions.length) {
            this.selectedSessions = [];
        } else {
            this.selectedSessions = this.sessions.map(s => s.id);
        }
    },

    async deleteSelectedSessions() {
        if (this.selectedSessions.length === 0) return;
        const count = this.selectedSessions.length;
        showConfirmDialog({
            title: 'Supprimer les conversations',
            message: `Voulez-vous vraiment supprimer ${count} conversation${count > 1 ? 's' : ''} ?`,
            type: 'danger',
            confirmText: 'Supprimer',
            onConfirm: async () => {
                try {
                    await fetch('/api/chat/sessions/bulk', {
                        method: 'DELETE',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ session_ids: this.selectedSessions })
                    });
                    this.sessions = this.sessions.filter(s => !this.selectedSessions.includes(s.id));
                    if (this.selectedSessions.includes(this.currentSessionId)) {
                        this.newChat();
                    }
                    this.selectedSessions = [];
                    this.selectionMode = false;
                    showToast(`${count} conversation${count > 1 ? 's' : ''} supprimée${count > 1 ? 's' : ''}`);
                } catch (e) {
                    showToast('Erreur lors de la suppression');
                }
            }
        });
    },

    async deleteAllSessions() {
        if (this.sessions.length === 0) return;
        const count = this.sessions.length;
        showConfirmDialog({
            title: 'Supprimer toutes les conversations',
            message: `Voulez-vous vraiment supprimer <strong>toutes</strong> les ${count} conversation${count > 1 ? 's' : ''} ? Cette action est irréversible.`,
            type: 'danger',
            confirmText: 'Tout supprimer',
            onConfirm: async () => {
                try {
                    await fetch('/api/chat/sessions/all', { method: 'DELETE' });
                    this.sessions = [];
                    this.newChat();
                    this.selectionMode = false;
                    this.selectedSessions = [];
                    showToast('Toutes les conversations ont été supprimées');
                } catch (e) {
                    showToast('Erreur lors de la suppression');
                }
            }
        });
    }
};
