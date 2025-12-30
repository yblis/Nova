## Brief (objectif & périmètre)

**Produit**
Application web **Python Flask** (français) pour gérer des modèles **Ollama** : lister, rechercher (remote), télécharger/mettre à jour (pull), supprimer, renommer (retag), voir variantes, vérifier mises à jour, surveiller/éjecter les modèles en cours d’exécution. **Mobile-first + PWA** (installable, offline partiel, notifications locales).

**Public visé**
Admins/devs utilisant un serveur Ollama local ou distant.

**Plateformes cibles**
Navigateurs modernes (desktop/mobile). Fonctionne avec **Ollama HTTP API** (par défaut `http://localhost:11434`).

**KPIs**

* <2 s pour afficher la liste locale.
* Feedback progression pull en temps réel (SSE/WebSocket) ; latence <200 ms.
* 100 % Core Web Vitals pass sur mobile.
* TTI <3 s en 4G.

**Hors périmètre v1**
Chat complet, historisation de prompts, multi-tenant, RBAC avancé.

---

## Guide de développement (architecture & spécifications)

### Stack

* **Backend** : Python 3.11+, Flask, Flask-Blueprints, Flask-Caching (simple cache mémoire), **Requests/HTTPX** (async pour streams), **Redis + RQ** (ou Celery) pour jobs longs (pull/verify).
* **Temps réel** : **Server-Sent Events (SSE)** via endpoint Flask pour progresser sans WebSocket.
* **Frontend** : HTML5, **Tailwind CSS** (mobile-first), **HTMX** (actions dynamiques sans SPA), **Alpine.js** (états légers).
* **PWA** : manifest.json, service worker (Workbox ou SW custom), stratégie **Stale-While-Revalidate** pour UI, **Network-Only** pour appels Ollama, cache d’assets versionné.
* **Qualité** : pytest, mypy, ruff, pre-commit.
* **Déploiement** : Gunicorn + gevent/eventlet (SSE), derrière Traefik/Nginx.

### Structure projet

```
ollama-webmgr/
  app/
    __init__.py
    config.py
    extensions.py          # cache, rq
    blueprints/
      core/                # pages & assets
        routes.py          # UI routes
        forms.py
        templates/         # Jinja (mobile-first)
        static/
          css/
          js/
          img/
      api/                 # façade REST -> Ollama
        routes_models.py   # tags, show, pull, delete, copy, ps, eject
        routes_remote.py   # search/variants (optionnel)
        sse.py             # flux SSE progression
    services/
      ollama_client.py     # appels HTTP vers Ollama (timeout/retry)
      progress_bus.py      # pub/sub progression (Redis)
      remote_search.py     # optionnel (API/HTML best-effort)
      tasks.py             # RQ jobs: pull, verify, eject forcé
    pwa/
      manifest.json
      service-worker.js
  tests/
  requirements.txt
  wsgi.py
  README.md
  .env.example
```

### Routes (résumé contractuel)

**UI (HTML)**

* `GET /` → Dashboard (résumé, en cours d’exécution).
* `GET /models` → Liste locale (tags, tailles, date MAJ, digest, statut MAJ).
* `GET /models/<name>` → Détails (show).
* `GET /search` → Recherche distante + variantes (optionnel).
* PWA : `GET /manifest.json`, `GET /service-worker.js`.

**API (JSON)**

* `GET /api/models` → proxy **GET /api/tags** (Ollama).
* `POST /api/models/show` → proxy **POST /api/show**.
* `POST /api/models/pull` body `{ "name": "qwen2.5:7b" }` → lance **job** pull, renvoie `job_id`.
* `DELETE /api/models/<name>` → proxy **DELETE /api/delete**.
* `POST /api/models/copy` body `{ "source": "a:b", "dest": "a:c" }` → proxy **POST /api/copy**.
* `GET /api/running` → proxy **GET /api/ps**.
* **Éjection** :

  * Douce : `POST /api/eject` → **POST /api/generate** `{prompt:"", keep_alive:0, stream:false}`.
  * Forcée (job) : `POST /api/eject/force` → loop + vérif `/api/ps`.
* **Vérif MAJ** : `POST /api/models/check_update` → job qui “sonde” `/api/pull` en stream et s’arrête dès décision.
* **Progression SSE** : `GET /api/stream/progress?job_id=...` → events `progress`, `status`, `done`, `error`.
* **Recherche/variantes (optionnel)** :

  * `GET /api/remote/search?q=...`
  * `GET /api/remote/variants?model=...`

### Comportements clés

* **Pull & progression** : job RQ lit le flux JSON d’Ollama (`status`, `total`, `completed`) et publie sur `progress_bus`. L’UI s’abonne via **SSE**.
* **Vérif MAJ** : démarrage d’un `/api/pull` en streaming, arrêt immédiat dès trace “up to date” ou “downloading/verifying”.
* **Liste locale** : cache 5–10 s (rafraîchit à la demande).
* **Mobile-first** : tables en cartes empilées <640 px ; actions en bottom-sheet.
* **Dates** : format **JJ/MM/AAAA** (Intl.DateTimeFormat côté client).
* **Erreurs** : mapping propre des codes réseau (Ollama down, timeout, 5xx), toasts UI.

### PWA (exigences)

* `manifest.json` : nom, icônes 192/512, `display: standalone`, `start_url: /`.
* `service-worker.js` :

  * cache static `app-shell` (CSS/JS/icônes).
  * **No-cache** pour `/api/*` (toujours réseau).
  * Mise à jour SW : `skipWaiting` + `clientsClaim`.
* **Installabilité** : `beforeinstallprompt` + bouton “Installer”.
* **Offline** : pages shell accessibles, UI affiche “Hors ligne” et désactive actions réseau.

### Sécurité & config

* **CORS** : autoriser uniquement l’origin de l’app.
* **URL Ollama** : configurable (UI + `.env`), validée (schéma, host, port).
* **Timeouts** : 5–10 s connect, 60–600 s read (pull). Retries exponentiels sûrs.
* **Logs** : structured logging (json), corrélation par `request_id`/`job_id`.
* **Limites** : taille réponses stream gérée en chunk, pas de chargement mémoire total.

### Tests (minimum)

* Mocks d’API Ollama (tags/show/pull/delete/copy/ps).
* Tests jobs (pull, verify, eject forcé) + SSE.
* Tests PWA : présence manifest/SW et headers corrects.

---

## Processus (cycle de vie)

1. **Initialisation**

   * Créer repo, structure, tooling : `ruff`, `mypy`, `pytest`, `pre-commit`.
   * Écrire `.env.example` : `OLLAMA_BASE_URL`, `REDIS_URL`, `SECRET_KEY`.

2. **Implémentation backend**

   * `services/ollama_client.py` : wrappers sûrs (timeouts, retries).
   * `services/tasks.py` : jobs `pull_model`, `check_update`, `eject_force`.
   * `blueprints/api/*.py` : endpoints JSON + SSE progress.
   * Cache `GET /api/models` (tags).

3. **Frontend & UX**

   * Templates Jinja (Tailwind, mobile-first).
   * Pages : Dashboard, Modèles, Détails, En cours, Recherche (opt.).
   * Composants : barre de progression (SSE), toasts, confirm modales.

4. **PWA**

   * Ajouter `manifest.json`, `service-worker.js`, icônes.
   * Bouton “Installer” + bannière état offline.

5. **Tests & qualité**

   * Couvrir flux critiques (pull + SSE, delete, copy, ps, eject).
   * Lighthouse mobile : corriger jusqu’au vert.

6. **Packaging & déploiement**

   * `requirements.txt` minimal.
   * WSGI : Gunicorn (`--worker-class gevent`), 2–4 workers.
   * Reverse proxy (Traefik/Nginx) : GZip/Brotli, cache static, TLS.

7. **Observabilité**

   * Logs structurés, métriques basiques (compteurs pulls, durées).
   * Healthcheck : `GET /health` (inclut ping Redis & Ollama).

8. **Maintenance**

   * Versionner SW (bump cacheName).
   * Gérer changements API Ollama (contrats/tests).

---

## Détails d’acceptation (v1)

* Liste locale rendue <2 s (cache actif).
* Pull d’un modèle affiche progression via SSE, sans blocage UI.
* Éjecter un modèle enlève l’entrée de `/api/ps` en <5 s (forcé si besoin).
* PWA installable sur Android/iOS (Safari iOS 16.4+), icônes correctes.
* Hors-ligne : app-shell s’ouvre, actions réseau désactivées avec message clair.
* Formats et libellés 100 % français (dates JJ/MM/AAAA).
