# Command Palette — Documentation Technique

## Architecture

Module autonome de recherche globale (Command Palette) permettant la navigation rapide dans l'application via `Cmd/Ctrl+K`.

**Responsabilite** : fournir une interface de recherche/navigation modale accessible depuis n'importe quelle page de l'application.

**Place dans le systeme** : composant global, monté au niveau du layout `base.html`, indépendant de la page active.

## Interface publique

### Composant Alpine.js : `commandPalette()`

| Propriété | Type | Description |
|---|---|---|
| `isOpen` | `boolean` | État d'ouverture du modal |
| `query` | `string` | Texte de recherche courant |
| `selectedIndex` | `number` | Index de l'item sélectionné |
| `commands` | `Array<Command>` | Registre de toutes les commandes |
| `filteredCommands` | `Array<Command>` (computed) | Commandes filtrées par la query |
| `groupedCommands` | `Array<Group>` (computed) | Commandes groupées par section |

### Événements

| Événement | Direction | Description |
|---|---|---|
| `command-palette:open` (window) | Entrant | Ouvre la palette |
| `spa:navigate-to` (window) | Sortant | Navigation SPA |
| `settings-tab-change` (window) | Sortant | Changement d'onglet Settings |

### Structure `Command`

```
{ id, section, title, path, keywords[], action? }
```

## Dépendances

- **Alpine.js** (global) — framework réactif
- **SpaRouter** (global) — navigation SPA (optionnel, fallback sur `window.location`)

## Effets de bord

- Navigation via `SpaRouter` ou manipulation de `window.location.href`
- Dispatch d'événements `CustomEvent` sur `window`
- Manipulation du thème via `uiState` (action "toggleTheme")

## Fichiers

| Fichier | Rôle |
|---|---|
| `static/js/components/command-palette.js` | Composant Alpine.js |
| `static/css/command-palette.css` | Styles centralisés |
| `templates/layouts/base.html` | Intégration HTML + raccourci clavier |

## Décisions d'architecture

- **Recherche côté client uniquement** : le registre de commandes est statique et léger (~20 items). Pas de besoin d'API serveur.
- **Normalisation des accents** : utilisation de `String.normalize('NFD')` pour permettre la recherche `"general"` qui matche `"Général"`.
- **SVG paths en JS** : les icônes sont référencées par path SVG dans un map centralisé pour éviter de dupliquer le markup et rester cohérent avec l'existant.
- **CSS séparé du Tailwind** : fichier `.css` dédié pour maintenir les styles de la palette indépendamment du build Tailwind et garantir le support dark mode.

## Considérations de sécurité

- Aucune donnée utilisateur n'est traitée (registre statique).
- Le champ de recherche est protégé contre l'autocomplétion navigateur (`autocomplete="off"`).
- Aucune requête réseau n'est effectuée.
- Les commandes admin (`nav-users`) sont présentes dans le registre mais la route `/admin/users` est protégée côté serveur par le middleware d'authentification.
