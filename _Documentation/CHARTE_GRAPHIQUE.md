# 🎨 Design System - Charte Graphique Universelle

> **Version :** 2.0  
> **Date :** 29 Décembre 2024  
> **Type :** Charte graphique réutilisable pour applications web modernes  
> **Stack recommandée :** Tailwind CSS + Alpine.js (ou React/Vue)

---

## 📑 Table des Matières

1. [Philosophie de Design](#philosophie-de-design)
2. [Palette de Couleurs](#palette-de-couleurs)
3. [Variables CSS Personnalisées](#variables-css-personnalisées)
4. [Typographie](#typographie)
5. [Iconographie](#iconographie)
6. [Espacements et Grilles](#espacements-et-grilles)
7. [Layouts SPA](#layouts-spa)
8. [Composants UI](#composants-ui)
9. [Navigation et Menus](#navigation-et-menus)
10. [Formulaires](#formulaires)
11. [Feedback Utilisateur](#feedback-utilisateur)
12. [Animations et Transitions](#animations-et-transitions)
13. [Mode Sombre / Clair](#mode-sombre--clair)
14. [Accessibilité](#accessibilité)
15. [Responsive Design](#responsive-design)
16. [Templates de Base](#templates-de-base)

---

## 🎯 Philosophie de Design

### Vision
Ce design system adopte une approche **moderne, épurée et professionnelle** inspirée des meilleures interfaces contemporaines. L'objectif est de fournir une base solide et cohérente pour construire n'importe quelle application web.

### Principes Fondamentaux

| Principe | Description |
|----------|-------------|
| **Minimalisme fonctionnel** | Chaque élément a un but précis, pas de décoration superflue |
| **Dark-first** | Mode sombre par défaut, thème clair comme alternative |
| **Mobile-first** | Conception responsive partant du mobile |
| **Performance** | Transitions fluides, chargement optimisé |
| **Accessibilité** | WCAG AA minimum, navigation clavier |
| **Cohérence** | Patterns réutilisables, vocabulaire visuel unifié |

### Personnalisation

Pour adapter ce design system à votre marque, modifiez uniquement :
1. Les couleurs `brand-*` dans la configuration
2. La police principale (remplacer Inter)
3. Le logo et favicon
4. Les textes et labels

---

## 🎨 Palette de Couleurs

### Couleurs de Marque (Brand) - Personnalisables

```css
/* À personnaliser selon votre marque */
--brand-50:  #eef6ff;  /* Backgrounds très légers */
--brand-100: #d9ebff;  /* Surbrillance subtile */
--brand-200: #b7d8ff;  /* Bordures actives (light) */
--brand-300: #8fc1ff;  /* Éléments secondaires */
--brand-400: #64a6ff;  /* Hover states */
--brand-500: #3c8dff;  /* COULEUR PRIMAIRE */
--brand-600: #1d74f0;  /* Boutons, liens actifs */
--brand-700: #185ec4;  /* Hover boutons */
--brand-800: #144e9f;  /* États pressés */
--brand-900: #123f7f;  /* Texte accentué foncé */
```

### Palettes Alternatives Prêtes à l'Emploi

```css
/* Violet/Purple */
--brand-500: #8b5cf6;
--brand-600: #7c3aed;
--brand-700: #6d28d9;

/* Émeraude/Teal */
--brand-500: #14b8a6;
--brand-600: #0d9488;
--brand-700: #0f766e;

/* Orange/Amber */
--brand-500: #f59e0b;
--brand-600: #d97706;
--brand-700: #b45309;

/* Rose/Pink */
--brand-500: #ec4899;
--brand-600: #db2777;
--brand-700: #be185d;
```

### Couleurs Neutres (Zinc) - Base Universelle

| Token | Hex | Mode Clair | Mode Sombre |
|-------|-----|------------|-------------|
| `neutral-50` | `#fafafa` | Fond principal | - |
| `neutral-100` | `#f4f4f5` | Fond secondaire, cartes | - |
| `neutral-200` | `#e4e4e7` | Bordures | - |
| `neutral-300` | `#d4d4d8` | Bordures hover | - |
| `neutral-400` | `#a1a1aa` | Texte désactivé | Texte tertiaire |
| `neutral-500` | `#71717a` | Texte secondaire | - |
| `neutral-600` | `#52525b` | - | Bordures |
| `neutral-700` | `#3f3f46` | - | Fond cartes |
| `neutral-800` | `#27272a` | - | Fond secondaire |
| `neutral-900` | `#18181b` | Texte principal | Fond principal |

### Couleurs Sémantiques

| État | Light | Dark | Usage |
|------|-------|------|-------|
| **Success** | `#22c55e` | `#4ade80` | Confirmations, validation |
| **Error** | `#dc2626` | `#f87171` | Erreurs, suppression |
| **Warning** | `#f59e0b` | `#fbbf24` | Avertissements |
| **Info** | `#3b82f6` | `#60a5fa` | Informations |

---

## 🔧 Variables CSS Personnalisées

### Configuration Racine

```css
:root {
  /* Couleurs principales */
  --color-brand: #3c8dff;
  --color-brand-hover: #1d74f0;
  --color-brand-active: #185ec4;
  
  /* Backgrounds */
  --bg-primary: #ffffff;
  --bg-secondary: #f4f4f5;
  --bg-tertiary: #e4e4e7;
  --bg-elevated: #ffffff;
  
  /* Textes */
  --text-primary: #18181b;
  --text-secondary: #71717a;
  --text-tertiary: #a1a1aa;
  --text-inverse: #ffffff;
  
  /* Bordures */
  --border-default: #e4e4e7;
  --border-hover: #d4d4d8;
  --border-focus: var(--color-brand);
  
  /* Ombres */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.07);
  --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.1);
  --shadow-xl: 0 20px 25px rgba(0, 0, 0, 0.15);
  
  /* Layout */
  --sidebar-width: 280px;
  --sidebar-collapsed: 64px;
  --header-height: 64px;
  --content-max-width: 1280px;
  
  /* Transitions */
  --transition-fast: 150ms ease;
  --transition-normal: 200ms ease;
  --transition-slow: 300ms ease;
  
  /* Rayons */
  --radius-sm: 0.25rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;
  --radius-xl: 1rem;
  --radius-full: 9999px;
}

/* Mode sombre */
.dark {
  --bg-primary: #18181b;
  --bg-secondary: #27272a;
  --bg-tertiary: #3f3f46;
  --bg-elevated: #27272a;
  
  --text-primary: #fafafa;
  --text-secondary: #a1a1aa;
  --text-tertiary: #71717a;
  
  --border-default: #3f3f46;
  --border-hover: #52525b;
  
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.5);
}
```

---

## 📝 Typographie

### Police Principale

```css
font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif;
```

### Import Google Fonts

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

### Échelle Typographique

| Token | Taille | Line Height | Poids | Usage |
|-------|--------|-------------|-------|-------|
| `text-xs` | 0.75rem (12px) | 1rem | 400 | Badges, légendes |
| `text-sm` | 0.875rem (14px) | 1.25rem | 400 | Labels, metadata |
| `text-base` | 1rem (16px) | 1.5rem | 400 | Corps de texte |
| `text-lg` | 1.125rem (18px) | 1.75rem | 500 | Sous-titres |
| `text-xl` | 1.25rem (20px) | 1.75rem | 600 | Titres section |
| `text-2xl` | 1.5rem (24px) | 2rem | 600 | Titres page |
| `text-3xl` | 1.875rem (30px) | 2.25rem | 700 | Titres principaux |

### Police Monospace

```css
font-family: 'Fira Code', 'SF Mono', 'Monaco', 'Consolas', monospace;
```

---

## 🔣 Iconographie

### Spécifications

| Propriété | Valeur |
|-----------|--------|
| **Bibliothèque** | Heroicons, Lucide, ou Phosphor Icons |
| **Format** | SVG inline |
| **Stroke width** | 1.5 - 2 |
| **Style** | Outline par défaut, Solid pour états actifs |

### Tailles Standard

```css
.icon-xs { width: 12px; height: 12px; }
.icon-sm { width: 16px; height: 16px; }
.icon-md { width: 20px; height: 20px; } /* Défaut */
.icon-lg { width: 24px; height: 24px; }
.icon-xl { width: 32px; height: 32px; }
```

### Favicon et Assets

```html
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#18181b">
```

---

## 📐 Espacements et Grilles

### Système d'Espacement (4px base)

| Token | Valeur | Usage |
|-------|--------|-------|
| `space-0.5` | 2px | Micro-ajustements |
| `space-1` | 4px | Entre icône et texte |
| `space-2` | 8px | Padding interne compact |
| `space-3` | 12px | Padding boutons |
| `space-4` | 16px | Espacement standard |
| `space-5` | 20px | - |
| `space-6` | 24px | Séparation sections |
| `space-8` | 32px | Marges larges |
| `space-10` | 40px | - |
| `space-12` | 48px | Grandes séparations |
| `space-16` | 64px | Espacements majeurs |

### Grille de Conteneurs

```css
.container-sm { max-width: 640px; }
.container-md { max-width: 768px; }
.container-lg { max-width: 1024px; }
.container-xl { max-width: 1280px; }
.container-2xl { max-width: 1536px; }
```

---

## 🏗️ Layouts SPA

### Structure de Base

```
┌─────────────────────────────────────────────────────┐
│                     HEADER (64px)                   │
├──────────────┬──────────────────────────────────────┤
│              │                                      │
│   SIDEBAR    │              MAIN                    │
│   (280px)    │            CONTENT                   │
│              │                                      │
│  [Collapsible│                                      │
│   sur mobile]│                                      │
│              │                                      │
└──────────────┴──────────────────────────────────────┘
```

### Header Fixe

```css
.header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: var(--header-height);
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border-default);
  z-index: 40;
  display: flex;
  align-items: center;
  padding: 0 1rem;
  backdrop-filter: blur(8px);
  background: rgba(255, 255, 255, 0.8);
}

.dark .header {
  background: rgba(24, 24, 27, 0.9);
}
```

### Sidebar Collapsible

```css
.sidebar {
  position: fixed;
  top: var(--header-height);
  left: 0;
  bottom: 0;
  width: var(--sidebar-width);
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-default);
  overflow-y: auto;
  overflow-x: hidden;
  transition: transform var(--transition-normal), width var(--transition-normal);
  z-index: 30;
}

/* État collapsed (desktop) */
.sidebar.collapsed {
  width: var(--sidebar-collapsed);
}

.sidebar.collapsed .sidebar-label {
  opacity: 0;
  width: 0;
}

/* Mobile: off-canvas */
@media (max-width: 768px) {
  .sidebar {
    transform: translateX(-100%);
    width: 100%;
    max-width: 320px;
  }
  
  .sidebar.open {
    transform: translateX(0);
  }
  
  .sidebar-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 25;
    opacity: 0;
    pointer-events: none;
    transition: opacity var(--transition-normal);
  }
  
  .sidebar-overlay.visible {
    opacity: 1;
    pointer-events: auto;
  }
}
```

### Main Content

```css
.main-content {
  margin-left: var(--sidebar-width);
  margin-top: var(--header-height);
  min-height: calc(100vh - var(--header-height));
  padding: 1.5rem;
  transition: margin-left var(--transition-normal);
}

.sidebar.collapsed ~ .main-content {
  margin-left: var(--sidebar-collapsed);
}

@media (max-width: 768px) {
  .main-content {
    margin-left: 0;
  }
}
```

### Layout Chat/Messages

```css
.chat-layout {
  display: flex;
  flex-direction: column;
  height: calc(100vh - var(--header-height));
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.chat-input-area {
  border-top: 1px solid var(--border-default);
  padding: 1rem;
  background: var(--bg-elevated);
}
```

### Layout Split/Panneaux

```css
.split-layout {
  display: flex;
  height: calc(100vh - var(--header-height));
}

.split-panel {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.split-panel + .split-panel {
  border-left: 1px solid var(--border-default);
}

/* Redimensionnable */
.split-resizer {
  width: 4px;
  background: var(--border-default);
  cursor: col-resize;
  transition: background var(--transition-fast);
}

.split-resizer:hover {
  background: var(--color-brand);
}
```

---

## 🧩 Composants UI

### Boutons

```css
/* Base commune */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Variantes */
.btn-primary {
  background: var(--color-brand);
  color: var(--text-inverse);
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-brand-hover);
}

.btn-secondary {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
}

.btn-ghost:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.btn-danger {
  background: #dc2626;
  color: white;
}

/* Tailles */
.btn-sm { padding: 0.25rem 0.75rem; font-size: 0.75rem; }
.btn-lg { padding: 0.75rem 1.5rem; font-size: 1rem; }

/* Icon only */
.btn-icon {
  width: 2.5rem;
  height: 2.5rem;
  padding: 0;
}
```

### Cartes

```css
.card {
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.card-header {
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-default);
  font-weight: 600;
}

.card-body {
  padding: 1.5rem;
}

.card-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border-default);
  background: var(--bg-secondary);
}

/* Card interactive */
.card-interactive {
  cursor: pointer;
  transition: all var(--transition-fast);
}

.card-interactive:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}
```

### Modales

```css
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 1rem;
}

.modal {
  background: var(--bg-elevated);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  max-width: 32rem;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  animation: modal-enter 0.2s ease-out;
}

@keyframes modal-enter {
  from {
    opacity: 0;
    transform: scale(0.95) translateY(-10px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.modal-header {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-default);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.modal-body {
  padding: 1.5rem;
}

.modal-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border-default);
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
}
```

### Badges et Tags

```css
.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.125rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 500;
  border-radius: var(--radius-full);
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}

.badge-primary { background: var(--color-brand); color: white; }
.badge-success { background: #dcfce7; color: #166534; }
.badge-warning { background: #fef3c7; color: #92400e; }
.badge-error { background: #fee2e2; color: #991b1b; }

.dark .badge-success { background: #166534; color: #dcfce7; }
.dark .badge-warning { background: #92400e; color: #fef3c7; }
.dark .badge-error { background: #991b1b; color: #fee2e2; }
```

### Avatars

```css
.avatar {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: var(--radius-full);
  background: var(--bg-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: var(--text-secondary);
  overflow: hidden;
}

.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-sm { width: 2rem; height: 2rem; font-size: 0.75rem; }
.avatar-lg { width: 3rem; height: 3rem; font-size: 1.125rem; }
.avatar-xl { width: 4rem; height: 4rem; font-size: 1.5rem; }

/* Groupe d'avatars */
.avatar-group {
  display: flex;
}

.avatar-group .avatar {
  border: 2px solid var(--bg-primary);
  margin-left: -0.5rem;
}

.avatar-group .avatar:first-child {
  margin-left: 0;
}
```

### Dropdowns

```css
.dropdown {
  position: relative;
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  min-width: 12rem;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  padding: 0.5rem;
  z-index: 50;
  opacity: 0;
  visibility: hidden;
  transform: translateY(-8px);
  transition: all var(--transition-fast);
}

.dropdown.open .dropdown-menu {
  opacity: 1;
  visibility: visible;
  transform: translateY(4px);
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.dropdown-item:hover {
  background: var(--bg-tertiary);
}

.dropdown-divider {
  height: 1px;
  background: var(--border-default);
  margin: 0.5rem 0;
}
```

---

## 🧭 Navigation et Menus

### Navigation Sidebar

```css
.nav-section {
  padding: 0.5rem;
}

.nav-section-title {
  padding: 0.5rem 0.75rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.625rem 0.75rem;
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.nav-item:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--color-brand);
  color: white;
}

.nav-item .nav-icon {
  flex-shrink: 0;
  width: 1.25rem;
  height: 1.25rem;
}

.nav-item .nav-badge {
  margin-left: auto;
  font-size: 0.75rem;
  padding: 0.125rem 0.375rem;
  background: var(--bg-primary);
  border-radius: var(--radius-full);
}
```

### Tabs

```css
.tabs {
  display: flex;
  border-bottom: 1px solid var(--border-default);
  gap: 0.5rem;
}

.tab {
  padding: 0.75rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary);
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tab:hover {
  color: var(--text-primary);
}

.tab.active {
  color: var(--color-brand);
  border-bottom-color: var(--color-brand);
}

/* Tabs pills */
.tabs-pills {
  display: flex;
  gap: 0.5rem;
  padding: 0.25rem;
  background: var(--bg-secondary);
  border-radius: var(--radius-lg);
}

.tabs-pills .tab {
  border: none;
  border-radius: var(--radius-md);
  margin: 0;
}

.tabs-pills .tab.active {
  background: var(--bg-elevated);
  box-shadow: var(--shadow-sm);
}
```

### Breadcrumbs

```css
.breadcrumbs {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
}

.breadcrumb-item {
  color: var(--text-secondary);
}

.breadcrumb-item.active {
  color: var(--text-primary);
  font-weight: 500;
}

.breadcrumb-separator {
  color: var(--text-tertiary);
}
```

---

## 📝 Formulaires

### Inputs

```css
.form-group {
  margin-bottom: 1.5rem;
}

.form-label {
  display: block;
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
}

.form-input {
  width: 100%;
  padding: 0.625rem 0.875rem;
  font-size: 0.875rem;
  background: var(--bg-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  transition: all var(--transition-fast);
}

.form-input:hover {
  border-color: var(--border-hover);
}

.form-input:focus {
  outline: none;
  border-color: var(--color-brand);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.form-input::placeholder {
  color: var(--text-tertiary);
}

.form-input:disabled {
  background: var(--bg-secondary);
  cursor: not-allowed;
  opacity: 0.6;
}

/* États */
.form-input.error {
  border-color: #dc2626;
}

.form-input.success {
  border-color: #22c55e;
}

.form-hint {
  margin-top: 0.375rem;
  font-size: 0.75rem;
  color: var(--text-tertiary);
}

.form-error {
  margin-top: 0.375rem;
  font-size: 0.75rem;
  color: #dc2626;
}
```

### Textarea

```css
.form-textarea {
  min-height: 120px;
  resize: vertical;
  line-height: 1.5;
}

/* Auto-resize avec JS */
.form-textarea-auto {
  resize: none;
  overflow: hidden;
  transition: height 0.1s ease;
}
```

### Select

```css
.form-select {
  appearance: none;
  background-image: url("data:image/svg+xml,..."); /* Chevron */
  background-repeat: no-repeat;
  background-position: right 0.75rem center;
  background-size: 1rem;
  padding-right: 2.5rem;
}
```

### Checkbox et Radio

```css
.form-checkbox,
.form-radio {
  appearance: none;
  width: 1.25rem;
  height: 1.25rem;
  border: 2px solid var(--border-default);
  background: var(--bg-primary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.form-checkbox {
  border-radius: var(--radius-sm);
}

.form-radio {
  border-radius: var(--radius-full);
}

.form-checkbox:checked,
.form-radio:checked {
  background: var(--color-brand);
  border-color: var(--color-brand);
}

.form-checkbox:checked {
  background-image: url("data:image/svg+xml,..."); /* Checkmark */
}

.form-radio:checked::after {
  content: '';
  display: block;
  width: 0.5rem;
  height: 0.5rem;
  background: white;
  border-radius: var(--radius-full);
  margin: 0.125rem;
}
```

### Toggle/Switch

```css
.toggle {
  position: relative;
  width: 2.75rem;
  height: 1.5rem;
  background: var(--bg-tertiary);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.toggle::after {
  content: '';
  position: absolute;
  top: 0.125rem;
  left: 0.125rem;
  width: 1.25rem;
  height: 1.25rem;
  background: white;
  border-radius: var(--radius-full);
  box-shadow: var(--shadow-sm);
  transition: transform var(--transition-fast);
}

.toggle.active {
  background: var(--color-brand);
}

.toggle.active::after {
  transform: translateX(1.25rem);
}
```

---

## 💬 Feedback Utilisateur

### Toasts/Notifications

```css
.toast-container {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  z-index: 200;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.toast {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  min-width: 300px;
  max-width: 400px;
  animation: toast-enter 0.3s ease;
}

@keyframes toast-enter {
  from {
    opacity: 0;
    transform: translateX(100%);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.toast-success { border-left: 4px solid #22c55e; }
.toast-error { border-left: 4px solid #dc2626; }
.toast-warning { border-left: 4px solid #f59e0b; }
.toast-info { border-left: 4px solid #3b82f6; }
```

### Loading States

```css
/* Spinner */
.spinner {
  width: 1.5rem;
  height: 1.5rem;
  border: 2px solid var(--border-default);
  border-top-color: var(--color-brand);
  border-radius: var(--radius-full);
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Skeleton */
.skeleton {
  background: linear-gradient(
    90deg,
    var(--bg-tertiary) 25%,
    var(--bg-secondary) 50%,
    var(--bg-tertiary) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: var(--radius-md);
}

@keyframes skeleton-loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.skeleton-text {
  height: 1rem;
  width: 100%;
}

.skeleton-avatar {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: var(--radius-full);
}
```

### Tooltips

```css
.tooltip {
  position: relative;
}

.tooltip::after {
  content: attr(data-tooltip);
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%) translateY(-4px);
  padding: 0.375rem 0.625rem;
  background: var(--text-primary);
  color: var(--bg-primary);
  font-size: 0.75rem;
  border-radius: var(--radius-md);
  white-space: nowrap;
  opacity: 0;
  visibility: hidden;
  transition: all var(--transition-fast);
  z-index: 100;
}

.tooltip:hover::after {
  opacity: 1;
  visibility: visible;
  transform: translateX(-50%) translateY(-8px);
}
```

### Empty States

```css
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 2rem;
  text-align: center;
}

.empty-state-icon {
  width: 4rem;
  height: 4rem;
  color: var(--text-tertiary);
  margin-bottom: 1rem;
}

.empty-state-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}

.empty-state-description {
  color: var(--text-secondary);
  max-width: 24rem;
  margin-bottom: 1.5rem;
}
```

---

## ✨ Animations et Transitions

### Transitions Standards

```css
/* Durées */
--transition-fast: 150ms ease;
--transition-normal: 200ms ease;
--transition-slow: 300ms ease;

/* Usage recommandé */
.interactive-element {
  transition: 
    background var(--transition-fast),
    border-color var(--transition-fast),
    color var(--transition-fast),
    transform var(--transition-fast),
    box-shadow var(--transition-fast);
}
```

### Animations Réutilisables

```css
/* Fade */
@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes fade-out {
  from { opacity: 1; }
  to { opacity: 0; }
}

/* Slide */
@keyframes slide-up {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes slide-down {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Scale */
@keyframes scale-in {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

/* Pulse */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Bounce */
@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-25%); }
}

/* Spin */
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Shake */
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-5px); }
  75% { transform: translateX(5px); }
}
```

### Classes Utilitaires

```css
.animate-fade-in { animation: fade-in 0.2s ease forwards; }
.animate-slide-up { animation: slide-up 0.2s ease forwards; }
.animate-scale-in { animation: scale-in 0.2s ease forwards; }
.animate-pulse { animation: pulse 2s infinite; }
.animate-bounce { animation: bounce 1s infinite; }
.animate-spin { animation: spin 1s linear infinite; }
```

---

## 🌓 Mode Sombre / Clair

### Détection et Persistence

```javascript
// Initialisation au chargement
(function() {
  const theme = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  
  if (theme === 'dark' || (!theme && prefersDark)) {
    document.documentElement.classList.add('dark');
  }
})();

// Toggle
function toggleTheme() {
  const isDark = document.documentElement.classList.toggle('dark');
  localStorage.setItem('theme', isDark ? 'dark' : 'light');
}

// Respecter les préférences système
window.matchMedia('(prefers-color-scheme: dark)')
  .addEventListener('change', (e) => {
    if (!localStorage.getItem('theme')) {
      document.documentElement.classList.toggle('dark', e.matches);
    }
  });
```

### Meta Tags

```html
<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#18181b" media="(prefers-color-scheme: dark)">
<meta name="color-scheme" content="light dark">
```

---

## ♿ Accessibilité

### Focus Visible

```css
/* Reset du focus par défaut */
*:focus {
  outline: none;
}

/* Focus visible pour navigation clavier */
*:focus-visible {
  outline: 2px solid var(--color-brand);
  outline-offset: 2px;
}

/* Alternative pour les éléments sombres */
.dark *:focus-visible {
  outline-color: var(--brand-400);
}
```

### Screen Readers

```css
/* Masquer visuellement, accessible aux SR */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* Afficher au focus */
.sr-only-focusable:focus {
  position: static;
  width: auto;
  height: auto;
  margin: 0;
  overflow: visible;
  clip: auto;
  white-space: normal;
}
```

### Réduction de Mouvement

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 📱 Responsive Design

### Breakpoints

| Token | Min-width | Usage |
|-------|-----------|-------|
| `sm` | 640px | Téléphones paysage |
| `md` | 768px | Tablettes |
| `lg` | 1024px | Desktop |
| `xl` | 1280px | Large desktop |
| `2xl` | 1536px | Extra large |

### iOS Safe Areas

```css
/* Padding pour encoche et barre home */
.safe-top { padding-top: env(safe-area-inset-top); }
.safe-bottom { padding-bottom: env(safe-area-inset-bottom); }
.safe-left { padding-left: env(safe-area-inset-left); }
.safe-right { padding-right: env(safe-area-inset-right); }

/* Header avec safe area */
.header-safe {
  padding-top: calc(1rem + env(safe-area-inset-top));
}
```

### Dynamic Viewport Height

```css
/* Hauteur viewport dynamique (évite les sauts sur mobile) */
.h-screen-dynamic {
  height: 100vh;
  height: 100dvh;
}

.min-h-screen-dynamic {
  min-height: 100vh;
  min-height: 100dvh;
}
```

### Touch Optimizations

```css
/* Améliorer le scroll sur iOS */
.scroll-smooth {
  -webkit-overflow-scrolling: touch;
  scroll-behavior: smooth;
}

/* Désactiver le overscroll bounce */
.no-bounce {
  overscroll-behavior: none;
}

/* Taille minimale pour éléments tactiles */
.touch-target {
  min-width: 44px;
  min-height: 44px;
}
```

---

## 📄 Templates de Base

### HTML de Base

```html
<!DOCTYPE html>
<html lang="fr" class="h-full">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#18181b">
  <meta name="color-scheme" content="light dark">
  
  <!-- PWA -->
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <link rel="manifest" href="/manifest.json">
  
  <!-- Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  
  <!-- Dark mode early detection -->
  <script>
    (function() {
      const t = localStorage.getItem('theme');
      const p = window.matchMedia('(prefers-color-scheme: dark)').matches;
      if (t === 'dark' || (!t && p)) document.documentElement.classList.add('dark');
    })();
  </script>
  
  <title>Application</title>
</head>
<body class="h-full bg-[--bg-primary] text-[--text-primary]">
  <!-- Header -->
  <header class="header safe-top">
    <!-- Logo, navigation, actions -->
  </header>
  
  <!-- Sidebar -->
  <aside class="sidebar">
    <!-- Navigation -->
  </aside>
  
  <!-- Main Content -->
  <main class="main-content">
    <!-- Page content -->
  </main>

  <!-- Scripts -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script defer src="https://unpkg.com/alpinejs@3/dist/cdn.min.js"></script>
</body>
</html>
```

### Configuration Tailwind Complète

```javascript
tailwind.config = {
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['Fira Code', 'ui-monospace', 'monospace']
      },
      colors: {
        brand: {
          50: '#eef6ff',
          100: '#d9ebff',
          200: '#b7d8ff',
          300: '#8fc1ff',
          400: '#64a6ff',
          500: '#3c8dff',
          600: '#1d74f0',
          700: '#185ec4',
          800: '#144e9f',
          900: '#123f7f'
        }
      },
      boxShadow: {
        'card': '0 2px 10px rgba(0, 0, 0, 0.06)',
      },
      animation: {
        'fade-in': 'fade-in 0.2s ease forwards',
        'slide-up': 'slide-up 0.2s ease forwards',
        'pulse-slow': 'pulse 3s infinite',
      }
    }
  }
};
```

---

## 📦 Fichiers CSS Recommandés

```
styles/
├── base.css           # Reset, variables, utilitaires globaux
├── components/
│   ├── buttons.css
│   ├── cards.css
│   ├── forms.css
│   ├── modals.css
│   └── navigation.css
├── layouts/
│   ├── header.css
│   ├── sidebar.css
│   └── grid.css
├── utilities/
│   ├── animations.css
│   └── responsive.css
└── themes/
    ├── light.css
    └── dark.css
```

---

## ✅ Checklist d'Implémentation

Pour chaque nouveau composant :

- [ ] Variables CSS utilisées (pas de valeurs hardcodées)
- [ ] Support mode sombre (`.dark` prefix)
- [ ] États hover, focus, active, disabled
- [ ] Transitions fluides
- [ ] Responsive (mobile-first)
- [ ] Safe areas iOS si applicable
- [ ] Accessibilité clavier (focus-visible)
- [ ] Contrastes WCAG AA
- [ ] Tests sur Chrome, Firefox, Safari

---

*Design System v2.0 - Mis à jour le 29/12/2024*
