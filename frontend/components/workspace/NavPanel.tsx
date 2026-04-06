"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  ChevronRight,
  ChevronDown,
  Folder,
  GitBranch,
  BookOpen,
  Layers,
  TestTube,
  X,
} from "lucide-react";
import { fetcher } from "@/lib/api/client";
import type { Project, Epic, UserStory, Feature, TestCase, PaginatedResponse } from "@/types";

// ── Status color maps ──────────────────────────────────────────────────────

const PROJECT_STATUS_COLORS: Record<string, string> = {
  planning: "bg-[var(--paper-warm)] text-[var(--ink-mid)]",
  active: "bg-[rgba(82,107,94,.1)] text-[var(--green)]",
  done: "bg-[rgba(74,85,104,.06)] text-[var(--navy)]",
  archived: "bg-[var(--paper-rule2)] text-[var(--ink-faint)]",
};

const STORY_STATUS_COLORS: Record<string, string> = {
  draft: "bg-[var(--paper-warm)] text-[var(--ink-mid)]",
  in_review: "bg-[rgba(var(--btn-primary-rgb),.08)] text-[var(--btn-primary)]",
  ready: "bg-[rgba(74,85,104,.06)] text-[var(--navy)]",
  in_progress: "bg-[rgba(122,100,80,.1)] text-[var(--brown)]",
  testing: "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]",
  done: "bg-[rgba(82,107,94,.1)] text-[var(--green)]",
  archived: "bg-[var(--paper-rule2)] text-[var(--ink-faint)]",
};

const EPIC_STATUS_COLORS: Record<string, string> = {
  planning: "bg-[var(--paper-warm)] text-[var(--ink-mid)]",
  in_progress: "bg-[rgba(122,100,80,.1)] text-[var(--brown)]",
  done: "bg-[rgba(82,107,94,.1)] text-[var(--green)]",
  archived: "bg-[var(--paper-rule2)] text-[var(--ink-faint)]",
};

const FEATURE_STATUS_COLORS: Record<string, string> = {
  draft: "bg-[var(--paper-warm)] text-[var(--ink-mid)]",
  in_progress: "bg-[rgba(122,100,80,.1)] text-[var(--brown)]",
  testing: "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]",
  done: "bg-[rgba(82,107,94,.1)] text-[var(--green)]",
  archived: "bg-[var(--paper-rule2)] text-[var(--ink-faint)]",
};

const TC_RESULT_COLORS: Record<string, string> = {
  pending: "bg-[var(--paper-warm)] text-[var(--ink-mid)]",
  passed: "bg-[rgba(82,107,94,.1)] text-[var(--green)]",
  failed: "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]",
  skipped: "bg-[rgba(122,100,80,.1)] text-[var(--brown)]",
};

const PRIORITY_COLORS: Record<string, string> = {
  low: "bg-[var(--ink-faintest)]",
  medium: "bg-[var(--navy)]",
  high: "bg-[var(--brown)]",
  critical: "bg-[var(--accent-red)]",
};

// ── Label helpers ──────────────────────────────────────────────────────────

const PROJECT_STATUS_LABELS: Record<string, string> = {
  planning: "Planung",
  active: "Aktiv",
  done: "Fertig",
  archived: "Archiviert",
};

const EPIC_STATUS_LABELS: Record<string, string> = {
  planning: "Planung",
  in_progress: "In Arbeit",
  done: "Fertig",
  archived: "Archiviert",
};

const STORY_STATUS_LABELS: Record<string, string> = {
  draft: "Entwurf",
  in_review: "Überarbeitung",
  ready: "Bereit",
  in_progress: "In Arbeit",
  testing: "Test",
  done: "Fertig",
  archived: "Archiviert",
};

const FEATURE_STATUS_LABELS: Record<string, string> = {
  draft: "Entwurf",
  in_progress: "In Arbeit",
  testing: "Test",
  done: "Fertig",
  archived: "Archiviert",
};

const TC_RESULT_LABELS: Record<string, string> = {
  pending: "Ausstehend",
  passed: "Bestanden",
  failed: "Fehlgeschlagen",
  skipped: "Übersprungen",
};

// ── Small helpers ──────────────────────────────────────────────────────────

function StatusChip({ status, map }: { status: string; map: Record<string, string> }) {
  const cls = map[status] ?? "bg-[var(--paper-warm)] text-[var(--ink-mid)]";
  return (
    <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium shrink-0 ${cls}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

// ── Props ──────────────────────────────────────────────────────────────────

interface NavPanelProps {
  orgId: string;
  orgSlug: string;
  open: boolean;
  onToggle: () => void;
}

// ── Component ──────────────────────────────────────────────────────────────

export function NavPanel({ orgId, open, onToggle }: NavPanelProps) {
  // Which accordion sections are expanded (default: all)
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    () => new Set(["projects", "epics", "stories", "features", "testcases"])
  );

  // Cascade filter state
  const [filterProjectId, setFilterProjectId] = useState<string | null>(null);
  const [filterEpicId, setFilterEpicId] = useState<string | null>(null);
  const [filterStoryId, setFilterStoryId] = useState<string | null>(null);

  // Status / result filter state
  const [projectStatus, setProjectStatus] = useState("");
  const [epicStatus, setEpicStatus] = useState("");
  const [storyStatus, setStoryStatus] = useState("");
  const [featureStatus, setFeatureStatus] = useState("");
  const [tcResult, setTcResult] = useState("");

  // ── Data fetching ────────────────────────────────────────────────────────

  const projectsUrl = orgId
    ? `/api/v1/projects?org_id=${orgId}${projectStatus ? `&status=${projectStatus}` : ""}`
    : null;

  const epicsUrl = orgId
    ? `/api/v1/epics?org_id=${orgId}${filterProjectId ? `&project_id=${filterProjectId}` : ""}`
    : null;

  const storiesUrl = orgId
    ? `/api/v1/user-stories?org_id=${orgId}${filterProjectId ? `&project_id=${filterProjectId}` : ""}${filterEpicId ? `&epic_id=${filterEpicId}` : ""}`
    : null;

  const featuresUrl = orgId
    ? `/api/v1/features?org_id=${orgId}${filterProjectId ? `&project_id=${filterProjectId}` : ""}${filterStoryId ? `&story_id=${filterStoryId}` : ""}`
    : null;

  const testCasesUrl = filterStoryId
    ? `/api/v1/user-stories/${filterStoryId}/test-cases`
    : null;

  const { data: projectsData } = useSWR<PaginatedResponse<Project> | Project[]>(projectsUrl, fetcher);
  const { data: epicsData } = useSWR<PaginatedResponse<Epic> | Epic[]>(epicsUrl, fetcher);
  const { data: storiesData } = useSWR<PaginatedResponse<UserStory> | UserStory[]>(storiesUrl, fetcher);
  const { data: featuresData } = useSWR<PaginatedResponse<Feature> | Feature[]>(featuresUrl, fetcher);
  const { data: testCasesData } = useSWR<PaginatedResponse<TestCase> | TestCase[]>(testCasesUrl, fetcher);

  // Normalise paginated vs plain array responses
  const projects: Project[] = Array.isArray(projectsData)
    ? projectsData
    : (projectsData as PaginatedResponse<Project> | undefined)?.items ?? [];

  const allEpics: Epic[] = Array.isArray(epicsData)
    ? epicsData
    : (epicsData as PaginatedResponse<Epic> | undefined)?.items ?? [];

  const allStories: UserStory[] = Array.isArray(storiesData)
    ? storiesData
    : (storiesData as PaginatedResponse<UserStory> | undefined)?.items ?? [];

  const allFeatures: Feature[] = Array.isArray(featuresData)
    ? featuresData
    : (featuresData as PaginatedResponse<Feature> | undefined)?.items ?? [];

  const allTestCases: TestCase[] = Array.isArray(testCasesData)
    ? testCasesData
    : (testCasesData as PaginatedResponse<TestCase> | undefined)?.items ?? [];

  // Client-side filters
  const epics = epicStatus ? allEpics.filter(e => e.status === epicStatus) : allEpics;
  const stories = storyStatus ? allStories.filter(s => s.status === storyStatus) : allStories;
  const features = featureStatus ? allFeatures.filter(f => f.status === featureStatus) : allFeatures;
  const testCases = tcResult ? allTestCases.filter(tc => tc.result === tcResult) : allTestCases;

  // ── Helpers ──────────────────────────────────────────────────────────────

  function toggleSection(id: string) {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectProject(id: string) {
    setFilterProjectId(prev => (prev === id ? null : id));
    setFilterEpicId(null);
    setFilterStoryId(null);
  }

  function selectEpic(id: string) {
    setFilterEpicId(prev => (prev === id ? null : id));
    setFilterStoryId(null);
  }

  function selectStory(id: string) {
    setFilterStoryId(prev => (prev === id ? null : id));
  }

  const sectionIsOpen = (id: string) => expandedSections.has(id);

  // ── Closed strip (48 px) ─────────────────────────────────────────────────

  if (!open) {
    return (
      <div
        className="flex flex-col items-center py-3 gap-3 shrink-0 border-r border-[var(--paper-rule)] bg-[var(--card)]"
        style={{ width: 48 }}
      >
        <button
          onClick={onToggle}
          className="p-1.5 rounded-sm hover:bg-[var(--paper-warm)] transition-colors"
          title="Navigation öffnen"
        >
          <ChevronRight size={14} style={{ color: "var(--ink-faint)" }} />
        </button>

        <div className="w-full border-t border-[var(--paper-rule)]" />

        {[
          { icon: <Folder size={13} />, active: !!filterProjectId, title: "Projekte" },
          { icon: <GitBranch size={13} />, active: !!filterEpicId, title: "Epics" },
          { icon: <BookOpen size={13} />, active: !!filterStoryId, title: "User Stories" },
          { icon: <Layers size={13} />, active: false, title: "Features" },
          { icon: <TestTube size={13} />, active: false, title: "Testfälle" },
        ].map((item, i) => (
          <div key={i} className="relative flex items-center justify-center">
            <button
              onClick={onToggle}
              title={item.title}
              className="p-1.5 rounded-sm hover:bg-[var(--paper-warm)] transition-colors"
              style={{ color: item.active ? "var(--accent-red)" : "var(--ink-faint)" }}
            >
              {item.icon}
            </button>
            {item.active && (
              <span
                className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-[var(--accent-red)]"
              />
            )}
          </div>
        ))}
      </div>
    );
  }

  // ── Open panel (260 px) ──────────────────────────────────────────────────

  return (
    <div
      className="flex flex-col shrink-0 border-r border-[var(--paper-rule)] bg-[var(--card)] overflow-hidden"
      style={{ width: 260 }}
    >
      {/* Panel header */}
      <div
        className="flex items-center justify-between px-3 py-2 border-b border-[var(--paper-rule)]"
        style={{ background: "var(--paper-warm)" }}
      >
        <span
          className="text-xs font-bold uppercase tracking-wide text-[var(--ink-faint)]"
          style={{ fontFamily: "var(--font-body)" }}
        >
          Navigation
        </span>
        <button
          onClick={onToggle}
          className="p-1 rounded-sm hover:bg-[var(--paper-warm)] transition-colors"
          title="Navigation schließen"
        >
          <ChevronRight
            size={13}
            style={{ color: "var(--ink-faint)", transform: "rotate(180deg)" }}
          />
        </button>
      </div>

      {/* Scrollable sections */}
      <div className="flex-1 overflow-y-auto">

        {/* ── Projekte ── */}
        <Section
          id="projects"
          label="Projekte"
          icon={<Folder size={12} />}
          count={projects.length}
          isOpen={sectionIsOpen("projects")}
          onToggle={() => toggleSection("projects")}
          hasSelection={!!filterProjectId}
          onClearSelection={() => { setFilterProjectId(null); setFilterEpicId(null); setFilterStoryId(null); }}
        >
          <select
            value={projectStatus}
            onChange={e => setProjectStatus(e.target.value)}
            className="text-xs px-2 py-1 bg-[var(--paper)] border border-[var(--paper-rule)] rounded-sm outline-none text-[var(--ink-mid)] mb-1"
            style={{ width: "calc(100% - 24px)", marginLeft: 12 }}
          >
            <option value="">Alle Status</option>
            <option value="planning">Planung</option>
            <option value="active">Aktiv</option>
            <option value="done">Fertig</option>
            <option value="archived">Archiviert</option>
          </select>

          <div className="max-h-48 overflow-y-auto">
            {projects.length === 0 && (
              <p className="px-3 py-2 text-xs text-[var(--ink-faint)]">Keine Projekte</p>
            )}
            {projects.map(p => (
              <button
                key={p.id}
                onClick={() => selectProject(p.id)}
                className={`w-full text-left px-3 py-1.5 text-xs cursor-pointer flex items-center gap-2 transition-colors ${
                  filterProjectId === p.id
                    ? "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]"
                    : "hover:bg-[var(--paper-warm)]"
                }`}
              >
                {p.color && (
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ background: p.color }}
                  />
                )}
                <span className="flex-1 truncate">{p.name}</span>
                <StatusChip status={p.status} map={PROJECT_STATUS_COLORS} />
              </button>
            ))}
          </div>
        </Section>

        {/* ── Epics ── */}
        <Section
          id="epics"
          label="Epics"
          icon={<GitBranch size={12} />}
          count={epics.length}
          isOpen={sectionIsOpen("epics")}
          onToggle={() => toggleSection("epics")}
          hasSelection={!!filterEpicId}
          onClearSelection={() => { setFilterEpicId(null); setFilterStoryId(null); }}
        >
          <select
            value={epicStatus}
            onChange={e => setEpicStatus(e.target.value)}
            className="text-xs px-2 py-1 bg-[var(--paper)] border border-[var(--paper-rule)] rounded-sm outline-none text-[var(--ink-mid)] mb-1"
            style={{ width: "calc(100% - 24px)", marginLeft: 12 }}
          >
            <option value="">Alle Status</option>
            <option value="planning">Planung</option>
            <option value="in_progress">In Arbeit</option>
            <option value="done">Fertig</option>
            <option value="archived">Archiviert</option>
          </select>

          {filterProjectId && (
            <p className="px-3 pb-1 text-[10px] text-[var(--ink-faint)] italic">
              Gefiltert nach Projekt
            </p>
          )}

          <div className="max-h-48 overflow-y-auto">
            {epics.length === 0 && (
              <p className="px-3 py-2 text-xs text-[var(--ink-faint)]">Keine Epics</p>
            )}
            {epics.map(e => (
              <button
                key={e.id}
                onClick={() => selectEpic(e.id)}
                className={`w-full text-left px-3 py-1.5 text-xs cursor-pointer flex items-center gap-2 transition-colors ${
                  filterEpicId === e.id
                    ? "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]"
                    : "hover:bg-[var(--paper-warm)]"
                }`}
              >
                <span className="flex-1 truncate">{e.title}</span>
                <StatusChip status={e.status} map={EPIC_STATUS_COLORS} />
              </button>
            ))}
          </div>
        </Section>

        {/* ── User Stories ── */}
        <Section
          id="stories"
          label="User Stories"
          icon={<BookOpen size={12} />}
          count={stories.length}
          isOpen={sectionIsOpen("stories")}
          onToggle={() => toggleSection("stories")}
          hasSelection={!!filterStoryId}
          onClearSelection={() => setFilterStoryId(null)}
        >
          <select
            value={storyStatus}
            onChange={e => setStoryStatus(e.target.value)}
            className="text-xs px-2 py-1 bg-[var(--paper)] border border-[var(--paper-rule)] rounded-sm outline-none text-[var(--ink-mid)] mb-1"
            style={{ width: "calc(100% - 24px)", marginLeft: 12 }}
          >
            <option value="">Alle Status</option>
            <option value="draft">Entwurf</option>
            <option value="in_review">Überarbeitung</option>
            <option value="ready">Bereit</option>
            <option value="in_progress">In Arbeit</option>
            <option value="testing">Test</option>
            <option value="done">Fertig</option>
            <option value="archived">Archiviert</option>
          </select>

          <div className="max-h-48 overflow-y-auto">
            {stories.length === 0 && (
              <p className="px-3 py-2 text-xs text-[var(--ink-faint)]">Keine Stories</p>
            )}
            {stories.map(s => (
              <button
                key={s.id}
                onClick={() => selectStory(s.id)}
                className={`w-full text-left px-3 py-1.5 text-xs cursor-pointer flex items-center gap-2 transition-colors ${
                  filterStoryId === s.id
                    ? "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]"
                    : "hover:bg-[var(--paper-warm)]"
                }`}
              >
                <span className="flex-1 truncate">{s.title}</span>
                <span
                  className={`w-2 h-2 rounded-full shrink-0 ${PRIORITY_COLORS[s.priority] ?? "bg-[var(--ink-faintest)]"}`}
                  title={s.priority}
                />
                <StatusChip status={s.status} map={STORY_STATUS_COLORS} />
              </button>
            ))}
          </div>
        </Section>

        {/* ── Features ── */}
        <Section
          id="features"
          label="Features"
          icon={<Layers size={12} />}
          count={features.length}
          isOpen={sectionIsOpen("features")}
          onToggle={() => toggleSection("features")}
          hasSelection={false}
          onClearSelection={() => {}}
        >
          <select
            value={featureStatus}
            onChange={e => setFeatureStatus(e.target.value)}
            className="text-xs px-2 py-1 bg-[var(--paper)] border border-[var(--paper-rule)] rounded-sm outline-none text-[var(--ink-mid)] mb-1"
            style={{ width: "calc(100% - 24px)", marginLeft: 12 }}
          >
            <option value="">Alle Status</option>
            <option value="draft">Entwurf</option>
            <option value="in_progress">In Arbeit</option>
            <option value="testing">Test</option>
            <option value="done">Fertig</option>
            <option value="archived">Archiviert</option>
          </select>

          <div className="max-h-48 overflow-y-auto">
            {features.length === 0 && (
              <p className="px-3 py-2 text-xs text-[var(--ink-faint)]">Keine Features</p>
            )}
            {features.map(f => (
              <div
                key={f.id}
                className="px-3 py-1.5 text-xs cursor-default flex items-start gap-2 hover:bg-[var(--paper-warm)] transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <p className="truncate">{f.title}</p>
                  {f.story_title && (
                    <p className="text-[10px] text-[var(--ink-faint)] truncate">{f.story_title}</p>
                  )}
                </div>
                <StatusChip status={f.status} map={FEATURE_STATUS_COLORS} />
              </div>
            ))}
          </div>
        </Section>

        {/* ── Testfälle ── */}
        <Section
          id="testcases"
          label="Testfälle"
          icon={<TestTube size={12} />}
          count={testCases.length}
          isOpen={sectionIsOpen("testcases")}
          onToggle={() => toggleSection("testcases")}
          hasSelection={false}
          onClearSelection={() => {}}
        >
          {!filterStoryId ? (
            <p className="px-3 py-2 text-xs text-[var(--ink-faint)] italic">Story auswählen</p>
          ) : (
            <>
              <select
                value={tcResult}
                onChange={e => setTcResult(e.target.value)}
                className="text-xs px-2 py-1 bg-[var(--paper)] border border-[var(--paper-rule)] rounded-sm outline-none text-[var(--ink-mid)] mb-1"
                style={{ width: "calc(100% - 24px)", marginLeft: 12 }}
              >
                <option value="">Alle Ergebnisse</option>
                <option value="pending">Ausstehend</option>
                <option value="passed">Bestanden</option>
                <option value="failed">Fehlgeschlagen</option>
                <option value="skipped">Übersprungen</option>
              </select>

              <div className="max-h-48 overflow-y-auto">
                {testCases.length === 0 && (
                  <p className="px-3 py-2 text-xs text-[var(--ink-faint)]">Keine Testfälle</p>
                )}
                {testCases.map(tc => (
                  <div
                    key={tc.id}
                    className="px-3 py-1.5 text-xs flex items-center gap-2 hover:bg-[var(--paper-warm)] transition-colors"
                  >
                    <span className="flex-1 truncate">{tc.title}</span>
                    <span
                      className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium shrink-0 ${TC_RESULT_COLORS[tc.result] ?? "bg-[var(--paper-warm)] text-[var(--ink-mid)]"}`}
                    >
                      {TC_RESULT_LABELS[tc.result] ?? tc.result}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </Section>
      </div>
    </div>
  );
}

// ── Section sub-component ──────────────────────────────────────────────────

interface SectionProps {
  id: string;
  label: string;
  icon: React.ReactNode;
  count: number;
  isOpen: boolean;
  onToggle: () => void;
  hasSelection: boolean;
  onClearSelection: () => void;
  children: React.ReactNode;
}

function Section({
  label,
  icon,
  count,
  isOpen,
  onToggle,
  hasSelection,
  onClearSelection,
  children,
}: SectionProps) {
  return (
    <div className="border-b border-[var(--paper-rule)]">
      {/* Header */}
      <div
        className="px-3 py-2 flex items-center gap-2 cursor-pointer hover:bg-[var(--paper-warm)] transition-colors"
        onClick={onToggle}
      >
        <span style={{ color: "var(--ink-faint)" }}>
          {isOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        </span>
        <span style={{ color: "var(--ink-faint)" }}>{icon}</span>
        <span
          className="flex-1 text-xs font-bold uppercase tracking-wide text-[var(--ink-faint)]"
          style={{ fontFamily: "Architects Daughter, var(--font-body)" }}
        >
          {label}
        </span>
        <span className="text-[10px] px-1.5 py-0.5 bg-[var(--paper-warm)] text-[var(--ink-mid)] rounded-full font-bold">
          {count}
        </span>
        {hasSelection && (
          <button
            onClick={e => { e.stopPropagation(); onClearSelection(); }}
            className="p-0.5 rounded-sm hover:bg-[var(--paper-rule)] transition-colors"
            title="Filter zurücksetzen"
          >
            <X size={10} style={{ color: "var(--ink-faint)" }} />
          </button>
        )}
      </div>

      {/* Body */}
      {isOpen && <div>{children}</div>}
    </div>
  );
}
