# Plan de Refactoring : Unification des Templates (SPA)

## Problème Actuel
L'architecture actuelle utilise des modèles dupliqués pour la navigation classique et la navigation SPA (dossier `partials/`). Cela crée une dette technique importante : toute modification d'interface doit être répliquée manuellement à deux endroits, ce qui est source d'erreurs et d'oublis.

## Solution Proposée : Héritage Dynamique
Utiliser le mécanisme d'héritage de Jinja2 pour permettre à un template unique de s'adapter au contexte (page complète vs fragment HTML) via une variable passée par le backend.

> [!IMPORTANT]
> **Respect Impératif du Comportement SPA (Single Page Application)**
> Cette solution est conçue spécifiquement pour maintenir le fonctionnement "SPA-like" actuel (HTMX).
> *   Les requêtes via le menu continueront de recevoir uniquement le fragment HTML nécessaire.
> *   Le navigateur ne rechargera pas la page complète.
> *   Les transitions fluides seront conservées à l'identique.

## Étapes d'Implémentation

### 1. Création du Layout "Neutre" (SPA Mode)
Créer un fichier `app/templates/ajax.html` qui sert de conteneur vide. C'est la clé pour le SPA : il permet de rendre le *mëme* contenu, mais sans le `<html>`, `<head>`, et `<body>` autour.

```html
<!-- app/templates/ajax.html -->
<!-- Ce layout ne rend QUE le contenu, parfait pour l'injection HTMX -->
{% block content %}{% endblock %}
```

### 2. Modification des Templates
Mettre à jour tous les templates principaux (`chat.html`, `models.html`, `settings.html`, etc.) pour rendre leur héritage conditionnel.

**Avant :**
```html
{% extends 'base.html' %}
```

**Après :**
```html
<!-- Si c'est une requête SPA (HTMX), on utilise ajax.html (vide).
     Sinon, on utilise base.html (complet avec headers/scripts). -->
{% extends layout_template|default('base.html') %}
```

### 3. Mise à jour du Routeur (Backend)
Modifier la logique des routes Flask pour injecter le bon layout. Le routeur SPA existant sera conservé mais optimisé.

**Fichier :** `app/blueprints/core/routes.py`

```python
# Routeur SPA existant
@core_bp.route("/partials/<page>")
def spa_partial(page):
    # CRITIQUE : Au lieu de chercher un fichier séparé dans /partials/,
    # on réutilise le fichier principal mais on force le layout 'ajax.html'.
    # Cela garantit que HTMX reçoit exactement le fragment HTML attendu.
    return render_template(f"{page}.html", layout_template="ajax.html")
```

### 4. Vérification et Nettoyage
1.  Tester la navigation classique (F5) -> Doit charger `base.html`.
2.  Tester la navigation menu (HTMX) -> Doit charger `ajax.html` (fragment).
3.  Une fois validé, supprimer le dossier `templates/partials/`.

## Avantages
*   **Zero Duplication** : Une seule modification met à jour toute l'application.
*   **SPA Preservée** : Le comportement utilisateur est strictement identique.
*   **Fiabilité** : Impossible d'avoir des divergences de design.
