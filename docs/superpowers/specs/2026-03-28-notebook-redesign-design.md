# Notebook Redesign — Design Spec

**Date:** 2026-03-28
**Scope:** Complete visual redesign of the assist2 frontend to a paper/notebook aesthetic, plus a new AI Workspace page with backend-integrated chat.

---

## 1. Goals

- Replace the neobrutalist design system (orange, hard shadows, bold borders) with a warm paper/notebook aesthetic across all pages
- Redesign the shell (Sidebar, Topbar) to match the notebook style
- Add a new AI Workspace page (`/[org]/ai-workspace`) with streaming chat and auto-generated User Story panel
- All AI calls route through the backend — no Anthropic API key in the frontend

---

## 2. Design System

### CSS Custom Properties (`globals.css`)

```css
--paper:        #faf9f6   /* page background */
--paper-warm:   #f7f4ee   /* header, sidebar content areas */
--paper-rule:   #e2ddd4   /* horizontal ruled lines, dividers */
--paper-rule2:  #ece8e0   /* hover states, subtle backgrounds */
--margin-red:   #e8b4b0   /* vertical margin line */
--ink:          #1c1810   /* primary text, borders */
--ink-mid:      #5a5040   /* secondary text */
--ink-faint:    #a09080   /* hints, placeholders, disabled */
--ink-faintest: #cec8bc   /* decorative lines, timestamps */
--accent-red:   #c0392b   /* active states, errors, streaming cursor */
--green:        #2d6a4f   /* story section accent */
--brown:        #8b4513   /* docs section accent */
--navy:         #1e3a5f   /* tasks section accent */
--binding:      #2a2018   /* sidebar background */
--line-h:       28px      /* ruled line height */
--margin-w:     52px      /* left margin width */
```

### Typography

| Role | Font | Weight | Style |
|---|---|---|---|
| Headings / titles | Lora | 400, 500 | italic |
| Body / messages | Crimson Pro | 300, 400 | regular + italic |
| Labels / mono / code | JetBrains Mono | 300, 400, 500 | regular |

Loaded via Google Fonts in root `layout.tsx`.

### Background

- `body`: linen-grid desk texture (two repeating-linear-gradients at 40px, `#c8c2b8` base)
- `main` content area: `--paper` with horizontally repeating ruled lines (`--paper-rule` every `--line-h`)

### Tailwind Config

Existing color tokens (primary, secondary, neo-*) are replaced with the paper palette. Existing `boxShadow.neo-*` keys are removed. No hard offset shadows — depth via `--paper-rule` borders only.

---

## 3. Shell

### Sidebar

- **Width:** 200px
- **Background:** `--binding` (`#2a2018`)
- **Right border:** 1.5px linear-gradient stripe (`#5a4a30 → #2a2018 → #5a4a30`)
- **Org name:** Lora italic, 13px, `rgba(255,255,255,.7)`
- **Nav items:** JetBrains Mono, 9px, uppercase, letter-spacing `.1em`, `rgba(255,255,255,.45)`
- **Active item:** Left 2px `--paper` bar + item text in `rgba(255,255,255,.95)`
- **Icons:** Lucide, 13px, same opacity as text
- **Hover:** `rgba(255,255,255,.06)` background
- **No** box-shadows, no hard borders — binding aesthetic only

### Topbar

- **Height:** 48px
- **Background:** `--paper-warm`
- **Border-bottom:** 1.5px `--ink`
- **Left:** page title in Lora italic 17px + org slug in JetBrains Mono 8px `--ink-faint`
- **Right:** live clock (JetBrains Mono 8px `--ink-faintest`) + user avatar (20px circle, initials, `--paper-rule2` bg)

---

## 4. Existing Pages — Styling Updates

All existing pages inherit the new design system automatically via token replacement. Additionally:

### Components

| Component | Change |
|---|---|
| `Button` | `0.5px --ink` border, `--paper-rule2` hover, no hard shadow, JetBrains Mono font |
| `Card` | `--paper` background, `0.5px --paper-rule` border, `--ink` 1px border on hover |
| `Badge` | Pill shape, JetBrains Mono 8px, color from section accent tokens |
| `AISuggestPanel` | Typography update only — logic/API calls unchanged |

**Not changed:** page logic, routing, backend integration, state management.

---

## 5. AI Workspace Page

### Route

`/[org]/ai-workspace` — inside the standard org shell (Sidebar + Topbar).

### Layout

Two-column split within the main content area:

```
[ Left Panel — flex:1        ] [ Right Panel — 320px ]
  Chat with 3 tab modes          User Story Document
```

Both panels have ruled lines and margin decoration matching the notebook aesthetic.

### Left Panel — Chat

**Tabs:** Konversation (`--green`) / Dokumente (`--brown`) / Aufgaben (`--navy`)

Each tab has:
- System prompt tailored to mode
- Suggestion chips when empty
- Streaming message display with cursor animation
- User messages: Lora italic, right-aligned
- AI messages: Crimson Pro, left-aligned with `KI` avatar

### Right Panel — Story Document

Four collapsible sections:

| ID | Label | Accent |
|---|---|---|
| `story` | User Story | `#2d6a4f` |
| `accept` | Akzeptanzkriterien | `#1e3a5f` |
| `tests` | Testfälle | `#6b3a2a` |
| `release` | Release Notes | `#5a3a7a` |

Each section: inline-editable textarea items, add/delete, collapse/expand.

Additional button: **"Als Story speichern"** — POSTs to `POST /api/v1/user-stories/` using the `story` and `accept` sections.

### Backend Integration

| Function | Endpoint | Method | Notes |
|---|---|---|---|
| Chat stream | `/api/v1/ai/chat` | POST + SSE | New endpoint; takes `{messages, mode, org_id}`, streams text/event-stream |
| Story extraction | `/api/v1/ai/extract-story` | POST | New endpoint; takes conversation transcript, returns structured JSON |
| Save story | `/api/v1/user-stories/` | POST | Existing endpoint |

**No Anthropic API key in frontend.** All AI calls go through the backend which holds the key in `.env`.

### Chat Endpoint Contract

Request:
```json
{
  "messages": [{ "role": "user" | "assistant", "content": "..." }],
  "mode": "chat" | "docs" | "tasks",
  "org_id": "uuid"
}
```

Response: `text/event-stream`, each event `data: <text chunk>\n\n`, terminated by `data: [DONE]\n\n`.

### Extract-Story Endpoint Contract

Request:
```json
{ "transcript": "Nutzer: ...\nKI: ...", "org_id": "uuid" }
```

Response:
```json
{
  "story": ["Als ... möchte ich ... damit ..."],
  "accept": ["Gegeben ... wenn ... dann ..."],
  "tests": ["TC-01: ..."],
  "release": ["v1.0: ..."]
}
```

---

## 6. Implementation Sequence

1. **Design tokens** — Replace `globals.css` and `tailwind.config.ts`
2. **Fonts** — Add Google Fonts import to `app/layout.tsx`
3. **Sidebar** — Rewrite `components/shell/Sidebar.tsx`
4. **Topbar** — Rewrite `components/shell/Topbar.tsx`
5. **UI components** — Update `Button`, `Card`, `Badge`
6. **Backend: `/api/v1/ai/chat`** — New SSE streaming endpoint
7. **Backend: `/api/v1/ai/extract-story`** — New JSON extraction endpoint
8. **Frontend: AI Workspace page** — `/app/[org]/ai-workspace/page.tsx`
9. **Sidebar nav entry** — Add "AI Workspace" link to sidebar

---

## 7. Out of Scope

- Individual page content redesign beyond token inheritance
- Mobile/responsive layout changes
- Authentication or permission changes
- n8n workflow changes
- Existing story CRUD logic
