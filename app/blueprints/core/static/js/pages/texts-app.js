/**
 * Texts Application Component
 * Alpine.js component for the /texts page (text tools)
 */
(function () {
    // Définition du composant
    const textsAppComponent = () => ({
        // Load current tool from URL hash, localStorage, or default
        currentTool: (() => {
            const hash = window.location.hash.slice(1);
            const validTools = ['reformulation', 'translation', 'correction', 'email', 'prompt', 'summarize', 'resume'];
            if (hash && validTools.includes(hash)) return hash;
            const stored = localStorage.getItem('texts_current_tool');
            if (stored && validTools.includes(stored)) return stored;
            return 'reformulation';
        })(),
        tools: [
            { id: 'reformulation', name: 'Reformulation' },
            { id: 'summarize', name: 'Résumer' },
            { id: 'translation', name: 'Traduction' },
            { id: 'correction', name: 'Correction' },
            { id: 'email', name: 'Email' },
            { id: 'prompt', name: 'Prompt IA' },
            { id: 'resume', name: 'CV Generator' }
        ],
        processing: false,
        // RAG State
        ragSessionId: localStorage.getItem('texts_rag_session_id') || 'gen-' + Date.now(),
        uploadedFile: null,
        uploading: false,
        uploadStatus: '',

        // Helper to get localStorage key for a tool's input
        getInputStorageKey(toolId) {
            return `texts_input_${toolId}`;
        },

        // Load input text for a specific tool from localStorage
        loadInputForTool(toolId) {
            return localStorage.getItem(this.getInputStorageKey(toolId)) || '';
        },

        // Save input text for a specific tool to localStorage
        saveInputForTool(toolId, value) {
            const key = this.getInputStorageKey(toolId);
            if (value) {
                localStorage.setItem(key, value);
            } else {
                localStorage.removeItem(key);
            }
        },

        // Input text - initialized from localStorage for current tool
        inputText: (() => {
            const hash = window.location.hash.slice(1);
            const validTools = ['reformulation', 'translation', 'correction', 'email', 'prompt', 'summarize', 'resume'];
            let currentTool = 'reformulation';
            if (hash && validTools.includes(hash)) {
                currentTool = hash;
            } else {
                const stored = localStorage.getItem('texts_current_tool');
                if (stored && validTools.includes(stored)) currentTool = stored;
            }
            return localStorage.getItem(`texts_input_${currentTool}`) || '';
        })(),
        resultText: '',
        currentModel: localStorage.getItem('selected_model') || '',
        models: [],
        showTools: true,
        showHistory: false,
        showModelSelector: false,
        loadingFromHistory: false,
        loadingFromHistory: false,
        history: [],
        historySearchQuery: '',
        historySearchQuery: '',
        historyTypeFilter: '',
        synonyms: null,
        options: { tones: [], formats: [], lengths: [], languages: [], email_tones: [] },
        selectedTone: 'Professionnel',
        selectedFormat: 'Paragraphe',
        selectedLength: 'Moyen',
        targetLanguage: 'Anglais',
        addEmojis: false,
        emailType: '',
        senderName: '',
        correctionOptions: { spelling: true, grammar: true, syntax: true, style: true },
        // New variables for redesigned UI
        showContext: false,
        contextText: '',
        showOptions: true,
        sidebarOpen: localStorage.getItem('texts_sidebar_open') !== 'false',
        mobileMenuOpen: false,

        // Resume/CV Generator data
        resumeData: {
            firstname: 'Jean',
            lastname: 'Dupont',
            title: 'Product Designer',
            email: 'jean.dupont@example.com',
            phone: '+33 6 12 34 56 78',
            location: 'Paris, France',
            website: 'www.jeandupont.com',
            summary: 'Designer passionné avec plus de 5 ans d\'expérience dans la création d\'interfaces utilisateur intuitives et esthétiques.',
            experience: [
                { role: 'Senior Product Designer', company: 'Tech Solutions Inc.', date: '2020 - Présent', description: 'Direction de la conception de la nouvelle plateforme SaaS.' }
            ],
            education: [
                { school: 'École de Design de Paris', degree: 'Master en Design Numérique', date: '2016 - 2018' }
            ],
            skills: [{ name: 'Figma' }, { name: 'Adobe XD' }, { name: 'HTML/CSS' }],
            languages: [{ name: 'Français (Natif)' }, { name: 'Anglais (Courant)' }],
            interests: [{ name: 'Photographie' }, { name: 'Voyage' }],
            instructions: ''
        },
        resumeStyle: 'modern',
        resumeStyles: [
            { id: 'modern', name: 'Moderne' },
            { id: 'elegant', name: 'Élégant' },
            { id: 'minimalist', name: 'Minimaliste' }
        ],
        resumeSelectedModel: localStorage.getItem('resume_selected_model') || '',
        resumeGeneratedHtml: '',
        resumeLoading: false,
        resumeError: '',
        resumeFullscreen: false,

        // SPA lifecycle - stored handlers for cleanup
        _hashChangeHandler: null,
        _saveDebounceTimer: null,

        get filteredHistory() {
            let filtered = this.history;

            // Filter by Type
            if (this.historyTypeFilter) {
                filtered = filtered.filter(item => item.type === this.historyTypeFilter);
            }

            // Filter by Search Query
            if (this.historySearchQuery.trim()) {
                const query = this.historySearchQuery.toLowerCase();
                filtered = filtered.filter(item => {
                    const searchContent = (item.input + ' ' + item.result).toLowerCase();
                    return searchContent.includes(query);
                });
            }
            return filtered;
        },

        formatResult(content) {
            try {
                if (typeof marked === 'undefined') return content;
                // Configure marked to handle line breaks if needed, or use default
                let html = marked.parse(content);
                // Add copy button to each <pre> block (reusing chat logic style)
                html = html.replace(/<pre>([\s\S]*?)<\/pre>/g, (match, codeContent) => {
                    return `<div class="code-block-wrapper"><button class="copy-code-btn" onclick="copyCodeBlock(this)" title="Copier le code"><svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg></button><pre>${codeContent}</pre></div>`;
                });
                return html;
            } catch (e) {
                return content;
            }
        },

        async init() {
            // Load input for current tool from its dedicated localStorage key
            this.inputText = this.loadInputForTool(this.currentTool);

            // Update URL hash to match current tool
            if (window.location.hash.slice(1) !== this.currentTool) {
                history.replaceState(null, '', '#' + this.currentTool);
            }

            await this.loadModels();
            await this.loadOptions();
            await this.loadHistory();

            this.$watch('currentModel', value => localStorage.setItem('selected_model', value));

            // Watch currentTool changes - save current input, load new tool's input
            this.$watch('currentTool', (newTool, oldTool) => {
                // Save current input to old tool's storage before switching
                if (oldTool) {
                    this.saveInputForTool(oldTool, this.inputText);
                }

                // Persist current tool
                localStorage.setItem('texts_current_tool', newTool);
                history.replaceState(null, '', '#' + newTool);

                // Load input for new tool (unless loading from history)
                if (!this.loadingFromHistory) {
                    this.inputText = this.loadInputForTool(newTool);
                    this.resultText = '';
                    this.synonyms = null;
                }
                this.loadingFromHistory = false;
            });

            // Watch inputText changes - save to current tool's storage with debounce
            this.$watch('inputText', value => {
                // Debounce saves to avoid excessive writes
                if (this._saveDebounceTimer) {
                    clearTimeout(this._saveDebounceTimer);
                }
                this._saveDebounceTimer = setTimeout(() => {
                    this.saveInputForTool(this.currentTool, value);
                }, 300);
            });

            // Listen for hash changes (browser back/forward)
            this._hashChangeHandler = () => {
                const hash = window.location.hash.slice(1);
                const validTools = ['reformulation', 'translation', 'correction', 'email', 'prompt', 'summarize', 'resume'];
                if (hash && validTools.includes(hash) && hash !== this.currentTool) {
                    this.currentTool = hash;
                }
            };
            window.addEventListener('hashchange', this._hashChangeHandler);

            // Listen for provider changes
            this._providerChangeHandler = async () => {
                console.log('[textsApp] Provider changed, reloading models...');
                await this.loadModels();
            };
            window.addEventListener('provider-changed', this._providerChangeHandler);
        },

        // Retourne le titre de l'outil courant
        getToolTitle() {
            const tool = this.tools.find(t => t.id === this.currentTool);
            return tool ? tool.name : 'Outil';
        },

        getOutputLabel() {
            const labels = {
                'reformulation': 'Texte reformulé',
                'summarize': 'Résumé',
                'translation': 'Traduction',
                'correction': 'Texte corrigé',
                'email': 'Email généré',
                'prompt': 'Prompt généré'
            };
            return labels[this.currentTool] || 'Résultat';
        },

        toggleSidebar() {
            this.sidebarOpen = !this.sidebarOpen;
            localStorage.setItem('texts_sidebar_open', this.sidebarOpen);
        },

        // Change l'outil courant - le $watch('currentTool') gère la sauvegarde/chargement
        setTool(toolId) {
            // Modification de currentTool déclenche le $watch qui fait le reste
            this.currentTool = toolId;
            // Fermer le panneau outils sur mobile
            if (window.innerWidth < 640) {
                this.showTools = false;
                this.mobileMenuOpen = false;
            }
        },



        // Reset method
        resetCurrentTool() {
            this.inputText = '';
            this.resultText = '';
            this.synonyms = null;
            this.uploadedFile = null;
            this.uploadStatus = '';

            // Also clear from localStorage
            this.saveInputForTool(this.currentTool, '');

            if (this.currentTool === 'email') {
                this.emailType = '';
                this.senderName = '';
            }
            if (this.currentTool === 'reformulation') {
                this.contextText = '';
                this.showContext = false;
            }
        },

        generateUUID() {
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
                var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        },

        async uploadFile(event) {
            const file = event.target.files[0];
            if (!file) return;

            if (file.type !== 'application/pdf') {
                alert('Seuls les fichiers PDF sont acceptés via RAG');
                return;
            }

            this.uploading = true;
            this.uploadStatus = 'Upload en cours...';
            this.uploadedFile = null;

            const formData = new FormData();
            formData.append('file', file);
            formData.append('session_id', this.ragSessionId);

            try {
                const response = await fetch('/api/chat/upload-pdf', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Erreur lors de l\'upload');
                }

                // Document is pending/processing - start polling
                this.uploadedFile = {
                    name: file.name,
                    id: data.document_id,
                    status: data.status || 'pending'
                };
                this.uploadStatus = 'Indexation en cours...';
                this.uploading = false;

                // Start polling for status
                this.pollDocumentStatus();

            } catch (e) {
                console.error('Upload Error:', e);
                this.uploadStatus = 'Erreur: ' + e.message;
                this.uploadedFile = null;
                this.uploading = false;
            } finally {
                event.target.value = '';
            }
        },

        async pollDocumentStatus() {
            if (!this.uploadedFile || !this.ragSessionId) return;

            try {
                const response = await fetch(`/api/chat/sessions/${this.ragSessionId}/documents`);
                if (response.ok) {
                    const data = await response.json();
                    const doc = (data.documents || []).find(d => d.id === this.uploadedFile.id);

                    if (doc) {
                        this.uploadedFile.status = doc.status;

                        if (doc.status === 'completed') {
                            // Fetch document stats to get token count
                            try {
                                const statsResp = await fetch(`/api/rag/documents/${doc.id}/chunks`);
                                if (statsResp.ok) {
                                    const statsData = await statsResp.json();
                                    const tokens = statsData.stats?.estimated_tokens || 0;
                                    this.uploadedFile.tokens = tokens;
                                    this.uploadStatus = `~${tokens.toLocaleString()} tokens`;
                                } else {
                                    this.uploadStatus = 'PDF indexé';
                                }
                            } catch (e) {
                                this.uploadStatus = 'PDF indexé';
                            }
                            return; // Stop polling
                        } else if (doc.status === 'error') {
                            this.uploadStatus = 'Erreur lors de l\'indexation';
                            return; // Stop polling
                        } else {
                            // Still processing - continue polling
                            this.uploadStatus = 'Indexation en cours...';
                            setTimeout(() => this.pollDocumentStatus(), 2000);
                        }
                    } else {
                        // Document not found yet, keep polling
                        setTimeout(() => this.pollDocumentStatus(), 2000);
                    }
                }
            } catch (e) {
                console.error('Polling error:', e);
                // Retry after delay
                setTimeout(() => this.pollDocumentStatus(), 3000);
            }
        },

        removeFile() {
            this.uploadedFile = null;
            this.uploadStatus = '';
        },

        async loadModels() {
            try {
                // First try active provider
                const r = await fetch('/api/settings/providers/active/models');
                if (r.ok) {
                    const data = await r.json();
                    if (data.models && data.models.length > 0) {
                        // Filter embedding models and extract unique IDs
                        const embeddingPatterns = ['embed', 'bge-', 'bge:', 'all-minilm', 'snowflake-arctic', 'paraphrase', '/e5-', ':e5-', '/e5:', 'gte-', 'gte:', 'jina-', 'text-embedding', 'embedding-'];
                        const seen = new Set();
                        this.models = data.models
                            .map(m => {
                                if (typeof m === 'string') return m;
                                return m.id || m.name || '';
                            })
                            .filter(name => {
                                if (!name || seen.has(name)) return false;
                                seen.add(name);
                                const lowerName = name.toLowerCase();
                                return !embeddingPatterns.some(pattern => lowerName.includes(pattern));
                            });
                        // Use provider_default_model if set, otherwise fallback to localStorage or first model
                        // Logic:
                        // 1. If we have a provider default, and current is empty/invalid, use default.
                        // 2. If current is set but not in list, try default.
                        // 3. If no default, use first.
                        const isValidCurrent = this.currentModel && this.models.includes(this.currentModel);

                        if (!isValidCurrent) {
                            if (data.provider_default_model && this.models.includes(data.provider_default_model)) {
                                this.currentModel = data.provider_default_model;
                            } else if (this.models.length > 0) {
                                this.currentModel = this.models[0];
                            } else {
                                this.currentModel = '';
                            }
                        }
                        return;
                    }
                }
                // Fallback to old endpoint
                const fallback = await fetch('/api/models');
                const data = await fallback.json();
                this.models = (data.models || []).map(m => typeof m === 'string' ? m : m.name);

                if (this.models.length > 0) {
                    const isValidCurrent = this.currentModel && this.models.includes(this.currentModel);
                    if (!isValidCurrent) {
                        this.currentModel = this.models[0];
                    }
                } else {
                    this.currentModel = '';
                }
            } catch (e) {
                console.error('Error loading models:', e);
            }
        },

        async loadOptions() {
            try {
                const response = await fetch('/api/texts/options');
                const data = await response.json();
                if (data.options) this.options = data.options;
            } catch (e) {
                console.error('Error loading options:', e);
            }
        },

        async loadHistory() {
            try {
                const response = await fetch('/api/texts/history');
                const data = await response.json();
                this.history = data.history || [];
            } catch (e) {
                console.error('Error loading history:', e);
            }
        },

        // Main processing function
        async process() {
            if (this.currentTool === 'resume') {
                // For CV generation, use dedicated method
                await this.generateResume();
                return;
            }

            // For other tools, use standard processing
            const hasValidFile = this.uploadedFile && this.uploadedFile.status === 'completed';
            const hasContent = this.inputText || (this.currentTool === 'summarize' && hasValidFile);
            if (this.processing || !hasContent || !this.currentModel) return;
            this.processing = true;
            this.resultText = '';
            this.synonyms = null;

            let endpoint = '';
            let payload = { text: this.inputText, model: this.currentModel };

            switch (this.currentTool) {
                case 'reformulation':
                    endpoint = '/api/texts/reformulate';
                    payload.tone = this.selectedTone;
                    payload.format = this.selectedFormat;
                    payload.length = this.selectedLength;
                    payload.add_emojis = this.addEmojis;
                    break;
                case 'translation':
                    endpoint = '/api/texts/translate';
                    payload.target_language = this.targetLanguage;
                    break;
                case 'correction':
                    endpoint = '/api/texts/correct';
                    Object.assign(payload, this.correctionOptions);
                    payload.synonyms = true;
                    break;
                case 'email':
                    endpoint = '/api/texts/generate-email';
                    delete payload.text;
                    payload.content = this.inputText;
                    payload.email_type = this.emailType;
                    payload.sender_name = this.senderName;
                    payload.tone = this.selectedTone;
                    break;
                case 'prompt':
                    endpoint = '/api/texts/generate-prompt';
                    delete payload.text;
                    payload.description = this.inputText;
                    break;
                case 'summarize':
                    endpoint = '/api/texts/summarize';
                    if (this.uploadedFile) {
                        payload.session_id = this.ragSessionId;
                    }
                    if (!payload.text && !payload.session_id) {
                        // Should be handled by backend, but safe measure
                    }
                    break;
            }

            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (data.error) throw new Error(data.error);
                this.resultText = data.result;
                if (data.synonyms) this.synonyms = data.synonyms;
                await this.loadHistory();
            } catch (e) {
                console.error('Processing error:', e);
                this.resultText = "Erreur: " + e.message;
            } finally {
                this.processing = false;
            }
        },

        copyResult() {
            navigator.clipboard.writeText(this.resultText);
        },

        async pasteFromClipboard() {
            try {
                const text = await navigator.clipboard.readText();
                this.inputText = text;
            } catch (e) {
                console.error('Error pasting from clipboard:', e);
            }
        },

        async clearHistory() {
            if (!confirm('Supprimer tout l\'historique ?')) return;
            try {
                await fetch('/api/texts/history', { method: 'DELETE' });
                this.history = [];
            } catch (e) {
                console.error('Error clearing history:', e);
            }
        },

        async deleteHistoryItem(id) {
            try {
                await fetch(`/api/texts/history/${id}`, { method: 'DELETE' });
                this.history = this.history.filter(h => h.id !== id);
            } catch (e) {
                console.error('Error deleting item:', e);
            }
        },

        loadHistoryItem(item) {
            // Mark as loading from history to avoid reset
            this.loadingFromHistory = true;
            this.currentTool = item.type;
            this.inputText = item.input || item.options?.content || '';
            this.resultText = item.output || '';
            if (item.model) {
                const itemModel = item.model; // Sauvegarder le modèle
                this.currentModel = itemModel;

                // Résoudre le provider pour ce modèle et le définir comme actif
                (async () => {
                    try {
                        const providerResp = await fetch('/api/settings/providers/resolve-model', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ model: itemModel })
                        });
                        if (providerResp.ok) {
                            const providerData = await providerResp.json();
                            if (providerData.found && providerData.provider_id) {
                                // Changer le provider actif
                                await fetch('/api/settings/providers/active', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ provider_id: providerData.provider_id })
                                });
                                // Recharger les modèles du nouveau provider
                                await this.loadModels();
                                // Forcer le modèle de l'historique (peut avoir été écrasé par loadModels)
                                this.currentModel = itemModel;
                                // Mettre à jour le sélecteur de provider global
                                window.dispatchEvent(new CustomEvent('providers-changed'));
                                console.log(`[textsApp] Provider switched to ${providerData.provider_name} for model ${itemModel}`);
                            }
                        }
                    } catch (e) {
                        console.log('[textsApp] Could not resolve provider for model:', itemModel);
                    }
                })();
            }
            if (item.options) {
                if (item.type === 'reformulation') {
                    this.selectedTone = item.options.tone || 'Professionnel';
                    this.selectedFormat = item.options.format || 'Paragraphe';
                    this.selectedLength = item.options.length || 'Moyen';
                    this.addEmojis = item.options.add_emojis || false;
                } else if (item.type === 'translation') {
                    this.targetLanguage = item.options.target_language || 'Anglais';
                } else if (item.type === 'email') {
                    this.emailType = item.options.email_type || '';
                    this.senderName = item.options.sender_name || '';
                    this.selectedTone = item.options.tone || 'Professionnel';
                } else if (item.type === 'correction') {
                    this.correctionOptions = {
                        spelling: item.options.spelling ?? true,
                        grammar: item.options.grammar ?? true,
                        syntax: item.options.syntax ?? true,
                        style: item.options.style ?? false
                    };
                }
            }
        },

        formatDate(isoString) {
            return new Date(isoString).toLocaleString('fr-FR', {
                month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
            });
        },

        // ========== CV Generator Methods ==========

        // CRUD methods for CV sections
        addExperience() { this.resumeData.experience.push({ role: '', company: '', date: '', description: '' }); },
        removeExperience(index) { this.resumeData.experience.splice(index, 1); },
        addEducation() { this.resumeData.education.push({ school: '', degree: '', date: '' }); },
        removeEducation(index) { this.resumeData.education.splice(index, 1); },
        addSkill() { this.resumeData.skills.push({ name: '' }); },
        removeSkill(index) { this.resumeData.skills.splice(index, 1); },
        addLanguage() { this.resumeData.languages.push({ name: '' }); },
        removeLanguage(index) { this.resumeData.languages.splice(index, 1); },
        addInterest() { this.resumeData.interests.push({ name: '' }); },
        removeInterest(index) { this.resumeData.interests.splice(index, 1); },

        // Reset all CV fields to empty
        resetResume() {
            this.resumeData = {
                firstname: '',
                lastname: '',
                title: '',
                email: '',
                phone: '',
                location: '',
                website: '',
                summary: '',
                experience: [],
                education: [],
                skills: [],
                languages: [],
                interests: [],
                instructions: ''
            };
            this.resumeGeneratedHtml = '';
            this.resumeError = '';
        },

        // Generate CV
        async generateResume() {
            if (!this.currentModel) {
                this.resumeError = 'Veuillez sélectionner un modèle IA en haut à gauche';
                return;
            }

            this.resumeLoading = true;
            this.resumeError = '';

            try {
                const response = await fetch('/api/resume/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        data: this.resumeData,
                        style: this.resumeStyle,
                        model: this.currentModel
                    })
                });

                const result = await response.json();

                if (result.success) {
                    this.resumeGeneratedHtml = result.html;
                    this.resumeError = '';
                } else {
                    this.resumeError = result.error || 'Erreur lors de la génération du CV';
                    this.resumeGeneratedHtml = '';
                }
            } catch (err) {
                console.error('CV Generation Error:', err);
                this.resumeError = 'Erreur de connexion au serveur';
                this.resumeGeneratedHtml = '';
            } finally {
                this.resumeLoading = false;
            }
        },

        // Download HTML
        downloadResumeHTML() {
            if (!this.resumeGeneratedHtml) {
                alert('Veuillez d\'abord générer le CV');
                return;
            }

            const fullHTML = `<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CV - ${this.resumeData.firstname} ${this.resumeData.lastname}</title>
    <script src="https://cdn.tailwindcss.com"><\/script>
    <style>
        body { background-color: #f3f4f6; display: flex; justify-content: center; padding: 40px; }
        .cv-container { box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25); margin: 0 auto; }
        @media print {
            body { background: none; padding: 0; display: block; }
            .cv-container { box-shadow: none; margin: 0; width: 100%; height: 100%; }
        }
    </style>
</head>
<body>
    ${this.resumeGeneratedHtml}
</body>
</html>`;
            const blob = new Blob([fullHTML], { type: 'text/html' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `cv-${this.resumeData.firstname.toLowerCase()}-${this.resumeData.lastname.toLowerCase()}.html`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        },

        // Download PDF
        async downloadResumePDF() {
            if (!this.resumeGeneratedHtml) {
                alert('Veuillez d\'abord générer le CV');
                return;
            }

            // Check if jsPDF is loaded
            if (typeof window.jspdf === 'undefined') {
                alert('Bibliothèque PDF non chargée. Veuillez rafraîchir la page.');
                return;
            }

            const { jsPDF } = window.jspdf;
            const element = document.getElementById('cv-preview-resume');

            if (!element) {
                alert('Erreur: Zone de prévisualisation introuvable');
                return;
            }

            try {
                const canvas = await html2canvas(element, {
                    scale: 2,
                    useCORS: true,
                    logging: false
                });

                const imgData = canvas.toDataURL('image/jpeg', 1.0);
                const pdf = new jsPDF('p', 'mm', 'a4');
                const pdfWidth = pdf.internal.pageSize.getWidth();
                const pdfHeight = pdf.internal.pageSize.getHeight();

                pdf.addImage(imgData, 'JPEG', 0, 0, pdfWidth, pdfHeight);
                pdf.save(`cv-${this.resumeData.firstname.toLowerCase()}-${this.resumeData.lastname.toLowerCase()}.pdf`);
            } catch (error) {
                console.error('PDF Generation Error:', error);
                alert('Erreur lors de la génération du PDF');
            }
        },

        /**
         * Destroy method for SPA lifecycle.
         * Cleans up event listeners.
         */
        destroy() {
            console.log('[textsApp] Destroying component');

            // Remove hashchange listener
            if (this._hashChangeHandler) {
                window.removeEventListener('hashchange', this._hashChangeHandler);
                this._hashChangeHandler = null;
            }

            // Remove provider-changed listener
            if (this._providerChangeHandler) {
                window.removeEventListener('provider-changed', this._providerChangeHandler);
                this._providerChangeHandler = null;
            }

            console.log('[textsApp] Cleanup complete');
        }
    });

    // Fonction d'enregistrement
    function registerComponent() {
        if (typeof Alpine !== 'undefined' && Alpine.data) {
            Alpine.data('textsApp', textsAppComponent);
            console.log('[textsApp] Component registered');
        }
    }

    // Enregistrer immédiatement si Alpine est déjà chargé (cas SPA navigation)
    if (typeof Alpine !== 'undefined' && Alpine.data) {
        registerComponent();
    }

    // Aussi s'enregistrer sur alpine:init pour le chargement initial
    document.addEventListener('alpine:init', registerComponent);
})();
