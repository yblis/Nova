/**
 * SPA Router
 * Gère la navigation sans rechargement de page
 * avec gestion correcte du cycle de vie Alpine.js
 */

const SpaRouter = {
    // Configuration des routes
    routes: {
        '/': { partial: '/partials/index', component: null, title: 'Dashboard' },
        '/models': { partial: '/partials/models', component: null, title: 'Modèles installés' },
        '/discover': { partial: '/partials/discover', component: null, title: 'Découvrir' },
        '/downloads': { partial: '/partials/downloads', component: null, title: 'Téléchargements' },
        '/chat': { partial: '/partials/chat', component: 'chatApp', title: 'Chat' },
        '/texts': { partial: '/partials/texts', component: 'textsApp', title: 'Assistant' },
        '/settings': { partial: '/partials/settings', component: 'settingsPage', title: 'Paramètres' },
        '/admin/users': { partial: '/admin/partials/users', component: null, title: 'Utilisateurs' },
        '/specialists': { partial: '/partials/specialists', component: 'specialistsApp', title: 'Spécialistes' }
    },

    // État interne
    currentRoute: null,
    currentComponent: null,
    contentContainer: null,
    isNavigating: false,
    componentInstances: new WeakMap(),
    
    // Cache des scripts externes déjà chargés (évite les rechargements)
    loadedScripts: new Set(),

    /**
     * Initialise le routeur
     */
    init() {
        // Trouver le container principal
        this.contentContainer = document.getElementById('spa-content');
        if (!this.contentContainer) {
            console.warn('[SpaRouter] #spa-content not found, SPA routing disabled');
            return;
        }

        // Définir la route actuelle basée sur l'URL
        this.currentRoute = window.location.pathname;

        // Intercepter les clics sur les liens de navigation
        document.addEventListener('click', (e) => this.handleClick(e));

        // Gérer les événements popstate (back/forward)
        window.addEventListener('popstate', (e) => this.handlePopState(e));

        // Écouter les demandes de navigation programmatique
        window.addEventListener('spa:navigate-to', (e) => {
            if (e.detail && e.detail.path) {
                this.navigate(e.detail.path, { updateHistory: true });
            }
        });

        console.log('[SpaRouter] Initialized on route:', this.currentRoute);
    },

    /**
     * Gère les clics sur les liens
     */
    handleClick(e) {
        // Trouver le lien cliqué (peut être un enfant du <a>)
        const link = e.target.closest('a[href]');
        if (!link) return;

        const href = link.getAttribute('href');

        // Ignorer les liens externes, avec target, ou avec modificateurs
        if (!href ||
            href.startsWith('http') ||
            href.startsWith('#') ||
            href.startsWith('mailto:') ||
            link.hasAttribute('target') ||
            link.hasAttribute('download') ||
            e.ctrlKey || e.metaKey || e.shiftKey) {
            return;
        }

        // Vérifier si c'est une route connue
        const path = this.normalizePath(href);
        if (!this.routes[path]) {
            // Route non gérée par le SPA, laisser le comportement par défaut
            return;
        }

        // Empêcher le comportement par défaut et naviguer via SPA
        e.preventDefault();
        // Préserver le query string et le hash de l'URL originale
        this.navigate(path, { updateHistory: true, fullHref: href });
    },

    /**
     * Normalise un chemin (enlève les trailing slashes)
     */
    normalizePath(path) {
        // Enlever les query strings et hash pour la comparaison de route
        let cleanPath = path.split('?')[0].split('#')[0];
        // Enlever le trailing slash sauf pour la racine
        if (cleanPath !== '/' && cleanPath.endsWith('/')) {
            cleanPath = cleanPath.slice(0, -1);
        }
        return cleanPath;
    },

    /**
     * Gère les événements popstate (navigation arrière/avant)
     */
    handlePopState(e) {
        const path = this.normalizePath(window.location.pathname);
        if (this.routes[path]) {
            this.navigate(path, { updateHistory: false });
        }
    },

    /**
     * Navigue vers une nouvelle route
     */
    async navigate(path, options = {}) {
        const { updateHistory = true, fullHref = null } = options;

        // Éviter les navigations multiples simultanées
        if (this.isNavigating) {
            console.log('[SpaRouter] Navigation already in progress, skipping');
            return;
        }

        // Ne rien faire si on est déjà sur cette route
        if (path === this.currentRoute && !options.force) {
            return;
        }

        const route = this.routes[path];
        if (!route) {
            console.warn('[SpaRouter] Unknown route:', path);
            // Fallback: navigation classique
            window.location.href = path;
            return;
        }

        this.isNavigating = true;
        console.log('[SpaRouter] Navigating to:', path);

        try {
            // Émettre l'événement avant navigation
            window.dispatchEvent(new CustomEvent('spa:before-navigate', {
                detail: { from: this.currentRoute, to: path }
            }));

            // Mettre à jour l'historique (préserver query string et hash) AVANT d'initialiser les composants
            if (updateHistory) {
                // Utiliser le href complet s'il est fourni, sinon reconstruire
                let fullUrl = path;
                if (fullHref) {
                    // Extraire query string et hash du href original
                    const urlParts = fullHref.split('?');
                    if (urlParts.length > 1) {
                        const queryAndHash = urlParts[1].split('#');
                        fullUrl = path + '?' + queryAndHash[0];
                        if (queryAndHash.length > 1) {
                            fullUrl += '#' + queryAndHash[1];
                        }
                    } else if (fullHref.includes('#')) {
                        fullUrl = path + '#' + fullHref.split('#')[1];
                    }
                } else {
                    fullUrl = path + window.location.search + window.location.hash;
                }
                history.pushState({ path, fullUrl }, '', fullUrl);
                console.log('[SpaRouter] URL updated to:', fullUrl);
            }

            // Détruire le composant actuel si nécessaire
            await this.destroyCurrentComponent();

            // Charger le nouveau contenu
            const html = await this.loadPartial(route.partial);

            // Utiliser Alpine.mutateDom() pour notifier Alpine des changements
            if (typeof Alpine !== 'undefined') {
                Alpine.mutateDom(() => {
                    // Détruire l'arbre Alpine existant
                    if (this.contentContainer.children.length > 0) {
                        Alpine.destroyTree(this.contentContainer);
                        console.log('[SpaRouter] Alpine.destroyTree() called');
                    }

                    // Mettre à jour le DOM
                    this.contentContainer.innerHTML = html;
                });

                // Exécuter les scripts ET initialiser Alpine après
                await this.executeScripts(this.contentContainer, true);
            } else {
                // Fallback si Alpine n'est pas disponible
                this.contentContainer.innerHTML = html;
                await this.executeScripts(this.contentContainer, false);
            }



            // Mettre à jour le titre
            document.title = route.title + ' • Ollama Manager';

            // Mettre à jour la route actuelle
            const previousRoute = this.currentRoute;
            this.currentRoute = path;

            // Initialiser le nouveau composant si nécessaire
            if (route.component) {
                await this.initComponent(route.component);
            }

            // Réinitialiser HTMX sur le nouveau contenu
            if (typeof htmx !== 'undefined') {
                htmx.process(this.contentContainer);
            }

            // Émettre l'événement après navigation
            window.dispatchEvent(new CustomEvent('spa:navigate', {
                detail: { from: previousRoute, to: path }
            }));

            // Mettre à jour l'état UI (sidebar active, etc.)
            this.updateUIState(path);

        } catch (error) {
            console.error('[SpaRouter] Navigation error:', error);
            // En cas d'erreur, fallback sur la navigation classique
            window.location.href = path;
        } finally {
            this.isNavigating = false;
        }
    },

    /**
     * Charge un partial depuis le serveur
     */
    async loadPartial(partialUrl) {
        const response = await fetch(partialUrl, {
            headers: {
                'X-Requested-With': 'SpaRouter',
                'Accept': 'text/html'
            }
        });

        if (!response.ok) {
            throw new Error(`Failed to load partial: ${response.status}`);
        }

        return await response.text();
    },

    /**
     * Détruit le composant Alpine actuel
     */
    async destroyCurrentComponent() {
        if (!this.currentComponent) return;

        // Trouver tous les éléments avec x-data dans le container
        const alpineElements = this.contentContainer.querySelectorAll('[x-data]');

        for (const el of alpineElements) {
            if (el._x_dataStack) {
                const component = el._x_dataStack[0];

                // Appeler la méthode destroy si elle existe
                if (component && typeof component.destroy === 'function') {
                    console.log('[SpaRouter] Destroying component');
                    try {
                        await component.destroy();
                    } catch (e) {
                        console.error('[SpaRouter] Error destroying component:', e);
                    }
                }
            }
        }

        this.currentComponent = null;
    },

    /**
     * Initialise un nouveau composant Alpine
     */
    async initComponent(componentName) {
        this.currentComponent = componentName;

        // Alpine.js devrait automatiquement initialiser les composants
        // car ils sont pré-enregistrés via Alpine.data()
        // Mais on peut forcer une réinitialisation si nécessaire

        return new Promise((resolve) => {
            // Attendre le prochain tick pour que Alpine traite le nouveau DOM
            requestAnimationFrame(() => {
                // Vérifier si le composant a été initialisé
                const el = this.contentContainer.querySelector(`[x-data="${componentName}"]`);
                if (el && el._x_dataStack) {
                    console.log('[SpaRouter] Component initialized:', componentName);
                }
                resolve();
            });
        });
    },

    /**
     * Met à jour l'état UI global (path pour highlighting du menu)
     */
    updateUIState(path) {
        // Trouver le store ou composant uiState d'Alpine
        const uiStateEl = document.querySelector('[x-data="uiState()"]');
        if (uiStateEl && uiStateEl._x_dataStack) {
            const uiState = uiStateEl._x_dataStack[0];
            if (uiState && typeof uiState.path !== 'undefined') {
                uiState.path = path;
            }
        }
    },

    /**
     * Force une navigation (utile pour les redirections)
     */
    goto(path) {
        this.navigate(path, { updateHistory: true, force: true });
    },

    /**
     * Recharge la page actuelle
     */
    reload() {
        this.navigate(this.currentRoute, { updateHistory: false, force: true });
    },

    /**
     * Exécute les scripts trouvés dans un container
     * Les scripts injectés via innerHTML ne s'exécutent pas automatiquement
     * @param {HTMLElement} container - Le container contenant les scripts
     * @param {boolean} initAlpine - Si true, initialise Alpine après les scripts
     */
    async executeScripts(container, initAlpine = false) {
        const scripts = container.querySelectorAll('script');
        const scriptPromises = [];

        for (const oldScript of scripts) {
            if (oldScript.src) {
                // Script externe - vérifier le cache
                const scriptSrc = oldScript.src;
                
                if (this.loadedScripts.has(scriptSrc)) {
                    // Script déjà chargé, on le supprime simplement du DOM
                    console.log('[SpaRouter] Script already cached, skipping:', scriptSrc);
                    oldScript.remove();
                    continue;
                }
                
                // Marquer comme chargé avant de commencer
                this.loadedScripts.add(scriptSrc);
                
                const newScript = document.createElement('script');
                Array.from(oldScript.attributes).forEach(attr => {
                    newScript.setAttribute(attr.name, attr.value);
                });
                
                const promise = new Promise((resolve, reject) => {
                    newScript.onload = () => {
                        console.log('[SpaRouter] External script loaded:', scriptSrc);
                        resolve();
                    };
                    newScript.onerror = () => {
                        // Retirer du cache en cas d'erreur pour réessayer
                        this.loadedScripts.delete(scriptSrc);
                        reject(new Error(`Failed to load: ${scriptSrc}`));
                    };
                });
                oldScript.parentNode.replaceChild(newScript, oldScript);
                scriptPromises.push(promise);
            } else {
                // Script inline - exécuter directement
                const newScript = document.createElement('script');
                Array.from(oldScript.attributes).forEach(attr => {
                    newScript.setAttribute(attr.name, attr.value);
                });
                newScript.textContent = oldScript.textContent;
                oldScript.parentNode.replaceChild(newScript, oldScript);
            }
        }

        // Attendre que tous les scripts externes soient chargés
        if (scriptPromises.length > 0) {
            await Promise.all(scriptPromises);
            console.log('[SpaRouter] All external scripts loaded');
        }

        // Initialiser Alpine APRÈS que tous les scripts soient chargés
        if (initAlpine && typeof Alpine !== 'undefined') {
            // Attendre un tick pour que les scripts soient complètement exécutés
            await new Promise(resolve => setTimeout(resolve, 10));
            await new Promise(resolve => requestAnimationFrame(resolve));

            Alpine.initTree(container);
            console.log('[SpaRouter] Alpine.initTree() called after all scripts');
        }
    }
};

// Initialiser le routeur quand le DOM est prêt
document.addEventListener('DOMContentLoaded', () => {
    SpaRouter.init();
});

// Exposer globalement pour usage externe
window.SpaRouter = SpaRouter;
