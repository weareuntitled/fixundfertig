# Design Token Architecture

> Fintech light-theme design system extracted from Lumina Ledger HTML specifications.
> All values are source-derived — nothing invented.

## Token Tiers

| Tier | Purpose | Consumers |
|------|---------|-----------|
| **Global** | Raw palette values, primitive scales | Token authors only |
| **Alias** | Semantic references (`color-text-primary`, `color-border`) | Component authors |
| **Component** | Scoped to specific components (`button-primary-bg`) | Component internals |

**Rule**: Components never reference global tokens. Always go through alias or component tokens.

---

## Tier 1: Global Tokens

### Color — Palette

| Token | Hex | Notes |
|-------|-----|-------|
| `color-black` | `#000000` | Primary brand in HTML |
| `color-white` | `#ffffff` | On-color text, card fills |
| `color-blue-50` | `#eaf1ff` | inverse-on-surface |
| `color-blue-100` | `#dae2fd` | primary-fixed |
| `color-blue-200` | `#bec6e0` | primary-fixed-dim, inverse-primary |
| `color-blue-300` | `#adc6ff` | tertiary-fixed-dim |
| `color-blue-500` | `#3980f4` | on-tertiary-container (interactive accent) |
| `color-blue-600` | `#004395` | on-tertiary-fixed-variant |
| `color-blue-800` | `#001a42` | tertiary-container, on-tertiary-fixed |
| `color-blue-900` | `#0b1c30` | on-background, on-surface |
| `color-green-400` | `#6cf8bb` | secondary-container |
| `color-green-500` | `#4edea3` | secondary-fixed-dim |
| `color-green-600` | `#006c49` | secondary |
| `color-green-700` | `#005236` | on-secondary-fixed-variant |
| `color-green-800` | `#002113` | on-secondary-fixed |
| `color-red-100` | `#ffdad6` | error-container |
| `color-red-500` | `#ba1a1a` | error |
| `color-red-900` | `#93000a` | on-error-container |
| `color-gray-50` | `#f8f9ff` | surface, background, surface-bright |
| `color-gray-100` | `#eff4ff` | surface-container-low |
| `color-gray-200` | `#e5eeff` | surface-container |
| `color-gray-300` | `#dce9ff` | surface-container-high |
| `color-gray-400` | `#d3e4fe` | surface-container-highest, surface-variant |
| `color-gray-500` | `#cbdbf5` | surface-dim |
| `color-gray-600` | `#c6c6cd` | outline-variant |
| `color-gray-700` | `#7c839b` | on-primary-container |
| `color-gray-800` | `#76777d` | outline |
| `color-gray-900` | `#565e74` | surface-tint |
| `color-gray-950` | `#45464d` | on-surface-variant |
| `color-gray-980` | `#3f465c` | on-primary-fixed-variant |
| `color-gray-990` | `#213145` | inverse-surface |

### Typography — Font Families

| Token | Value |
|-------|-------|
| `font-family-display` | `"Inter", system-ui, sans-serif` |
| `font-family-body` | `"Inter", system-ui, sans-serif` |
| `font-family-mono` | `"JetBrains Mono", "Fira Code", ui-monospace, monospace` |

### Typography — Size Scale

| Token | Size | Line Height | Letter Spacing | Weight |
|-------|------|-------------|----------------|--------|
| `font-size-display-lg` | `48px` | `56px` | `-0.02em` | `700` |
| `font-size-headline-lg` | `32px` | `40px` | `-0.01em` | `600` |
| `font-size-headline-lg-mobile` | `24px` | `32px` | — | `600` |
| `font-size-title-md` | `20px` | `28px` | — | `600` |
| `font-size-body-lg` | `16px` | `24px` | — | `400` |
| `font-size-body-sm` | `14px` | `20px` | — | `400` |
| `font-size-data-mono` | `14px` | `20px` | — | `500` |
| `font-size-label-caps` | `12px` | `16px` | `0.05em` | `600` |

### Spacing Scale

| Token | Value | Pixels |
|-------|-------|--------|
| `space-base` | `4px` | 4 |
| `space-xs` | `0.5rem` | 8 |
| `space-sm` | `1rem` | 16 |
| `space-md` | `1.5rem` | 24 |
| `space-lg` | `2rem` | 32 |
| `space-xl` | `3rem` | 48 |
| `space-gutter` | `24px` | 24 |
| `space-container-max` | `1280px` | 1280 |

### Border Radius

| Token | Value |
|-------|-------|
| `radius-default` | `0.25rem` |
| `radius-lg` | `0.5rem` |
| `radius-xl` | `0.75rem` |
| `radius-full` | `9999px` |

### Elevation

| Token | Value |
|-------|-------|
| `shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` |
| `shadow-md` | `0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.05)` |
| `shadow-lg` | `0 8px 30px rgba(0,0,0,0.02)` |
| `shadow-xl` | `0 20px 50px rgba(0,0,0,0.1)` |

### Motion

| Token | Value |
|-------|-------|
| `duration-fast` | `150ms` |
| `duration-normal` | `200ms` |
| `duration-slow` | `300ms` |
| `ease-out-expo` | `cubic-bezier(0.16, 1, 0.3, 1)` |
| `ease-default` | `cubic-bezier(0.4, 0, 0.2, 1)` |

---

## Tier 2: Alias Tokens

### Background

| Token | References | Usage |
|-------|-----------|-------|
| `color-background` | `color-gray-50` | Page background |
| `color-background-alt` | `color-white` | Alternate sections |
| `color-surface` | `color-gray-50` | App surface |
| `color-surface-card` | `color-white` | Card backgrounds |
| `color-surface-raised` | `color-white` | Raised elements (inputs, popovers) |
| `color-surface-sunken` | `color-gray-100` | Inset areas, code blocks |
| `color-surface-overlay` | `color-gray-200` | Hover states, dropdowns |
| `color-surface-dim` | `color-gray-500` | Modal backdrop area |
| `color-surface-bright` | `color-gray-50` | Bright surface areas |
| `color-surface-container-lowest` | `color-white` | Lowest container |
| `color-surface-container-low` | `color-gray-100` | Low container |
| `color-surface-container` | `color-gray-200` | Default container |
| `color-surface-container-high` | `color-gray-300` | High container |
| `color-surface-container-highest` | `color-gray-400` | Highest container |

### Text

| Token | References | Usage |
|-------|-----------|-------|
| `color-text-primary` | `color-gray-900` | Headings, primary content |
| `color-text-secondary` | `color-gray-950` | Body text, descriptions |
| `color-text-muted` | `color-gray-800` | Labels, placeholders |
| `color-text-on-brand` | `color-white` | Text on primary/brand bg |
| `color-text-on-surface` | `color-gray-900` | Text on surface bg |
| `color-text-link` | `color-blue-500` | Links, interactive text |
| `color-text-danger` | `color-red-500` | Error text |

### Border

| Token | References | Usage |
|-------|-----------|-------|
| `color-border` | `color-gray-600` | Default borders |
| `color-border-strong` | `color-gray-800` | Emphasized borders |
| `color-border-subtle` | `color-gray-200` | Subtle dividers |
| `color-border-focus` | `color-blue-500` | Focus rings |

### Brand / Primary

| Token | References | Usage |
|-------|-----------|-------|
| `color-brand` | `color-black` | Primary actions |
| `color-brand-hover` | `color-gray-990` | Primary hover |
| `color-brand-text` | `color-blue-500` | Interactive/accent text |
| `color-brand-text-hover` | `color-blue-600` | Interactive text hover |
| `color-brand-surface` | `color-gray-200` | Brand-tinted surfaces |
| `color-brand-surface-subtle` | `color-gray-100` | Subtle brand tint |

### Status

| Token | References | Usage |
|-------|-----------|-------|
| `color-status-draft` | `color-gray-700` | Draft status |
| `color-status-draft-bg` | `color-gray-500` | Draft background |
| `color-status-open` | `color-blue-500` | Open/finalized |
| `color-status-open-bg` | `color-blue-100` | Open background |
| `color-status-sent` | `color-blue-500` | Sent status |
| `color-status-sent-bg` | `color-blue-100` | Sent background |
| `color-status-paid` | `color-green-600` | Paid status |
| `color-status-paid-bg` | `color-green-400` | Paid background |
| `color-status-cancelled` | `color-red-500` | Cancelled status |
| `color-status-cancelled-bg` | `color-red-100` | Cancelled background |

### Semantic

| Token | References | Usage |
|-------|-----------|-------|
| `color-info` | `color-blue-500` | Info banners |
| `color-info-bg` | `color-gray-100` | Info banner bg |
| `color-success` | `color-green-600` | Success states |
| `color-success-bg` | `color-green-400` | Success bg |
| `color-danger` | `color-red-500` | Destructive actions |
| `color-danger-bg` | `color-red-100` | Danger bg |

---

## Tier 3: Component Tokens

### Button

| Token | Value | Usage |
|-------|-------|-------|
| `button-primary-bg` | `var(--color-brand)` | Primary fill |
| `button-primary-text` | `var(--color-text-on-brand)` | Primary label |
| `button-primary-hover` | `var(--color-brand-hover)` | Primary hover |
| `button-secondary-bg` | `color-white` | Secondary fill |
| `button-secondary-text` | `var(--color-text-primary)` | Secondary label |
| `button-secondary-border` | `var(--color-border)` | Secondary border |
| `button-ghost-text` | `var(--color-text-secondary)` | Ghost label |
| `button-ghost-hover-bg` | `var(--color-surface-container-low)` | Ghost hover |

### Input

| Token | Value | Usage |
|-------|-------|-------|
| `input-bg` | `color-white` | Background |
| `input-border` | `var(--color-border)` | Border |
| `input-border-focus` | `var(--color-border-focus)` | Focus border |
| `input-text` | `var(--color-text-primary)` | Text |
| `input-placeholder` | `var(--color-text-muted)` | Placeholder |
| `input-prefix-text` | `var(--color-text-muted)` | Prefix/suffix (INV-, $) |

### Card

| Token | Value | Usage |
|-------|-------|-------|
| `card-bg` | `var(--color-surface-card)` | Background |
| `card-border` | `var(--color-border)` | Border |
| `card-radius` | `radius-xl` | Corner radius |
| `card-shadow` | `shadow-lg` | Elevation |

### Table

| Token | Value | Usage |
|-------|-------|-------|
| `table-header-bg` | `#f1f5f9` | Header row bg |
| `table-header-text` | `var(--color-text-muted)` | Header label |
| `table-row-border` | `var(--color-border)` | Row separator |
| `table-row-hover` | `var(--color-surface-bright)` | Row hover |
| `table-cell-text` | `var(--color-text-primary)` | Cell text |

### Sidebar

| Token | Value | Usage |
|-------|-------|-------|
| `sidebar-bg` | `color-white` | Background |
| `sidebar-width` | `280px` | Width |
| `sidebar-border` | `var(--color-border)` | Right border |
| `sidebar-nav-active-border` | `var(--color-brand-text)` | Active indicator |
| `sidebar-nav-active-text` | `var(--color-brand-text)` | Active label |
| `sidebar-nav-hover-bg` | `var(--color-surface-container)` | Nav hover |

### Modal

| Token | Value | Usage |
|-------|-------|-------|
| `modal-backdrop` | `rgba(11, 28, 48, 0.4)` | Overlay |
| `modal-backdrop-blur` | `4px` | Backdrop blur |
| `modal-radius` | `radius-xl` | Corners |
| `modal-shadow` | `shadow-xl` | Elevation |

---

## Mapping: HTML tailwind.config → CSS Custom Properties

| HTML Config Key | CSS Custom Property |
|-----------------|---------------------|
| `primary: #000000` | `--color-brand` |
| `on-tertiary-container: #3980f4` | `--color-brand-text` |
| `surface: #f8f9ff` | `--color-surface` |
| `surface-container: #e5eeff` | `--color-surface-overlay` |
| `outline-variant: #c6c6cd` | `--color-border` |
| `on-surface: #0b1c30` | `--color-text-primary` |
| `on-surface-variant: #45464d` | `--color-text-secondary` |
| `outline: #76777d` | `--color-text-muted` |
| `background: #f8f9ff` | `--color-background` |
| `surface-container-low: #eff4ff` | `--color-surface-sunken` |
| `surface-dim: #cbdbf5` | `--color-surface-dim` |

---

## Naming Convention

```
{category}-{property}-{variant}-{state}

Examples:
  color-text-primary
  color-border-focus
  button-primary-hover
  color-status-paid-bg
  input-border-focus
```

## Usage Rules

1. Components reference only alias (`var(--color-*)`) or component tokens
2. Global tokens appear only in the token definition file
3. New colors go through the global palette first, then get alias tokens
4. Component tokens inherit from alias tokens — never from globals directly
5. Theme switching works by reassigning alias tokens, not globals
