"use client";

import { useState, useRef } from "react";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { Feature, FeatureStatus, StoryPriority } from "@/types";
import Link from "next/link";
import { LayoutList, Columns, Plus, Layers, GitBranch, BookOpen } from "lucide-react";

const COLUMNS: { status: FeatureStatus; label: string; color: string; dot: string; dropHighlight: string }[] = [
  { status: "draft",       label: "Entwurf",   color: "bg-slate-100 text-slate-700 border-slate-200",   dot: "bg-slate-400",  dropHighlight: "ring-2 ring-slate-400 bg-slate-100" },
  { status: "in_progress", label: "In Arbeit", color: "bg-amber-50 text-amber-800 border-amber-200",    dot: "bg-amber-500",  dropHighlight: "ring-2 ring-amber-400 bg-amber-50" },
  { status: "testing",     label: "Test",      color: "bg-orange-50 text-orange-800 border-orange-200", dot: "bg-orange-500", dropHighlight: "ring-2 ring-orange-400 bg-orange-50" },
  { status: "done",        label: "Fertig",    color: "bg-green-50 text-green-800 border-green-200",    dot: "bg-green-500",  dropHighlight: "ring-2 ring-green-400 bg-green-50" },
  { status: "archived",    label: "Archiviert",color: "bg-gray-100 text-gray-500 border-gray-200",      dot: "bg-gray-400",   dropHighlight: "ring-2 ring-gray-400 bg-gray-100" },
];

const PRIORITY_COLORS: Record<StoryPriority, string> = {
  low: "bg-slate-100 text-slate-500", medium: "bg-blue-100 text-blue-600",
  high: "bg-amber-100 text-amber-700", critical: "bg-red-100 text-red-600",
};

const PRIORITY_LABELS: Record<StoryPriority, string> = {
  low: "Niedrig", medium: "Mittel", high: "Hoch", critical: "Kritisch",
};

function FeatureCard({
  feature,
  dragging,
  onDragStart,
  onDragEnd,
}: {
  feature: Feature;
  dragging: boolean;
  onDragStart: (id: string) => void;
  onDragEnd: () => void;
}) {
  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", feature.id);
        onDragStart(feature.id);
      }}
      onDragEnd={onDragEnd}
      className={`bg-white rounded-xl border border-slate-200 p-3.5 shadow-sm hover:shadow-md hover:border-brand-300 transition-all cursor-grab active:cursor-grabbing select-none ${dragging ? "opacity-40 scale-95" : ""}`}
    >
      <p className="text-sm font-semibold text-slate-800 line-clamp-2 mb-2.5 leading-snug">
        {feature.title}
      </p>
      {feature.description && (
        <p className="text-xs text-slate-400 line-clamp-2 mb-2.5 leading-relaxed">{feature.description}</p>
      )}
      <div className="flex flex-wrap items-center gap-1">
        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${PRIORITY_COLORS[feature.priority]}`}>
          {PRIORITY_LABELS[feature.priority]}
        </span>
        {feature.story_points !== null && (
          <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 text-xs font-medium">
            {feature.story_points} SP
          </span>
        )}
      </div>
      {feature.story_title && (
        <div className="flex items-center gap-1 mt-2 pt-2 border-t border-slate-100">
          <BookOpen size={10} className="text-slate-400 shrink-0" />
          <span className="text-xs text-slate-400 truncate">{feature.story_title}</span>
        </div>
      )}
    </div>
  );
}

export default function FeaturesBoardPage({ params }: { params: { org: string } }) {
  const { org } = useOrg(params.org);
  const [dragId, setDragId] = useState<string | null>(null);
  const [dragOverStatus, setDragOverStatus] = useState<FeatureStatus | null>(null);
  const dragCounters = useRef<Record<string, number>>({});
  const [showNewForm, setShowNewForm] = useState(false);

  const { data: features, isLoading, error, mutate } = useSWR<Feature[]>(
    org ? `/api/v1/features?org_id=${org.id}` : null,
    fetcher
  );

  async function handleStatusChange(featureId: string, newStatus: FeatureStatus) {
    mutate(
      (prev) => prev?.map((f) => f.id === featureId ? { ...f, status: newStatus } : f),
      false
    );
    try {
      await apiRequest(`/api/v1/features/${featureId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
    } finally {
      await mutate();
    }
  }

  function handleDragOver(e: React.DragEvent, s: FeatureStatus) {
    e.preventDefault(); e.dataTransfer.dropEffect = "move"; setDragOverStatus(s);
  }
  function handleDragEnter(e: React.DragEvent, s: FeatureStatus) {
    e.preventDefault();
    dragCounters.current[s] = (dragCounters.current[s] ?? 0) + 1;
    setDragOverStatus(s);
  }
  function handleDragLeave(e: React.DragEvent, s: FeatureStatus) {
    dragCounters.current[s] = (dragCounters.current[s] ?? 1) - 1;
    if (dragCounters.current[s] <= 0) { dragCounters.current[s] = 0; if (dragOverStatus === s) setDragOverStatus(null); }
  }
  async function handleDrop(e: React.DragEvent, s: FeatureStatus) {
    e.preventDefault(); dragCounters.current = {}; setDragOverStatus(null);
    const id = e.dataTransfer.getData("text/plain");
    if (!id) return;
    const feature = features?.find((f) => f.id === id);
    if (!feature || feature.status === s) return;
    await handleStatusChange(id, s);
  }

  const byStatus = (s: FeatureStatus) => (features ?? []).filter((f) => f.status === s);
  const total = features?.length ?? 0;

  return (
    <div className="flex flex-col h-full space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Features</h1>
          {total > 0 && <p className="text-slate-500 mt-0.5 text-sm">{total} Features</p>}
        </div>
        <button
          onClick={() => setShowNewForm(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          Neues Feature
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-200 shrink-0 overflow-x-auto">
        <Link href={`/${params.org}/stories/list`} className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-slate-500 hover:text-slate-700 transition-colors whitespace-nowrap">
          <LayoutList size={15} /> Liste
        </Link>
        <Link href={`/${params.org}/stories/board`} className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-slate-500 hover:text-slate-700 transition-colors whitespace-nowrap">
          <Columns size={15} /> Board
        </Link>
        <span className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-brand-600 text-brand-600 whitespace-nowrap">
          <Layers size={15} /> Features
        </span>
        <Link href={`/${params.org}/stories/epics/board`} className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-slate-500 hover:text-slate-700 transition-colors whitespace-nowrap">
          <GitBranch size={15} /> Epics
        </Link>
      </div>

      {/* New Feature Inline Form */}
      {showNewForm && org && (
        <NewFeatureForm orgId={org.id} onSaved={() => { void mutate(); setShowNewForm(false); }} onCancel={() => setShowNewForm(false)} />
      )}

      {isLoading && <div className="flex items-center justify-center py-16"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500" /></div>}
      {error && <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">Fehler beim Laden.</div>}

      {!isLoading && !error && features && features.length === 0 && !showNewForm && (
        <div className="text-center py-16 bg-white rounded-xl border border-slate-200">
          <div className="text-4xl mb-4">🧩</div>
          <h3 className="text-lg font-semibold text-slate-700 mb-2">Noch keine Features</h3>
          <p className="text-slate-400 mb-6 text-sm">Features sind Teilaufgaben einer User Story.</p>
          <button onClick={() => setShowNewForm(true)} className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-sm font-medium transition-colors">
            <Plus size={16} /> Erstes Feature erstellen
          </button>
        </div>
      )}

      {!isLoading && !error && features && features.length > 0 && (
        <div className="flex gap-3 overflow-x-auto pb-4 -mx-4 px-4 md:mx-0 md:px-0 flex-1">
          {COLUMNS.map((col) => {
            const colItems = byStatus(col.status);
            const isOver = dragOverStatus === col.status;
            return (
              <div key={col.status} className="flex flex-col min-w-[240px] w-[240px] shrink-0">
                <div className={`flex items-center justify-between px-3 py-2.5 rounded-t-xl border-x border-t ${col.color}`}>
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full shrink-0 ${col.dot}`} />
                    <span className="text-xs font-semibold uppercase tracking-wide">{col.label}</span>
                  </div>
                  <span className="text-xs font-bold opacity-70">{colItems.length}</span>
                </div>
                <div
                  onDragOver={(e) => handleDragOver(e, col.status)}
                  onDragEnter={(e) => handleDragEnter(e, col.status)}
                  onDragLeave={(e) => handleDragLeave(e, col.status)}
                  onDrop={(e) => void handleDrop(e, col.status)}
                  className={`flex-1 rounded-b-xl border border-slate-200 p-2 space-y-2 min-h-[120px] transition-all ${isOver ? col.dropHighlight : "bg-slate-50/60"}`}
                >
                  {isOver && dragId && <div className="border-2 border-dashed border-current rounded-xl h-12 opacity-40" />}
                  {colItems.length === 0 && !isOver && <p className="text-xs text-slate-400 text-center py-8">Keine Features</p>}
                  {colItems.map((f) => (
                    <FeatureCard key={f.id} feature={f} dragging={dragId === f.id}
                      onDragStart={(id) => { setDragId(id); dragCounters.current = {}; }}
                      onDragEnd={() => { setDragId(null); setDragOverStatus(null); dragCounters.current = {}; }}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {dragId && (
        <p className="fixed bottom-4 left-1/2 -translate-x-1/2 text-xs bg-slate-800 text-white px-3 py-1.5 rounded-full shadow-lg pointer-events-none z-50">
          Feature in eine andere Spalte ziehen
        </p>
      )}
    </div>
  );
}

function NewFeatureForm({ orgId, onSaved, onCancel }: { orgId: string; onSaved: () => void; onCancel: () => void }) {
  const { data: stories } = useSWR<import("@/types").UserStory[]>(`/api/v1/user-stories?org_id=${orgId}`, fetcher);
  const [title, setTitle] = useState("");
  const [storyId, setStoryId] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !storyId) return;
    setSaving(true);
    try {
      await apiRequest(`/api/v1/features?org_id=${orgId}`, {
        method: "POST",
        body: JSON.stringify({ title, story_id: storyId }),
      });
      onSaved();
    } catch { /* ignore */ } finally { setSaving(false); }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="bg-white rounded-xl border border-brand-200 p-4 space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-slate-700 mb-1">Titel *</label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Feature-Titel" className="w-full px-3 py-1.5 text-sm border border-slate-300 rounded-lg outline-none focus:border-brand-400 bg-white" />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-700 mb-1">User Story *</label>
          <select value={storyId} onChange={(e) => setStoryId(e.target.value)} className="w-full px-3 py-1.5 text-sm border border-slate-300 rounded-lg outline-none focus:border-brand-400 bg-white">
            <option value="">Story wählen…</option>
            {stories?.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
          </select>
        </div>
      </div>
      <div className="flex gap-2">
        <button type="submit" disabled={saving || !title.trim() || !storyId} className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-400 text-white rounded-lg text-xs font-medium transition-colors">
          <Plus size={12} /> Erstellen
        </button>
        <button type="button" onClick={onCancel} className="px-3 py-1.5 border border-slate-300 text-slate-600 hover:bg-slate-50 rounded-lg text-xs font-medium transition-colors">Abbrechen</button>
      </div>
    </form>
  );
}
