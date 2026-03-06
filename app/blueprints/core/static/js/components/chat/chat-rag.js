/**
 * Chat App — RAG/PDF Mixin
 * Methods for RAG document upload, chunks visualization, and search.
 * Merged into chatApp via spread operator.
 */
window.ChatRagMixin = {

    async loadRagDocuments(sessionId) {
        if (!sessionId) { this.ragDocuments = []; return; }
        try {
            const r = await fetch(`/api/chat/sessions/${sessionId}/documents`);
            if (r.ok) {
                const data = await r.json();
                this.ragDocuments = data.documents || [];

                // Auto-polling if documents are processing
                if (this.ragDocuments.some(d => d.status === 'processing' || d.status === 'pending')) {
                    if (this._ragPollingTimeout) clearTimeout(this._ragPollingTimeout);
                    this._ragPollingTimeout = setTimeout(() => this.loadRagDocuments(sessionId), 2000);
                }
            }
        } catch (e) {
            this.ragDocuments = [];
        }
    },

    async handlePdfUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        if (!this.currentSessionId) {
            if (!this.currentModel) {
                showToast('Veuillez d\'abord sélectionner un modèle');
                event.target.value = '';
                return;
            }
            try {
                const r = await fetch('/api/chat/sessions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model: this.currentModel })
                });
                if (r.ok) {
                    this.currentSessionId = (await r.json()).id;
                    this.loadSessions();
                } else {
                    showToast('Erreur création session');
                    event.target.value = '';
                    return;
                }
            } catch (e) {
                showToast('Erreur lors de la création de la session');
                event.target.value = '';
                return;
            }
        }

        this.pdfUploading = true;
        const formData = new FormData();
        formData.append('file', file);
        formData.append('session_id', this.currentSessionId);

        try {
            const r = await fetch('/api/chat/upload-pdf', { method: 'POST', body: formData });
            const data = await r.json();
            if (r.ok) {
                await this.loadRagDocuments(this.currentSessionId);
            } else {
                showToast(data.error || 'Erreur lors de l\'upload du PDF');
            }
        } catch (e) {
            showToast('Erreur lors de l\'upload du PDF');
        } finally {
            this.pdfUploading = false;
            event.target.value = '';
        }
    },

    async deleteRagDocument(docId, filename) {
        if (!confirm(`Supprimer le document "${filename}" ?`)) return;
        try {
            const r = await fetch(`/api/chat/documents/${docId}`, { method: 'DELETE' });
            if (r.ok) {
                this.ragDocuments = this.ragDocuments.filter(d => d.id !== docId);
            } else {
                showToast((await r.json()).error || 'Erreur lors de la suppression');
            }
        } catch (e) {
            showToast('Erreur lors de la suppression');
        }
    },

    async viewChunks(docId, filename) {
        this.currentDocFilename = filename;
        this.currentDocId = docId;
        this.showChunksModal = true;
        this.currentDocChunks = [];
        this.currentDocStats = {};
        this.currentDocSearchQuery = '';
        try {
            const r = await fetch(`/api/rag/documents/${docId}/chunks`);
            if (r.ok) {
                const data = await r.json();
                this.currentDocChunks = data.chunks || [];
                this.currentDocStats = data.stats || {};
            }
        } catch (e) {
            console.error('Failed to load chunks', e);
            showToast('Erreur chargement chunks');
        }
    },

    async searchChunks() {
        if (!this.currentDocSearchQuery.trim()) {
            // If empty, reload all chunks
            this.viewChunks(this.currentDocId, this.currentDocFilename);
            return;
        }
        try {
            const r = await fetch(`/api/rag/documents/${this.currentDocId}/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: this.currentDocSearchQuery })
            });
            if (r.ok) {
                const data = await r.json();
                this.currentDocChunks = data.results || [];
            }
        } catch (e) {
            showToast('Erreur recherche');
        }
    },

    async deleteChunk(chunkId) {
        if (!confirm('Supprimer ce chunk ?')) return;
        try {
            const r = await fetch(`/api/rag/chunks/${chunkId}`, { method: 'DELETE' });
            if (r.ok) {
                this.currentDocChunks = this.currentDocChunks.filter(c => c.id !== chunkId);
                // Update stats locally (simple approximation)
                this.currentDocStats.total_chunks = (this.currentDocStats.total_chunks || 1) - 1;
            } else {
                showToast('Erreur suppression chunk');
            }
        } catch (e) {
            showToast('Erreur suppression chunk');
        }
    }
};
