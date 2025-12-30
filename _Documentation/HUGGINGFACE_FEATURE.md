# Fonctionnalité HuggingFace GGUF

## Vue d'ensemble

Cette fonctionnalité permet de rechercher et télécharger des modèles GGUF directement depuis HuggingFace Hub dans l'application Ollama Manager.

## Caractéristiques

### 🔍 Recherche Avancée

L'interface de recherche offre plusieurs filtres pour trouver le modèle parfait :

- **Recherche textuelle** : Recherchez par nom de modèle (llama, mistral, qwen, etc.)
- **Nombre de paramètres** : Filtrez par taille de modèle (1B, 3B, 7B, 13B, 30B, 70B, 180B)
- **Quantification** : Choisissez le niveau de compression
  - Q2_K : Très petite (qualité réduite)
  - Q3_K_M : Petite (bon compromis)
  - Q4_K_M : Moyenne (recommandé)
  - Q5_K_M : Grande (haute qualité)
  - Q6_K : Très grande
  - Q8_0 : Maximale (quasi-lossless)
- **Tri** : Par téléchargements, likes, date de mise à jour, ou date de création
- **Limite de résultats** : 10, 20, 50 ou 100 modèles

### 📥 Téléchargement Asynchrone

- Téléchargement en arrière-plan avec RQ (Redis Queue)
- Suivi de progression en temps réel via Server-Sent Events
- Barre de progression visuelle
- Statut de téléchargement en direct

### 📦 Fichiers Détaillés

Pour chaque modèle trouvé, vous pouvez voir :
- Liste de tous les fichiers GGUF disponibles
- Taille de chaque fichier (Mo/Go)
- Niveau de quantification détecté automatiquement
- Nombre de paramètres du modèle

## Architecture Technique

### Nouveaux Fichiers

```
app/
├── services/
│   ├── huggingface_client.py      # Client API HuggingFace
│   └── tasks.py                    # Workers ajoutés (enqueue_pull_gguf, pull_gguf_job)
├── blueprints/
│   ├── api/
│   │   └── routes_huggingface.py  # Routes API HuggingFace
│   └── core/
│       ├── routes.py               # Route /huggingface ajoutée
│       └── templates/
│           └── huggingface.html    # Interface utilisateur
```

### Flux de Données

```
1. Utilisateur → Formulaire de recherche
   ↓
2. GET /api/huggingface/search
   ↓
3. HuggingFaceClient.search_gguf_models()
   - Appel API HuggingFace
   - Filtrage des modèles GGUF
   - Parsing des métadonnées
   ↓
4. Retour HTML (HTMX) avec liste des modèles
   ↓
5. Utilisateur clique "Télécharger"
   ↓
6. POST /api/huggingface/pull
   ↓
7. enqueue_pull_gguf() → RQ Job
   ↓
8. pull_gguf_job() en arrière-plan
   - Télécharge le fichier GGUF
   - Publie la progression sur Redis
   ↓
9. Frontend écoute SSE /api/stream/progress
   - Met à jour la barre de progression
   - Affiche le statut
```

## API Endpoints

### GET /api/huggingface/search

Recherche de modèles GGUF sur HuggingFace.

**Paramètres de requête :**
- `q` : Texte de recherche
- `limit` : Nombre de résultats (défaut: 20)
- `sort` : Tri (downloads, likes, updated, created)
- `quantization` : Filtrer par quantification
- `parameter_size` : Filtrer par taille (ex: "7B")
- `min_downloads` : Nombre minimum de téléchargements

**Réponse :** HTML (HTMX) ou JSON

### POST /api/huggingface/pull

Lance le téléchargement d'un modèle GGUF.

**Paramètres :**
- `model_id` : ID du modèle (ex: "TheBloke/Llama-2-7B-GGUF")
- `filename` : Nom du fichier GGUF
- `output_dir` : (Optionnel) Répertoire de sortie

**Réponse :** HTML avec barre de progression et script SSE

### GET /api/huggingface/model/<model_id>

Récupère les détails d'un modèle spécifique.

**Réponse :** JSON avec métadonnées complètes

### GET /api/huggingface/quantizations

Liste des niveaux de quantification disponibles.

**Réponse :** `{"quantizations": ["Q2_K", "Q3_K_M", ...]}`

### GET /api/huggingface/parameter_sizes

Liste des tailles de paramètres communes.

**Réponse :** `{"parameter_sizes": ["1B", "3B", "7B", ...]}`

## Configuration

### Variables d'Environnement

Ajoutez à votre fichier de configuration ou `.env` :

```bash
# Optionnel : Token HuggingFace pour accéder aux modèles privés
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxx

# Timeouts pour les requêtes HTTP (déjà configurés)
HTTP_CONNECT_TIMEOUT=10
HTTP_READ_TIMEOUT=600
```

### Répertoire de Téléchargement

Par défaut, les modèles GGUF sont téléchargés dans `/tmp/gguf_models/`.

Pour changer ce répertoire, passez le paramètre `output_dir` lors de l'appel API.

## Utilisation

### Interface Web

1. Accédez à l'application Ollama Manager
2. Cliquez sur "HuggingFace" dans la navigation
3. Utilisez le formulaire de recherche :
   - Entrez un terme de recherche (ex: "llama")
   - (Optionnel) Ouvrez les filtres avancés
   - Sélectionnez la taille de modèle souhaitée
   - Choisissez le niveau de quantification
   - Cliquez sur "Rechercher sur HuggingFace"
4. Parcourez les résultats
5. Cliquez sur "Voir les fichiers" pour chaque modèle
6. Cliquez sur "Télécharger" pour le fichier souhaité
7. Suivez la progression en temps réel

### API Directe

```bash
# Recherche
curl "http://localhost:5000/api/huggingface/search?q=llama&parameter_size=7B&quantization=Q4_K_M"

# Téléchargement
curl -X POST http://localhost:5000/api/huggingface/pull \
  -d "model_id=TheBloke/Llama-2-7B-GGUF" \
  -d "filename=llama-2-7b.Q4_K_M.gguf"
```

## Parsing des Métadonnées

Le système analyse automatiquement les noms de fichiers GGUF pour extraire :

### Quantification

Détecte les patterns comme :
- `Q4_K_M` : Quantification 4-bit K-quant Medium
- `Q5_0` : Quantification 5-bit
- `F16` : Float16 (non quantifié)

Regex : `[._-](Q\d+_[KF]_[MSL]|Q\d+_\d+)[._-]`

### Taille de Paramètres

Détecte les patterns comme :
- `7B` : 7 milliards de paramètres
- `13B` : 13 milliards
- `70B` : 70 milliards

Regex : `[._-](\d+)B[._-]` ou `(\d+)b`

## Dépendances

Les dépendances suivantes sont utilisées (déjà présentes) :

```
httpx>=0.24.0        # Client HTTP async
redis>=5.0.0         # Pub/Sub pour progression
rq>=1.15.0           # Job queue
flask>=3.0.0         # Framework web
```

## Exemples d'Utilisation

### Rechercher les meilleurs modèles Llama 7B quantifiés en Q4

```python
from app.services.huggingface_client import HuggingFaceClient

client = HuggingFaceClient()
models = client.search_gguf_models(
    query="llama",
    sort="downloads",
    filter_params={
        "parameter_size": "7B",
        "quantization": "Q4_K_M"
    }
)

for model in models:
    print(f"{model['id']} - {model['downloads']} téléchargements")
```

### Télécharger un modèle spécifique

```python
from app.services.tasks import enqueue_pull_gguf

job_id = enqueue_pull_gguf(
    model_id="TheBloke/Llama-2-7B-GGUF",
    filename="llama-2-7b.Q4_K_M.gguf",
    output_dir="/path/to/models"
)

print(f"Job ID: {job_id}")
```

## Limitations Connues

1. **Dépendance Redis** : Nécessite Redis pour le suivi de progression
2. **Espace disque** : Les modèles GGUF peuvent être volumineux (plusieurs Go)
3. **API HuggingFace** : Limite de taux potentielle (non authentifié : ~1000 req/h)
4. **Pas d'import automatique** : Les fichiers téléchargés doivent être importés manuellement dans Ollama

## Intégration avec Ollama

Pour utiliser un modèle GGUF téléchargé avec Ollama :

```bash
# Créer un Modelfile
cat > Modelfile << EOF
FROM /tmp/gguf_models/llama-2-7b.Q4_K_M.gguf
PARAMETER temperature 0.7
PARAMETER top_p 0.9
EOF

# Créer le modèle dans Ollama
ollama create my-llama-7b -f Modelfile
```

## Améliorations Futures

- [ ] Import automatique dans Ollama après téléchargement
- [ ] Cache des résultats de recherche
- [ ] Support des modèles privés avec authentification HF
- [ ] Téléchargement parallèle de plusieurs fichiers
- [ ] Prévisualisation des model cards
- [ ] Filtrage par licence (Apache, MIT, etc.)
- [ ] Support des modèles quantifiés GGML (anciens)
- [ ] Notifications push quand le téléchargement est terminé

## Support et Contribution

Pour signaler des bugs ou proposer des améliorations :
- Ouvrez une issue sur GitHub
- Consultez la documentation HuggingFace : https://huggingface.co/docs

## Licence

Cette fonctionnalité fait partie d'Ollama Manager et est soumise à la même licence que le projet principal.
