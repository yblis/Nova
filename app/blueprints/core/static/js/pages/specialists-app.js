/**
 * Specialists App - Alpine.js Component
 * AI Assistants with Custom Knowledge
 */

// Register specialistsApp component
// Enregistrement immédiat si Alpine est déjà prêt (cas SPA navigation)
// ou via l'événement alpine:init (cas chargement initial)
function registerSpecialistsApp() {
    if (typeof Alpine !== 'undefined' && Alpine.data) {
        Alpine.data('specialistsApp', specialistsApp);
        console.log('[Specialists] Component registered');
    }
}

// Si Alpine est déjà initialisé (navigation SPA), enregistrer immédiatement
if (typeof Alpine !== 'undefined' && Alpine.version) {
    registerSpecialistsApp();
} else {
    // Sinon attendre l'initialisation d'Alpine
    document.addEventListener('alpine:init', registerSpecialistsApp);
}

// Charger marked.js pour le rendu markdown (nécessaire pour SPA)
if (typeof marked === 'undefined') {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/marked/marked.min.js';
    document.head.appendChild(script);
}

function specialistsApp() {
    return {
        // State
        loading: true,
        specialists: [],
        currentSpecialist: null,
        showSidebar: window.innerWidth >= 640, // Visible par défaut sur desktop
        showKnowledgePanel: false,

        // Modals
        showCreateModal: false,
        showEditModal: false,
        showAddUrlModal: false,
        showAddTextModal: false,
        showChunksModal: false,

        // Confirm Modal
        showConfirmModal: false,
        confirmTitle: '',
        confirmMessage: '',
        confirmCallback: null,

        // Chunks viewer
        currentDocChunks: [],
        currentDocStats: {},
        currentDocName: '',
        loadingChunks: false,


        confirmAction() {
            if (this.confirmCallback) {
                this.confirmCallback();
            }
            this.showConfirmModal = false;
        },

        openConfirmModal(title, message, callback) {
            this.confirmTitle = title;
            this.confirmMessage = message;
            this.confirmCallback = callback;
            this.showConfirmModal = true;
        },

        form: {
            name: '',
            description: '',
            system_prompt: '',
            model: '',
            provider_id: '',
            color: '#6366f1',
            icon: 'computer'
        },

        // Available icons for specialists
        availableIcons: [
            { id: 'computer', name: 'Ordinateur', path: 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z' },
            { id: 'chat', name: 'Chat', path: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z' },
            { id: 'code', name: 'Code', path: 'M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4' },
            { id: 'book', name: 'Livre', path: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253' },
            { id: 'lightbulb', name: 'Idée', path: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z' },
            { id: 'academic', name: 'Académie', path: 'M12 14l9-5-9-5-9 5 9 5z M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z M12 14l9-5-9-5-9 5 9 5zm0 0l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14zm-4 6v-7.5l4-2.222' },
            { id: 'chart', name: 'Graphique', path: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
            { id: 'globe', name: 'Globe', path: 'M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9' },
            { id: 'briefcase', name: 'Business', path: 'M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z' },
            { id: 'heart', name: 'Santé', path: 'M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z' },
            { id: 'music', name: 'Musique', path: 'M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3' },
            { id: 'camera', name: 'Photo', path: 'M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z M15 13a3 3 0 11-6 0 3 3 0 016 0z' },
            { id: 'puzzle', name: 'Puzzle', path: 'M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z' },
            { id: 'beaker', name: 'Science', path: 'M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z' },
            { id: 'cog', name: 'Technique', path: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
            { id: 'shield', name: 'Sécurité', path: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z' },
            { id: 'pencil', name: 'Écriture', path: 'M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z' },
            { id: 'currency', name: 'Finance', path: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
            { id: 'users', name: 'Équipe', path: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z' },
            { id: 'star', name: 'Étoile', path: 'M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z' }
        ],

        // Helper to get icon path
        getIconPath(iconId) {
            const icon = this.availableIcons.find(i => i.id === iconId);
            return icon ? icon.path : this.availableIcons[0].path;
        },

        // Knowledge
        knowledge: [],
        urlToAdd: '',

        // Sessions History
        sessions: [],
        sessionSearchQuery: '',
        selectionMode: false,
        selectedSessions: [],
        currentSidebarTab: 'history',
        loadingSessions: false,

        addingUrl: false,
        textToAdd: { name: '', content: '' },
        addingText: false,

        // Chat
        messages: [],
        input: '',
        chatLoading: false,
        sessionId: null,

        // Models & Providers
        models: [],
        availableModels: [],
        providers: [],

        // Translation helper
        t(key, fallback) {
            if (window.t) return window.t(key, fallback);
            return fallback;
        },

        // Fonction pour créer un slug à partir d'un nom
        slugify(text) {
            return text
                .toString()
                .toLowerCase()
                .normalize('NFD')
                .replace(/[\u0300-\u036f]/g, '')
                .replace(/[^a-z0-9]+/g, '-')
                .replace(/^-+|-+$/g, '')
                .substring(0, 50);
        },

        async init() {
            await this.loadSpecialists();
            await this.loadProviders();

            // Restaurer l'état depuis l'URL: /specialists/<specialist_slug>#<session_id>
            const path = window.location.pathname;
            const match = path.match(/\/specialists\/([^\/]+)/);
            const hash = window.location.hash.slice(1);

            if (match && match[1]) {
                const specSlug = decodeURIComponent(match[1]);
                const spec = this.specialists.find(s =>
                    this.slugify(s.name) === specSlug || s.id === specSlug
                );
                if (spec) {
                    await this.selectSpecialist(spec, false);

                    if (hash) {
                        await this.loadSessions(spec.id);
                        const session = this.sessions.find(s => s.id === hash);
                        if (session) {
                            await this.loadSession(session, false);
                        }
                    }
                }
            }
        },

        async loadProviders() {
            try {
                const r = await fetch('/api/settings/providers');
                if (r.ok) {
                    const data = await r.json();
                    this.providers = data.providers || [];
                }
            } catch (e) {
                console.error('Error loading providers:', e);
            }
        },

        async loadModelsForProvider(providerId) {
            if (!providerId) {
                this.availableModels = [];
                return;
            }
            try {
                const r = await fetch(`/api/settings/providers/${providerId}/models`);
                if (r.ok) {
                    const data = await r.json();
                    const embeddingPatterns = ['embed', 'bge-', 'bge:', 'all-minilm', 'snowflake-arctic', 'paraphrase', '/e5-', ':e5-', '/e5:', 'gte-', 'gte:', 'jina-', 'text-embedding', 'embedding-'];
                    const seen = new Set();
                    this.availableModels = (data.models || [])
                        .map(m => typeof m === 'string' ? m : m.id || m.name)
                        .filter(name => {
                            if (!name || seen.has(name)) return false;
                            seen.add(name);
                            const lowerName = name.toLowerCase();
                            return !embeddingPatterns.some(pattern => lowerName.includes(pattern));
                        });
                } else {
                    this.availableModels = [];
                }
            } catch (e) {
                console.error('Error loading provider models:', e);
                this.availableModels = [];
            }
        },

        async loadModels() {
            try {
                const r = await fetch('/api/settings/providers/active/models');
                if (r.ok) {
                    const data = await r.json();
                    if (data.models) {
                        this.models = data.models.map(m => typeof m === 'string' ? m : m.id || m.name);
                    }
                }
            } catch (e) { }
        },

        async loadSpecialists() {
            this.loading = true;
            try {
                const r = await fetch('/api/specialists');
                if (r.ok) {
                    const data = await r.json();
                    this.specialists = data.specialists || [];
                }
            } catch (e) {
                console.error('Error loading specialists:', e);
            } finally {
                this.loading = false;
            }
        },

        async selectSpecialist(spec, updateUrl = true) {
            this.currentSpecialist = spec;
            if (window.innerWidth < 640) {
                this.showSidebar = false;
            }
            this.messages = [];
            this.sessionId = null;
            this.sessions = [];
            this.sessionSearchQuery = '';
            this.selectionMode = false;
            this.selectedSessions = [];
            this.currentSidebarTab = 'history';
            this.loadSessions(spec.id);

            if (updateUrl) {
                const slug = this.slugify(spec.name);
                const newUrl = `/specialists/${slug}`;
                history.pushState({ specialistId: spec.id, slug: slug }, '', newUrl);
            }

            try {
                const r = await fetch(`/api/specialists/${spec.id}`);
                if (r.ok) {
                    const data = await r.json();
                    this.currentSpecialist = data;
                    this.knowledge = data.knowledge || [];

                    if (data.provider_id) {
                        await fetch('/api/settings/providers/active', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ provider_id: data.provider_id })
                        });
                        window.dispatchEvent(new CustomEvent('providers-changed'));
                    } else if (data.model) {
                        try {
                            const providerResp = await fetch('/api/settings/providers/resolve-model', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ model: data.model })
                            });
                            if (providerResp.ok) {
                                const providerData = await providerResp.json();
                                if (providerData.found && providerData.provider_id) {
                                    await fetch('/api/settings/providers/active', {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({ provider_id: providerData.provider_id })
                                    });
                                    window.dispatchEvent(new CustomEvent('providers-changed'));
                                    console.log(`[Specialists] Provider switched to ${providerData.provider_name} for model ${data.model}`);
                                }
                            }
                        } catch (e) {
                            console.log('[Specialists] Could not resolve provider for model:', data.model);
                        }
                    }
                }
            } catch (e) {
                console.error('Error loading specialist:', e);
            }
        },

        async createSpecialist() {
            try {
                const r = await fetch('/api/specialists', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.form)
                });
                if (r.ok) {
                    const spec = await r.json();
                    this.specialists.unshift(spec);
                    this.selectSpecialist(spec);
                    this.showCreateModal = false;
                    this.resetForm();
                    showToast('Spécialiste créé !');
                } else {
                    const data = await r.json();
                    showToast(data.error || 'Erreur');
                }
            } catch (e) {
                showToast('Erreur lors de la création');
            }
        },

        async updateSpecialist() {
            if (!this.currentSpecialist) return;
            try {
                const r = await fetch(`/api/specialists/${this.currentSpecialist.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.form)
                });
                if (r.ok) {
                    const spec = await r.json();
                    const idx = this.specialists.findIndex(s => s.id === spec.id);
                    if (idx >= 0) this.specialists[idx] = spec;
                    this.currentSpecialist = { ...this.currentSpecialist, ...spec };
                    this.showEditModal = false;
                    showToast('Modifications enregistrées !');
                }
            } catch (e) {
                showToast('Erreur lors de la mise à jour');
            }
        },

        async deleteCurrentSpecialist() {
            if (!this.currentSpecialist) return;
            if (!confirm('Supprimer ce spécialiste et toutes ses données ?')) return;

            try {
                const r = await fetch(`/api/specialists/${this.currentSpecialist.id}`, {
                    method: 'DELETE'
                });
                if (r.ok) {
                    this.specialists = this.specialists.filter(s => s.id !== this.currentSpecialist.id);
                    this.currentSpecialist = null;
                    this.knowledge = [];
                    this.messages = [];
                    showToast('Spécialiste supprimé');
                }
            } catch (e) {
                showToast('Erreur lors de la suppression');
            }
        },

        resetForm() {
            this.form = {
                name: '',
                description: '',
                system_prompt: '',
                model: '',
                provider_id: '',
                color: '#6366f1',
                icon: 'computer'
            };
            this.availableModels = [];
        },

        openEditModal() {
            this.form = {
                name: this.currentSpecialist.name || '',
                description: this.currentSpecialist.description || '',
                system_prompt: this.currentSpecialist.system_prompt || '',
                model: this.currentSpecialist.model || '',
                provider_id: this.currentSpecialist.provider_id || '',
                color: this.currentSpecialist.color || '#6366f1',
                icon: this.currentSpecialist.icon || 'computer'
            };
            if (this.currentSpecialist.provider_id) {
                this.loadModelsForProvider(this.currentSpecialist.provider_id);
            } else {
                this.availableModels = [];
            }
            this.showEditModal = true;
        },

        // Knowledge management
        async uploadFile(event) {
            if (!this.currentSpecialist) return;
            const files = event.target.files;
            if (!files.length) return;

            for (const file of files) {
                const formData = new FormData();
                formData.append('file', file);

                try {
                    const r = await fetch(`/api/specialists/${this.currentSpecialist.id}/knowledge/upload`, {
                        method: 'POST',
                        body: formData
                    });
                    if (r.ok) {
                        const item = await r.json();
                        this.knowledge.unshift(item);
                        showToast(`${file.name} ajouté`);
                    } else {
                        const data = await r.json();
                        showToast(data.error || 'Erreur upload');
                    }
                } catch (e) {
                    showToast('Erreur upload');
                }
            }
            event.target.value = '';
        },

        async addUrl() {
            if (!this.currentSpecialist || !this.urlToAdd) return;

            const urls = this.urlToAdd.split('\n').map(u => u.trim()).filter(u => u.length > 0);
            if (urls.length === 0) return;

            this.addingUrl = true;
            let successCount = 0;
            let errorCount = 0;

            try {
                for (const url of urls) {
                    try {
                        const r = await fetch(`/api/specialists/${this.currentSpecialist.id}/knowledge/web`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ url: url })
                        });

                        if (r.ok) {
                            const item = await r.json();
                            this.knowledge.unshift(item);
                            successCount++;
                        } else {
                            errorCount++;
                            console.error(`Failed to add ${url}`);
                        }
                    } catch (e) {
                        errorCount++;
                        console.error(`Error adding ${url}:`, e);
                    }
                }

                if (successCount > 0) {
                    this.urlToAdd = '';
                    this.showAddUrlModal = false;
                    showToast(`${successCount} URL(s) ajoutée(s)${errorCount > 0 ? `, ${errorCount} échec(s)` : ''}`);
                } else if (errorCount > 0) {
                    showToast(`Échec de l'ajout des URLs`);
                }

            } catch (e) {
                showToast('Erreur ajout URL');
            } finally {
                this.addingUrl = false;
            }
        },

        async addText() {
            if (!this.currentSpecialist || !this.textToAdd.name || !this.textToAdd.content) return;
            this.addingText = true;
            try {
                const r = await fetch(`/api/specialists/${this.currentSpecialist.id}/knowledge/text`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.textToAdd)
                });
                if (r.ok) {
                    const item = await r.json();
                    this.knowledge.unshift(item);
                    this.textToAdd = { name: '', content: '' };
                    this.showAddTextModal = false;
                    showToast('Texte ajouté !');
                } else {
                    const data = await r.json();
                    showToast(data.error || 'Erreur');
                }
            } catch (e) {
                showToast('Erreur ajout texte');
            } finally {
                this.addingText = false;
            }
        },

        async deleteKnowledge(knowledgeId) {
            if (!this.currentSpecialist) return;
            if (!confirm('Supprimer cette connaissance ?')) return;

            try {
                const r = await fetch(`/api/specialists/${this.currentSpecialist.id}/knowledge/${knowledgeId}`, {
                    method: 'DELETE'
                });
                if (r.ok) {
                    this.knowledge = this.knowledge.filter(k => k.id !== knowledgeId);
                    showToast('Supprimé');
                }
            } catch (e) {
                showToast('Erreur suppression');
            }
        },

        // Chat
        async sendMessage() {
            if (!this.currentSpecialist || this.chatLoading || !this.input.trim()) return;

            const message = this.input.trim();
            const oldSessionId = this.sessionId;
            this.input = '';
            this.chatLoading = true;

            this.messages.push({
                id: 'temp-' + Date.now(),
                role: 'user',
                content: message
            });

            this.$nextTick(() => {
                if (this.$refs.messagesContainer) {
                    this.$refs.messagesContainer.scrollTop = this.$refs.messagesContainer.scrollHeight;
                }
            });

            try {
                const response = await fetch(`/api/specialists/${this.currentSpecialist.id}/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message,
                        session_id: this.sessionId
                    })
                });

                const reader = response.body.getReader();
                const decoder = new TextDecoder();

                let assistantMessage = {
                    id: 'assistant-' + Date.now(),
                    role: 'assistant',
                    content: '',
                    sources: []
                };
                this.messages.push(assistantMessage);
                const assistantIndex = this.messages.length - 1;

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\n');

                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6));

                                if (data.session_id) {
                                    this.sessionId = data.session_id;
                                }
                                if (data.sources) {
                                    this.messages[assistantIndex].sources = data.sources;
                                }
                                if (data.content) {
                                    this.messages[assistantIndex].content += data.content;
                                }
                                if (data.error) {
                                    showToast(data.error);
                                }
                            } catch (e) {
                                // Ignore parse errors
                            }
                        }
                    }

                    this.messages = [...this.messages];

                    this.$nextTick(() => {
                        if (this.$refs.messagesContainer) {
                            this.$refs.messagesContainer.scrollTop = this.$refs.messagesContainer.scrollHeight;
                        }
                    });
                }
            } catch (e) {
                console.error('Chat error:', e);
                showToast('Erreur de communication');
            } finally {
                this.chatLoading = false;
                if (this.sessionId) {
                    this.loadSessions(this.currentSpecialist.id);
                }
            }
        },

        async viewKnowledgeChunks(knowledgeId, knowledgeName) {
            this.currentDocName = knowledgeName;
            this.currentDocChunks = [];
            this.currentDocStats = {};
            this.showChunksModal = true;
            this.loadingChunks = true;

            try {
                const r = await fetch(`/api/specialists/${this.currentSpecialist.id}/knowledge/${knowledgeId}/chunks`);
                if (r.ok) {
                    const data = await r.json();
                    this.currentDocChunks = data.chunks || [];
                    this.currentDocStats = data.stats || {};
                } else {
                    showToast('Erreur chargement chunks');
                }
            } catch (e) {
                console.error('Error loading chunks:', e);
                showToast('Erreur chargement chunks');
            } finally {
                this.loadingChunks = false;
            }
        },


        get filteredSessions() {
            if (!this.sessionSearchQuery) return this.sessions;
            const query = this.sessionSearchQuery.toLowerCase();
            return this.sessions.filter(s =>
                (s.title && s.title.toLowerCase().includes(query))
            );
        },

        toggleSelectionMode() {
            this.selectionMode = !this.selectionMode;
            this.selectedSessions = [];
        },

        toggleSessionSelection(sessionId) {
            if (this.selectedSessions.includes(sessionId)) {
                this.selectedSessions = this.selectedSessions.filter(id => id !== sessionId);
            } else {
                this.selectedSessions.push(sessionId);
            }
        },

        selectAllSessions() {
            if (this.selectedSessions.length === this.filteredSessions.length) {
                this.selectedSessions = [];
            } else {
                this.selectedSessions = this.filteredSessions.map(s => s.id);
            }
        },

        async deleteSelectedSessions() {
            this.openConfirmModal(
                'Supprimer les conversations ?',
                `Voulez-vous vraiment supprimer ${this.selectedSessions.length} conversation(s) ? Cette action est irréversible.`,
                async () => {
                    try {
                        const r = await fetch(`/api/specialists/${this.currentSpecialist.id}/sessions/bulk`, {
                            method: 'DELETE',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ session_ids: this.selectedSessions })
                        });

                        if (r.ok) {
                            const data = await r.json();
                            this.sessions = this.sessions.filter(s => !this.selectedSessions.includes(s.id));

                            if (this.sessionId && this.selectedSessions.includes(this.sessionId)) {
                                this.createNewSession();
                            }

                            this.selectedSessions = [];
                            this.selectionMode = false;
                            showToast(`${data.deleted_count} conversation(s) supprimée(s)`);
                        } else {
                            const err = await r.json();
                            showToast(err.error || 'Erreur suppression');
                        }
                    } catch (e) {
                        showToast('Erreur suppression');
                    }
                }
            );
        },


        async loadSessions(specialistId) {
            this.loadingSessions = true;
            this.sessions = [];
            try {
                const r = await fetch(`/api/specialists/${specialistId}/sessions`);
                if (r.ok) {
                    const data = await r.json();
                    this.sessions = data.sessions || [];
                }
            } catch (e) {
                console.error('Error loading sessions:', e);
            } finally {
                this.loadingSessions = false;
            }
        },

        async loadSession(session, updateUrl = true) {
            this.sessionId = session.id;
            this.messages = [];
            this.chatLoading = true;

            if (updateUrl && this.currentSpecialist) {
                const slug = this.slugify(this.currentSpecialist.name);
                const newUrl = `/specialists/${slug}#${session.id}`;
                history.pushState({ specialistId: this.currentSpecialist.id, sessionId: session.id, slug: slug }, '', newUrl);
            }

            try {
                const r = await fetch(`/api/specialists/${this.currentSpecialist.id}/sessions/${session.id}/messages`);
                if (r.ok) {
                    const data = await r.json();
                    this.messages = data.messages || [];
                    this.$nextTick(() => {
                        if (this.$refs.messagesContainer) {
                            this.$refs.messagesContainer.scrollTop = this.$refs.messagesContainer.scrollHeight;
                        }
                    });
                }
            } catch (e) {
                showToast('Erreur chargement messages');
            } finally {
                this.chatLoading = false;
            }
        },

        createNewSession() {
            this.sessionId = null;
            this.messages = [];
            this.input = '';
        },

        async deleteSession(sessionId) {
            this.openConfirmModal(
                'Supprimer la conversation ?',
                'Voulez-vous vraiment supprimer cette conversation ? Cette action est irréversible.',
                async () => {
                    try {
                        const r = await fetch(`/api/specialists/${this.currentSpecialist.id}/sessions/${sessionId}`, {
                            method: 'DELETE'
                        });
                        if (r.ok) {
                            this.sessions = this.sessions.filter(s => s.id !== sessionId);
                            if (this.sessionId === sessionId) {
                                this.createNewSession();
                            }
                            showToast('Conversation supprimée');
                        } else {
                            showToast('Erreur suppression session');
                        }
                    } catch (e) {
                        showToast('Erreur suppression session');
                    }
                }
            );
        },

        formatContent(content) {
            if (!content) return '';
            try {
                if (typeof marked === 'undefined') return content;
                let html = marked.parse(content);
                // Ajouter un bouton de copie sur chaque bloc <pre>
                html = html.replace(/<pre>([\s\S]*?)<\/pre>/g, (match, codeContent) => {
                    return `<div class="code-block-wrapper"><button class="copy-code-btn" onclick="copyCodeBlock(this)" title="Copier le code"><svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg></button><pre>${codeContent}</pre></div>`;
                });
                return html;
            } catch (e) {
                return content
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/\n/g, '<br>');
            }
        }
    };
}
