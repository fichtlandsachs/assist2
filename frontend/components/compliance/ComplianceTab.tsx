"use client";

import { useState, useCallback } from "react";
import {
  Shield, AlertTriangle, CheckCircle2, Clock, FileX,
  Filter, Search, RefreshCw, Camera, ChevronRight,
  Lock, Zap, GitMerge, CircleDot,
  TrendingUp, TrendingDown, Minus, Bot,
} from "lucide-react";
import { ComplianceChatWidget } from "./ComplianceChatWidget";
import {
  useAssessmentByObject, useAssessmentItems, createOrGetAssessment,
  refreshAssessment, takeSnapshot,
  type AssessmentSummary, type AssessmentItem,
} from "@/lib/hooks/useCompliance";
import { ComplianceItemPanel } from "./ComplianceItemPanel";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ComplianceTabProps {
  orgId: string;
  objectType: "project" | "product" | "custom";
  objectId: string;
  objectName: string;
  contextParams?: Record<string, unknown>;
  /** Role: admin | quality | product_owner | auditor | viewer */
  userRole?: string;
}

// ── Config maps ───────────────────────────────────────────────────────────────

const TRAFFIC_LIGHT_CONFIG = {
  green:  { bg: "bg-green-100",  border: "border-green-300",  text: "text-green-800",  dot: "bg-green-500",  label: "Erfüllt"   },
  yellow: { bg: "bg-amber-100",  border: "border-amber-300",  text: "text-amber-800",  dot: "bg-amber-500",  label: "Teilweise" },
  red:    { bg: "bg-red-100",    border: "border-red-300",    text: "text-red-800",    dot: "bg-red-500",    label: "Kritisch"  },
  grey:   { bg: "bg-slate-100",  border: "border-slate-200",  text: "text-slate-600",  dot: "bg-slate-400",  label: "Offen"     },
};

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  compliant:           { label: "Compliant",              color: "bg-green-100 text-green-800 border-green-300" },
  partially_compliant: { label: "Eingeschränkt Compliant", color: "bg-amber-100 text-amber-800 border-amber-300" },
  non_compliant:       { label: "Nicht Compliant",        color: "bg-red-100 text-red-800 border-red-300"       },
  not_assessed:        { label: "Nicht bewertet",         color: "bg-slate-100 text-slate-600 border-slate-200" },
};

const ITEM_STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  open:          { label: "Offen",             color: "bg-slate-100 text-slate-600" },
  in_progress:   { label: "In Bearbeitung",    color: "bg-blue-100 text-blue-700"   },
  fulfilled:     { label: "Erfüllt",           color: "bg-green-100 text-green-700" },
  deviation:     { label: "Abweichung",        color: "bg-amber-100 text-amber-700" },
  not_fulfilled: { label: "Nicht erfüllt",     color: "bg-red-100 text-red-700"     },
  not_assessable:{ label: "Nicht bewertbar",   color: "bg-slate-100 text-slate-500" },
};

const ACTIVATION_CONFIG: Record<string, { label: string; icon: React.ElementType; color: string }> = {
  fixed:   { label: "Fest",         icon: Lock,      color: "text-slate-500" },
  trigger: { label: "Trigger",      icon: Zap,       color: "text-amber-500" },
  gate:    { label: "Gate",         icon: GitMerge,  color: "text-violet-500"},
  manual:  { label: "Manuell",      icon: CircleDot, color: "text-blue-500"  },
};

const GATE_READINESS_CONFIG: Record<string, { label: string; color: string }> = {
  ready:          { label: "Freigabebereit",   color: "bg-green-100 text-green-800" },
  conditional:    { label: "Eingeschränkt",    color: "bg-amber-100 text-amber-800" },
  blocked:        { label: "Blockiert",        color: "bg-red-100 text-red-800"     },
  incomplete:     { label: "Unvollständig",    color: "bg-sky-100 text-sky-800"     },
  not_applicable: { label: "Nicht relevant",   color: "bg-slate-100 text-slate-500" },
};

// ── Sub-components ────────────────────────────────────────────────────────────

function TrafficDot({ tl, size = "sm" }: { tl: string; size?: "sm" | "lg" }) {
  const cfg = TRAFFIC_LIGHT_CONFIG[tl as keyof typeof TRAFFIC_LIGHT_CONFIG] ?? TRAFFIC_LIGHT_CONFIG.grey;
  const sz = size === "lg" ? "w-4 h-4" : "w-2.5 h-2.5";
  return <span className={`${sz} rounded-full shrink-0 ${cfg.dot}`} />;
}

function ScoreBadge({ score }: { score: number }) {
  const colors = ["bg-slate-100 text-slate-500", "bg-red-100 text-red-700", "bg-amber-100 text-amber-700", "bg-green-100 text-green-700"];
  return (
    <span className={`w-7 h-7 rounded flex items-center justify-center text-sm font-bold ${colors[score] ?? colors[0]}`}>
      {score}
    </span>
  );
}

function SummaryStat({ label, value, icon: Icon, color, highlighted }: {
  label: string; value: number | string; icon: React.ElementType;
  color: string; highlighted?: boolean;
}) {
  return (
    <div className={`flex items-center gap-3 p-4 rounded-xl border ${highlighted ? "border-red-200 bg-red-50" : "border-[var(--border-subtle)] bg-[var(--bg-card)]"}`}>
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <p className="text-xl font-bold text-[var(--ink-strong)]">{value}</p>
        <p className="text-xs text-[var(--ink-muted)]">{label}</p>
      </div>
    </div>
  );
}

function GateReadinessRow({ gate, entry }: { gate: string; entry: { status: string; blocking_count?: number; avg_score?: number } }) {
  const cfg = GATE_READINESS_CONFIG[entry.status] ?? GATE_READINESS_CONFIG.not_applicable;
  const gateColors: Record<string, string> = {
    G1: "bg-sky-100 text-sky-700",
    G2: "bg-violet-100 text-violet-700",
    G3: "bg-amber-100 text-amber-700",
    G4: "bg-emerald-100 text-emerald-700",
  };
  return (
    <div className="flex items-center gap-3">
      <span className={`w-9 h-7 rounded flex items-center justify-center text-xs font-bold ${gateColors[gate] ?? "bg-slate-100 text-slate-600"}`}>{gate}</span>
      <span className={`px-2 py-0.5 rounded text-xs font-medium border ${cfg.color}`}>{cfg.label}</span>
      {entry.blocking_count && (
        <span className="text-xs text-red-600">{entry.blocking_count} blockierend</span>
      )}
      {entry.avg_score !== undefined && (
        <span className="text-xs text-[var(--ink-muted)]">⌀ {entry.avg_score}</span>
      )}
    </div>
  );
}

function ControlRow({
  item,
  onSelect,
}: {
  item: AssessmentItem;
  onSelect: (item: AssessmentItem) => void;
}) {
  const statusCfg = ITEM_STATUS_CONFIG[item.status] ?? ITEM_STATUS_CONFIG.open;
  const activationCfg = ACTIVATION_CONFIG[item.activation_source] ?? ACTIVATION_CONFIG.fixed;
  const ActivationIcon = activationCfg.icon;

  return (
    <div
      onClick={() => onSelect(item)}
      className={`flex items-center gap-3 px-4 py-3 border-b border-[var(--border-subtle)] last:border-0 cursor-pointer hover:bg-[var(--bg-hover)] transition-colors group ${item.blocks_gate ? "bg-red-50/40" : ""}`}
    >
      {/* Score */}
      <ScoreBadge score={item.score} />

      {/* Traffic light */}
      <TrafficDot tl={item.traffic_light} />

      {/* Name */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-[var(--ink-strong)] truncate">
            {item.control_name}
          </span>
          {item.hard_stop && (
            <span className="flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700 shrink-0">
              <AlertTriangle className="h-3 w-3" /> Stop
            </span>
          )}
          {item.blocks_gate && (
            <span className="px-1.5 py-0.5 rounded text-xs font-bold bg-red-600 text-white shrink-0">
              BLOCKIERT
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 mt-0.5 flex-wrap">
          {item.category_name && (
            <span className="text-xs text-[var(--ink-muted)]">{item.category_name}</span>
          )}
          <span className={`flex items-center gap-0.5 text-xs ${activationCfg.color}`}>
            <ActivationIcon className="h-3 w-3" />
            {activationCfg.label}
          </span>
          {item.activating_trigger_name && (
            <span className="text-xs text-[var(--ink-muted)] truncate max-w-32">
              via {item.activating_trigger_name}
            </span>
          )}
        </div>
      </div>

      {/* Gates */}
      <div className="hidden md:flex gap-1 shrink-0">
        {item.gate_phases.map(g => (
          <span key={g} className="px-1.5 py-0.5 rounded text-xs bg-violet-50 text-violet-600 font-medium">{g}</span>
        ))}
      </div>

      {/* Status */}
      <span className={`hidden lg:inline-flex px-2 py-0.5 rounded text-xs font-medium shrink-0 ${statusCfg.color}`}>
        {statusCfg.label}
      </span>

      {/* Evidence */}
      <span className={`hidden xl:inline-flex text-xs shrink-0 ${
        item.evidence_status === "complete" ? "text-green-600" :
        item.evidence_status === "partial"  ? "text-amber-600" : "text-slate-400"
      }`}>
        {item.evidence_status === "complete" ? "✓ Nachweis" :
         item.evidence_status === "partial"  ? "~ Teilweise" : "✗ Fehlt"}
      </span>

      <ChevronRight className="h-4 w-4 text-[var(--ink-muted)] shrink-0 opacity-0 group-hover:opacity-100" />
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function ComplianceTab({
  orgId, objectType, objectId, objectName, contextParams = {}, userRole = "viewer",
}: ComplianceTabProps) {
  const [selectedItem, setSelectedItem] = useState<AssessmentItem | null>(null);
  const [activeTab, setActiveTab] = useState<"controls" | "chat">("controls");
  const [creating, setCreating] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [snapping, setSnapping] = useState(false);

  // Filters
  const [search, setSearch] = useState("");
  const [filterGate, setFilterGate] = useState("");
  const [filterKind, setFilterKind] = useState("");
  const [filterSource, setFilterSource] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterHardStop, setFilterHardStop] = useState(false);
  const [filterBlocking, setFilterBlocking] = useState(false);
  const [filterNoEvidence, setFilterNoEvidence] = useState(false);
  const [page, setPage] = useState(1);

  const {
    data: assessment,
    isLoading: assessmentLoading,
    mutate: mutateAssessment,
    error: assessmentError,
  } = useAssessmentByObject(objectType, objectId);

  const {
    data: itemsData,
    isLoading: itemsLoading,
    mutate: mutateItems,
  } = useAssessmentItems(assessment?.id ?? null, {
    search: search || undefined,
    gate_phase: filterGate || undefined,
    control_kind: filterKind || undefined,
    activation_source: filterSource || undefined,
    status_filter: filterStatus || undefined,
    hard_stop_only: filterHardStop || undefined,
    blocks_gate_only: filterBlocking || undefined,
    no_evidence_only: filterNoEvidence || undefined,
    page,
    page_size: 30,
  });

  const canEdit = userRole === "admin" || userRole === "quality";
  const canScore = canEdit || userRole === "product_owner";
  const canView = userRole !== undefined;

  const handleCreate = async () => {
    setCreating(true);
    try {
      await createOrGetAssessment({ org_id: orgId, object_type: objectType, object_id: objectId, object_name: objectName, context_params: contextParams });
      mutateAssessment();
    } catch (e) {
      console.error(e);
    } finally {
      setCreating(false);
    }
  };

  const handleRefresh = async () => {
    if (!assessment) return;
    setRefreshing(true);
    try {
      await refreshAssessment(assessment.id);
      mutateAssessment();
      mutateItems();
    } catch (e) {
      console.error(e);
    } finally {
      setRefreshing(false);
    }
  };

  const handleSnapshot = async () => {
    if (!assessment) return;
    setSnapping(true);
    try {
      await takeSnapshot(assessment.id, "manual_gate_check");
    } catch (e) {
      console.error(e);
    } finally {
      setSnapping(false);
    }
  };

  const clearFilters = () => {
    setSearch(""); setFilterGate(""); setFilterKind(""); setFilterSource("");
    setFilterStatus(""); setFilterHardStop(false); setFilterBlocking(false); setFilterNoEvidence(false);
    setPage(1);
  };

  const hasFilters = search || filterGate || filterKind || filterSource || filterStatus || filterHardStop || filterBlocking || filterNoEvidence;

  // ── Empty state: no assessment yet ───────────────────────────────────────
  if (assessmentLoading) {
    return (
      <div className="flex items-center justify-center h-48">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-violet-500" />
      </div>
    );
  }

  if (!assessment || assessmentError) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-4">
        <Shield className="h-12 w-12 text-slate-300" />
        <div className="text-center">
          <p className="text-sm font-medium text-[var(--ink-strong)]">Noch keine Compliance-Bewertung</p>
          <p className="text-xs text-[var(--ink-muted)] mt-1">
            Erstelle eine Compliance-Bewertung um Controls zu aktivieren, zu bewerten und nachzuverfolgen.
          </p>
        </div>
        {canEdit && (
          <button
            onClick={handleCreate}
            disabled={creating}
            className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-lg text-sm hover:bg-violet-700 transition-colors disabled:opacity-60"
          >
            <Shield className="h-4 w-4" />
            {creating ? "Wird erstellt…" : "Compliance-Bewertung starten"}
          </button>
        )}
      </div>
    );
  }

  const tl = TRAFFIC_LIGHT_CONFIG[assessment.traffic_light] ?? TRAFFIC_LIGHT_CONFIG.grey;
  const statusCfg = STATUS_CONFIG[assessment.compliance_status] ?? STATUS_CONFIG.not_assessed;

  return (
    <div className="space-y-4">
      {/* ── Tab switcher ─────────────────────────────────────────────────── */}
      <div className="flex gap-0 border-b border-[var(--border-subtle)]">
        {[
          { key: "controls" as const, label: "Controls & Bewertung", icon: Shield },
          { key: "chat" as const, label: "Assistent", icon: Bot, badge: assessment.not_assessed_controls > 0 ? assessment.not_assessed_controls : undefined },
        ].map(({ key, label, icon: Icon, badge }) => (
          <button key={key} onClick={() => setActiveTab(key)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm border-b-2 transition-colors ${
              activeTab === key
                ? "border-violet-500 text-violet-700 font-medium"
                : "border-transparent text-[var(--ink-muted)] hover:text-[var(--ink-mid)]"
            }`}>
            <Icon className="h-4 w-4" />
            {label}
            {badge !== undefined && (
              <span className="ml-1 px-1.5 py-0.5 text-xs font-medium bg-amber-100 text-amber-700 rounded-full">
                {badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Chat tab ─────────────────────────────────────────────────────── */}
      {activeTab === "chat" && (
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] overflow-hidden">
          <ComplianceChatWidget
            assessment={assessment}
            orgId={orgId}
            onAssessmentUpdated={() => { mutateAssessment(); mutateItems(); }}
          />
        </div>
      )}

      {activeTab === "controls" && <>
      {/* ── Summary header ───────────────────────────────────────────────── */}
      <div className={`flex items-center gap-4 p-4 rounded-xl border-2 ${tl.border} ${tl.bg}`}>
        <div className={`w-12 h-12 rounded-xl ${tl.dot} flex items-center justify-center`}>
          <Shield className="h-6 w-6 text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <span className={`px-2.5 py-1 rounded-lg border text-sm font-semibold ${statusCfg.color}`}>
              {statusCfg.label}
            </span>
            {assessment.overall_score !== null && (
              <span className={`text-sm font-bold ${tl.text}`}>
                Score: {assessment.overall_score} / 3
              </span>
            )}
          </div>
          <p className="text-xs text-[var(--ink-muted)] mt-0.5">
            {assessment.total_controls} Controls aktiv ·
            zuletzt aktualisiert {new Date(assessment.updated_at).toLocaleDateString("de-DE")}
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          {canEdit && (
            <button onClick={handleRefresh} disabled={refreshing}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-white/80 border border-white rounded-lg hover:bg-white transition-colors disabled:opacity-60">
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
              Aktualisieren
            </button>
          )}
          <button onClick={handleSnapshot} disabled={snapping}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-white/80 border border-white rounded-lg hover:bg-white transition-colors disabled:opacity-60">
            <Camera className="h-3.5 w-3.5" />
            Snapshot
          </button>
        </div>
      </div>

      {/* ── KPI grid ─────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SummaryStat label="Erfüllt" value={assessment.fulfilled_controls} icon={CheckCircle2} color="bg-green-100 text-green-600" />
        <SummaryStat label="Abweichung" value={assessment.deviation_controls} icon={TrendingDown} color="bg-amber-100 text-amber-600" />
        <SummaryStat label="Nicht bewertet" value={assessment.not_assessed_controls} icon={Clock} color="bg-slate-100 text-slate-500" />
        <SummaryStat
          label="Hard-Stops kritisch" value={assessment.hard_stop_critical}
          icon={AlertTriangle} color="bg-red-100 text-red-600"
          highlighted={assessment.hard_stop_critical > 0}
        />
      </div>

      {/* ── Gate Readiness ────────────────────────────────────────────────── */}
      {Object.keys(assessment.gate_readiness).length > 0 && (
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-4">
          <p className="text-xs font-semibold text-[var(--ink-muted)] uppercase tracking-wider mb-3">Gate-Freigabestatus</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {["G1", "G2", "G3", "G4"].map(gate => {
              const entry = assessment.gate_readiness[gate];
              if (!entry) return null;
              return <GateReadinessRow key={gate} gate={gate} entry={entry} />;
            })}
          </div>
        </div>
      )}

      {/* ── Filter bar ───────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-2">
        <div className="relative flex-1 min-w-36">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--ink-muted)]" />
          <input
            type="text"
            placeholder="Suchen…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            className="w-full pl-8 pr-3 py-1.5 text-sm bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg focus:outline-none focus:border-violet-400"
          />
        </div>
        <select value={filterGate} onChange={e => { setFilterGate(e.target.value); setPage(1); }}
          className="px-2.5 py-1.5 text-sm bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg focus:outline-none">
          <option value="">Alle Gates</option>
          {["G1","G2","G3","G4"].map(g => <option key={g} value={g}>{g}</option>)}
        </select>
        <select value={filterKind} onChange={e => { setFilterKind(e.target.value); setPage(1); }}
          className="px-2.5 py-1.5 text-sm bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg focus:outline-none">
          <option value="">Typ</option>
          <option value="fixed">Fest</option>
          <option value="dynamic">Dynamisch</option>
        </select>
        <select value={filterStatus} onChange={e => { setFilterStatus(e.target.value); setPage(1); }}
          className="px-2.5 py-1.5 text-sm bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg focus:outline-none">
          <option value="">Status</option>
          <option value="open">Offen</option>
          <option value="in_progress">In Bearbeitung</option>
          <option value="fulfilled">Erfüllt</option>
          <option value="deviation">Abweichung</option>
          <option value="not_fulfilled">Nicht erfüllt</option>
        </select>
        {/* Quick filter toggles */}
        {[
          { label: "Hard-Stop", active: filterHardStop, onChange: (v: boolean) => { setFilterHardStop(v); setPage(1); } },
          { label: "Blockiert",  active: filterBlocking, onChange: (v: boolean) => { setFilterBlocking(v); setPage(1); } },
          { label: "Kein Nachweis", active: filterNoEvidence, onChange: (v: boolean) => { setFilterNoEvidence(v); setPage(1); } },
        ].map(({ label, active, onChange }) => (
          <button key={label} onClick={() => onChange(!active)}
            className={`px-2.5 py-1.5 text-xs rounded-lg border transition-colors ${
              active
                ? "bg-violet-600 text-white border-violet-600"
                : "bg-[var(--bg-card)] border-[var(--border-subtle)] text-[var(--ink-mid)] hover:border-violet-400"
            }`}
          >
            {label}
          </button>
        ))}
        {hasFilters && (
          <button onClick={clearFilters} className="text-xs text-[var(--ink-muted)] hover:text-[var(--ink-mid)] px-2">
            × Filter zurücksetzen
          </button>
        )}
      </div>

      {/* ── Control list ─────────────────────────────────────────────────── */}
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] overflow-hidden">
        {/* Column headers */}
        <div className="hidden md:grid grid-cols-[52px_12px_1fr_80px_100px_80px] gap-2 px-4 py-2 border-b border-[var(--border-subtle)] bg-[var(--bg-base)]">
          {["Score","","Control","Gates","Status","Nachweis"].map(h => (
            <span key={h} className="text-xs font-medium text-[var(--ink-muted)] uppercase tracking-wide">{h}</span>
          ))}
        </div>

        {itemsLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-violet-500" />
          </div>
        ) : !itemsData?.items.length ? (
          <div className="text-center py-12">
            <CircleDot className="h-8 w-8 text-slate-200 mx-auto mb-2" />
            <p className="text-sm text-[var(--ink-muted)]">
              {hasFilters ? "Keine Controls mit diesen Filtern." : "Noch keine Controls aktiv."}
            </p>
          </div>
        ) : (
          itemsData.items.map(item => (
            <ControlRow key={item.id} item={item} onSelect={setSelectedItem} />
          ))
        )}

        {/* Pagination */}
        {itemsData && itemsData.total > itemsData.page_size && (
          <div className="px-4 py-3 border-t border-[var(--border-subtle)] flex items-center justify-between">
            <p className="text-xs text-[var(--ink-muted)]">{itemsData.total} Controls</p>
            <div className="flex gap-2">
              <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
                className="px-2.5 py-1 text-xs rounded border border-[var(--border-subtle)] disabled:opacity-40">←</button>
              <span className="px-2 py-1 text-xs text-[var(--ink-muted)]">{page} / {Math.ceil(itemsData.total / itemsData.page_size)}</span>
              <button disabled={page >= Math.ceil(itemsData.total / itemsData.page_size)} onClick={() => setPage(p => p + 1)}
                className="px-2.5 py-1 text-xs rounded border border-[var(--border-subtle)] disabled:opacity-40">→</button>
            </div>
          </div>
        )}
      </div>

      {/* ── Detail Side Panel ─────────────────────────────────────────────── */}
      {selectedItem && (
        <ComplianceItemPanel
          assessmentId={assessment.id}
          itemId={selectedItem.id}
          canScore={canScore}
          canEdit={canEdit}
          onClose={() => setSelectedItem(null)}
          onScored={() => { mutateAssessment(); mutateItems(); }}
        />
      )}
      </>}
    </div>
  );
}
