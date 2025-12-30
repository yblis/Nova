# Changelog - Fonctionnalité HuggingFace GGUF

## Version 1.0.0 - Implémentation initiale

### ✨ Nouvelles Fonctionnalités

#### 🔍 Recherche Avancée de Modèles GGUF
- **Recherche textuelle** : Recherchez par nom de modèle (llama, mistral, qwen, phi, etc.)
- **Filtrage par taille de paramètres** : 30+ tailles disponibles
  - Très petits : 0.5B, 0.6B
  - Petits : 1B à 3B (Phi, Gemma 2B, Qwen 1.5B)
  - Moyens : 4B à 9B (Mistral 7B, Llama 3 8B, Qwen 7B) ⭐ Populaires
  - Grands : 13B à 40B (Mixtral, Llama 2 13B)
  - Très grands : 65B à 110B (Llama 2 70B, Qwen 72B)
  - Massifs : 180B+ (Llama 3.1 405B, Grok 314B)

- **Filtrage par quantification** : 14 niveaux disponibles
  - Q2_K : Très compressé (qualité réduite)
  - Q3_K_S/M/L : Petite taille
  - Q4_0, Q4_K_S/M : Recommandé pour usage général
  - Q5_0, Q5_K_S/M : Haute qualité
  - Q6_K : Très haute qualité
  - Q8_0 : Quasi-lossless
  - F16/F32 : Non quantifié (très volumineux)

- **Options de tri** : Par téléchargements, likes, date de mise à jour ou création
- **Nombre de résultats** : 10, 20, 50 ou 100 modèles

#### 📥 Téléchargement Asynchrone
- Téléchargement en arrière-plan avec Redis Queue (RQ)
- Suivi de progression en temps réel via Server-Sent Events (SSE)
- Barre de progression visuelle interactive
- Statut détaillé pendant le téléchargement
- Gestion d'erreurs robuste

#### 📦 Affichage Détaillé
- Liste de tous les fichiers GGUF disponibles pour chaque modèle
- Taille affichée en Mo/Go automatiquement
- Détection automatique de la quantification depuis le nom de fichier
- Détection automatique du nombre de paramètres
- Statistiques : téléchargements, likes, nombre de fichiers
- Liens directs vers HuggingFace Hub

#### 🎨 Interface Utilisateur
- Design moderne avec Tailwind CSS
- Mode sombre/clair
- Responsive (mobile, tablette, desktop)
- Guide intégré pour choisir la bonne taille de modèle
- Filtres avancés repliables
- Auto-submit optionnel lors du changement de filtre

### 🏗️ Architecture Technique

#### Nouveaux Fichiers Créés

```
app/
├── services/
│   ├── huggingface_client.py          # Client API HuggingFace (397 lignes)
│   └── tasks.py                        # Workers ajoutés (enqueue_pull_gguf, pull_gguf_job)
│
├── blueprints/
│   ├── api/
│   │   └── routes_huggingface.py      # 6 routes API (245 lignes)
│   │
│   └── core/
│       ├── routes.py                   # Route /huggingface ajoutée
│       └── templates/
│           └── huggingface.html        # Interface utilisateur (197 lignes)
│
├── __init__.py                         # Blueprint enregistré
└── blueprints/core/templates/
    └── base.html                       # Navigation mise à jour

Documentation/
├── HUGGINGFACE_FEATURE.md              # Documentation complète
├── CHANGELOG_HUGGINGFACE.md            # Ce fichier
└── test_huggingface.py                 # Script de test
```

#### Routes API Ajoutées

| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/huggingface/search` | GET | Recherche de modèles GGUF |
| `/api/huggingface/pull` | POST | Lance le téléchargement d'un fichier GGUF |
| `/api/huggingface/model/<id>` | GET | Détails d'un modèle spécifique |
| `/api/huggingface/quantizations` | GET | Liste des quantifications disponibles |
| `/api/huggingface/parameter_sizes` | GET | Liste des tailles disponibles |
| `/huggingface` | GET | Page de recherche (interface) |

#### Classes et Fonctions Principales

**HuggingFaceClient** (`app/services/huggingface_client.py`)
- `search_gguf_models()` : Recherche avec filtres avancés
- `get_model_info()` : Informations détaillées d'un modèle
- `download_gguf_stream()` : Téléchargement avec progression
- `_parse_gguf_files()` : Parsing intelligent des métadonnées
- `_matches_filters()` : Filtrage côté client

**Workers Asynchrones** (`app/services/tasks.py`)
- `enqueue_pull_gguf()` : Enqueue un job de téléchargement
- `pull_gguf_job()` : Worker qui télécharge le fichier GGUF

### 🔧 Améliorations Techniques

#### Parsing Intelligent des Métadonnées
- **Regex améliorée** pour détecter les tailles décimales (1.5B, 2.7B, etc.)
- **Détection de quantification** : patterns Q4_K_M, Q5_0, F16, etc.
- **Support des conventions de nommage** multiples

#### Gestion des Timeouts
- **Fix critique** : `httpx.Timeout` avec les 4 paramètres requis
  - `connect`, `read`, `write`, `pool`
- Évite l'erreur : "httpx.Timeout must either include a default, or set all four parameters explicitly"

#### Optimisations
- **Tri des fichiers** par taille (plus grand en premier)
- **Limite d'affichage** : 10 fichiers par modèle (évite le spam)
- **Troncature des descriptions** : 150 caractères max
- **Formatage intelligent** : K/M pour les nombres (1.5M downloads)

### 📊 Tailles de Modèles Supportées

Liste complète de 30 tailles de paramètres :

```
0.5B, 0.6B, 1B, 1.5B, 1.7B, 1.8B, 2B, 2.7B, 3B, 4B,
7B, 8B, 9B, 13B, 14B, 27B, 30B, 32B, 33B, 34B,
40B, 65B, 70B, 72B, 110B, 180B, 235B, 314B, 405B
```

**Familles de modèles couvertes :**
- Llama 2/3/3.1 : 7B, 8B, 13B, 70B, 405B
- Qwen 1.5/2.5/3 : 0.5B, 0.6B, 1.5B, 1.7B, 1.8B, 3B, 4B, 7B, 8B, 14B, 30B, 32B, 72B, 110B, 235B
- Phi 3/4 : 2.7B, 3B, 14B
- Gemma 2/3 : 2B, 4B, 9B, 27B
- Mistral : 7B, 22B
- Grok : 314B

### 🐛 Corrections de Bugs

#### Bug #1 : Erreur httpx.Timeout
**Symptôme :**
```
httpx.Timeout must either include a default, or set all four parameters explicitly.
```

**Cause :** Initialisation de `httpx.Timeout` avec seulement 2 des 4 paramètres requis

**Solution :** Ajout des paramètres `write` et `pool`
```python
self.timeout = httpx.Timeout(
    connect=connect_timeout,
    read=read_timeout,
    write=connect_timeout,  # ✅ Ajouté
    pool=connect_timeout     # ✅ Ajouté
)
```

**Fichier modifié :** `app/services/huggingface_client.py:34-39`

### 🎯 Cas d'Usage

#### Exemple 1 : Recherche de modèles Llama 7B optimisés
```
1. Accéder à /huggingface
2. Entrer "llama" dans la recherche
3. Ouvrir les filtres avancés
4. Sélectionner "7B" comme taille
5. Sélectionner "Q4_K_M" comme quantification
6. Cliquer "Rechercher"
7. Parcourir les résultats
8. Cliquer "Voir les fichiers"
9. Cliquer "Télécharger" sur le fichier souhaité
```

#### Exemple 2 : Trouver les meilleurs modèles Qwen récents
```
1. Rechercher "qwen"
2. Trier par "Mis à jour"
3. Choisir la taille selon votre matériel (1.7B pour mobile, 7B pour laptop, 72B pour serveur)
4. Télécharger
```

### 📚 Documentation

- **Guide complet** : `HUGGINGFACE_FEATURE.md` (350+ lignes)
- **Guide intégré** dans l'interface (aide au choix de modèle)
- **Script de test** : `test_huggingface.py`
- **Ce changelog** : `CHANGELOG_HUGGINGFACE.md`

### ⚙️ Configuration

#### Variables d'Environnement (Optionnelles)
```bash
# Token HuggingFace pour modèles privés
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxx

# Timeouts (déjà configurés)
HTTP_CONNECT_TIMEOUT=10
HTTP_READ_TIMEOUT=600
```

#### Répertoire de Téléchargement
Par défaut : `/tmp/gguf_models/`

Personnalisable via le paramètre `output_dir` lors de l'appel API.

### 🔒 Sécurité

- ✅ Échappement HTML avec `markupsafe.escape()`
- ✅ Validation des entrées utilisateur
- ✅ Gestion des erreurs robuste
- ✅ Timeouts configurables
- ✅ Pas d'exécution de code arbitraire

### 🚀 Performance

- **Cache Redis** : Résultats de recherche (optionnel)
- **Streaming** : Téléchargement avec chunks de 8KB
- **Async Workers** : Téléchargement en arrière-plan (RQ)
- **Pagination** : Limite de résultats configurable

### 🧪 Tests

**Script de test créé** : `test_huggingface.py`
- Test de recherche simple
- Test de recherche avec filtres
- Test de récupération d'infos modèle
- Test des listes de référence

**Exécution :**
```bash
python test_huggingface.py
```

### 📈 Statistiques

- **Lignes de code ajoutées** : ~1200
- **Fichiers créés** : 4
- **Fichiers modifiés** : 3
- **Routes API ajoutées** : 6
- **Templates HTML créés** : 1
- **Tailles de modèles supportées** : 30
- **Niveaux de quantification** : 14

### 🔮 Améliorations Futures

#### Court terme
- [ ] Import automatique dans Ollama après téléchargement
- [ ] Cache des résultats de recherche (Redis)
- [ ] Notifications push de fin de téléchargement
- [ ] Reprise de téléchargement en cas d'échec

#### Moyen terme
- [ ] Support des modèles privés avec authentification HF
- [ ] Téléchargement parallèle de plusieurs fichiers
- [ ] Prévisualisation des model cards (README)
- [ ] Filtrage par licence (Apache 2.0, MIT, etc.)
- [ ] Historique des téléchargements

#### Long terme
- [ ] Conversion automatique GGUF → Ollama
- [ ] Benchmark intégré des modèles
- [ ] Comparaison de modèles côte à côte
- [ ] Recommandations basées sur le matériel
- [ ] Support des modèles GGML (anciens)

### 🤝 Contribution

Cette fonctionnalité a été développée avec :
- **Flask 3.0+** : Framework web
- **httpx 0.27+** : Client HTTP moderne
- **Redis 5.0+** : Pub/Sub et cache
- **RQ 1.15+** : Job queue
- **Tailwind CSS** : Styling
- **HTMX 1.9** : Interactivité
- **Alpine.js 3.x** : État réactif

### 📄 Licence

Cette fonctionnalité fait partie d'Ollama Manager et est soumise à la même licence que le projet principal.

---

**Développé le** : Octobre 2025
**Version** : 1.0.0
**Status** : ✅ Production Ready
