# Command Palette — Documentation Fonctionnelle

## Objectif métier

Permettre aux utilisateurs de naviguer instantanément vers n'importe quelle page ou paramètre de l'application en tapant quelques caractères, sans parcourir la sidebar manuellement. Le raccourci `Cmd+K` (Mac) / `Ctrl+K` (Windows/Linux) ouvre un champ de recherche modal.

## Cas d'usage

1. **Navigation rapide** : un utilisateur sur la page Chat veut aller aux paramètres RAG. Il tape `Cmd+K`, écrit "rag", appuie sur Entrée. Il est redirigé instantanément.
2. **Recherche floue** : l'utilisateur tape "modele" (sans accent), le système trouve "Modèles installés".
3. **Action depuis n'importe où** : l'utilisateur tape `Cmd+K` puis "nouveau chat" pour créer une conversation sans quitter sa page actuelle.
4. **Changement de thème** : l'utilisateur tape "theme" pour basculer entre mode clair et sombre.
5. **Découverte des paramètres** : un nouvel utilisateur tape "email" pour trouver la configuration Email Agent sans connaître la structure des menus.

## Règles métier

- La palette s'ouvre avec `Cmd+K` / `Ctrl+K` depuis n'importe quelle page
- Le bouton "Recherche" dans la sidebar ouvre également la palette
- La recherche est insensible à la casse et aux accents
- Les résultats sont groupés : Navigation, Paramètres, Actions
- Les flèches haut/bas naviguent dans les résultats, Entrée valide, Echap ferme
- Un clic sur le fond semi-transparent ferme la palette
- La palette se ferme automatiquement après exécution d'une commande
- L'input est vidé à chaque ouverture

## Comportement aux limites

- Si aucun résultat ne correspond : affichage "Aucun résultat"
- Si la page de destination n'est pas dans le SPA router : fallback sur navigation classique (`window.location.href`)
- Sur mobile : le modal s'adapte en pleine largeur avec marges

## Idées d'enrichissement validées

1. Mots-clés et alias pour recherche tolérante
2. Catégories visuelles avec séparateurs
3. Navigation au clavier complète
4. Indicateur de raccourci dans la sidebar (`⌘K`)
5. Actions rapides (nouveau chat, changer thème)

## Glossaire

| Terme | Définition |
|---|---|
| Command Palette | Interface modale de recherche/navigation rapide |
| Fuzzy search | Recherche approximative tolérante aux variations (accents, casse) |
| SPA Router | Système de navigation sans rechargement de page |
