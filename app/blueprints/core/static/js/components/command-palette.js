function commandPalette() {
    return {
        isOpen: false,
        query: '',
        selectedIndex: 0,
        commands: [
            { id: 'nav-dashboard',   section: 'Navigation', title: 'Dashboard',     path: '/',            keywords: ['accueil', 'home', 'tableau de bord', 'overview'] },
            { id: 'nav-models',      section: 'Navigation', title: 'Modèles installés', path: '/models',  keywords: ['models', 'installed', 'library', 'bibliothèque'] },
            { id: 'nav-discover',    section: 'Navigation', title: 'Découvrir',      path: '/discover',    keywords: ['discover', 'search', 'chercher', 'explorer', 'huggingface'] },
            { id: 'nav-downloads',   section: 'Navigation', title: 'Téléchargements', path: '/downloads', keywords: ['downloads', 'pull', 'installer'] },
            { id: 'nav-chat',        section: 'Navigation', title: 'Chat',           path: '/chat',        keywords: ['conversation', 'message', 'ia', 'llm', 'discuter'] },
            { id: 'nav-tools',       section: 'Navigation', title: 'Assistant',      path: '/tools',       keywords: ['tools', 'outils', 'texte', 'rédaction', 'résumé'] },
            { id: 'nav-specialists', section: 'Navigation', title: 'Spécialistes',   path: '/specialists', keywords: ['specialist', 'expert', 'ia', 'agent', 'knowledge'] },
            { id: 'nav-users',       section: 'Navigation', title: 'Utilisateurs',   path: '/admin/users', keywords: ['admin', 'users', 'gestion', 'comptes'] },

            { id: 'set-general',    section: 'Paramètres', title: 'General',          path: '/settings#general',    keywords: ['settings', 'paramètres', 'général', 'configuration', 'langue', 'thème'] },
            { id: 'set-providers',  section: 'Paramètres', title: 'LLM Providers',    path: '/settings#providers',  keywords: ['fournisseurs', 'ollama', 'openai', 'gemini', 'anthropic', 'provider'] },
            { id: 'set-shortcuts',  section: 'Paramètres', title: 'Raccourcis',       path: '/settings#shortcuts',  keywords: ['shortcuts', 'keyboard', 'clavier', 'raccourcis'] },
            { id: 'set-rag',        section: 'Paramètres', title: 'RAG / Documents',  path: '/settings#rag',        keywords: ['rag', 'documents', 'embeddings', 'vectoriel', 'fichiers'] },
            { id: 'set-about',      section: 'Paramètres', title: 'À propos',         path: '/settings#about',      keywords: ['about', 'version', 'info', 'informations'] },
            { id: 'set-llm',        section: 'Paramètres', title: 'LLM',              path: '/settings#llm',        keywords: ['llm', 'modèle', 'model', 'température', 'context'] },
            { id: 'set-websearch',  section: 'Paramètres', title: 'Web Search',       path: '/settings#websearch',  keywords: ['web', 'search', 'searxng', 'recherche web', 'internet'] },
            { id: 'set-prompts',    section: 'Paramètres', title: 'Text Prompts',     path: '/settings#prompts',     keywords: ['prompts', 'templates', 'system prompt', 'consignes'] },
            { id: 'set-audio',      section: 'Paramètres', title: 'Audio',            path: '/settings#audio',      keywords: ['audio', 'voix', 'tts', 'stt', 'whisper', 'speech'] },
            { id: 'set-email',      section: 'Paramètres', title: 'Email Agent',      path: '/settings#email',      keywords: ['email', 'mail', 'smtp', 'agent email'] },
            { id: 'set-bookstack',  section: 'Paramètres', title: 'Bookstack',        path: '/settings#bookstack',  keywords: ['bookstack', 'wiki', 'documentation', 'knowledge base'] },

            { id: 'act-newchat',    section: 'Actions',    title: 'Nouveau Chat',     path: null,           keywords: ['new', 'nouveau', 'conversation', 'créer'], action: 'newChat' },
            { id: 'act-theme',      section: 'Actions',    title: 'Changer le thème', path: null,           keywords: ['theme', 'dark', 'light', 'sombre', 'clair', 'mode'], action: 'toggleTheme' },

            { id: 'tool-reformulation', section: 'Outils', title: 'Reformulation',    path: '/tools#reformulation', keywords: ['reformuler', 'réécrire', 'paraphraser', 'rédaction'] },
            { id: 'tool-email',         section: 'Outils', title: 'Email',            path: '/tools#email',         keywords: ['mail', 'courrier', 'lettre', 'rédiger', 'rédaction'] },
            { id: 'tool-speech',        section: 'Outils', title: 'Discours',         path: '/tools#speech',        keywords: ['speech', 'oral', 'présentation', 'rédaction'] },
            { id: 'tool-admin_letter',  section: 'Outils', title: 'Lettre admin.',    path: '/tools#admin_letter',  keywords: ['administrative', 'officiel', 'courrier', 'rédaction'] },
            { id: 'tool-summarize',     section: 'Outils', title: 'Résumer',          path: '/tools#summarize',     keywords: ['résumé', 'synthèse', 'condenser', 'analyse'] },
            { id: 'tool-correction',    section: 'Outils', title: 'Correction',       path: '/tools#correction',    keywords: ['orthographe', 'grammaire', 'fautes', 'corriger', 'analyse'] },
            { id: 'tool-extractor',     section: 'Outils', title: 'Extracteur',       path: '/tools#extractor',     keywords: ['extraire', 'données', 'json', 'csv', 'analyse'] },
            { id: 'tool-simplify',      section: 'Outils', title: 'Simplificateur',   path: '/tools#simplify',      keywords: ['simplifier', 'vulgariser', 'facile', 'analyse'] },
            { id: 'tool-expand',        section: 'Outils', title: 'Expandeur',        path: '/tools#expand',        keywords: ['développer', 'enrichir', 'étoffer', 'analyse'] },
            { id: 'tool-script',        section: 'Outils', title: 'Script',           path: '/tools#script',        keywords: ['code', 'bash', 'python', 'programmation', 'technique'] },
            { id: 'tool-mermaid',       section: 'Outils', title: 'Diagramme',        path: '/tools#mermaid',       keywords: ['mermaid', 'flowchart', 'schéma', 'graphique', 'technique'] },
            { id: 'tool-documentation', section: 'Outils', title: 'Documentation',    path: '/tools#documentation', keywords: ['doc', 'readme', 'wiki', 'technique'] },
            { id: 'tool-regex',         section: 'Outils', title: 'Regex',            path: '/tools#regex',         keywords: ['expression régulière', 'pattern', 'regexp', 'technique'] },
            { id: 'tool-converter',     section: 'Outils', title: 'Convertisseur',    path: '/tools#converter',     keywords: ['convertir', 'format', 'json', 'yaml', 'xml', 'technique'] },
            { id: 'tool-log_parser',    section: 'Outils', title: 'Parseur Logs',     path: '/tools#log_parser',    keywords: ['logs', 'debug', 'diagnostic', 'erreurs', 'technique'] },
            { id: 'tool-prompt',        section: 'Outils', title: 'Générateur de Prompt', path: '/tools#prompt', keywords: ['prompt', 'ia', 'chatgpt', 'generateur', 'créer'] },
            { id: 'tool-todolist',      section: 'Outils', title: "Plan d'action",    path: '/tools#todolist',      keywords: ['todo', 'tâches', 'planifier', 'organiser', 'generateur'] },
            { id: 'tool-flashcards',    section: 'Outils', title: 'Flashcards',       path: '/tools#flashcards',    keywords: ['cartes', 'révision', 'apprendre', 'quiz', 'generateur'] },
            { id: 'tool-resume',        section: 'Outils', title: 'CV Generator',     path: '/tools#resume',        keywords: ['cv', 'curriculum vitae', 'candidature', 'generateur'] },
            { id: 'tool-translation',   section: 'Outils', title: 'Traduction',       path: '/tools#translation',   keywords: ['traduire', 'anglais', 'français', 'langue', 'quotidien'] },
            { id: 'tool-eli5',          section: 'Outils', title: 'Expliqueur',       path: '/tools#eli5',          keywords: ['expliquer', 'vulgariser', 'enfant', 'simple', 'quotidien'] },
            { id: 'tool-recipe',        section: 'Outils', title: 'Recettes',         path: '/tools#recipe',        keywords: ['cuisine', 'repas', 'ingrédients', 'quotidien'] },
            { id: 'tool-fitness',       section: 'Outils', title: 'Coach sportif',    path: '/tools#fitness',       keywords: ['sport', 'exercice', 'entraînement', 'musculation', 'quotidien'] },
            { id: 'tool-decision',      section: 'Outils', title: 'Aide décision',    path: '/tools#decision',      keywords: ['choix', 'comparer', 'décider', 'pour contre', 'quotidien'] },
        ],

        get filteredCommands() {
            if (!this.query.trim()) {
                return this.commands;
            }

            const normalizedQuery = this.normalizeText(this.query.trim());
            const terms = normalizedQuery.split(/\s+/);

            return this.commands.filter(cmd => {
                const searchable = this.normalizeText(
                    cmd.title + ' ' + cmd.keywords.join(' ') + ' ' + cmd.section
                );
                return terms.every(term => searchable.includes(term));
            });
        },

        get groupedCommands() {
            const groups = {};
            const sectionOrder = ['Navigation', 'Paramètres', 'Outils', 'Actions'];

            for (const cmd of this.filteredCommands) {
                if (!groups[cmd.section]) {
                    groups[cmd.section] = [];
                }
                groups[cmd.section].push(cmd);
            }

            const ordered = [];
            for (const section of sectionOrder) {
                if (groups[section]) {
                    ordered.push({ section, items: groups[section] });
                }
            }
            return ordered;
        },

        get flatFiltered() {
            return this.groupedCommands.flatMap(g => g.items);
        },

        normalizeText(text) {
            return text
                .toLowerCase()
                .normalize('NFD')
                .replace(/[\u0300-\u036f]/g, '');
        },

        open() {
            this.isOpen = true;
            this.query = '';
            this.selectedIndex = 0;
            this.$nextTick(() => {
                const input = this.$refs.commandInput;
                if (input) input.focus();
            });
        },

        close() {
            this.isOpen = false;
            this.query = '';
            this.selectedIndex = 0;
        },

        onQueryChange() {
            this.selectedIndex = 0;
        },

        moveSelection(direction) {
            const total = this.flatFiltered.length;
            if (total === 0) return;

            this.selectedIndex = (this.selectedIndex + direction + total) % total;

            this.$nextTick(() => {
                const active = this.$refs.commandList?.querySelector('[data-active="true"]');
                if (active) {
                    active.scrollIntoView({ block: 'nearest' });
                }
            });
        },

        executeSelected() {
            const cmd = this.flatFiltered[this.selectedIndex];
            if (cmd) this.executeCommand(cmd);
        },

        executeCommand(cmd) {
            this.close();

            if (cmd.action) {
                this.executeAction(cmd.action);
                return;
            }

            if (!cmd.path) return;

            const hashIndex = cmd.path.indexOf('#');

            if (hashIndex !== -1) {
                const basePath = cmd.path.substring(0, hashIndex);
                const hash = cmd.path.substring(hashIndex + 1);

                if (basePath === '/tools') {
                    // Pre-set localStorage so texts-app.js picks up the correct tool on init
                    localStorage.setItem('texts_current_tool', hash);
                    if (window.location.pathname === '/tools') {
                        window.location.hash = hash;
                    } else {
                        window.dispatchEvent(new CustomEvent('spa:navigate-to', {
                            detail: { path: basePath }
                        }));
                        setTimeout(() => {
                            window.location.hash = hash;
                        }, 500);
                    }
                    return;
                }

                // Settings: use localStorage + hash (same pattern as tools)
                localStorage.setItem('settings_active_tab', hash);
                if (window.location.pathname === basePath) {
                    window.location.hash = hash;
                } else {
                    window.dispatchEvent(new CustomEvent('spa:navigate-to', {
                        detail: { path: basePath }
                    }));
                    setTimeout(() => {
                        window.location.hash = hash;
                    }, 500);
                }
                return;
            }

            if (typeof SpaRouter !== 'undefined' && SpaRouter.routes && SpaRouter.routes[cmd.path]) {
                window.dispatchEvent(new CustomEvent('spa:navigate-to', {
                    detail: { path: cmd.path }
                }));
            } else {
                window.location.href = cmd.path;
            }
        },

        executeAction(actionName) {
            switch (actionName) {
                case 'newChat':
                    if (window.location.pathname === '/chat') {
                        const chatEl = document.querySelector('[x-data="chatApp"]');
                        if (chatEl && chatEl._x_dataStack && chatEl._x_dataStack[0]?.newChat) {
                            chatEl._x_dataStack[0].newChat();
                        }
                    } else {
                        window.dispatchEvent(new CustomEvent('spa:navigate-to', {
                            detail: { path: '/chat' }
                        }));
                    }
                    break;

                case 'toggleTheme': {
                    const uiEl = document.querySelector('[x-data="uiState()"]');
                    if (uiEl && uiEl._x_dataStack) {
                        const ui = uiEl._x_dataStack[0];
                        const next = ui.theme === 'dark' ? 'light' : 'dark';
                        ui.setTheme(next);
                    }
                    break;
                }
            }
        },

        handleKeydown(event) {
            switch (event.key) {
                case 'ArrowDown':
                    event.preventDefault();
                    this.moveSelection(1);
                    break;
                case 'ArrowUp':
                    event.preventDefault();
                    this.moveSelection(-1);
                    break;
                case 'Enter':
                    event.preventDefault();
                    this.executeSelected();
                    break;
                case 'Escape':
                    event.preventDefault();
                    this.close();
                    break;
            }
        },

        getSvgIcon(cmd) {
            const icons = {
                'nav-dashboard':   'M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z',
                'nav-models':      'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10',
                'nav-discover':    'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z',
                'nav-downloads':   'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4',
                'nav-chat':        'M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z',
                'nav-tools':       'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z',
                'nav-specialists': 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
                'nav-users':       'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z',
                'set-general':     'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z',
                'set-providers':   'M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z',
                'set-shortcuts':   'M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z',
                'set-rag':         'M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z',
                'set-about':       'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
                'set-llm':         'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z',
                'set-websearch':   'M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9',
                'set-prompts':     'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z',
                'set-audio':       'M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z',
                'set-email':       'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
                'set-bookstack':   'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253',
                'act-newchat':     'M12 6v6m0 0v6m0-6h6m-6 0H6',
                'act-theme':       'M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z',
                'tool-reformulation': 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z',
                'tool-email':       'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
                'tool-speech':      'M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z',
                'tool-admin_letter': 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
                'tool-summarize':   'M4 6h16M4 12h16m-7 6h7',
                'tool-correction':  'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
                'tool-extractor':   'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4',
                'tool-simplify':    'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
                'tool-expand':      'M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4',
                'tool-script':      'M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4',
                'tool-mermaid':     'M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01',
                'tool-documentation':'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253',
                'tool-regex':       'M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4',
                'tool-converter':   'M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4',
                'tool-log_parser':  'M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
                'tool-prompt':      'M13 10V3L4 14h7v7l9-11h-7z',
                'tool-todolist':    'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4',
                'tool-flashcards':  'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10',
                'tool-resume':      'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
                'tool-translation': 'M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129',
                'tool-eli5':        'M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
                'tool-recipe':      'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253',
                'tool-fitness':     'M13 10V3L4 14h7v7l9-11h-7z',
                'tool-decision':    'M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3',
            };
            return icons[cmd.id] || 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z';
        },

        init() {
            window.addEventListener('command-palette:open', () => this.open());
        }
    };
}
