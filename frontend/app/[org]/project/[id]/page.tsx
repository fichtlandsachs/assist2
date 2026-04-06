"use client";

import { use, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useOrg } from "@/lib/hooks/useOrg";
import { fetcher, apiRequest } from "@/lib/api/client";
import type { Project, Epic, UserStory, Feature } from "@/types";
import {
  ArrowLeft,
  CalendarDays,
  Zap,
  Layers,
  ExternalLink,
  Plus,
  BarChart3,
  Target,
  TrendingUp,
  CheckCircle2,
  BookOpen,
  GitBranch,
  Pencil,
  Save,
  X,
} from "lucide-react";

// ── Labels ────────────────────────────────────────────────────────────────────

const EFFORT_LABELS: Record<string, string> = {
  low: "Niedrig", medium: "Mittel", high: "Hoch", xl: "XL",
};
const COMPLEXITY_LABELS: Record<string, string> = {
  low: "Niedrig", medium: "Mittel", high: "Hoch", xl: "XL",
};

const PROJECT_STATUS_LABELS: Record<string, string> = {
  planning: "Planung", active: "Aktiv", done: "Fertig", archived: "Archiviert",
};
const PROJECT_STATUS_COLORS: Record<string, string> = {
  planning: "bg-[var(--paper-warm)] text-[var(--ink-mid)]",
  active:   "bg-[rgba(82,107,94,.1)] text-[var(--green)]",
  done:     "bg-[rgba(82,107,94,.1)] text-[var(--green)]",
  archived: "bg-[var(--paper-rule2)] text-[var(--ink-faint)]",
};

const STORY_STATUS_LABELS: Record<string, string> = {
  draft:       "Entwurf",
  in_review:   "Überarbeitung",
  ready:       "Bereit",
  in_progress: "In Arbeit",
  testing:     "Test",
  done:        "Fertig",
  archived:    "Archiviert",
};
const STORY_STATUS_COLORS: Record<string, string> = {
  draft:       "bg-[var(--paper-warm)] text-[var(--ink-mid)]",
  in_review:   "bg-[rgba(var(--btn-primary-rgb),.08)] text-[var(--btn-primary)]",
  ready:       "bg-[rgba(74,85,104,.06)] text-[var(--navy)]",
  in_progress: "bg-[rgba(122,100,80,.1)] text-[var(--brown)]",
  testing:     "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]",
  done:        "bg-[rgba(82,107,94,.1)] text-[var(--green)]",
  archived:    "bg-[var(--paper-rule2)] text-[var(--ink-faint)]",
};
const STORY_STATUS_DOT: Record<string, string> = {
  draft:       "bg-[var(--ink-faint)]",
  in_review:   "bg-[var(--btn-primary)]",
  ready:       "bg-[var(--navy)]",
  in_progress: "bg-[var(--brown)]",
  testing:     "bg-[var(--accent-red)]",
  done:        "bg-[var(--green)]",
  archived:    "bg-[var(--ink-faint)]",
};
const STORY_STATUS_BAR: Record<string, string> = {
  draft:       "bg-[var(--ink-faint)]",
  in_review:   "bg-[var(--btn-primary)]",
  ready:       "bg-[var(--navy)]",
  in_progress: "bg-[var(--brown)]",
  testing:     "bg-[var(--accent-red)]",
  done:        "bg-[var(--green)]",
  archived:    "bg-[var(--ink-faint)] opacity-40",
};

const EPIC_STATUS_LABELS: Record<string, string> = {
  planning:    "Planung",
  in_progress: "In Arbeit",
  done:        "Fertig",
  archived:    "Archiviert",
};
const EPIC_STATUS_COLORS: Record<string, string> = {
  planning:    "bg-[var(--paper-warm)] text-[var(--ink-mid)]",
  in_progress: "bg-[rgba(122,100,80,.1)] text-[var(--brown)]",
  done:        "bg-[rgba(82,107,94,.1)] text-[var(--green)]",
  archived:    "bg-[var(--paper-rule2)] text-[var(--ink-faint)]",
};

const FEATURE_STATUS_LABELS: Record<string, string> = {
  draft:       "Entwurf",
  in_progress: "In Arbeit",
  testing:     "Test",
  done:        "Fertig",
  archived:    "Archiviert",
};
const FEATURE_STATUS_COLORS: Record<string, string> = {
  draft:       "bg-[var(--paper-warm)] text-[var(--ink-mid)]",
  in_progress: "bg-[rgba(122,100,80,.1)] text-[var(--brown)]",
  testing:     "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]",
  done:        "bg-[rgba(82,107,94,.1)] text-[var(--green)]",
  archived:    "bg-[var(--paper-rule2)] text-[var(--ink-faint)]",
};

const STORY_STATUSES = ["draft", "in_review", "ready", "in_progress", "testing", "done", "archived"] as const;
const FEATURE_STATUSES = ["draft", "in_progress", "testing", "done", "archived"] as const;

// ── Helpers ───────────────────────────────────────────────────────────────────

function CountBadge({ n }: { n: number }) {
  return (
    <span className="ml-1.5 px-1.5 py-0.5 bg-[var(--paper-warm)] text-[var(--ink-mid)] rounded-sm text-[9px] font-bold">
      {n}
    </span>
  );
}

function SectionCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-[var(--card)] border border-[var(--paper-rule)] rounded-sm p-6 flex flex-col gap-4">
      {children}
    </div>
  );
}

function MetricBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-[11px] text-[var(--ink-mid)] w-24 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-[var(--paper-warm)] rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
      </div>
      <span className="text-[11px] text-[var(--ink-mid)] w-8 text-right">{value}%</span>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function ProjectDetailPage({
  params,
}: {
  params: Promise<{ org: string; id: string }>;
}) {
  const { org: orgSlug, id: projectId } = use(params);
  const { org } = useOrg(orgSlug);

  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [saving, setSaving] = useState(false);

  const { data: project, isLoading: loadingProject, mutate: mutateProject } = useSWR<Project>(
    `/api/v1/projects/${projectId}`,
    fetcher
  );

  const { data: epics } = useSWR<Epic[]>(
    `/api/v1/projects/${projectId}/epics`,
    fetcher
  );

  const { data: stories } = useSWR<UserStory[]>(
    org ? `/api/v1/user-stories?org_id=${org.id}&project_id=${projectId}` : null,
    fetcher
  );

  const { data: features } = useSWR<Feature[]>(
    org ? `/api/v1/features?org_id=${org.id}&project_id=${projectId}` : null,
    fetcher
  );

  // ── Loading / not found ─────────────────────────────────────────────────────

  if (loadingProject) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--ink-mid)]" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="text-center py-20">
        <p className="text-[var(--ink-faint)] text-sm">Projekt nicht gefunden</p>
        <Link
          href={`/${orgSlug}/project`}
          className="mt-3 inline-block text-[var(--btn-primary)] text-sm hover:underline"
        >
          ← Zurück
        </Link>
      </div>
    );
  }

  // ── Edit handlers ───────────────────────────────────────────────────────────

  function startEdit() {
    if (!project) return;
    setEditName(project.name);
    setEditDescription(project.description ?? "");
    setEditing(true);
  }

  async function handleSave() {
    setSaving(true);
    try {
      await apiRequest(`/api/v1/projects/${projectId}`, {
        method: "PATCH",
        body: JSON.stringify({ name: editName.trim(), description: editDescription.trim() || null }),
      });
      await mutateProject();
      setEditing(false);
    } finally { setSaving(false); }
  }

  // ── Computed metrics ────────────────────────────────────────────────────────

  const storyList = stories ?? [];
  const epicList = epics ?? [];
  const featureList = features ?? [];

  // Story status counts
  const statusCounts = Object.fromEntries(
    STORY_STATUSES.map((s) => [s, storyList.filter((st) => st.status === s).length])
  ) as Record<string, number>;
  const totalStories = storyList.length;

  // Metrics
  const storiesWithQuality = storyList.filter((s) => s.quality_score != null);
  const avgQuality =
    storiesWithQuality.length > 0
      ? Math.round(
          storiesWithQuality.reduce((acc, s) => acc + (s.quality_score ?? 0), 0) /
            storiesWithQuality.length
        )
      : 0;

  const storiesWithDesc = storyList.filter(
    (s) => s.description && s.description.trim().length > 0
  ).length;
  const klarheit = totalStories > 0 ? Math.round((storiesWithDesc / totalStories) * 100) : 0;

  const sicherheit = avgQuality;
  const sicherheitColor =
    avgQuality >= 80 ? "bg-[var(--green)]" : avgQuality >= 50 ? "bg-amber-400" : "bg-rose-400";
  const klarheitColor =
    klarheit >= 80 ? "bg-[var(--green)]" : klarheit >= 50 ? "bg-amber-400" : "bg-rose-400";

  // Complexity: map label to percent
  const complexityMap: Record<string, number> = {
    low: 25, medium: 50, high: 75, xl: 100,
  };
  const complexityVal = project.complexity ? complexityMap[project.complexity] ?? 50 : 50;
  const complexityColor =
    complexityVal <= 25
      ? "bg-[var(--green)]"
      : complexityVal <= 50
      ? "bg-amber-400"
      : "bg-rose-400";

  const riskCount = statusCounts["testing"] + 0; // blocked not tracked; use testing as proxy
  const risiko =
    totalStories > 0 ? Math.round((riskCount / totalStories) * 100) : 0;
  const risikoColor =
    risiko <= 10 ? "bg-[var(--green)]" : risiko <= 30 ? "bg-amber-400" : "bg-rose-400";

  const donePct =
    totalStories > 0 ? Math.round(((statusCounts["done"] ?? 0) / totalStories) * 100) : 0;
  const totalPoints = storyList.reduce((acc, s) => acc + (s.story_points ?? 0), 0);

  // Feature status counts
  const featureCounts = Object.fromEntries(
    FEATURE_STATUSES.map((s) => [s, featureList.filter((f) => f.status === s).length])
  ) as Record<string, number>;

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col gap-6 pb-12">
      {/* Header row */}
      <div>
        <Link
          href={`/${orgSlug}/project`}
          className="inline-flex items-center gap-1.5 text-[11px] text-[var(--ink-faint)] hover:text-[var(--btn-primary)] mb-3 transition-colors"
        >
          <ArrowLeft size={12} />
          Alle Projekte
        </Link>

        <div className="flex items-center gap-3 flex-wrap">
          {project.color && (
            <span
              className="w-4 h-4 rounded-full shrink-0 border border-white/20 shadow-sm"
              style={{ background: project.color }}
            />
          )}
          {editing ? (
            <input
              className="text-2xl font-bold text-[var(--ink)] leading-tight bg-transparent border-b border-[var(--accent-red)] outline-none w-full max-w-md"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              autoFocus
            />
          ) : (
            <h1 className="text-2xl font-bold text-[var(--ink)] leading-tight">{project.name}</h1>
          )}
          <span
            className={`text-[10px] font-semibold px-2 py-0.5 rounded-sm shrink-0 ${
              PROJECT_STATUS_COLORS[project.status] ?? "bg-[var(--paper-warm)] text-[var(--ink-mid)]"
            }`}
          >
            {PROJECT_STATUS_LABELS[project.status] ?? project.status}
          </span>
          {editing ? (
            <>
              <button
                onClick={handleSave}
                disabled={saving || !editName.trim()}
                className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-sm bg-[var(--btn-primary)] text-white disabled:opacity-50"
              >
                <Save size={12} />
                {saving ? "Speichern…" : "Speichern"}
              </button>
              <button
                onClick={() => setEditing(false)}
                className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-sm border border-[var(--paper-rule)] text-[var(--ink-mid)] hover:text-[var(--ink)]"
              >
                <X size={12} />
                Abbrechen
              </button>
            </>
          ) : (
            <button
              onClick={startEdit}
              className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-sm border border-[var(--paper-rule)] text-[var(--ink-mid)] hover:text-[var(--ink)] hover:border-[var(--ink-mid)] transition-colors"
            >
              <Pencil size={11} />
              Bearbeiten
            </button>
          )}
        </div>
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* LEFT column (2/3) */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          {/* Block 1 — Project info */}
          <SectionCard>
            <h2 className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-mid)]">
              Projektbeschreibung
            </h2>
            {editing ? (
              <textarea
                className="w-full text-sm text-[var(--ink)] leading-relaxed bg-transparent border border-[var(--paper-rule)] rounded-sm p-2 outline-none focus:border-[var(--accent-red)] resize-none"
                rows={4}
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                placeholder="Projektbeschreibung…"
              />
            ) : project.description ? (
              <p className="text-sm text-[var(--ink)] leading-relaxed">{project.description}</p>
            ) : (
              <p className="text-sm text-[var(--ink-faint)] italic">Keine Beschreibung</p>
            )}
            <div className="flex items-center gap-2 flex-wrap">
              {project.deadline && (
                <span className="flex items-center gap-1 bg-[var(--paper-warm)] rounded-sm px-2 py-1 text-xs text-[var(--ink-mid)]">
                  <CalendarDays size={11} />
                  {new Date(project.deadline).toLocaleDateString("de-DE")}
                </span>
              )}
              {project.effort && (
                <span className="flex items-center gap-1 bg-[var(--paper-warm)] rounded-sm px-2 py-1 text-xs text-[var(--ink-mid)]">
                  <Zap size={11} />
                  {EFFORT_LABELS[project.effort] ?? project.effort}
                </span>
              )}
              {project.complexity && (
                <span className="flex items-center gap-1 bg-[var(--paper-warm)] rounded-sm px-2 py-1 text-xs text-[var(--ink-mid)]">
                  <Layers size={11} />
                  {COMPLEXITY_LABELS[project.complexity] ?? project.complexity}
                </span>
              )}
              {!project.deadline && !project.effort && !project.complexity && (
                <span className="text-xs text-[var(--ink-faint)]">—</span>
              )}
            </div>
          </SectionCard>

          {/* Block 2 — User Stories */}
          <SectionCard>
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-mid)] flex items-center">
                <BookOpen size={13} className="mr-1.5" />
                User Stories
                <CountBadge n={totalStories} />
              </h2>
              <Link
                href={`/${orgSlug}/stories/board?project_id=${projectId}`}
                className="text-[11px] text-[var(--btn-primary)] hover:underline flex items-center gap-1"
              >
                Board <ExternalLink size={10} />
              </Link>
            </div>

            {totalStories > 0 ? (
              <>
                {/* Progress bar */}
                <div className="flex h-2 rounded-full overflow-hidden gap-px">
                  {STORY_STATUSES.map((s) => {
                    const pct = (statusCounts[s] / totalStories) * 100;
                    if (pct === 0) return null;
                    return (
                      <div
                        key={s}
                        className={`h-full ${STORY_STATUS_BAR[s]}`}
                        style={{ width: `${pct}%` }}
                        title={`${STORY_STATUS_LABELS[s]}: ${statusCounts[s]}`}
                      />
                    );
                  })}
                </div>

                {/* Status rows */}
                <div className="flex flex-col gap-1.5">
                  {STORY_STATUSES.map((s) => {
                    const count = statusCounts[s];
                    if (count === 0) return null;
                    return (
                      <div key={s} className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full shrink-0 ${STORY_STATUS_DOT[s]}`} />
                        <span className="text-[11px] text-[var(--ink-mid)] flex-1">
                          {STORY_STATUS_LABELS[s]}
                        </span>
                        <span className="text-[11px] font-semibold text-[var(--ink)]">{count}</span>
                      </div>
                    );
                  })}
                </div>
              </>
            ) : (
              <p className="text-sm text-[var(--ink-faint)]">Keine User Stories vorhanden.</p>
            )}
          </SectionCard>

          {/* Block 3 — Epics */}
          <SectionCard>
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-mid)] flex items-center">
                <Layers size={13} className="mr-1.5" />
                Epics
                <CountBadge n={epicList.length} />
              </h2>
              <Link
                href={`/${orgSlug}/stories/epics`}
                className="inline-flex items-center gap-1 text-[11px] text-[var(--btn-primary)] hover:underline"
              >
                <Plus size={11} />
                Neues Epic
              </Link>
            </div>

            {epicList.length === 0 ? (
              <p className="text-sm text-[var(--ink-faint)]">Keine Epics zugewiesen.</p>
            ) : (
              <div className="flex flex-col gap-1.5">
                {epicList.map((epic) => (
                  <Link
                    key={epic.id}
                    href={`/${orgSlug}/stories/epics/${epic.id}`}
                    className="flex items-center gap-2 group p-2 -mx-2 rounded-sm hover:bg-[var(--paper-warm)] transition-colors"
                  >
                    <span className="text-[12px] text-[var(--ink)] flex-1 truncate">
                      {epic.title}
                    </span>
                    <span
                      className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-sm shrink-0 ${
                        EPIC_STATUS_COLORS[epic.status] ?? "bg-[var(--paper-warm)] text-[var(--ink-mid)]"
                      }`}
                    >
                      {EPIC_STATUS_LABELS[epic.status] ?? epic.status}
                    </span>
                    <ExternalLink
                      size={11}
                      className="text-[var(--ink-faint)] opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                    />
                  </Link>
                ))}
              </div>
            )}
          </SectionCard>

          {/* Block 4 — Features */}
          <SectionCard>
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-mid)] flex items-center">
                <GitBranch size={13} className="mr-1.5" />
                Features
                <CountBadge n={featureList.length} />
              </h2>
              <Link
                href={`/${orgSlug}/stories/features/board`}
                className="text-[11px] text-[var(--btn-primary)] hover:underline flex items-center gap-1"
              >
                Board <ExternalLink size={10} />
              </Link>
            </div>

            {featureList.length === 0 ? (
              <p className="text-sm text-[var(--ink-faint)]">Keine Features vorhanden.</p>
            ) : (
              <div className="flex flex-col gap-1.5">
                {FEATURE_STATUSES.map((s) => {
                  const count = featureCounts[s];
                  if (count === 0) return null;
                  return (
                    <div key={s} className="flex items-center gap-2">
                      <span
                        className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-sm ${
                          FEATURE_STATUS_COLORS[s]
                        }`}
                      >
                        {FEATURE_STATUS_LABELS[s]}
                      </span>
                      <span className="text-[11px] font-semibold text-[var(--ink)]">{count}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </SectionCard>
        </div>

        {/* RIGHT column (1/3) */}
        <div className="flex flex-col gap-6 xl:sticky xl:top-6 xl:self-start">
          {/* Block 5 — Metrics */}
          <SectionCard>
            <h2 className="text-xs font-semibold uppercase tracking-widest text-[var(--ink-mid)] flex items-center">
              <BarChart3 size={13} className="mr-1.5" />
              Qualität &amp; Risiko
            </h2>

            <div className="flex flex-col gap-3">
              <MetricBar label="Sicherheit" value={sicherheit} color={sicherheitColor} />
              <MetricBar label="Klarheit" value={klarheit} color={klarheitColor} />
              <MetricBar label="Komplexität" value={complexityVal} color={complexityColor} />
              <MetricBar label="Risiko" value={risiko} color={risikoColor} />
            </div>

            <div className="border-t border-[var(--paper-rule)] pt-4 flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <Target size={13} className="text-[var(--ink-faint)]" />
                <span className="text-[11px] text-[var(--ink-mid)] flex-1">Story Points gesamt</span>
                <span className="text-[12px] font-bold text-[var(--ink)]">{totalPoints}</span>
              </div>
              <div className="flex items-center gap-2">
                <TrendingUp size={13} className="text-[var(--ink-faint)]" />
                <span className="text-[11px] text-[var(--ink-mid)] flex-1">Ø Qualitätsscore</span>
                <span className="text-[12px] font-bold text-[var(--ink)]">
                  {storiesWithQuality.length > 0 ? `${avgQuality}%` : "—"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 size={13} className="text-[var(--ink-faint)]" />
                <span className="text-[11px] text-[var(--ink-mid)] flex-1">Stories erledigt</span>
                <span className="text-[12px] font-bold text-[var(--ink)]">
                  {totalStories > 0 ? `${donePct}%` : "—"}
                </span>
              </div>
            </div>
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
