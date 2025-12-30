# Ollama Manager (Flask)

Application web Flask pour gérer des modèles Ollama (liste, show, pull avec progression SSE, delete, copy, ps, éjection), mobile-first avec Tailwind, HTMX et Alpine, et PWA complète.

## Fonctionnalités

✅ **Gestion complète des modèles**
- Liste des modèles locaux avec recherche
- Affichage détaillé (digest, taille, parent)
- Pull avec progression temps réel (SSE)
- Suppression avec confirmation
- Copie/renommage de modèles
- Dates formatées (JJ/MM/AAAA)

✅ **Recherche distante**
- Recherche de modèles sur ollama.com
- Affichage des variantes disponibles
- Pull rapide depuis la recherche

✅ **Surveillance**
- Modèles en cours d'exécution
- Éjection douce ou forcée
- Vérification des mises à jour

✅ **PWA (Progressive Web App)**
- Installable sur desktop/mobile
- Mode offline partiel
- Cache intelligent (stale-while-revalidate)
- Manifest et Service Worker complets

✅ **Interface moderne**
- Dark mode automatique
- Mobile-first responsive
- Notifications toast
- Paramètres configurables (URL Ollama)

✅ **Monitoring**
- Healthcheck complet (/health)
- Vérification Redis + Ollama
- Gestion d'erreurs robuste

## Démarrage rapide

### 1. Installation

```bash
# Créer un environnement virtuel
python3 -m venv .venv
source .venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt
```

### 2. Configuration

Copiez `.env.example` vers `.env` et ajustez si nécessaire:

```bash
cp .env.example .env
```

Variables principales:
- `SECRET_KEY`: Clé secrète Flask (changez en production!)
- `OLLAMA_BASE_URL`: URL de votre serveur Ollama (défaut: http://localhost:11434)
- `REDIS_URL`: URL Redis (défaut: redis://localhost:6379/0)

### 3. Lancement

```bash
# 1. Redis (dans un terminal)
redis-server
# Ou utilisez le script d'aide:
python start_redis.py

# 2. Application Flask (dans un autre terminal)
FLASK_APP=wsgi.py flask run

# 3. Worker RQ pour les jobs (dans un 3ème terminal)
rq worker ollama
```

L'application est accessible sur http://localhost:5000

### 4. Dépannage Redis

Si vous rencontrez une erreur `ConnectionRefusedError: [Errno 61] Connection refused` lors de l'utilisation de l'application:

1. **Vérifiez que Redis est en cours d'exécution**:
   ```bash
   python start_redis.py
   ```

2. **Démarrez Redis manuellement** si le script ne fonctionne pas:
   - Avec Homebrew (macOS): `brew services start redis`
   - Directement: `redis-server --daemonize yes`

3. **Sans Redis**: L'application peut fonctionner sans Redis, mais les fonctionnalités de suivi de progression seront limitées.

### 4. Tests

```bash
# Lancer les tests
pytest tests/

# Avec couverture
pytest --cov=app tests/
```

## Structure du projet

```
Ollamanager-flask/
├── app/
│   ├── __init__.py              # Factory Flask
│   ├── config.py                # Configuration
│   ├── extensions.py            # Cache, Redis, RQ
│   ├── utils.py                 # Utilitaires
│   ├── blueprints/
│   │   ├── core/                # Routes UI (HTML)
│   │   │   ├── routes.py
│   │   │   └── templates/       # Templates Jinja2
│   │   │       ├── base.html
│   │   │       ├── index.html
│   │   │       ├── models.html
│   │   │       ├── model_detail.html
│   │   │       └── search.html
│   │   └── api/                 # Routes API (JSON/HTML)
│   │       ├── routes_models.py # CRUD modèles
│   │       ├── routes_remote.py # Recherche distante
│   │       ├── routes_settings.py # Paramètres
│   │       └── sse.py           # Server-Sent Events
│   ├── services/
│   │   ├── ollama_client.py     # Client HTTP Ollama
│   │   ├── progress_bus.py      # Pub/Sub progression (Redis)
│   │   ├── remote_search.py     # Scraping ollama.com
│   │   └── tasks.py             # Jobs RQ (pull, check, eject)
│   └── pwa/
│       ├── manifest.json        # Manifest PWA
│       └── service-worker.js    # Service Worker
├── tests/
│   └── test_smoke.py            # Tests de base
├── requirements.txt
├── wsgi.py                      # Point d'entrée WSGI
└── README.md
```

## Déploiement en production

### 1. Gunicorn + Gevent

```bash
gunicorn -w 2 -k gevent --bind 0.0.0.0:8000 wsgi:app
```

### 2. Avec Docker

```bash
# Build
docker build -t ollama-manager .

# Run
docker run -d \
  -p 8000:8000 \
  -e OLLAMA_BASE_URL=http://ollama:11434 \
  -e REDIS_URL=redis://redis:6379/0 \
  ollama-manager
```

### 3. Reverse proxy (Nginx)

```nginx
server {
    listen 80;
    server_name ollama-manager.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 600s;
    }
}
```

## API Endpoints

### UI Routes
- `GET /` - Dashboard
- `GET /models` - Liste des modèles
- `GET /models/<name>` - Détails d'un modèle
- `GET /search` - Recherche distante
- `GET /health` - Healthcheck

### API Routes
- `GET /api/models` - Liste (HTML pour HTMX)
- `POST /api/models/show` - Détails
- `POST /api/models/pull` - Pull avec progression
- `DELETE /api/models/<name>` - Supprimer
- `POST /api/models/copy` - Copier/renommer
- `GET /api/running` - Modèles en exécution
- `POST /api/eject` - Éjection douce
- `POST /api/eject/force` - Éjection forcée
- `POST /api/models/check_update` - Vérifier MAJ
- `GET /api/stream/progress?job_id=...` - SSE progression
- `GET /api/remote/search?q=...` - Recherche distante
- `GET /api/remote/variants?model=...` - Variantes
- `GET /api/settings/ollama_base_url` - Get URL Ollama
- `POST /api/settings/ollama_base_url` - Set URL Ollama

## Technologies utilisées

- **Backend**: Python 3.11+, Flask, httpx
- **Queue**: Redis, RQ (jobs asynchrones)
- **Cache**: Flask-Caching
- **Frontend**: Tailwind CSS, HTMX, Alpine.js
- **PWA**: Service Worker avec cache stratégies
- **Tests**: pytest

## Contribuer

1. Fork le projet
2. Créez une branche (`git checkout -b feature/amélioration`)
3. Committez vos changements (`git commit -am 'Ajout fonctionnalité'`)
4. Push vers la branche (`git push origin feature/amélioration`)
5. Créez une Pull Request

## License

MIT

## Support

Pour toute question ou problème, ouvrez une issue sur GitHub.
