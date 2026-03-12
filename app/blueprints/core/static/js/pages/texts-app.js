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
            const validTools = ['reformulation', 'translation', 'correction', 'email', 'prompt', 'summarize', 'resume', 'mermaid', 'documentation', 'extractor', 'simplify', 'expand', 'todolist', 'script', 'recipe', 'fitness', 'admin_letter', 'flashcards', 'eli5', 'speech', 'decision', 'regex', 'converter', 'log_parser'];
            if (hash && validTools.includes(hash)) return hash;
            const stored = localStorage.getItem('texts_current_tool');
            if (stored && validTools.includes(stored)) return stored;
            return 'reformulation';
        })(),
        toolSections: [
            {
                id: 'redaction', name: 'Rédaction', icon: 'pencil',
                tools: [
                    { id: 'reformulation', name: 'Reformulation' },
                    { id: 'email', name: 'Email' },
                    { id: 'speech', name: 'Discours' },
                    { id: 'admin_letter', name: 'Lettre admin.' }
                ]
            },
            {
                id: 'analyse', name: 'Analyse', icon: 'search',
                tools: [
                    { id: 'summarize', name: 'Résumer' },
                    { id: 'correction', name: 'Correction' },
                    { id: 'extractor', name: 'Extracteur' },
                    { id: 'simplify', name: 'Simplificateur' },
                    { id: 'expand', name: 'Expandeur' }
                ]
            },
            {
                id: 'technique', name: 'Technique', icon: 'code',
                tools: [
                    { id: 'script', name: 'Script' },
                    { id: 'mermaid', name: 'Diagramme' },
                    { id: 'documentation', name: 'Documentation' },
                    { id: 'regex', name: 'Regex' },
                    { id: 'converter', name: 'Convertisseur' },
                    { id: 'log_parser', name: 'Parseur Logs' }
                ]
            },
            {
                id: 'generateurs', name: 'Générateurs', icon: 'bolt',
                tools: [
                    { id: 'prompt', name: 'Prompt IA' },
                    { id: 'todolist', name: 'Plan d\'action' },
                    { id: 'flashcards', name: 'Flashcards' },
                    { id: 'resume', name: 'CV Generator' }
                ]
            },
            {
                id: 'quotidien', name: 'Quotidien', icon: 'star',
                tools: [
                    { id: 'translation', name: 'Traduction' },
                    { id: 'eli5', name: 'Expliqueur' },
                    { id: 'recipe', name: 'Recettes' },
                    { id: 'fitness', name: 'Coach sportif' },
                    { id: 'decision', name: 'Aide décision' }
                ]
            }
        ],
        // Flat tools list (computed from sections)
        get tools() {
            return this.toolSections.flatMap(s => s.tools);
        },
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
            const validTools = ['reformulation', 'translation', 'correction', 'email', 'prompt', 'summarize', 'resume', 'mermaid', 'documentation', 'extractor', 'simplify', 'expand', 'todolist', 'script', 'recipe', 'fitness', 'admin_letter', 'flashcards', 'eli5', 'speech', 'decision', 'regex', 'converter', 'log_parser'];
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
        showTools: window.innerWidth >= 640,
        showHistory: false,
        showModelSelector: false,
        loadingFromHistory: false,
        history: [],
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
        // Documentation Writer state
        docStyle: 'Technique',
        docStyles: ['Technique', 'Fonctionnelle', 'Tutoriel', 'Procedure', 'Cheatsheet'],
        docPreviousResult: '',
        docImprovementPrompt: '',
        docOriginalOutline: '',
        docSourceImages: [],
        docEmbedImages: [],
        docPasteChoiceOpen: false,
        _docPendingPasteFile: null,
        // New variables for redesigned UI
        showContext: false,
        contextText: '',
        showOptions: true,
        sidebarOpen: localStorage.getItem('texts_sidebar_open') !== 'false',
        mobileMenuOpen: false,

        // New tools state
        extractFormat: 'JSON',
        simplifyLevel: 'Grand public',
        expandTone: 'Professionnel',
        expandLength: 'Moyen',
        emailMode: 'generate',
        emailReceived: '',
        replyType: 'Réponse neutre',
        coverLetterData: { job_title: '', company: '', profile: '' },
        paraphraseMode: false,
        outputFullscreen: false,

        // New tools state (9 new tools)
        recipeDiet: 'Sans restriction',
        recipeTime: '',
        recipeServings: '',
        fitnessGoal: '',
        fitnessEquipment: '',
        fitnessLevel: 'Débutant',
        adminLetterType: '',
        flashcardDifficulty: 'Intermédiaire',
        flashcardFormat: 'Question/Réponse',
        eli5Level: 'Grand public',
        speechOccasion: '',
        speechTone: '',
        convertTargetFormat: 'JSON',
        // Sidebar section collapse state
        collapsedSections: JSON.parse(localStorage.getItem('texts_collapsed_sections') || '{}'),

        // Log Parser state
        logParserLanguage: 'Auto',

        // Script Generator state
        scriptLanguage: 'Bash',
        scriptCommented: false,
        scriptStrictMode: false,

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

        // ============== Mixins ==============
        ...window.TextsResumeMixin,
        ...window.TextsMermaidMixin,

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
                const validTools = ['reformulation', 'translation', 'correction', 'email', 'prompt', 'summarize', 'resume', 'mermaid', 'documentation', 'extractor', 'simplify', 'expand', 'todolist', 'script', 'recipe', 'fitness', 'admin_letter', 'flashcards', 'eli5', 'speech', 'decision', 'regex', 'converter', 'log_parser'];
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
                'prompt': 'Prompt généré',
                'mermaid': 'Diagramme Mermaid',
                'documentation': 'Documentation générée',
                'extractor': 'Données extraites',
                'simplify': 'Texte simplifié',
                'expand': 'Texte développé',
                'todolist': 'Plan d\'action',
                'recipe': 'Recette générée',
                'fitness': 'Programme sportif',
                'admin_letter': 'Lettre administrative',
                'flashcards': 'Flashcards',
                'eli5': 'Explication',
                'speech': 'Discours',
                'decision': 'Analyse comparative',
                'regex': 'Expression reguliere',
                'converter': 'Donnees converties',
                'log_parser': 'Diagnostic'
            };
            return labels[this.currentTool] || 'Résultat';
        },

        toggleSection(sectionId) {
            this.collapsedSections[sectionId] = !this.collapsedSections[sectionId];
            localStorage.setItem('texts_collapsed_sections', JSON.stringify(this.collapsedSections));
        },

        isSectionCollapsed(sectionId) {
            return !!this.collapsedSections[sectionId];
        },

        toggleOutputFullscreen() {
            this.outputFullscreen = !this.outputFullscreen;
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
                this.emailMode = 'generate';
                this.emailReceived = '';
                this.replyType = 'Réponse neutre';
                this.coverLetterData = { job_title: '', company: '', profile: '' };
            }
            if (this.currentTool === 'reformulation') {
                this.contextText = '';
                this.showContext = false;
                this.paraphraseMode = false;
            }
            if (this.currentTool === 'mermaid') {
                this.resetMermaid();
            }
            if (this.currentTool === 'documentation') {
                this.docPreviousResult = '';
                this.docImprovementPrompt = '';
                this.docOriginalOutline = '';
                this.docSourceImages = [];
                this.docEmbedImages = [];
            }
            if (this.currentTool === 'extractor') {
                this.extractFormat = 'JSON';
            }
            if (this.currentTool === 'simplify') {
                this.simplifyLevel = 'Grand public';
            }
            if (this.currentTool === 'expand') {
                this.expandTone = 'Professionnel';
                this.expandLength = 'Moyen';
            }
            if (this.currentTool === 'script') {
                this.scriptLanguage = 'Bash';
                this.scriptCommented = false;
                this.scriptStrictMode = false;
            }
            if (this.currentTool === 'recipe') {
                this.recipeDiet = 'Sans restriction';
                this.recipeTime = '';
                this.recipeServings = '';
            }
            if (this.currentTool === 'fitness') {
                this.fitnessGoal = '';
                this.fitnessEquipment = '';
                this.fitnessLevel = 'Débutant';
            }
            if (this.currentTool === 'admin_letter') {
                this.adminLetterType = '';
            }
            if (this.currentTool === 'flashcards') {
                this.flashcardDifficulty = 'Intermédiaire';
                this.flashcardFormat = 'Question/Réponse';
            }
            if (this.currentTool === 'eli5') {
                this.eli5Level = 'Grand public';
            }
            if (this.currentTool === 'speech') {
                this.speechOccasion = '';
                this.speechTone = '';
            }
            if (this.currentTool === 'converter') {
                this.convertTargetFormat = 'JSON';
            }
            if (this.currentTool === 'log_parser') {
                this.logParserLanguage = 'Auto';
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
                        const isValidCurrent = this.currentModel && this.models.includes(this.currentModel);
                        const defaultModel = data.provider_default_model || '';

                        if (!isValidCurrent) {
                            console.log(`[textsApp] Provider default model: "${defaultModel}"`);
                            
                            // Try exact match first
                            if (defaultModel && this.models.includes(defaultModel)) {
                                this.currentModel = defaultModel;
                                console.log(`[textsApp] Using exact match for default model: ${defaultModel}`);
                            } else if (defaultModel) {
                                // Try case-insensitive match
                                const lowerDefault = defaultModel.toLowerCase();
                                const match = this.models.find(m => m.toLowerCase() === lowerDefault);
                                if (match) {
                                    this.currentModel = match;
                                    console.log(`[textsApp] Using case-insensitive match for default model: ${match}`);
                                } else if (this.models.length > 0) {
                                    this.currentModel = this.models[0];
                                    console.log(`[textsApp] Default model "${defaultModel}" not found, using first: ${this.models[0]}`);
                                } else {
                                    this.currentModel = '';
                                }
                            } else if (this.models.length > 0) {
                                this.currentModel = this.models[0];
                                console.log(`[textsApp] No default model set, using first: ${this.models[0]}`);
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
                const response = await fetch('/api/tools/options');
                const data = await response.json();
                if (data.options) this.options = data.options;
            } catch (e) {
                console.error('Error loading options:', e);
            }
        },

        async loadHistory() {
            try {
                const response = await fetch('/api/tools/history');
                const data = await response.json();
                this.history = data.history || [];
            } catch (e) {
                console.error('Error loading history:', e);
            }
        },

        // Main processing function
        async process() {
            if (this.currentTool === 'resume') {
                await this.generateResume();
                return;
            }

            if (this.currentTool === 'mermaid') {
                await this.generateMermaid();
                return;
            }

            if (this.currentTool === 'documentation') {
                await this.processDocumentation();
                return;
            }

            // For other tools, use standard processing
            const hasValidFile = this.uploadedFile && this.uploadedFile.status === 'completed';
            let hasContent = this.inputText || (this.currentTool === 'summarize' && hasValidFile);
            // For email reply/cover_letter modes, inputText is optional (instructions supplémentaires)
            if (this.currentTool === 'email' && this.emailMode === 'reply' && this.emailReceived) hasContent = true;
            if (this.currentTool === 'email' && this.emailMode === 'cover_letter' && this.coverLetterData.job_title && this.coverLetterData.company) hasContent = true;
            if (this.processing || !hasContent || !this.currentModel) return;
            this.processing = true;
            this.resultText = '';
            this.synonyms = null;

            let endpoint = '';
            let payload = { text: this.inputText, model: this.currentModel };

            switch (this.currentTool) {
                case 'reformulation':
                    endpoint = '/api/tools/reformulate';
                    payload.tone = this.selectedTone;
                    payload.format = this.selectedFormat;
                    payload.length = this.selectedLength;
                    payload.add_emojis = this.addEmojis;
                    payload.paraphrase = this.paraphraseMode;
                    break;
                case 'translation':
                    endpoint = '/api/tools/translate';
                    payload.target_language = this.targetLanguage;
                    break;
                case 'correction':
                    endpoint = '/api/tools/correct';
                    Object.assign(payload, this.correctionOptions);
                    payload.synonyms = true;
                    break;
                case 'email':
                    endpoint = '/api/tools/generate-email';
                    payload.mode = this.emailMode;
                    if (this.emailMode === 'reply') {
                        payload.email_received = this.emailReceived;
                        payload.reply_type = this.replyType;
                        payload.content = this.inputText;
                        payload.sender_name = this.senderName;
                        payload.tone = this.selectedTone;
                    } else if (this.emailMode === 'cover_letter') {
                        payload.job_title = this.coverLetterData.job_title;
                        payload.company = this.coverLetterData.company;
                        payload.profile = this.coverLetterData.profile;
                        payload.content = this.inputText;
                        payload.sender_name = this.senderName;
                    } else {
                        delete payload.text;
                        payload.content = this.inputText;
                        payload.email_type = this.emailType;
                        payload.sender_name = this.senderName;
                        payload.tone = this.selectedTone;
                    }
                    break;
                case 'prompt':
                    endpoint = '/api/tools/generate-prompt';
                    delete payload.text;
                    payload.description = this.inputText;
                    break;
                case 'summarize':
                    endpoint = '/api/tools/summarize';
                    if (this.uploadedFile) {
                        payload.session_id = this.ragSessionId;
                    }
                    break;
                case 'extractor':
                    endpoint = '/api/tools/extract';
                    payload.output_format = this.extractFormat;
                    break;
                case 'simplify':
                    endpoint = '/api/tools/simplify';
                    payload.level = this.simplifyLevel;
                    break;
                case 'expand':
                    endpoint = '/api/tools/expand';
                    payload.tone = this.expandTone;
                    payload.length = this.expandLength;
                    break;
                case 'todolist':
                    endpoint = '/api/tools/todolist';
                    break;
                case 'script':
                    endpoint = '/api/tools/generate-script';
                    payload.description = payload.text;
                    payload.language = this.scriptLanguage;
                    payload.commented = this.scriptCommented;
                    payload.strict_mode = this.scriptStrictMode;
                    break;
                case 'recipe':
                    endpoint = '/api/tools/generate-recipe';
                    payload.diet = this.recipeDiet;
                    payload.time = this.recipeTime;
                    payload.servings = this.recipeServings;
                    break;
                case 'fitness':
                    endpoint = '/api/tools/generate-fitness';
                    payload.goal = this.fitnessGoal;
                    payload.equipment = this.fitnessEquipment;
                    payload.level = this.fitnessLevel;
                    break;
                case 'admin_letter':
                    endpoint = '/api/tools/generate-admin-letter';
                    payload.letter_type = this.adminLetterType;
                    break;
                case 'flashcards':
                    endpoint = '/api/tools/generate-flashcards';
                    payload.difficulty = this.flashcardDifficulty;
                    payload.card_format = this.flashcardFormat;
                    break;
                case 'eli5':
                    endpoint = '/api/tools/explain-eli5';
                    payload.level = this.eli5Level;
                    break;
                case 'speech':
                    endpoint = '/api/tools/generate-speech';
                    payload.occasion = this.speechOccasion;
                    payload.tone = this.speechTone;
                    break;
                case 'decision':
                    endpoint = '/api/tools/compare-decide';
                    break;
                case 'regex':
                    endpoint = '/api/tools/generate-regex';
                    break;
                case 'converter':
                    endpoint = '/api/tools/convert-format';
                    payload.target_format = this.convertTargetFormat;
                    break;
                case 'log_parser':
                    endpoint = '/api/tools/parse-logs';
                    payload.language = this.logParserLanguage;
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

        async copyResultAsHtml() {
            if (!this.resultText) return;
            try {
                let html = typeof marked !== 'undefined' ? marked.parse(this.resultText) : this.resultText;
                const blob = new Blob([html], { type: 'text/html' });
                const plainBlob = new Blob([this.resultText], { type: 'text/plain' });
                await navigator.clipboard.write([
                    new ClipboardItem({
                        'text/html': blob,
                        'text/plain': plainBlob
                    })
                ]);
            } catch (e) {
                navigator.clipboard.writeText(this.resultText);
            }
        },

        getScriptExtension() {
            const lang = this.scriptLanguage;
            if (lang === 'Bash') return 'sh';
            if (lang === 'Python') return 'py';
            if (lang === 'PowerShell') return 'ps1';
            // Auto: detect from result
            if (this.resultText.includes('```bash') || this.resultText.includes('#!/bin/bash')) return 'sh';
            if (this.resultText.includes('```python') || this.resultText.includes('#!/usr/bin/env python')) return 'py';
            if (this.resultText.includes('```powershell')) return 'ps1';
            return 'sh';
        },

        downloadScript() {
            if (!this.resultText) return;
            // Extract code from markdown code block
            const codeMatch = this.resultText.match(/```(?:bash|python|powershell|sh|py|ps1)?\n([\s\S]*?)```/);
            const code = codeMatch ? codeMatch[1].trim() : this.resultText;
            const ext = this.getScriptExtension();
            const blob = new Blob([code], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `script.${ext}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        },

        async processDocumentation() {
            if (this.processing || !this.currentModel) return;
            const hasContent = this.inputText.trim() || this.docSourceImages.length > 0 || this.docEmbedImages.length > 0 || (this.docPreviousResult && this.docImprovementPrompt.trim());
            if (!hasContent) return;

            this.processing = true;
            this.resultText = '';

            const payload = {
                outline: this.inputText,
                model: this.currentModel,
                style: this.docStyle
            };

            if (this.docPreviousResult && this.docImprovementPrompt.trim()) {
                payload.previous_doc = this.docPreviousResult;
                payload.improvement_prompt = this.docImprovementPrompt;
            }

            if (this.docSourceImages.length > 0) {
                payload.source_images = this.docSourceImages.map(img => img.base64);
            }
            if (this.docEmbedImages.length > 0) {
                payload.embed_images = this.docEmbedImages.map((img, i) => ({ id: `IMAGE_${i + 1}`, base64: img.base64 }));
            }

            try {
                const response = await fetch('/api/tools/generate-documentation', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (data.error) throw new Error(data.error);
                this.resultText = data.result;
                this.docPreviousResult = data.result;
                this.docOriginalOutline = this.inputText;
                this.docImprovementPrompt = '';
                this.docSourceImages = [];
                await this.loadHistory();
            } catch (e) {
                console.error('Documentation error:', e);
                this.resultText = 'Erreur: ' + e.message;
            } finally {
                this.processing = false;
            }
        },

        docRenderWithImages(markdown) {
            if (!markdown) return '';
            let html = typeof marked !== 'undefined' ? marked.parse(markdown) : markdown;
            // Replace [IMAGE_N] markers with actual <img> tags from embed images
            if (this.docEmbedImages.length > 0) {
                html = html.replace(/\[IMAGE_(\d+)\]/g, (match, num) => {
                    const idx = parseInt(num) - 1;
                    if (idx >= 0 && idx < this.docEmbedImages.length) {
                        return `<img src="${this.docEmbedImages[idx].base64}" alt="Capture ${num}" style="max-width:100%;border-radius:8px;margin:8px 0;border:1px solid #e4e4e7;">`;
                    }
                    return match;
                });
            }
            // Add copy buttons to pre blocks
            html = html.replace(/<pre>([\s\S]*?)<\/pre>/g, (match, codeContent) => {
                return `<div class="code-block-wrapper"><button class="copy-code-btn" onclick="copyCodeBlock(this)" title="Copier le code"><svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg></button><pre>${codeContent}</pre></div>`;
            });
            return html;
        },

        async copyDocAsHtml() {
            if (!this.resultText) return;
            try {
                let html = typeof marked !== 'undefined' ? marked.parse(this.resultText) : this.resultText;
                // Replace [IMAGE_N] markers with embedded base64 images for Word paste
                if (this.docEmbedImages.length > 0) {
                    html = html.replace(/\[IMAGE_(\d+)\]/g, (match, num) => {
                        const idx = parseInt(num) - 1;
                        if (idx >= 0 && idx < this.docEmbedImages.length) {
                            return `<img src="${this.docEmbedImages[idx].base64}" alt="Capture ${num}" style="max-width:600px;">`;
                        }
                        return match;
                    });
                }
                const blob = new Blob([html], { type: 'text/html' });
                const plainBlob = new Blob([this.resultText], { type: 'text/plain' });
                await navigator.clipboard.write([
                    new ClipboardItem({
                        'text/html': blob,
                        'text/plain': plainBlob
                    })
                ]);
            } catch (e) {
                navigator.clipboard.writeText(this.resultText);
            }
        },

        copyDocAsMarkdown() {
            if (!this.resultText) return;
            navigator.clipboard.writeText(this.resultText);
        },

        improveDoc() {
            if (!this.docImprovementPrompt.trim() || !this.docPreviousResult) return;
            this.processDocumentation();
        },

        _docReadImageFile(file, targetArray) {
            if (!file.type.startsWith('image/')) return;
            if (file.size > 10 * 1024 * 1024) return;
            const reader = new FileReader();
            reader.onload = (e) => {
                targetArray.push({
                    id: 'img_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5),
                    base64: e.target.result,
                    preview: e.target.result,
                    name: file.name || 'Image'
                });
            };
            reader.readAsDataURL(file);
        },

        docAddSourceImages(event) {
            const files = event.target.files;
            if (!files) return;
            for (const file of files) {
                this._docReadImageFile(file, this.docSourceImages);
            }
            event.target.value = '';
        },

        async docHandlePaste(event) {
            const items = event?.clipboardData?.items || [];
            const imageFiles = [];
            let hasHtml = false;
            let hasText = false;

            // Synchronous scan: detect what's in clipboard BEFORE any await
            for (const item of items) {
                if (item.type === 'text/html') hasHtml = true;
                if (item.type === 'text/plain') hasText = true;
                if (item.type.startsWith('image/')) {
                    const file = item.getAsFile();
                    if (file) imageFiles.push(file);
                }
            }

            // Case 1: Direct image files (screenshot) — preventDefault synchronously
            if (imageFiles.length > 0) {
                event.preventDefault();
                if (hasText) {
                    // Read text async then add it
                    for (const item of items) {
                        if (item.type === 'text/plain') {
                            item.getAsString((text) => {
                                this.inputText = (this.inputText ? this.inputText + '\n' : '') + text;
                            });
                            break;
                        }
                    }
                    for (const file of imageFiles) {
                        this._docReadImageFile(file, this.docEmbedImages);
                    }
                } else {
                    this._docPendingPasteFile = imageFiles[0];
                    this.docPasteChoiceOpen = true;
                }
                return;
            }

            // Case 2: HTML content might contain <img> tags — preventDefault synchronously
            if (hasHtml) {
                event.preventDefault();

                // Now read content async
                let htmlContent = null;
                let textContent = null;
                const promises = [];
                for (const item of items) {
                    if (item.type === 'text/html') {
                        promises.push(new Promise(resolve => item.getAsString(s => { htmlContent = s; resolve(); })));
                    }
                    if (item.type === 'text/plain') {
                        promises.push(new Promise(resolve => item.getAsString(s => { textContent = s; resolve(); })));
                    }
                }
                await Promise.all(promises);

                const parser = new DOMParser();
                const doc = parser.parseFromString(htmlContent || '', 'text/html');
                const imgs = doc.querySelectorAll('img');

                // Always put text in textarea
                if (textContent) {
                    this.inputText = (this.inputText ? this.inputText + '\n' : '') + textContent;
                }

                // Extract images if found
                if (imgs.length > 0) {
                    for (const img of imgs) {
                        const src = img.getAttribute('src') || '';
                        if (src.startsWith('data:image/')) {
                            this.docEmbedImages.push({
                                id: 'img_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5),
                                base64: src, preview: src, name: 'Capture'
                            });
                        } else if (src.startsWith('http')) {
                            try {
                                const base64 = await this._docLoadImageFromUrl(src);
                                if (base64) {
                                    this.docEmbedImages.push({
                                        id: 'img_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5),
                                        base64, preview: base64, name: 'Capture'
                                    });
                                }
                            } catch (e) {
                                console.warn('Could not load pasted image:', src);
                            }
                        }
                    }
                }
                return;
            }

            // Case 3: No images, no HTML — let default textarea paste handle it
        },

        async _docLoadImageFromUrl(url) {
            try {
                const resp = await fetch('/api/tools/proxy-image', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });
                const data = await resp.json();
                return data.success ? data.base64 : null;
            } catch (e) {
                console.warn('Proxy image load failed:', url, e);
                return null;
            }
        },

        docPasteChoose(type) {
            if (!this._docPendingPasteFile) return;
            const target = type === 'source' ? this.docSourceImages : this.docEmbedImages;
            this._docReadImageFile(this._docPendingPasteFile, target);
            this._docPendingPasteFile = null;
            this.docPasteChoiceOpen = false;
        },

        docPasteChoiceCancel() {
            this._docPendingPasteFile = null;
            this.docPasteChoiceOpen = false;
        },

        docRemoveSourceImage(index) {
            this.docSourceImages.splice(index, 1);
        },

        docAddEmbedImages(event) {
            const files = event.target.files;
            if (!files) return;
            for (const file of files) {
                this._docReadImageFile(file, this.docEmbedImages);
            }
            event.target.value = '';
        },

        docRemoveEmbedImage(index) {
            this.docEmbedImages.splice(index, 1);
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
                await fetch('/api/tools/history', { method: 'DELETE' });
                this.history = [];
            } catch (e) {
                console.error('Error clearing history:', e);
            }
        },

        async deleteHistoryItem(id) {
            try {
                await fetch(`/api/tools/history/${id}`, { method: 'DELETE' });
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
                if (item.type === 'reformulation' || item.type === 'paraphrase') {
                    this.currentTool = 'reformulation';
                    this.selectedTone = item.options.tone || 'Professionnel';
                    this.selectedFormat = item.options.format || 'Paragraphe';
                    this.selectedLength = item.options.length || 'Moyen';
                    this.addEmojis = item.options.add_emojis || false;
                    this.paraphraseMode = item.options.paraphrase || false;
                } else if (item.type === 'translation') {
                    this.targetLanguage = item.options.target_language || 'Anglais';
                } else if (item.type === 'email') {
                    this.emailMode = item.options.mode || 'generate';
                    this.emailType = item.options.email_type || '';
                    this.senderName = item.options.sender_name || '';
                    this.selectedTone = item.options.tone || 'Professionnel';
                    if (item.options.mode === 'reply') {
                        this.replyType = item.options.reply_type || 'Réponse neutre';
                    } else if (item.options.mode === 'cover_letter') {
                        this.coverLetterData = {
                            job_title: item.options.job_title || '',
                            company: item.options.company || '',
                            profile: ''
                        };
                    }
                } else if (item.type === 'correction') {
                    this.correctionOptions = {
                        spelling: item.options.spelling ?? true,
                        grammar: item.options.grammar ?? true,
                        syntax: item.options.syntax ?? true,
                        style: item.options.style ?? false
                    };
                } else if (item.type === 'mermaid') {
                    this.mermaidCode = item.output || '';
                    this.mermaidEditorCode = item.output || '';
                    this.renderMermaidPreview();
                } else if (item.type === 'documentation') {
                    this.docStyle = item.options?.style || 'Technique';
                    this.docPreviousResult = item.output || '';
                    this.docOriginalOutline = item.options?.original_outline || item.input || '';
                } else if (item.type === 'extractor') {
                    this.extractFormat = item.options.output_format || 'JSON';
                } else if (item.type === 'simplify') {
                    this.simplifyLevel = item.options.level || 'Grand public';
                } else if (item.type === 'expand') {
                    this.expandTone = item.options.tone || 'Professionnel';
                    this.expandLength = item.options.length || 'Moyen';
                }
            }
        },

        formatDate(isoString) {
            return new Date(isoString).toLocaleString('fr-FR', {
                month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
            });
        },

        // CV Generator methods loaded from TextsResumeMixin

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

    // Fonction pour charger marked.js en arrière-plan (non-bloquant)
    function loadMarkedJs() {
        if (typeof marked !== 'undefined') {
            return;
        }
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/marked/marked.min.js';
        script.onload = () => {
            console.log('[textsApp] marked.js loaded');
        };
        script.onerror = () => {
            console.error('[textsApp] Failed to load marked.js');
        };
        document.head.appendChild(script);
    }

    // Fonction d'enregistrement
    function registerComponent() {
        if (typeof Alpine !== 'undefined' && Alpine.data) {
            Alpine.data('textsApp', textsAppComponent);
            console.log('[textsApp] Component registered');
        }
    }

    // Charger marked.js en arrière-plan (non-bloquant)
    loadMarkedJs();

    // Enregistrer immédiatement si Alpine est déjà chargé (cas SPA navigation)
    if (typeof Alpine !== 'undefined' && Alpine.data) {
        registerComponent();
    }

    // Aussi s'enregistrer sur alpine:init pour le chargement initial
    document.addEventListener('alpine:init', registerComponent);
})();
