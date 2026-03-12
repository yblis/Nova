# Listing dynamique des modèles LLM

## Objectif métier

Permettre aux utilisateurs de voir et sélectionner uniquement les modèles réellement disponibles chez leur fournisseur LLM, sans dépendre d'une liste pré-définie dans le code qui devient obsolète avec le temps.

## Cas d'usage

1. **Configuration initiale** : L'utilisateur ajoute un fournisseur LLM (ex: Google Gemini) et configure sa clé API. En ouvrant le sélecteur de modèle, seuls les modèles auxquels il a accès sont affichés.

2. **Nouveaux modèles** : Quand un fournisseur publie un nouveau modèle, il apparait automatiquement dans la liste sans nécessiter de mise à jour de l'application.

3. **Modèles dépréciés** : Quand un fournisseur retire un modèle, il disparait automatiquement de la liste, évitant les erreurs "model not found".

4. **Test de connexion** : L'utilisateur clique sur "Tester la connexion" pour vérifier que sa clé API est valide et voir le nombre de modèles disponibles.

## Règles métier

- La liste des modèles est récupérée à chaque ouverture du sélecteur (pas de cache longue durée)
- Si la clé API est invalide ou le service indisponible, la liste est vide (pas de modèles fantômes)
- Le modèle par défaut est celui choisi par l'utilisateur dans les paramètres, pas un modèle pré-défini par le code
- Le test de connexion ne consomme aucun token et ne génère aucun coût

## Comportement aux limites

- **Fournisseur indisponible** : la liste de modèles est vide, un avertissement est logué côté serveur
- **Clé API invalide** : la liste est vide, le test de connexion affiche une erreur explicite
- **Nouveau fournisseur sans endpoint de listing** : retourne une liste vide, l'utilisateur peut saisir manuellement le nom du modèle
- **Modèle sélectionné supprimé par le fournisseur** : l'erreur "model not found" est affichée lors de la prochaine utilisation, l'utilisateur doit en choisir un autre

## Glossaire

- **Provider** : Fournisseur de service LLM (Google, Anthropic, OpenAI, etc.)
- **Listing dynamique** : Récupération de la liste des modèles via l'API du fournisseur à chaque sollicitation
- **Modèle par défaut** : Le modèle pré-sélectionné dans les paramètres de l'utilisateur pour un fournisseur donné
