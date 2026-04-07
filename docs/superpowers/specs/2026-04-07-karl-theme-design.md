# Karl Theme Design Spec

## Goal

Add a third theme `"karl"` to the assist2 app that replicates the Landing Page (Ghost/karl-theme) design 1:1 — same color palette, typography, hard shadows, and navigation style.

## Architecture

A new `[data-theme="karl"]` CSS block is added to `globals.css`, overriding all CSS custom properties. The existing theme context (`lib/theme/context.tsx`) gains `"karl"` as a valid option. No structural changes to components — they consume CSS variables automatically.

**Files to change:**
- `frontend/app/globals.css` — new `[data-theme="karl"]` block
- `frontend/lib/theme/context.tsx` — add `"karl"` to `Theme` type and toggle cycle
- `frontend/components/shell/Sidebar.tsx` — karl-specific sidebar color overrides (dark sidebar → white)
- `frontend/components/shell/Topbar.tsx` — border style for karl

---

## 1. Color Palette

| CSS Variable | Karl Value | Purpose |
|---|---|---|
| `--paper` | `#F5F0E8` | Page background (Cream) |
| `--paper-warm` | `#EDE8DF` | Warm surface (inputs, hover) |
| `--paper-rule` | `rgba(10,10,10,0.08)` | Dividers |
| `--paper-rule2` | `#E5DFD4` | Secondary dividers |
| `--card` | `#FFFFFF` | Card background |
| `--ink` | `#0A0A0A` | Primary text, borders, shadows |
| `--ink-mid` | `#3A3A3A` | Secondary text |
| `--ink-faint` | `#6B6B6B` | Muted text |
| `--ink-faintest` | `#A0A0A0` | Placeholder text |
| `--accent-red` | `#FF5C00` | Orange — primary accent, CTA |
| `--accent-red-rgb` | `255,92,0` | RGB for rgba() usage |
| `--green` | `#00D4AA` | Teal — success, status |
| `--brown` | `#FFD700` | Gold — warnings, highlights |
| `--navy` | `#3B82F6` | Blue — info, links |
| `--binding` | `#0A0A0A` | Structural borders |
| `--margin-red` | `rgba(255,92,0,0.15)` | Orange tint for accents |

---

## 2. Typography

| Role | Font | Notes |
|---|---|---|
| Body / UI text | `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` | Matches Landing Page main font |
| Headings | `'Playfair Display', serif` | Retained from agile |
| Decorative (badges, tags, logo) | `'Architects Daughter', cursive` | Retained for brand accents |
| Monospace | `'JetBrains Mono', monospace` | Code blocks |

Applied via CSS variable overrides:
```css
[data-theme="karl"] {
  --font-body: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}
```

Body element gets `font-family: var(--font-body)` under the karl selector.

---

## 3. Shadows & Borders

Hard, offset shadows — no blur radius — matching the Landing Page exactly.

| Element | Shadow |
|---|---|
| Cards (default) | `4px 4px 0 #0A0A0A` |
| Cards (hover) | `6px 6px 0 #0A0A0A` + `translateY(-2px)` |
| Buttons (default) | `4px 4px 0 #0A0A0A` |
| Buttons (hover) | `translate(2px, 2px)` + `2px 2px 0 #0A0A0A` |
| Inputs (default) | `3px 3px 0 #0A0A0A` |
| Inputs (focus) | `4px 4px 0 #0A0A0A` + orange border |
| Nav items (active) | `4px 4px 0 #0A0A0A` |

Border: `2px solid #0A0A0A` on all interactive elements.
Border radius: `16px` cards, `12px` buttons/inputs, `8px` badges.

---

## 4. Sidebar & Navigation

The sidebar flips from dark to light — matching the Landing Page white nav bar.

| Element | Karl Value |
|---|---|
| `--sidebar-bg` | `#FFFFFF` |
| `--sidebar-border` | `#0A0A0A` (2px right border) |
| `--sidebar-text` | `#0A0A0A` |
| `--sidebar-text-active` | `#FF5C00` |
| `--sidebar-item-active-bg` | `#FF5C00` |
| `--sidebar-item-active-text` | `#FFFFFF` |
| `--sidebar-item-hover-bg` | `rgba(255,92,0,0.08)` |
| `--sidebar-divider` | `rgba(10,10,10,0.10)` |

Topbar: `background: #F5F0E8`, `border-bottom: 2px solid #0A0A0A`.

Logo accent ("2"): `color: #FF5C00` (already conditional on theme in Sidebar.tsx).

---

## 5. Theme Switcher

`lib/theme/context.tsx`:
- `Theme` type: `"agile" | "paperwork" | "karl"`
- Toggle cycle: `agile → paperwork → karl → agile`
- Display label: `"Karl"` with a flame or spark icon

The theme switcher button in the Topbar cycles through all three.

---

## 6. Karl-Widget Overrides

```css
[data-theme="karl"] {
  --karl-bg: #FFFFFF;
  --karl-border: #0A0A0A;
  --karl-shadow: 6px 6px 0 #0A0A0A;
  --karl-text: #0A0A0A;
  --karl-btn-bg: #0A0A0A;
  --karl-btn-text: #FFFFFF;
}
```

---

## Out of Scope

- No changes to component structure
- No new Tailwind tokens
- No changes to agile or paperwork themes
- No landing page changes
