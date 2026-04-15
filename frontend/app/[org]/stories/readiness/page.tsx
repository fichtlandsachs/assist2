"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import useSWR, { mutate } from "swr";
import {
  Activity, AlertTriangle, CheckCircle2, Clock, RefreshCw,
  ChevronDown, ChevronUp, Loader2, XCircle, AlertCircle, Info,
} from "lucide-react";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher } from "@/lib/api/client";
import type { MyReadinessResponse, StoryWithReadiness, StoryReadinessEvaluation } from "@/types";

// ── Helpers ───────────────────────────────────────────────────────────────────

type FilterKey = "" | "blocked" | "not_ready" | "missing_inputs" | "high_priority";

const STATE_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  implementation_ready: { label: "Bereit",          color: "#16a34a", bg: "#dcfce7" },
  mostly_ready:         { label: "Fast bereit",     color: "#ca8a04", bg: "#fef9c3" },
  partially_ready:      { label: "Teilweise bereit", color: "#ea580c", bg: "#ffedd5" },
  not_ready:            { label: "Nicht bereit",    color: "#dc2626", bg: "#fee2e2" },
};

const PRIORITY_CONFIG: Record<string, { label: string; color: string }> = {
  critical: { label: "Kritisch", color: "#dc2626" },
  high:     { label: "Hoch",     color: "#ea580c" },
  medium:   { label: "Mittel",   color: "#ca8a04" },
  low:      { label: "Niedrig",  color: "#6b7280" },
};

function ScoreBadge({ score, state }: { score: number; state: string }) {
  const cfg = STATE_CONFIG[state] ?? STATE_CONFIG.not_ready;
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold"
      style={{ background: cfg.bg, color: cfg.color }}>
      {score}%
    </span>
  );
}

function StateTile({ label, value, icon: Icon, accent }: {
  label: string; value: number; icon: React.ElementType; accent: string;
}) {
  return (
    <div className="neo-card p-4 flex flex-col gap-1">
      <div className="flex items-center gap-2">
        <Icon size={16} style={{ color: accent }} />
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{label}</span>
      </div>
      <p className="text-2xl font-bold" style={{ color: accent }}>{value}</p>
    </div>
  );
}

// ── Detail panel ──────────────────────────────────────────────────────────────

function EvalDetail({ ev }: { ev: StoryReadinessEvaluation }) {
  const cfg = STATE_CONFIG[ev.readiness_state] ?? STATE_CONFIG.not_ready;

  return (
    <div className="space-y-4 text-sm">
      <div className="flex items-center gap-3">
        <span className="text-2xl font-bold" style={{ color: cfg.color }}>{ev.readiness_score}</span>
        <span className="px-2 py-0.5 rounded-full text-xs font-semibold" style={{ background: cfg.bg, color: cfg.color }}>
          {cfg.label}
        </span>
        {ev.confidence != null && (
          <span className="text-xs text-gray-400">Konfidenz: {Math.round(ev.confidence * 100)}%</span>
        )}
      </div>

      {ev.summary && (
        <p className="text-gray-600 text-sm leading-relaxed border-l-2 pl-3" style={{ borderColor: cfg.color }}>
          {ev.summary}
        </p>
      )}

      {ev.blockers.length > 0 && (
        <Section title="Blocker" icon={XCircle} color="#dc2626">
          {ev.blockers.map((b, i) => (
            <Item key={i} label={b.description} badge={b.severity} badgeColor={b.severity === "critical" ? "#dc2626" : b.severity === "major" ? "#ea580c" : "#ca8a04"} />
          ))}
        </Section>
      )}

      {ev.missing_inputs.length > 0 && (
        <Section title="Fehlende Zuarbeiten" icon={AlertTriangle} color="#ea580c">
          {ev.missing_inputs.map((m, i) => (
            <Item key={i} label={m.input} badge={m.importance} badgeColor={m.importance === "high" ? "#dc2626" : m.importance === "medium" ? "#ea580c" : "#6b7280"} />
          ))}
        </Section>
      )}

      {ev.open_topics.length > 0 && (
        <Section title="Offene Themen" icon={AlertCircle} color="#ca8a04">
          {ev.open_topics.map((t, i) => (
            <Item key={i} label={t.topic} sub={t.detail ?? undefined} badge={t.source} badgeColor="#6b7280" />
          ))}
        </Section>
      )}

      {ev.risks.length > 0 && (
        <Section title="Risiken" icon={Info} color="#7c3aed">
          {ev.risks.map((r, i) => (
            <Item key={i} label={r.description} badge={`${r.probability} / ${r.impact}`} badgeColor="#7c3aed" />
          ))}
        </Section>
      )}

      {ev.recommended_next_steps.length > 0 && (
        <Section title="Nächste Schritte" icon={CheckCircle2} color="#16a34a">
          {ev.recommended_next_steps.sort((a, b) => a.priority - b.priority).map((s, i) => (
            <Item key={i} label={s.step} badge={s.responsible ?? undefined} badgeColor="#6b7280" />
          ))}
        </Section>
      )}

      <p className="text-xs text-gray-400">
        Bewertet am {new Date(ev.created_at).toLocaleString("de-DE")}
        {ev.model_used && ` · ${ev.model_used}`}
      </p>
    </div>
  );
}

function Section({ title, icon: Icon, color, children }: {
  title: string; icon: React.ElementType; color: string; children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1.5">
        <Icon size={13} style={{ color }} />
        <span className="text-xs font-semibold uppercase tracking-wide" style={{ color }}>{title}</span>
      </div>
      <ul className="space-y-1">{children}</ul>
    </div>
  );
}

function Item({ label, sub, badge, badgeColor }: {
  label: string; sub?: string; badge?: string; badgeColor?: string;
}) {
  return (
    <li className="flex items-start gap-2">
      <span className="mt-1.5 w-1 h-1 rounded-full bg-gray-300 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <span className="text-gray-700">{label}</span>
        {sub && <p className="text-gray-400 text-xs mt-0.5">{sub}</p>}
      </div>
      {badge && (
        <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded" style={{ background: `${badgeColor}20`, color: badgeColor }}>
          {badge}
        </span>
      )}
    </li>
  );
}

// ── Story row ─────────────────────────────────────────────────────────────────

function StoryRow({
  story, orgId, expanded, onToggle, onEvaluate, evaluating,
}: {
  story: StoryWithReadiness;
  orgId: string;
  expanded: boolean;
  onToggle: () => void;
  onEvaluate: () => void;
  evaluating: boolean;
}) {
  const ev = story.latest_evaluation;
  const priorityCfg = PRIORITY_CONFIG[story.priority] ?? PRIORITY_CONFIG.medium;

  return (
    <div className="neo-card overflow-hidden">
      <button
        className="w-full flex items-center gap-3 p-4 text-left hover:bg-gray-50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-sm text-gray-900 truncate">{story.title}</span>
            {story.epic_title && (
              <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded truncate max-w-[120px]">
                {story.epic_title}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs font-semibold" style={{ color: priorityCfg.color }}>{priorityCfg.label}</span>
            {story.story_points != null && (
              <span className="text-xs text-gray-400">{story.story_points} SP</span>
            )}
            <span className="text-xs text-gray-400 capitalize">{story.status.replace("_", " ")}</span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {ev ? (
            <ScoreBadge score={ev.readiness_score} state={ev.readiness_state} />
          ) : (
            <span className="text-xs text-gray-400 italic">Nicht bewertet</span>
          )}
          <button
            onClick={e => { e.stopPropagation(); onEvaluate(); }}
            disabled={evaluating}
            title="Neu bewerten"
            className="p-1.5 rounded-lg border text-gray-400 hover:text-gray-700 hover:border-gray-400 transition-colors"
            style={{ borderColor: "#e5e7eb" }}
          >
            {evaluating ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          </button>
          {expanded ? <ChevronUp size={14} className="text-gray-400" /> : <ChevronDown size={14} className="text-gray-400" />}
        </div>
      </button>

      {expanded && ev && (
        <div className="border-t border-gray-100 p-4 bg-gray-50">
          <EvalDetail ev={ev} />
        </div>
      )}

      {expanded && !ev && (
        <div className="border-t border-gray-100 p-4 text-sm text-gray-500 text-center">
          Noch keine Bewertung vorhanden. Klick auf{" "}
          <button onClick={onEvaluate} className="underline text-orange-600">Neu bewerten</button>.
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function MyStoryReadinessPage() {
  const params = useParams<{ org: string }>();
  const orgSlug = params.org;
  const { org } = useOrg(orgSlug);
  const orgId = org?.id;

  const [filter, setFilter] = useState<FilterKey>("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [evaluating, setEvaluating] = useState<Set<string>>(new Set());
  const [batchEvaluating, setBatchEvaluating] = useState(false);

  const swrKey = orgId ? `/api/v1/story-readiness/my-stories?org_id=${orgId}${filter ? `&filter_state=${filter}` : ""}` : null;
  const { data, error, isLoading } = useSWR<MyReadinessResponse>(swrKey, fetcher);

  async function evaluateSingle(storyId: string) {
    if (!orgId) return;
    setEvaluating(s => new Set(s).add(storyId));
    try {
      await apiRequest(`/api/v1/story-readiness/${storyId}/evaluate?org_id=${orgId}`, { method: "POST" });
      await mutate(swrKey);
    } catch (e) {
      console.error(e);
    } finally {
      setEvaluating(s => { const n = new Set(s); n.delete(storyId); return n; });
    }
  }

  async function evaluateBatch() {
    if (!orgId) return;
    setBatchEvaluating(true);
    try {
      await apiRequest(`/api/v1/story-readiness/evaluate?org_id=${orgId}`, { method: "POST", body: JSON.stringify({}) });
      await mutate(swrKey);
    } catch (e) {
      console.error(e);
    } finally {
      setBatchEvaluating(false);
    }
  }

  const FILTERS: { key: FilterKey; label: string }[] = [
    { key: "",              label: "Alle" },
    { key: "blocked",       label: "Blockiert" },
    { key: "not_ready",     label: "Nicht bereit" },
    { key: "missing_inputs", label: "Fehlende Zuarbeiten" },
    { key: "high_priority", label: "Hohe Priorität" },
  ];

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Activity size={22} style={{ color: "#FF5C00" }} />
          <div>
            <h1 className="text-xl font-bold text-gray-900">Meine Story-Lage</h1>
            <p className="text-xs text-gray-500">KI-Bewertung deiner zugewiesenen User Stories</p>
          </div>
        </div>
        <button
          onClick={evaluateBatch}
          disabled={batchEvaluating || !orgId}
          className="neo-btn neo-btn--default neo-btn--sm flex items-center gap-2"
        >
          {batchEvaluating ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          Alle neu bewerten
        </button>
      </div>

      {/* Dashboard tiles */}
      {data && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StateTile label="Gesamt"        value={data.total_stories}        icon={BookIcon}       accent="#6b7280" />
          <StateTile label="Umsetzbereit"  value={data.implementation_ready} icon={CheckCircle2}   accent="#16a34a" />
          <StateTile label="Blockiert"     value={data.blocked}              icon={XCircle}        accent="#dc2626" />
          <StateTile label="Fehlt Zuarb."  value={data.missing_inputs_count} icon={AlertTriangle}  accent="#ea580c" />
        </div>
      )}

      {/* Filter bar */}
      <div className="flex gap-2 flex-wrap">
        {FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`neo-btn neo-btn--sm ${filter === f.key ? "neo-btn--default" : "neo-btn--outline"}`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {isLoading && (
        <div className="flex items-center justify-center py-16 text-gray-400 gap-2">
          <Loader2 size={18} className="animate-spin" />
          <span>Lade Stories…</span>
        </div>
      )}

      {error && (
        <div className="neo-card p-4 text-sm text-red-600 flex items-center gap-2">
          <AlertTriangle size={15} />
          Fehler beim Laden. Bitte Seite neu laden.
        </div>
      )}

      {data && data.stories.length === 0 && (
        <div className="neo-card p-8 text-center text-gray-500 text-sm">
          <Clock size={24} className="mx-auto mb-2 text-gray-300" />
          Keine Stories gefunden{filter ? " für diesen Filter" : ""}.
        </div>
      )}

      {data && data.stories.map(story => (
        <StoryRow
          key={story.story_id}
          story={story}
          orgId={orgId ?? ""}
          expanded={expandedId === story.story_id}
          onToggle={() => setExpandedId(expandedId === story.story_id ? null : story.story_id)}
          onEvaluate={() => evaluateSingle(story.story_id)}
          evaluating={evaluating.has(story.story_id)}
        />
      ))}
    </div>
  );
}

// ── tiny icon shim ────────────────────────────────────────────────────────────
function BookIcon({ size, style }: { size: number; style?: React.CSSProperties }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style}>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </svg>
  );
}
