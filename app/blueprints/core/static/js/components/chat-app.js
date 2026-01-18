/**
 * Chat Application Component
 * Alpine.js component for the /chat page
 */
document.addEventListener('alpine:init', () => {
    Alpine.data('chatApp', () => ({
        models: [],
        currentModel: new URLSearchParams(window.location.search).get('model') || '',
        sessions: [],
        currentSessionId: null,
        messages: [],
        input: '',
        loading: false,
        sidebarOpen: window.innerWidth >= 640,
        debug: false,
        debugLogs: [],
        showSettings: false,
        systemPrompt: '',
        modelConfig: { temperature: 0.7, num_ctx: 4096, top_p: 0.9, top_k: 40 },
        pendingImages: [],
        pendingFiles: [],
        abortController: null,
        ragDocuments: [],
        pdfUploading: false,
        // Chunks Visualization
        showChunksModal: false,
        currentDocChunks: [],
        currentDocStats: {},
        currentDocFilename: '',
        currentDocSearchQuery: '',
        currentDocId: null,
        // Web Search
        webSearchEnabled: false,
        webSearchAvailable: false,
        // Multi-selection mode
        selectionMode: false,
        selectedSessions: [],
        // SPA lifecycle - stored handlers for cleanup
        _hashChangeHandler: null,
        // Session search
        sessionSearchQuery: '',
        // Multi-LLM Debate Mode
        debateMode: false,
        participants: [],           // [{id, provider_id, model, name, color}]
        availableProviders: [],     // [{id, name, type, color, default_model}]
        showParticipantSelector: false,
        debateLoading: false,
        debateModeOption: 'parallel', // 'parallel' or 'sequential'

        log(msg) {
            this.debugLogs.push(`[${new Date().toISOString().split('T')[1].split('.')[0]}] ${msg}`);
            console.log(`[ChatDebug] ${msg}`);
        },

        async init() {
            const initStart = performance.now();
            this.log("App initializing...");
            // Lire le paramètre model de l'URL (important pour la navigation SPA)
            const urlModel = new URLSearchParams(window.location.search).get('model');
            if (urlModel) {
                this.currentModel = urlModel;
                this.log("Model from URL: " + urlModel);
            }
            
            // Paralléliser les appels d'initialisation pour accélérer le chargement
            const fetchStart = performance.now();
            await Promise.all([
                this.loadModels(),
                this.loadSessions()
            ]);
            this.log(`Init: API calls completed in ${(performance.now() - fetchStart).toFixed(0)}ms`);
            this.log(`Init: ${this.sessions.length} sessions loaded, ${this.models.length} models loaded`);
            
            // Vérification web search en arrière-plan (non bloquant)
            this.checkWebSearchAvailable();

            // Load session from URL hash if present
            const hashSessionId = window.location.hash.slice(1);
            if (hashSessionId && this.sessions.some(s => s.id === hashSessionId)) {
                this.loadSession(hashSessionId); // Non bloquant
            }

            // Listen for hash changes (browser back/forward)
            this._hashChangeHandler = () => {
                const hash = window.location.hash.slice(1);
                if (hash && hash !== this.currentSessionId) {
                    // Check if session exists
                    if (this.sessions.some(s => s.id === hash)) {
                        this.loadSession(hash);
                    }
                } else if (!hash && this.currentSessionId) {
                    // Hash removed, start new chat
                    this.newChat();
                }
            };
            window.addEventListener('hashchange', this._hashChangeHandler);
        },

        async loadModels() {
            try {
                // First try to load models from active provider
                const r = await fetch('/api/settings/providers/active/models');
                if (r.ok) {
                    const data = await r.json();
                    if (data.models && data.models.length > 0) {
                        // Filter embedding models and extract unique IDs
                        const embeddingPatterns = ['embed', 'bge-', 'bge:', 'all-minilm', 'snowflake-arctic', 'paraphrase', '/e5-', ':e5-', '/e5:', 'gte-', 'gte:', 'jina-', 'text-embedding', 'embedding-'];
                        const seen = new Set();
                        this.models = data.models
                            .map(m => {
                                // Prefer id for uniqueness, but use name as fallback
                                if (typeof m === 'string') return m;
                                return m.id || m.name || '';
                            })
                            .filter(name => {
                                if (!name || seen.has(name)) return false;
                                seen.add(name);
                                const lowerName = name.toLowerCase();
                                return !embeddingPatterns.some(pattern => lowerName.includes(pattern));
                            });
                        // Use provider_default_model if currentModel is not set (no query param)
                        if (!this.currentModel && this.models.length > 0) {
                            if (data.provider_default_model && this.models.includes(data.provider_default_model)) {
                                this.currentModel = data.provider_default_model;
                            } else {
                                this.currentModel = this.models[0];
                            }
                        }
                        this.log(`Loaded ${this.models.length} models from active provider`);
                        return;
                    }
                }
                // Fallback to old Ollama endpoint
                const fallback = await fetch('/api/models', { headers: { 'Accept': 'application/json' } });
                if (fallback.ok) {
                    const data = await fallback.json();
                    if (data.models) {
                        const embeddingPatterns = ['embed', 'bge-', 'bge:', 'all-minilm', 'snowflake-arctic', 'paraphrase', '/e5-', ':e5-', '/e5:', 'gte-', 'gte:', 'jina-'];
                        this.models = data.models
                            .map(m => m.name)
                            .filter(name => {
                                const lowerName = name.toLowerCase();
                                return !embeddingPatterns.some(pattern => lowerName.includes(pattern));
                            });
                        // Vérifier si currentModel (venant de l'URL) est valide
                        const isValidCurrent = this.currentModel && this.models.includes(this.currentModel);
                        if (!isValidCurrent && this.models.length > 0) {
                            this.currentModel = this.models[0];
                        }
                    }
                }
            } catch (e) {
                this.log("Models fetch error: " + e);
            }
        },

        async checkWebSearchAvailable() {
            try {
                const r = await fetch('/api/settings/web_search/config');
                if (r.ok) {
                    const data = await r.json();
                    this.webSearchAvailable = data.is_available || false;
                }
            } catch (e) {
                this.webSearchAvailable = false;
            }
        },

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
                    this.messages = data.messages || [];
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
        },

        formatContent(content) {
            try {
                if (typeof marked === 'undefined') return content;
                let html = marked.parse(content);
                // Add copy button to each <pre> block
                html = html.replace(/<pre>([\s\S]*?)<\/pre>/g, (match, codeContent) => {
                    return `<div class="code-block-wrapper"><button class="copy-code-btn" onclick="copyCodeBlock(this)" title="Copier le code"><svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg></button><pre>${codeContent}</pre></div>`;
                });
                return html;
            } catch (e) {
                return content;
            }
        },

        formatUserContent(content, images) {
            if (!content) return '';
            if (images && images.length > 0) {
                content = content.replace(/^\[\d+ image\(s\) attached\]\s*/i, '');
            }
            // Escape HTML first for security
            const div = document.createElement('div');
            div.textContent = content;
            let escaped = div.innerHTML;
            // Convert line breaks to <br> tags
            escaped = escaped.replace(/\n/g, '<br>');
            // Support basic markdown: inline code with backticks
            escaped = escaped.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
            return escaped;
        },

        formatDate(timestamp) {
            if (!timestamp) return '';
            const d = new Date(timestamp * 1000);
            return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        },

        async handleImageUpload(event) {
            for (const file of event.target.files) {
                try {
                    const base64 = await this.fileToBase64(file);
                    this.pendingImages.push({ name: file.name, data: base64.split(',')[1] });
                } catch (e) { }
            }
            event.target.value = '';
        },

        async handleFileUpload(event) {
            const file = event.target.files[0];
            if (!file) return;
            const formData = new FormData();
            formData.append('file', file);
            try {
                const r = await fetch('/api/chat/upload', { method: 'POST', body: formData });
                if (r.ok) {
                    this.pendingFiles.push(await r.json());
                } else {
                    showToast((await r.json()).error || 'Failed to upload file');
                }
            } catch (e) {
                showToast('Failed to upload file');
            }
            event.target.value = '';
        },

        fileToBase64(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.readAsDataURL(file);
                reader.onload = () => resolve(reader.result);
                reader.onerror = error => reject(error);
            });
        },

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
        },

        async saveSettings() {
            if (!this.currentSessionId) {
                if (!this.currentModel) {
                    showToast('Please select a model first');
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
                    }
                } catch (e) {
                    return;
                }
            }
            try {
                const r = await fetch(`/api/chat/sessions/${this.currentSessionId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ system_prompt: this.systemPrompt, model_config: this.modelConfig })
                });
                if (r.ok) {
                    this.showSettings = false;
                } else {
                    showToast((await r.json()).error || 'Failed to save settings');
                }
            } catch (e) {
                showToast('Failed to save settings');
            }
        },

        async sendMessage() {
            if (this.loading || (!this.input.trim() && this.pendingImages.length === 0 && this.pendingFiles.length === 0) || !this.currentModel) return;
            const userMsg = this.input.trim();
            const imagesToSend = [...this.pendingImages];
            const filesToSend = [...this.pendingFiles];
            this.input = '';
            this.pendingImages = [];
            this.pendingFiles = [];

            // Reset textarea height and refocus
            this.$nextTick(() => {
                if (this.$refs.chatInput) {
                    this.$refs.chatInput.style.height = 'auto';
                    this.$refs.chatInput.rows = 1;
                    // Force focus to ensure cursor stays/moves to the correct input
                    this.$refs.chatInput.focus();
                }
            });

            let displayContent = '';
            if (imagesToSend.length > 0) {
                displayContent += `[${imagesToSend.length} image(s) attached]\n\n`;
            }
            if (filesToSend.length > 0) {
                displayContent += filesToSend.map(f => `[File: ${f.filename}]`).join('\n') + '\n\n';
            }
            displayContent += userMsg;
            this.messages.push({ role: 'user', content: displayContent.trim(), images: imagesToSend.length > 0 ? imagesToSend.map(img => img.data) : undefined });
            this.loading = true;
            this.scrollToBottom();

            try {
                this.abortController = new AbortController();
                const response = await fetch('/api/chat/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        model: this.currentModel,
                        message: userMsg,
                        session_id: this.currentSessionId,
                        images: imagesToSend.map(img => img.data),
                        files: filesToSend,
                        web_search: this.webSearchEnabled
                    }),
                    signal: this.abortController.signal
                });
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const assistantMsg = { role: 'assistant', content: '' };
                this.messages.push(assistantMsg);
                const msgIndex = this.messages.length - 1;
                if (!response.body) throw new Error("ReadableStream not supported.");
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                try {
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
                                    if (json.session_id && !this.currentSessionId) {
                                        this.currentSessionId = json.session_id;
                                        this.loadSessions();
                                    }
                                    if (json.error) {
                                        this.messages[msgIndex].content += "\n\n*[System Error: " + json.error + "]*";
                                        this.loadSessions();
                                    }
                                    if (json.content) {
                                        this.messages[msgIndex].content += json.content;
                                        this.scrollToBottom();
                                    }
                                    if (json.thinking) {
                                        if (!this.messages[msgIndex].thinking) this.messages[msgIndex].thinking = "";
                                        this.messages[msgIndex].thinking += json.thinking;
                                        this.scrollToBottom();
                                    }
                                    if (json.web_sources) {
                                        this.messages[msgIndex].web_sources = json.web_sources;
                                    }
                                    if (json.title_update) {
                                        const session = this.sessions.find(s => s.id === json.session_id);
                                        if (session) {
                                            session.title = json.title_update;
                                        }
                                    }
                                } catch (e) { }
                            }
                        }
                    }
                } catch (readError) {
                    this.messages[msgIndex].content += "\n*[Stream Error: " + readError + "]*";
                } finally {
                    this.loading = false;
                    this.abortController = null;
                    this.loadSessions();
                }
            } catch (e) {
                this.messages.push({ role: 'system', content: 'Error: ' + e });
            } finally {
                this.loading = false;
                this.abortController = null;
            }
        },

        stopGeneration() {
            if (this.abortController) {
                this.abortController.abort();
                this.abortController = null;
                this.loading = false;
                if (this.messages.length > 0) {
                    const lastMsg = this.messages[this.messages.length - 1];
                    if (lastMsg.role === 'assistant') {
                        lastMsg.content += '\n\n*[Generation stopped]*';
                    }
                }
                this.loadSessions();
            }
        },

        scrollToBottom() {
            this.$nextTick(() => {
                const c = document.getElementById('chat-container');
                if (c) c.scrollTop = c.scrollHeight;
            });
        },

        adjustTextareaHeight(el) {
            // Reset height to auto to calculate new scrollHeight correctly
            el.style.height = 'auto';
            // Set new height based on scrollHeight, max 200px (approx 8-9 lines)
            const newHeight = Math.min(el.scrollHeight, 200);
            el.style.height = newHeight + 'px';
            // Add scrollbar if content exceeds max height
            el.style.overflowY = el.scrollHeight > 200 ? 'auto' : 'hidden';
        },

        handleKeydown(event) {
            // Check if it's Enter key
            if (event.key === 'Enter') {
                // If Shift + Enter, let default behavior happen (new line)
                if (event.shiftKey) return;

                // Check device type (desktop vs mobile) using window width
                // Mobile behavior (< 768px): Enter = new line
                if (window.innerWidth < 768) return;

                // Desktop behavior (>= 768px): Enter = send
                // Prevent default new line behavior and send message
                event.preventDefault();
                this.sendMessage();
            }
        },

        // Copy assistant response to clipboard
        copyResponse(content) {
            navigator.clipboard.writeText(content).then(() => {
                showToast('Réponse copiée !');
            }).catch(err => {
                console.error('Failed to copy:', err);
                showToast('Erreur lors de la copie');
            });
        },

        // Regenerate a response
        async regenerateResponse(msgIndex) {
            if (this.loading || !this.currentModel) return;

            // Find the user message before this assistant message
            let userMsgIndex = msgIndex - 1;
            while (userMsgIndex >= 0 && this.messages[userMsgIndex].role !== 'user') {
                userMsgIndex--;
            }

            if (userMsgIndex < 0) {
                showToast('Impossible de régénérer : message utilisateur introuvable');
                return;
            }

            const userMsg = this.messages[userMsgIndex];
            // Extract the actual message content (remove file/image prefixes)
            let userContent = userMsg.content;
            userContent = userContent.replace(/^\[\d+ image\(s\) attached\]\s*/i, '');
            userContent = userContent.replace(/^\[File: [^\]]+\]\s*/gm, '');
            userContent = userContent.trim();

            // Remove the current assistant message
            this.messages.splice(msgIndex, 1);

            // Regenerate
            this.loading = true;
            this.scrollToBottom();

            try {
                this.abortController = new AbortController();
                const response = await fetch('/api/chat/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        model: this.currentModel,
                        message: userContent,
                        session_id: this.currentSessionId,
                        regenerate: true // Flag to indicate regeneration
                    }),
                    signal: this.abortController.signal
                });

                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

                const assistantMsg = { role: 'assistant', content: '' };
                this.messages.push(assistantMsg);
                const newMsgIndex = this.messages.length - 1;

                if (!response.body) throw new Error("ReadableStream not supported.");
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';

                try {
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
                                    if (json.error) {
                                        this.messages[newMsgIndex].content += "\n\n*[System Error: " + json.error + "]*";
                                    }
                                    if (json.content) {
                                        this.messages[newMsgIndex].content += json.content;
                                        this.scrollToBottom();
                                    }
                                    if (json.thinking) {
                                        if (!this.messages[newMsgIndex].thinking) this.messages[newMsgIndex].thinking = "";
                                        this.messages[newMsgIndex].thinking += json.thinking;
                                        this.scrollToBottom();
                                    }
                                } catch (e) { }
                            }
                        }
                    }
                } catch (readError) {
                    this.messages[newMsgIndex].content += "\n*[Stream Error: " + readError + "]*";
                } finally {
                    this.loading = false;
                    this.abortController = null;
                    this.loadSessions();
                }
            } catch (e) {
                this.messages.push({ role: 'system', content: 'Error: ' + e });
            } finally {
                this.loading = false;
                this.abortController = null;
            }
        },

        /**
         * Destroy method for SPA lifecycle.
         * Cleans up event listeners and timeouts.
         */
        destroy() {
            this.log("Destroying chatApp component");

            // Remove hashchange listener
            if (this._hashChangeHandler) {
                window.removeEventListener('hashchange', this._hashChangeHandler);
                this._hashChangeHandler = null;
            }

            // Clear RAG polling timeout
            if (this._ragPollingTimeout) {
                clearTimeout(this._ragPollingTimeout);
                this._ragPollingTimeout = null;
            }

            // Abort any pending requests
            if (this.abortController) {
                this.abortController.abort();
                this.abortController = null;
            }

            this.log("chatApp cleanup complete");
        },

        // ============== Multi-LLM Debate Mode ==============

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
        },

        // Get filtered sessions based on search query
        get filteredSessions() {
            if (!this.sessionSearchQuery.trim()) return this.sessions;
            const q = this.sessionSearchQuery.toLowerCase();
            return this.sessions.filter(s =>
                (s.title || '').toLowerCase().includes(q)
            );
        }
    }));
});
