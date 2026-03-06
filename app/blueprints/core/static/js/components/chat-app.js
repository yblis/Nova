/**
 * Chat Application Component
 * Alpine.js component for the /chat page
 *
 * Methods are split into mixins loaded before this file:
 * - ChatSessionsMixin  (chat-sessions.js)
 * - ChatRagMixin       (chat-rag.js)
 * - ChatDebateMixin    (chat-debate.js)
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
        // Email Agent
        emailAgentEnabled: false,
        emailAgentAvailable: false,
        // Bookstack Documentation
        bookstackEnabled: false,
        bookstackAvailable: false,
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
        // Debate Settings
        showDebateSettings: false,
        debateSystemPrompt: '',
        // Voice / TTS Settings
        voiceSettings: { lang: 'fr-FR', voiceURI: '', rate: 1, autoRead: false },
        availableVoices: [],
        // Audio / STT
        isRecording: false,
        audioBackendConfig: { stt_enabled: false, tts_enabled: false },
        // Drag & Drop
        isDragging: false,
        // TTS speaking state
        speakingId: null,

        // ============== Mixins ==============
        ...window.ChatSessionsMixin,
        ...window.ChatRagMixin,
        ...window.ChatDebateMixin,

        // ============== Core Methods ==============

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
            this.checkEmailAvailable();
            this.checkBookstackAvailable();

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
                            const defaultModel = data.provider_default_model || '';
                            this.log(`Provider default model: "${defaultModel}"`);
                            
                            // Try exact match first
                            if (defaultModel && this.models.includes(defaultModel)) {
                                this.currentModel = defaultModel;
                                this.log(`Using exact match for default model: ${defaultModel}`);
                            } else if (defaultModel) {
                                // Try case-insensitive match
                                const lowerDefault = defaultModel.toLowerCase();
                                const match = this.models.find(m => m.toLowerCase() === lowerDefault);
                                if (match) {
                                    this.currentModel = match;
                                    this.log(`Using case-insensitive match for default model: ${match}`);
                                } else {
                                    // Fallback to first model
                                    this.currentModel = this.models[0];
                                    this.log(`Default model "${defaultModel}" not found in models list, using first: ${this.models[0]}`);
                                }
                            } else {
                                this.currentModel = this.models[0];
                                this.log(`No default model set, using first: ${this.models[0]}`);
                            }
                        }
                        this.log(`Loaded ${this.models.length} models from active provider, current: ${this.currentModel}`);
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

        async checkEmailAvailable() {
            try {
                const r = await fetch('/api/settings/email/config');
                if (r.ok) {
                    const data = await r.json();
                    this.emailAgentAvailable = data.is_available || false;
                }
            } catch (e) {
                this.emailAgentAvailable = false;
            }
        },

        async checkBookstackAvailable() {
            try {
                const r = await fetch('/api/settings/bookstack/config');
                console.log('[Bookstack] Config response status:', r.status);
                if (r.ok) {
                    const data = await r.json();
                    console.log('[Bookstack] Config data:', JSON.stringify(data));
                    this.bookstackAvailable = data.is_available || false;
                    console.log('[Bookstack] bookstackAvailable set to:', this.bookstackAvailable);
                }
            } catch (e) {
                console.error('[Bookstack] Check failed:', e);
                this.bookstackAvailable = false;
            }
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
                        web_search: this.webSearchEnabled,
                        email_context: this.emailAgentEnabled,
                        bookstack_context: this.bookstackEnabled
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
                                    if (json.email_context) {
                                        this.messages[msgIndex].email_context = json.email_context;
                                    }
                                    if (json.email_actions) {
                                        this.messages[msgIndex].email_actions = json.email_actions;
                                    }
                                    if (json.bookstack_sources) {
                                        this.messages[msgIndex].bookstack_sources = json.bookstack_sources;
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

        // TTS: Toggle speech synthesis
        toggleSpeech(content, id) {
            if (this.speakingId === id) {
                window.speechSynthesis.cancel();
                this.speakingId = null;
                return;
            }
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(content);
            utterance.lang = this.voiceSettings.lang || 'fr-FR';
            utterance.rate = this.voiceSettings.rate || 1;
            if (this.voiceSettings.voiceURI) {
                const voice = this.availableVoices.find(v => v.voiceURI === this.voiceSettings.voiceURI);
                if (voice) utterance.voice = voice;
            }
            utterance.onend = () => { this.speakingId = null; };
            utterance.onerror = () => { this.speakingId = null; };
            this.speakingId = id;
            window.speechSynthesis.speak(utterance);
        },

        // Drag & Drop file handler
        handleDrop(event) {
            this.isDragging = false;
            const files = event.dataTransfer?.files;
            if (!files || files.length === 0) return;
            for (const file of files) {
                if (file.type.startsWith('image/')) {
                    this.fileToBase64(file).then(base64 => {
                        this.pendingImages.push({ name: file.name, data: base64.split(',')[1] });
                    });
                } else if (file.type === 'application/pdf') {
                    // Simulate PDF upload
                    const fakeEvent = { target: { files: [file], value: '' } };
                    this.handlePdfUpload(fakeEvent);
                }
            }
        },

        // Paste handler for images
        handlePaste(event) {
            const items = event.clipboardData?.items;
            if (!items) return;
            for (const item of items) {
                if (item.type.startsWith('image/')) {
                    const file = item.getAsFile();
                    if (file) {
                        this.fileToBase64(file).then(base64 => {
                            this.pendingImages.push({ name: 'pasted-image.png', data: base64.split(',')[1] });
                        });
                    }
                }
            }
        },

        // Get filtered sessions based on search query
        get filteredSessions() {
            if (!this.sessionSearchQuery.trim()) return this.sessions;
            const q = this.sessionSearchQuery.toLowerCase();
            return this.sessions.filter(s =>
                (s.title || '').toLowerCase().includes(q)
            );
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
        }
    }));
});
