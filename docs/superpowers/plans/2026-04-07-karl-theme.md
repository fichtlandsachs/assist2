# Karl Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a third app theme called "karl" that mirrors the landing page design — orange accent, cream background, hard ink shadows, system-sans body font, white sidebar with ink borders.

**Architecture:** A new `[data-theme="karl"]` CSS block in `globals.css` overrides all CSS custom properties. The theme context gains `"karl"` as a valid `ThemeId`. Sidebar and Topbar each get a third JSX branch. The settings page theme selector gets a new "karl" card.

**Tech Stack:** Next.js 14, Tailwind CSS, CSS custom properties, React context

---

## File Map

| File | Change |
|---|---|
| `frontend/app/globals.css` | Add `[data-theme="karl"]` variable block + component overrides |
| `frontend/lib/theme/context.tsx` | Add `"karl"` to `ThemeId`, update localStorage validation |
| `frontend/components/shell/Sidebar.tsx` | Add `karlSidebar` JSX branch |
| `frontend/components/shell/Topbar.tsx` | Add karl variant in render logic |
| `frontend/app/[org]/settings/page.tsx` | Add "Karl" entry to `THEMES` array |

---

### Task 1: CSS Variables and Component Overrides

**Files:**
- Modify: `frontend/app/globals.css` — after the `[data-theme="paperwork"]` block (line 175)

- [ ] **Step 1: Add the karl theme variable block**

Insert after line 175 in `frontend/app/globals.css` (after the closing `}` of the paperwork block):

```css
/* ── Karl theme (Landing Page design) ── */
[data-theme="karl"] {
  --paper:        #F5F0E8;
  --paper-warm:   #EDE8DF;
  --paper-rule:   rgba(10,10,10,0.08);
  --paper-rule2:  #E5DFD4;
  --margin-red:   rgba(255,92,0,0.15);

  --ink:          #0A0A0A;
  --ink-mid:      #3A3A3A;
  --ink-faint:    #6B6B6B;
  --ink-faintest: #A0A0A0;

  --accent-red:     #FF5C00;
  --accent-red-rgb: 255,92,0;
  --green:          #00D4AA;
  --brown:          #FFD700;
  --navy:           #3B82F6;
  --binding:        #0A0A0A;

  --font-serif: 'Playfair Display', serif;
  --font-body:  -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono:  'JetBrains Mono', monospace;

  --sidebar-width: 256px;
  --topbar-height: 64px;

  --btn-primary:       #FF5C00;
  --btn-primary-hover: #e05200;
  --btn-primary-rgb:   255,92,0;
  --btn-primary-muted: rgba(255,92,0,0.08);

  --karl-bg:       #FFFFFF;
  --karl-border:   #0A0A0A;
  --karl-shadow:   6px 6px 0 #0A0A0A;
  --karl-text:     #0A0A0A;
  --karl-btn-bg:   #0A0A0A;
  --karl-btn-text: #FFFFFF;

  --nav-icon-dashboard: #FF5C00;
  --nav-icon-workspace: #3B82F6;
  --nav-icon-stories:   #FFD700;
  --nav-icon-default:   #6B6B6B;

  --sidebar-text:           rgba(10,10,10,0.5);
  --sidebar-text-active:    #FFFFFF;
  --sidebar-text-active-bg: #FF5C00;
  --sidebar-active-border:  #0A0A0A;
  --sidebar-org-text:       rgba(10,10,10,0.6);
  --sidebar-divider:        rgba(10,10,10,0.10);
  --sidebar-user-text:      rgba(10,10,10,0.6);
  --sidebar-logout-text:    rgba(10,10,10,0.35);
  --sidebar-avatar-bg:      rgba(255,92,0,0.1);
  --sidebar-avatar-text:    #0A0A0A;

  --card:        #FFFFFF;
  --card-border: rgba(10,10,10,0.12);

  --main-content-bg: #F5F0E8;

  --topbar-border: 2px solid #0A0A0A;
}
```

- [ ] **Step 2: Add karl-specific font override on body**

After the existing `[data-theme="paperwork"] body { ... }` block, add:

```css
[data-theme="karl"] body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

[data-theme="karl"] button {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
```

- [ ] **Step 3: Add karl sidebar nav item overrides**

After the existing `[data-theme="paperwork"] .sidebar-nav-item` block, add:

```css
[data-theme="karl"] .sidebar-nav-item {
  border-radius: 12px;
  border: 2px solid transparent;
}
[data-theme="karl"] .sidebar-nav-item:hover:not(.is-active) {
  border-color: rgba(10,10,10,0.12);
  background: rgba(255,92,0,0.04);
}
[data-theme="karl"] .sidebar-nav-item.is-active {
  background: #FF5C00 !important;
  border-color: #0A0A0A !important;
  box-shadow: 4px 4px 0 #0A0A0A !important;
  transform: translateY(-1px);
}
```

- [ ] **Step 4: Add karl neo-card overrides**

After the existing `[data-theme="paperwork"] .neo-card` blocks, add:

```css
[data-theme="karl"] .neo-card {
  background: #FFFFFF;
  border: 2px solid #0A0A0A;
  border-radius: 16px;
  box-shadow: 4px 4px 0 #0A0A0A;
}
[data-theme="karl"] .neo-card:hover {
  border-color: #0A0A0A;
  box-shadow: 6px 6px 0 #0A0A0A;
  transform: translateY(-2px);
}
[data-theme="karl"] .neo-card--flat   { background: var(--paper); border: 2px solid #0A0A0A; border-radius: 16px; }
[data-theme="karl"] .neo-card--orange { background: #FFFFFF; border: 2px solid #0A0A0A; border-radius: 16px; border-left: 4px solid #FF5C00; }
[data-theme="karl"] .neo-card--yellow { background: #FFFFFF; border: 2px solid #0A0A0A; border-radius: 16px; border-left: 4px solid #FFD700; }
[data-theme="karl"] .neo-card--teal   { background: #FFFFFF; border: 2px solid #0A0A0A; border-radius: 16px; border-left: 4px solid #00D4AA; }
```

- [ ] **Step 5: Add karl neo-btn overrides**

After the existing `[data-theme="paperwork"] .neo-btn` blocks, add:

```css
[data-theme="karl"] .neo-btn {
  border: 2px solid #0A0A0A;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  border-radius: 12px;
}
[data-theme="karl"] .neo-btn:hover { transform: translate(2px, 2px); box-shadow: 2px 2px 0 #0A0A0A; }
[data-theme="karl"] .neo-btn--default { background: #0A0A0A; color: #fff; border-color: #0A0A0A; box-shadow: 4px 4px 0 #0A0A0A; }
[data-theme="karl"] .neo-btn--default:hover { background: #2A2A2A; border-color: #2A2A2A; }
[data-theme="karl"] .neo-btn--orange  { background: #FF5C00; color: #fff; border-color: #0A0A0A; box-shadow: 4px 4px 0 #0A0A0A; }
[data-theme="karl"] .neo-btn--orange:hover { background: #e05200; transform: translate(2px, 2px); box-shadow: 2px 2px 0 #0A0A0A; }
```

- [ ] **Step 6: Add karl neo-input overrides**

After the existing `[data-theme="paperwork"] .neo-input` blocks, add:

```css
[data-theme="karl"] .neo-input {
  border: 2px solid #0A0A0A;
  border-radius: 12px;
  box-shadow: 3px 3px 0 #0A0A0A;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
[data-theme="karl"] .neo-input:focus { border-color: #FF5C00; box-shadow: 4px 4px 0 #0A0A0A; }
```

- [ ] **Step 7: Add karl border/radius utility overrides**

After the existing `[data-theme="paperwork"] .rounded-*` overrides, add:

```css
[data-theme="karl"] .rounded-sm { border-radius: 10px; }
[data-theme="karl"] .rounded    { border-radius: 10px; }
[data-theme="karl"] .rounded-md { border-radius: 12px; }
[data-theme="karl"] .rounded-lg { border-radius: 14px; }

[data-theme="karl"] .border   { border-width: 2px; }
[data-theme="karl"] .border-t { border-top-width: 2px; }
[data-theme="karl"] .border-b { border-bottom-width: 2px; }
[data-theme="karl"] .border-l { border-left-width: 2px; }
[data-theme="karl"] .border-r { border-right-width: 2px; }

[data-theme="karl"] .bg-[var(--card)].border,
[data-theme="karl"] .bg-[var(--card)].rounded-sm,
[data-theme="karl"] .bg-[var(--card)].rounded-xl,
[data-theme="karl"] .bg-[var(--card)].rounded-2xl {
  box-shadow: 4px 4px 0 #0A0A0A;
  border-color: #0A0A0A !important;
}
[data-theme="karl"] .bg-[var(--card)].border:hover,
[data-theme="karl"] .bg-[var(--card)].rounded-sm:hover,
[data-theme="karl"] .bg-[var(--card)].rounded-xl:hover,
[data-theme="karl"] .bg-[var(--card)].rounded-2xl:hover {
  box-shadow: 6px 6px 0 #0A0A0A;
  transform: translateY(-2px);
}
```

- [ ] **Step 8: Verify visually**

Open the app in a browser. Set `document.documentElement.dataset.theme = "karl"` in the browser console. Check that the page background turns cream, cards get hard ink shadows, and accent colors become orange.

Expected: Cream `#F5F0E8` background, orange `#FF5C00` focus rings and buttons, hard black `4px 4px 0 #0A0A0A` card shadows.

- [ ] **Step 9: Commit**

```bash
git add frontend/app/globals.css
git commit -m "feat(theme): add karl CSS variable block and component overrides"
```

---

### Task 2: Update Theme Context

**Files:**
- Modify: `frontend/lib/theme/context.tsx`

- [ ] **Step 1: Add "karl" to ThemeId and update validation**

Replace the entire file content with:

```tsx
"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";

export type ThemeId = "agile" | "paperwork" | "karl";

interface ThemeContextValue {
  theme: ThemeId;
  setTheme: (t: ThemeId) => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: "agile",
  setTheme: () => {},
});

const STORAGE_KEY = "theme";
const VALID: ThemeId[] = ["agile", "paperwork", "karl"];

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>("agile");

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as ThemeId | null;
    const initial: ThemeId = stored && VALID.includes(stored) ? stored : "agile";
    setThemeState(initial);
    document.documentElement.dataset.theme = initial;
  }, []);

  const setTheme = useCallback((t: ThemeId) => {
    setThemeState(t);
    document.documentElement.dataset.theme = t;
    localStorage.setItem(STORAGE_KEY, t);
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /opt/assist2/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: No errors related to ThemeId.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/theme/context.tsx
git commit -m "feat(theme): add karl to ThemeId type"
```

---

### Task 3: Karl Sidebar

**Files:**
- Modify: `frontend/components/shell/Sidebar.tsx`

The existing file has two sidebar variants: `paperworkSidebar` (lines 109–243) and `agileSidebar` (lines 246–408). The selector at line 411 is:
```tsx
const sidebarContent = isPaperwork ? paperworkSidebar : agileSidebar;
```

- [ ] **Step 1: Add isKarl constant**

Find line 51 in `Sidebar.tsx`:
```tsx
  const isPaperwork = theme === "paperwork";
```

Add after it:
```tsx
  const isKarl = theme === "karl";
```

- [ ] **Step 2: Add karlSidebar JSX**

Insert the following JSX block right after the closing `);` of `agileSidebar` (after line 408, before the selector line):

```tsx
  const karlSidebar = (
    <aside className="flex flex-col h-full shrink-0"
      style={{ width: "var(--sidebar-width)", background: "#FFFFFF", borderRight: "2px solid #0A0A0A" }}>

      {/* Brand */}
      <div className="relative p-5 pb-4 flex flex-col items-center gap-1.5"
        style={{ borderBottom: "2px solid #0A0A0A" }}>
        <div className="karl-logo w-14 h-14 border-2 rounded-xl overflow-hidden flex items-center justify-center"
          style={{ background: "#FFF5EE", borderColor: "#0A0A0A", boxShadow: "4px 4px 0 #0A0A0A" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/karl-9.png" alt="Karl" className="w-full h-full object-contain" />
        </div>
        <span className="font-['Architects_Daughter'] text-lg tracking-tight leading-none truncate max-w-[160px]"
          style={{ color: "#0A0A0A" }}>
          {user?.display_name ?? "Karl"}
        </span>
        <span className="text-[9px] font-bold tracking-[0.2em] uppercase font-['Architects_Daughter'] truncate max-w-[160px]"
          style={{ color: "#6B6B6B" }}>
          {orgName ?? orgSlug}
        </span>
        <button onClick={onMobileClose} className="md:hidden absolute top-3 right-3 p-1.5 rounded-lg"
          style={{ border: "2px solid rgba(10,10,10,0.2)" }} aria-label="Schließen">
          <X size={14} style={{ color: "#6B6B6B" }} />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 flex flex-col gap-0.5 overflow-y-auto">
        {navItems.slice(0, 1).map(item => {
          const isActive = pathname === item.route || pathname.startsWith(item.route + "/");
          const Icon = item.icon;
          return (
            <Link key={item.id} href={item.route} onClick={onMobileClose}
              className={`sidebar-nav-item flex items-center gap-2.5 px-3 py-2 transition-all${isActive ? " is-active" : ""}`}>
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border-2 transition-all`}
                style={{ borderColor: isActive ? "#0A0A0A" : "transparent", background: isActive ? "#FFF5EE" : "transparent" }}>
                <Icon size={14} strokeWidth={2.5} style={{ color: isActive ? "#FF5C00" : "#6B6B6B" }} />
              </div>
              <span className="text-[13px] font-bold font-['Architects_Daughter'] truncate"
                style={{ color: isActive ? "#FFFFFF" : "#3A3A3A" }}>
                {item.label}
              </span>
            </Link>
          );
        })}

        <button onClick={() => setWorkspaceManualOpen(o => !o)}
          className="sidebar-nav-item flex items-center gap-2.5 px-3 py-2 w-full transition-all">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border-2 transition-all"
            style={{ borderColor: workspaceOpen ? "#0A0A0A" : "transparent", background: workspaceOpen ? "#EFF6FF" : "transparent" }}>
            <MessageSquare size={14} strokeWidth={2.5} style={{ color: workspaceOpen ? "#3B82F6" : "#6B6B6B" }} />
          </div>
          <span className="text-[13px] font-bold font-['Architects_Daughter'] truncate flex-1 text-left"
            style={{ color: workspaceOpen ? "#0A0A0A" : "#3A3A3A" }}>
            Workspace
          </span>
          <ChevronRight size={12} style={{ color: "#A0A0A0", transition: "transform .15s", transform: workspaceOpen ? "rotate(90deg)" : "none" }} />
        </button>
        {workspaceOpen && workspaceSubItems.map(item => {
          const isActive = pathname === item.route || pathname.startsWith(item.route + "/");
          const Icon = item.icon;
          return (
            <Link key={item.id} href={item.route} onClick={onMobileClose}
              className={`sidebar-nav-item flex items-center gap-2 pl-5 pr-3 py-1.5 transition-all${isActive ? " is-active" : ""}`}>
              <div className="w-1 h-1 rounded-full shrink-0" style={{ background: "#A0A0A0" }} />
              <div className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 border-2 transition-all"
                style={{ borderColor: isActive ? "#0A0A0A" : "transparent", background: isActive ? "#FFF5EE" : "transparent" }}>
                <Icon size={12} strokeWidth={2.5} style={{ color: isActive ? "#FF5C00" : "#6B6B6B" }} />
              </div>
              <span className="text-[12px] font-bold font-['Architects_Daughter'] truncate"
                style={{ color: isActive ? "#FFFFFF" : "#3A3A3A" }}>
                {item.label}
              </span>
            </Link>
          );
        })}

        {navItems.slice(1).map(item => {
          const isActive = pathname === item.route || pathname.startsWith(item.route + "/");
          const Icon = item.icon;
          return (
            <Link key={item.id} href={item.route} onClick={onMobileClose}
              className={`sidebar-nav-item flex items-center gap-2.5 px-3 py-2 transition-all${isActive ? " is-active" : ""}`}>
              <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border-2 transition-all"
                style={{ borderColor: isActive ? "#0A0A0A" : "transparent", background: isActive ? "#FFF5EE" : "transparent" }}>
                <Icon size={14} strokeWidth={2.5} style={{ color: isActive ? "#FF5C00" : "#6B6B6B" }} />
              </div>
              <span className="text-[13px] font-bold font-['Architects_Daughter'] truncate"
                style={{ color: isActive ? "#FFFFFF" : "#3A3A3A" }}>
                {item.label}
              </span>
            </Link>
          );
        })}

        <button onClick={() => setSettingsManualOpen(o => !o)}
          className="sidebar-nav-item flex items-center gap-2.5 px-3 py-2 w-full transition-all">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border-2 transition-all"
            style={{ borderColor: settingsOpen ? "#0A0A0A" : "transparent", background: settingsOpen ? "#F5F5F5" : "transparent" }}>
            <Settings size={14} strokeWidth={2.5} style={{ color: settingsOpen ? "#6B6B6B" : "#6B6B6B" }} />
          </div>
          <span className="text-[13px] font-bold font-['Architects_Daughter'] truncate flex-1 text-left"
            style={{ color: settingsOpen ? "#0A0A0A" : "#3A3A3A" }}>
            Einstellungen
          </span>
          <ChevronRight size={12} style={{ color: "#A0A0A0", transition: "transform .15s", transform: settingsOpen ? "rotate(90deg)" : "none" }} />
        </button>
        {settingsOpen && settingsSubItems.map(item => {
          const [itemPath, itemQuery] = item.route.split("?");
          const itemTab = new URLSearchParams(itemQuery ?? "").get("tab") ?? "";
          const isActive = itemTab
            ? pathname === itemPath && currentTab === itemTab
            : pathname === item.route || pathname.startsWith(item.route + "/");
          const Icon = item.icon;
          return (
            <Link key={item.id} href={item.route} onClick={onMobileClose}
              className={`sidebar-nav-item flex items-center gap-2 pl-5 pr-3 py-1.5 transition-all${isActive ? " is-active" : ""}`}>
              <div className="w-1 h-1 rounded-full shrink-0" style={{ background: "#A0A0A0" }} />
              <div className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 border-2 transition-all"
                style={{ borderColor: isActive ? "#0A0A0A" : "transparent", background: isActive ? "#FFF5EE" : "transparent" }}>
                <Icon size={12} strokeWidth={2.5} style={{ color: isActive ? "#FF5C00" : "#6B6B6B" }} />
              </div>
              <span className="text-[12px] font-bold font-['Architects_Daughter'] truncate"
                style={{ color: isActive ? "#FFFFFF" : "#3A3A3A" }}>
                {item.label}
              </span>
            </Link>
          );
        })}

        {navEntries.filter(e => e.slot === "sidebar_main").map(entry => {
          const PluginIcon = PLUGIN_ICONS[entry.icon?.toLowerCase()] ?? Folder;
          const route = `/${orgSlug}${entry.route}`;
          const isActive = pathname === route;
          return (
            <Link key={entry.id} href={route} onClick={onMobileClose}
              className={`sidebar-nav-item flex items-center gap-2.5 px-3 py-2 transition-all${isActive ? " is-active" : ""}`}>
              <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border-2"
                style={{ borderColor: isActive ? "#0A0A0A" : "transparent", background: isActive ? "#FFF5EE" : "transparent" }}>
                <PluginIcon size={14} strokeWidth={2.5} style={{ color: isActive ? "#FF5C00" : "#6B6B6B" }} />
              </div>
              <span className="text-[13px] font-bold font-['Architects_Daughter'] truncate"
                style={{ color: isActive ? "#FFFFFF" : "#3A3A3A" }}>
                {entry.label}
              </span>
            </Link>
          );
        })}

        <SlotRenderer slotId="sidebar_main" orgSlug={orgSlug} orgId={orgId} collapsed={false} />
      </nav>

      <KarlWidget orgSlug={orgSlug} onMobileClose={onMobileClose} />

      {user && (
        <div className="p-3 flex items-center gap-2.5" style={{ borderTop: "2px solid #0A0A0A" }}>
          <SlotRenderer slotId="sidebar_bottom" orgSlug={orgSlug} orgId={orgId} />
          <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: "rgba(255,92,0,0.1)", border: "2px solid #0A0A0A", boxShadow: "2px 2px 0 #0A0A0A" }}>
            <span className="text-[10px] font-bold font-['Architects_Daughter']" style={{ color: "#0A0A0A" }}>
              {user.display_name.slice(0, 2).toUpperCase()}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate text-[11px] font-bold font-['Architects_Daughter']" style={{ color: "#3A3A3A" }}>
              {user.display_name}
            </p>
          </div>
          <button onClick={() => void logout()}
            className="text-[10px] font-bold font-['Architects_Daughter'] transition-colors"
            style={{ color: "#A0A0A0" }}>
            Logout
          </button>
        </div>
      )}
    </aside>
  );
```

- [ ] **Step 3: Update the sidebar selector**

Find and replace line 411:
```tsx
  const sidebarContent = isPaperwork ? paperworkSidebar : agileSidebar;
```

Replace with:
```tsx
  const sidebarContent = isPaperwork ? paperworkSidebar : isKarl ? karlSidebar : agileSidebar;
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd /opt/assist2/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/shell/Sidebar.tsx
git commit -m "feat(theme): add karl sidebar variant"
```

---

### Task 4: Karl Topbar

**Files:**
- Modify: `frontend/components/shell/Topbar.tsx`

- [ ] **Step 1: Add isKarl constant**

Find line 45 in `Topbar.tsx`:
```tsx
  const isPaperwork = theme === "paperwork";
```

Add after it:
```tsx
  const isKarl = theme === "karl";
```

- [ ] **Step 2: Add karl render branch**

Find the existing:
```tsx
  if (isPaperwork) {
```

Add a new branch BEFORE it:

```tsx
  if (isKarl) {
    return (
      <header className="flex items-center justify-between px-5 lg:px-8 shrink-0"
        style={{ height: "var(--topbar-height)", background: "#F5F0E8", borderBottom: "2px solid #0A0A0A" }}>
        <div className="flex items-center gap-3">
          <button onClick={onMenuClick}
            className="lg:hidden p-2 rounded-xl transition-colors"
            style={{ border: "2px solid rgba(10,10,10,0.2)" }}
            aria-label="Menü öffnen">
            <Menu size={18} style={{ color: "#3A3A3A" }} />
          </button>
          <span className="font-['Architects_Daughter'] font-bold tracking-widest text-[10px] uppercase"
            style={{ color: "#A0A0A0" }}>
            Karl
          </span>
          <span style={{ color: "#A0A0A0", fontSize: "10px" }}>/</span>
          <span className="font-['Architects_Daughter'] text-[10px] font-bold tracking-widest uppercase"
            style={{ color: "#FF5C00" }}>
            {pageTitle}
          </span>
        </div>
        <div className="flex items-center gap-4">
          <SlotRenderer slotId="topbar_right" orgSlug={orgSlug} orgId={orgId} />
          {clock && (
            <span className="hidden sm:block font-['JetBrains_Mono'] text-[10px] font-bold"
              style={{ color: "#0A0A0A" }}>
              {clock}
            </span>
          )}
          {user && (
            <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
              style={{ background: "#FFFFFF", border: "2px solid #0A0A0A", boxShadow: "2px 2px 0 #0A0A0A" }}
              title={user.display_name}>
              <span className="text-[11px] font-bold font-['Architects_Daughter']" style={{ color: "#0A0A0A" }}>
                {user.display_name.slice(0, 2).toUpperCase()}
              </span>
            </div>
          )}
        </div>
      </header>
    );
  }
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /opt/assist2/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/shell/Topbar.tsx
git commit -m "feat(theme): add karl topbar variant"
```

---

### Task 5: Karl Entry in Theme Selector

**Files:**
- Modify: `frontend/app/[org]/settings/page.tsx` — `THEMES` array at line 992

- [ ] **Step 1: Add Karl to THEMES array**

Find the `THEMES` array (line 992). It currently has `"paperwork"` and `"agile"` entries. Add a third entry:

```tsx
const THEMES: { id: ThemeId; name: string; desc: string; preview: { bg: string; sidebar: string; text: string; accent: string; font: string } }[] = [
  {
    id: "paperwork",
    name: "Paperwork",
    desc: "Analoges Papier-Ästhetik mit Serifenschrift und Karo-Hintergrund",
    preview: { bg: "var(--paper)", sidebar: "var(--binding)", text: "var(--ink)", accent: "var(--accent-red)", font: "Georgia, serif" },
  },
  {
    id: "agile",
    name: "Agile",
    desc: "Cleanes, modernes Interface mit kräftigen Kontrasten",
    preview: { bg: "#FDFBF7", sidebar: "#231F1F", text: "#231F1F", accent: "#534D5F", font: "Inter, sans-serif" },
  },
  {
    id: "karl",
    name: "Karl",
    desc: "Landing-Page-Design: Orange, Cream und harte Schatten",
    preview: { bg: "#F5F0E8", sidebar: "#FFFFFF", text: "#0A0A0A", accent: "#FF5C00", font: "-apple-system, sans-serif" },
  },
];
```

Note: The sidebar preview for `"karl"` is `"#FFFFFF"` (white). The mini-preview fake sidebar uses `rgba(255,255,255,.25)` for nav lines — on a white sidebar that will be invisible. Update the `ThemeSelector` component to handle this: add an outline to the fake sidebar when `t.preview.sidebar` is white.

Find in `ThemeSelector` (around line 1032):
```tsx
                <div style={{ width: "28px", background: t.preview.sidebar, flexShrink: 0, display: "flex", flexDirection: "column", gap: "4px", padding: "6px 4px" }}>
                  {[1, 2, 3].map(i => (
                    <div key={i} style={{ height: "3px", borderRadius: "1px", background: "rgba(255,255,255,.25)" }} />
                  ))}
                </div>
```

Replace with:
```tsx
                <div style={{ width: "28px", background: t.preview.sidebar, flexShrink: 0, display: "flex", flexDirection: "column", gap: "4px", padding: "6px 4px", borderRight: t.preview.sidebar === "#FFFFFF" ? "2px solid #0A0A0A" : "none" }}>
                  {[1, 2, 3].map(i => (
                    <div key={i} style={{ height: "3px", borderRadius: "1px", background: t.preview.sidebar === "#FFFFFF" ? "rgba(10,10,10,.2)" : "rgba(255,255,255,.25)" }} />
                  ))}
                </div>
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /opt/assist2/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\[org\]/settings/page.tsx
git commit -m "feat(theme): add Karl entry to theme selector"
```

---

### Task 6: Build and Deploy

**Files:** None (build step only)

- [ ] **Step 1: Build the frontend container**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build frontend 2>&1 | tail -15
```

Expected: `assist2-frontend Started`

- [ ] **Step 2: Check container logs**

```bash
docker logs assist2-frontend --tail 10
```

Expected: `✓ Ready in ...ms`

- [ ] **Step 3: Verify the theme works end-to-end**

1. Navigate to the app in a browser
2. Go to Einstellungen → Benutzer (user tab has the theme selector)
3. Click the "Karl" theme card
4. Verify: cream background, white sidebar with ink border, orange active nav items, hard black card shadows

- [ ] **Step 4: Push to GitHub**

```bash
cd /opt/assist2 && git push origin main
```
