"use client";

import { useState, useCallback } from "react";
import { use } from "react";
import Link from "next/link";
import {
  Shield, ChevronDown, ChevronRight, Lock, Zap,
  AlertTriangle, Search, SlidersHorizontal, Plus,
  RefreshCw, FileText, Layers, GitMerge, Tag, BookOpen,
  Filter,
} from "lucide-react";
import {
  useStandards, useGroupedControls, seedStandards,
  type StandardGroup, type CategoryGroup, type GateGroup,
  type FamilyGroup, type GroupedControl, type ControlCounts,
} from "@/lib/hooks/useControlStandards";
import { useOrg } from "@/lib/hooks/useOrg";

interface Props { params: Promise<{ org: string }> }

// ── Color maps ────────────────────────────────────────────────────────────────

const STD_COLOR: Record<string, string> = {
  blue:    "bg-blue-100 text-blue-700 border-blue-200",
  violet:  "bg-violet-100 text-violet-700 border-violet-200",
  red:     "bg-red-100 text-red-700 border-red-200",
  slate:   "bg-slate-100 text-slate-600 border-slate-200",
  amber:   "bg-amber-100 text-amber-700 border-amber-200",
  emerald: "bg-emerald-100 text-emerald-700 border-emerald-200",
  default: "bg-slate-100 text-slate-600 border-slate-200",
};

const STATUS_COLOR: Record<string, string> = {
  approved: "bg-green-100 text-green-700",
  draft:    "bg-amber-100 text-amber-700",
  in_review:"bg-blue-100 text-blue-700",
  archived: "bg-slate-100 text-slate-500",
};
const STATUS_LABEL: Record<string, string> = {
  approved: "Aktiv", draft: "Entwurf", in_review: "Review", archived: "Archiviert",
};
const KIND_COLOR: Record<string, string> = {
  fixed:   "bg-slate-100 text-slate-600",
  dynamic: "bg-violet-50 text-violet-600",
};
const KIND_LABEL: Record<string, string> = { fixed: "Fest", dynamic: "Dynamisch" };

// ── Sub-components ────────────────────────────────────────────────────────────

function StandardBadge({ name, color, sectionRef }: {
  name: string; color: string | null; sectionRef?: string | null;
}) {
  const cls = STD_COLOR[color || "default"] ?? STD_COLOR.default;
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border ${cls}`}>
      {name}{sectionRef ? ` · ${sectionRef}` : ""}
    </span>
  );
}

function CounterRow({ counts, compact = false }: { counts: ControlCounts; compact?: boolean }) {
  if (compact) {
    return (
      <span className="flex items-center gap-2 text-xs text-[var(--ink-muted)]">
        <span>{counts.total} Controls</span>
        {counts.active > 0 && <span className="text-green-600">{counts.active} aktiv</span>}
        {counts.hard_stops > 0 && <span className="text-red-600 flex items-center gap-0.5"><AlertTriangle className="h-3 w-3" />{counts.hard_stops}</span>}
        {counts.drafts > 0 && <span className="text-amber-600">{counts.drafts} Entw.</span>}
        {counts.no_evidence > 0 && <span className="text-slate-400">{counts.no_evidence} ohne Nachw.</span>}
      </span>
    );
  }
  return (
    <div className="flex items-center gap-3 text-xs flex-wrap">
      <span className="text-[var(--ink-muted)]">{counts.total} Controls</span>
      <span className="text-green-600 font-medium">{counts.active} aktiv</span>
      {counts.hard_stops > 0 && (
        <span className="flex items-center gap-0.5 text-red-600 font-medium">
          <AlertTriangle className="h-3 w-3" /> {counts.hard_stops} Hard-Stop
        </span>
      )}
      {counts.drafts > 0 && <span className="text-amber-600">{counts.drafts} Entwurf</span>}
      {counts.no_evidence > 0 && <span className="text-slate-500">{counts.no_evidence} ohne Nachweise</span>}
    </div>
  );
}

function ControlRow({ control, orgSlug }: { control: GroupedControl; orgSlug: string }) {
  return (
    <Link
      href={`/${orgSlug}/admin/governance/controls/${control.id}`}
      className={`flex items-center gap-3 px-4 py-2.5 border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-hover)] transition-colors group ${control.hard_stop ? "bg-red-50/30" : ""}`}
    >
      {/* Kind */}
      <span className={`w-14 shrink-0 text-center px-1.5 py-0.5 rounded text-[10px] font-medium ${KIND_COLOR[control.kind]}`}>
        {KIND_LABEL[control.kind]}
      </span>

      {/* Name + description */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-[var(--ink-strong)] truncate">{control.name}</span>
          {control.hard_stop && (
            <span className="flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-100 text-red-700 shrink-0">
              <AlertTriangle className="h-3 w-3" /> Stop
            </span>
          )}
        </div>
        {control.short_description && (
          <p className="text-xs text-[var(--ink-muted)] truncate mt-0.5">{control.short_description}</p>
        )}
        {/* Standard badges */}
        {control.standards.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {control.standards.map((s, i) => (
              <StandardBadge key={i} name={s.standard_name} color={s.color} sectionRef={s.section_ref} />
            ))}
          </div>
        )}
      </div>

      {/* Gates */}
      <div className="hidden lg:flex gap-1 shrink-0">
        {control.gate_phases.map(g => (
          <span key={g} className="px-1.5 py-0.5 rounded text-[10px] bg-violet-50 text-violet-600 font-medium">{g}</span>
        ))}
      </div>

      {/* Status */}
      <span className={`hidden xl:inline-flex px-2 py-0.5 rounded text-[10px] font-medium shrink-0 ${STATUS_COLOR[control.status] ?? ""}`}>
        {STATUS_LABEL[control.status] ?? control.status}
      </span>

      {/* Version */}
      <span className="hidden xl:inline text-xs text-[var(--ink-muted)] shrink-0">v{control.version}</span>

      <ChevronRight className="h-4 w-4 text-[var(--ink-muted)] shrink-0 opacity-0 group-hover:opacity-100" />
    </Link>
  );
}

function FamilySection({ family, orgSlug, defaultOpen }: {
  family: FamilyGroup; orgSlug: string; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen ?? (family.counts.hard_stops > 0 || family.counts.total <= 4));
  return (
    <div className="border-l-2 border-[var(--border-subtle)] ml-4 pl-0">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-[var(--bg-hover)] transition-colors"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5 text-[var(--ink-muted)]" /> : <ChevronRight className="h-3.5 w-3.5 text-[var(--ink-muted)]" />}
        <span className="text-xs font-semibold text-[var(--ink-mid)] flex-1">{family.family}</span>
        <CounterRow counts={family.counts} compact />
      </button>
      {open && (
        <div className="ml-2">
          {family.controls.map(c => (
            <ControlRow key={c.id} control={c} orgSlug={orgSlug} />
          ))}
        </div>
      )}
    </div>
  );
}

function CategorySection({ category, orgSlug, defaultOpen }: {
  category: CategoryGroup; orgSlug: string; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  return (
    <div className="border-b border-[var(--border-subtle)] last:border-0">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-3 w-full px-4 py-3 text-left hover:bg-[var(--bg-hover)] transition-colors"
      >
        {open ? <ChevronDown className="h-4 w-4 text-[var(--ink-muted)]" /> : <ChevronRight className="h-4 w-4 text-[var(--ink-muted)]" />}
        <Layers className="h-4 w-4 text-violet-400 shrink-0" />
        <span className="text-sm font-semibold text-[var(--ink-strong)] flex-1">{category.category}</span>
        <CounterRow counts={category.counts} compact />
      </button>
      {open && (
        <div className="bg-[var(--bg-base)]/50 pb-2">
          {category.families.map(fam => (
            <FamilySection key={fam.family} family={fam} orgSlug={orgSlug} />
          ))}
        </div>
      )}
    </div>
  );
}

function StandardSection({ standard, orgSlug, defaultOpen, onFilterByStandard }: {
  standard: StandardGroup; orgSlug: string; defaultOpen?: boolean;
  onFilterByStandard: (id: string) => void;
}) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  const dotColor: Record<string, string> = {
    blue: "bg-blue-500", violet: "bg-violet-500", red: "bg-red-500",
    slate: "bg-slate-400", amber: "bg-amber-500", emerald: "bg-emerald-500",
  };
  const dot = dotColor[standard.standard_color] ?? "bg-slate-400";

  return (
    <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] overflow-hidden">
      {/* Standard header */}
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-3 w-full px-5 py-4 text-left hover:bg-[var(--bg-hover)] transition-colors"
      >
        {open ? <ChevronDown className="h-5 w-5 text-[var(--ink-muted)]" /> : <ChevronRight className="h-5 w-5 text-[var(--ink-muted)]" />}
        <span className={`w-3 h-3 rounded-full shrink-0 ${dot}`} />
        <div className="flex-1 min-w-0">
          <span className="text-sm font-bold text-[var(--ink-strong)]">{standard.standard_name}</span>
          <span className="ml-2 text-xs text-[var(--ink-muted)] capitalize">{standard.standard_type.replace("_", " ")}</span>
        </div>
        <CounterRow counts={standard.counts} />
        <button
          onClick={e => { e.stopPropagation(); onFilterByStandard(standard.standard_id); }}
          className="ml-3 px-2 py-1 text-xs text-violet-600 hover:bg-violet-50 rounded shrink-0"
        >
          Nur dieser
        </button>
      </button>

      {/* Categories inside standard */}
      {open && (
        <div className="border-t border-[var(--border-subtle)]">
          {standard.categories.map(cat => (
            <CategorySection key={cat.category} category={cat} orgSlug={orgSlug} defaultOpen={standard.counts.total <= 10} />
          ))}
        </div>
      )}
    </div>
  );
}

function GateSection({ group, orgSlug }: { group: GateGroup; orgSlug: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] overflow-hidden">
      <button onClick={() => setOpen(o => !o)}
        className="flex items-center gap-3 w-full px-5 py-4 text-left hover:bg-[var(--bg-hover)]">
        {open ? <ChevronDown className="h-5 w-5 text-[var(--ink-muted)]" /> : <ChevronRight className="h-5 w-5 text-[var(--ink-muted)]" />}
        <GitMerge className="h-4 w-4 text-violet-500 shrink-0" />
        <span className="text-sm font-bold text-[var(--ink-strong)] flex-1">{group.gate}</span>
        <CounterRow counts={group.counts} />
      </button>
      {open && (
        <div className="border-t border-[var(--border-subtle)]">
          {group.controls.map(c => <ControlRow key={c.id} control={c} orgSlug={orgSlug} />)}
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ControlsOverviewPage({ params }: Props) {
  const { org: orgSlug } = use(params);
  const { org } = useOrg(orgSlug);

  const [view, setView] = useState<"standard" | "category" | "gate">("standard");
  const [filterStandardId, setFilterStandardId] = useState<string | undefined>();
  const [filterKind, setFilterKind] = useState("");
  const [filterHardStop, setFilterHardStop] = useState(false);
  const [filterActive, setFilterActive] = useState(false);
  const [filterDraft, setFilterDraft] = useState(false);
  const [filterNoEvidence, setFilterNoEvidence] = useState(false);
  const [filterMultiStd, setFilterMultiStd] = useState(false);
  const [search, setSearch] = useState("");
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);

  const { data: standards } = useStandards();
  const { data: grouped, isLoading, mutate } = useGroupedControls({
    view,
    standard_id: filterStandardId,
    kind: filterKind || undefined,
    hard_stop_only: filterHardStop || undefined,
    active_only: filterActive || undefined,
    draft_only: filterDraft || undefined,
    no_evidence_only: filterNoEvidence || undefined,
    multi_standard_only: filterMultiStd || undefined,
    search: search || undefined,
  });

  const hasFilters = filterStandardId || filterKind || filterHardStop || filterActive || filterDraft || filterNoEvidence || filterMultiStd || search;

  const clearFilters = () => {
    setFilterStandardId(undefined); setFilterKind(""); setFilterHardStop(false);
    setFilterActive(false); setFilterDraft(false); setFilterNoEvidence(false);
    setFilterMultiStd(false); setSearch("");
  };

  const handleSeed = async () => {
    setSeeding(true);
    try {
      const r = await seedStandards();
      setSeedMsg(`${r.standards_created} Standards, ${r.mappings_created} Mappings erstellt`);
      mutate();
    } catch {
      setSeedMsg("Fehler beim Seeden");
    } finally {
      setSeeding(false);
    }
  };

  const groups = grouped?.groups ?? [];

  // Total counts across all groups
  const totalControls = groups.reduce((s, g) => s + ((g as StandardGroup).counts?.total ?? 0), 0);

  return (
    <div className="space-y-5 p-6 pb-16">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-[var(--ink-strong)] flex items-center gap-2">
            <Shield className="h-5 w-5 text-violet-500" />
            Controls
          </h1>
          <p className="text-sm text-[var(--ink-muted)] mt-0.5">
            {groups.length > 0
              ? `${groups.length} Gruppen · mehrstufige Sicht`
              : "Noch keine Controls oder Standards vorhanden"}
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button onClick={handleSeed} disabled={seeding}
            className="flex items-center gap-2 px-3 py-1.5 text-xs bg-slate-100 hover:bg-slate-200 rounded-lg text-[var(--ink-mid)] disabled:opacity-60">
            <RefreshCw className={`h-3.5 w-3.5 ${seeding ? "animate-spin" : ""}`} />
            Standards & Mappings seeden
          </button>
          <Link href={`/${orgSlug}/admin/governance/controls/new`}
            className="flex items-center gap-2 px-3 py-1.5 text-xs bg-violet-600 text-white rounded-lg hover:bg-violet-700">
            <Plus className="h-3.5 w-3.5" /> Neues Control
          </Link>
        </div>
      </div>

      {seedMsg && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-green-50 border border-green-200 text-xs text-green-800">
          ✓ {seedMsg}
          <button onClick={() => setSeedMsg(null)} className="ml-auto">×</button>
        </div>
      )}

      {/* View switcher */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex gap-0 rounded-lg border border-[var(--border-subtle)] overflow-hidden text-sm">
          {[
            { key: "standard" as const, label: "Standard", icon: BookOpen },
            { key: "category" as const, label: "Kategorie", icon: Layers },
            { key: "gate" as const, label: "Gate", icon: GitMerge },
          ].map(({ key, label, icon: Icon }) => (
            <button key={key} onClick={() => setView(key)}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs transition-colors ${
                view === key
                  ? "bg-violet-600 text-white"
                  : "bg-[var(--bg-card)] text-[var(--ink-muted)] hover:bg-[var(--bg-hover)]"
              }`}>
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>

        {/* Standard quick-filter chips */}
        {view === "standard" && standards && (
          <div className="flex flex-wrap gap-1.5">
            {filterStandardId && (
              <button onClick={() => setFilterStandardId(undefined)}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-violet-100 text-violet-700 rounded-lg">
                × Alle Standards
              </button>
            )}
            {!filterStandardId && standards.map(s => (
              <button key={s.id} onClick={() => setFilterStandardId(s.id)}
                className={`px-2 py-1 text-xs rounded-lg border ${STD_COLOR[s.color || "default"] ?? STD_COLOR.default} hover:opacity-80`}>
                {s.short_name}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--ink-muted)]" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Suchen…"
            className="pl-8 pr-3 py-1.5 text-sm bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg focus:outline-none focus:border-violet-400 w-48" />
        </div>

        <button onClick={() => setShowFilters(f => !f)}
          className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border transition-colors ${showFilters ? "bg-violet-50 border-violet-300 text-violet-700" : "bg-[var(--bg-card)] border-[var(--border-subtle)] text-[var(--ink-muted)]"}`}>
          <SlidersHorizontal className="h-3.5 w-3.5" />
          Filter{hasFilters ? " (aktiv)" : ""}
        </button>

        {showFilters && (
          <>
            <select value={filterKind} onChange={e => setFilterKind(e.target.value)}
              className="px-2.5 py-1.5 text-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg focus:outline-none">
              <option value="">Alle Typen</option>
              <option value="fixed">Fest</option>
              <option value="dynamic">Dynamisch</option>
            </select>
            {[
              { label: "Hard-Stop", value: filterHardStop, set: setFilterHardStop },
              { label: "Aktiv",     value: filterActive,   set: setFilterActive   },
              { label: "Entwurf",   value: filterDraft,    set: setFilterDraft    },
              { label: "Kein Nachweis", value: filterNoEvidence, set: setFilterNoEvidence },
              { label: "Multi-Standard", value: filterMultiStd, set: setFilterMultiStd },
            ].map(({ label, value, set }) => (
              <button key={label} onClick={() => set(v => !v)}
                className={`px-2.5 py-1.5 text-xs rounded-lg border transition-colors ${value ? "bg-violet-600 text-white border-violet-600" : "bg-[var(--bg-card)] border-[var(--border-subtle)] text-[var(--ink-muted)] hover:border-violet-400"}`}>
                {label}
              </button>
            ))}
            {hasFilters && (
              <button onClick={clearFilters}
                className="text-xs text-[var(--ink-muted)] hover:text-[var(--ink-mid)] px-2">
                × Zurücksetzen
              </button>
            )}
          </>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex items-center justify-center h-48">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-violet-500" />
        </div>
      ) : groups.length === 0 ? (
        <div className="text-center py-16 text-[var(--ink-muted)]">
          <Shield className="h-10 w-10 mx-auto mb-3 text-slate-200" />
          <p className="text-sm">
            {hasFilters
              ? "Keine Controls mit diesen Filtern."
              : "Noch keine Controls. Erstelle zuerst Controls und seede Standards."}
          </p>
          {!hasFilters && (
            <button onClick={handleSeed} disabled={seeding}
              className="mt-4 px-4 py-2 text-sm bg-violet-600 text-white rounded-lg hover:bg-violet-700">
              Standards & Mappings jetzt erstellen
            </button>
          )}
        </div>
      ) : view === "standard" ? (
        <div className="space-y-3">
          {(groups as StandardGroup[]).map(std => (
            <StandardSection
              key={std.standard_id}
              standard={std}
              orgSlug={orgSlug}
              defaultOpen={groups.length === 1}
              onFilterByStandard={setFilterStandardId}
            />
          ))}
        </div>
      ) : view === "category" ? (
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] overflow-hidden">
          {(groups as CategoryGroup[]).map(cat => (
            <CategorySection key={cat.category} category={cat} orgSlug={orgSlug} />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {(groups as GateGroup[]).map(g => (
            <GateSection key={g.gate} group={g} orgSlug={orgSlug} />
          ))}
        </div>
      )}
    </div>
  );
}
