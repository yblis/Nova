# Correction du problème de création de blob Ollama

## Problème identifié

L'erreur `Ollama /api/blobs did not return a path` se produisait quand :
1. L'API Ollama `/api/blobs` retournait HTTP 200 (succès)
2. Mais ne fournissait pas le chemin du blob dans la réponse
3. Ce qui entraînait un échec de création du modèle Ollama

## Corrections apportées

### 1. Nouvelle exception spécialisée (`ollama_client.py`)

```python
class BlobUploadedWithoutPath(Exception):
    """
    Exception levée quand l'upload d'un blob réussit (HTTP 200/201) 
    mais qu'Ollama ne retourne pas le chemin du blob.
    """
    def __init__(self, message: str, digest: str, status_code: int):
        super().__init__(message)
        self.digest = digest
        self.status_code = status_code
```

### 2. Amélioration de la méthode `create_blob` (`ollama_client.py`)

- Filtrage amélioré du texte de réponse (éviter HTML/JSON vides)
- Lever `BlobUploadedWithoutPath` au lieu de `ValueError` générique
- Distinction claire entre échec d'upload et absence de chemin

### 3. Logique améliorée dans `tasks.py`

- **Variable `blob_uploaded`** : suit l'état réel de l'upload
- **Gestion spécialisée** de `BlobUploadedWithoutPath` :
  - Marque l'upload comme réussi
  - Continue vers la vérification HEAD et l'inférence de chemin
- **Messages moins alarmants** : "Avertissement" au lieu d'"Erreur"
- **Vérification HEAD** même en cas d'erreur de chemin
- **Création de modèle conditionnelle** : seulement si `blob_uploaded = True`

### 4. Flux de traitement amélioré

1. **Upload du blob** → Succès ou échec
2. **Si échec de chemin mais HTTP 200** → Marquer comme uploadé
3. **Vérification HEAD** → Confirmer la présence du blob
4. **Inférence de chemin** → Essayer plusieurs sources
5. **Création du modèle** → Seulement si blob confirmé présent

## Résultat attendu

- **Plus d'erreurs bloquantes** quand Ollama ne retourne pas le chemin
- **Continuation du processus** avec fallback intelligent
- **Messages informatifs** au lieu d'erreurs
- **Création réussie du modèle** dans la plupart des cas

## Test

Relancer le téléchargement GGUF devrait maintenant :
1. Afficher "Blob uploadé mais chemin non retourné par Ollama"
2. Continuer avec la vérification HEAD
3. Tenter l'inférence du chemin
4. Réussir la création du modèle avec un des chemins candidats