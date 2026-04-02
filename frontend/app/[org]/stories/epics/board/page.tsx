"use client";

import { use, useState, useRef } from "react";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { Epic, EpicStatus } from "@/types";
import Link from "next/link";
import { LayoutList, Columns, Plus, Layers, GitBranch } from "lucide-react";
import { ProjectSelector } from "@/components/stories/ProjectSelector";

const COLUMNS: { status: EpicStatus; label: string; color: string; dot: string; dropHighlight: string }[] = [
  { status: "planning",    label: "Planung",    color: "bg-[var(--paper-warm)] text-[var(--ink-mid)] border-[var(--paper-rule)]",                        dot: "bg-[var(--ink-faintest)]",  dropHighlight: "ring-2 ring-[var(--ink-faint)] bg-[var(--paper-warm)]" },
  { status: "in_progress", label: "In Arbeit",  color: "bg-[rgba(122,100,80,.1)] text-[var(--brown)] border-[rgba(122,100,80,.3)]",  dot: "bg-[var(--brown)]",  dropHighlight: "ring-2 ring-[var(--brown)] bg-[rgba(122,100,80,.1)]" },
  { status: "done",        label: "Fertig",     color: "bg-[rgba(82,107,94,.1)] text-[var(--green)] border-[rgba(82,107,94,.3)]",  dot: "bg-[var(--green)]",  dropHighlight: "ring-2 ring-[var(--green)] bg-[rgba(82,107,94,.1)]" },
  { status: "archived",    label: "Archiviert", color: "bg-[var(--paper-warm)] text-[var(--ink-faint)] border-[var(--paper-rule)]",                        dot: "bg-[var(--ink-faintest)]",  dropHighlight: "ring-2 ring-[var(--ink-faint)] bg-[var(--paper-warm)]" },
];

function EpicCard({ epic, dragging, onDragStart, onDragEnd }: {
  epic: Epic; dragging: boolean; onDragStart: (id: string) => void; onDragEnd: () => void;
}) {
  return (
    <div
      draggable
      onDragStart={(e) => { e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", epic.id); onDragStart(epic.id); }}
      onDragEnd={onDragEnd}
      className={`bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-3.5 hover:border-[rgba(var(--accent-red-rgb),.3)] transition-all cursor-grab active:cursor-grabbing select-none ${dragging ? "opacity-40 scale-95" : ""}`}
    >
      <p className="text-sm font-semibold text-[var(--ink)] line-clamp-2 mb-1.5 leading-snug">{epic.title}</p>
      {epic.description && <p className="text-xs text-[var(--ink-faint)] line-clamp-2 leading-relaxed">{epic.description}</p>}
    </div>
  );
}

export default function EpicsBoardPage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { org } = useOrg(resolvedParams.org);
  const [dragId, setDragId] = useState<string | null>(null);
  const [dragOverStatus, setDragOverStatus] = useState<EpicStatus | null>(null);
  const dragCounters = useRef<Record<string, number>>({});
  const [showNewForm, setShowNewForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [projectFilter, setProjectFilter] = useState<string | null>(null);

  const { data: epics, isLoading, error, mutate } = useSWR<Epic[]>(
    org ? `/api/v1/epics?org_id=${org.id}${projectFilter ? `&project_id=${projectFilter}` : ""}` : null,
    fetcher
  );

  async function handleStatusChange(epicId: string, newStatus: EpicStatus) {
    mutate((prev) => prev?.map((e) => e.id === epicId ? { ...e, status: newStatus } : e), false);
    try {
      await apiRequest(`/api/v1/epics/${epicId}`, { method: "PATCH", body: JSON.stringify({ status: newStatus }) });
    } finally { await mutate(); }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newTitle.trim() || !org) return;
    setSaving(true);
    try {
      await apiRequest(`/api/v1/epics?org_id=${org.id}`, { method: "POST", body: JSON.stringify({ title: newTitle }) });
      await mutate();
      setNewTitle(""); setShowNewForm(false);
    } catch { /* ignore */ } finally { setSaving(false); }
  }

  function handleDragOver(e: React.DragEvent, s: EpicStatus) { e.preventDefault(); e.dataTransfer.dropEffect = "move"; setDragOverStatus(s); }
  function handleDragEnter(e: React.DragEvent, s: EpicStatus) { e.preventDefault(); dragCounters.current[s] = (dragCounters.current[s] ?? 0) + 1; setDragOverStatus(s); }
  function handleDragLeave(e: React.DragEvent, s: EpicStatus) {
    dragCounters.current[s] = (dragCounters.current[s] ?? 1) - 1;
    if (dragCounters.current[s] <= 0) { dragCounters.current[s] = 0; if (dragOverStatus === s) setDragOverStatus(null); }
  }
  async function handleDrop(e: React.DragEvent, s: EpicStatus) {
    e.preventDefault(); dragCounters.current = {}; setDragOverStatus(null);
    const id = e.dataTransfer.getData("text/plain");
    if (!id) return;
    const epic = epics?.find((ep) => ep.id === id);
    if (!epic || epic.status === s) return;
    await handleStatusChange(id, s);
  }

  const byStatus = (s: EpicStatus) => (epics ?? []).filter((ep) => ep.status === s);
  const total = epics?.length ?? 0;

  return (
    <div className="flex flex-col h-full space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-[var(--ink)]">Epics</h1>
          {total > 0 && <p className="text-[var(--ink-faint)] mt-0.5 text-sm">{total} Epics</p>}
        </div>
        <div className="flex items-center gap-3">
          {org && (
            <div className="w-44">
              <ProjectSelector orgId={org.id} value={projectFilter} onChange={setProjectFilter} label="" />
            </div>
          )}
          <button onClick={() => setShowNewForm(true)} className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--accent-red)] hover:bg-[var(--accent-red)] text-white rounded-sm text-sm font-medium transition-colors">
            <Plus size={16} /> Neues Epic
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--paper-rule)] shrink-0 overflow-x-auto">
        <Link href={`/${resolvedParams.org}/stories/list`} className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-[var(--ink-faint)] hover:text-[var(--ink-mid)] transition-colors whitespace-nowrap"><LayoutList size={15} /> Liste</Link>
        <Link href={`/${resolvedParams.org}/stories/board`} className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-[var(--ink-faint)] hover:text-[var(--ink-mid)] transition-colors whitespace-nowrap"><Columns size={15} /> Board</Link>
        <Link href={`/${resolvedParams.org}/stories/features/board`} className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-[var(--ink-faint)] hover:text-[var(--ink-mid)] transition-colors whitespace-nowrap"><Layers size={15} /> Features</Link>
        <span className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-[var(--accent-red)] text-[var(--accent-red)] whitespace-nowrap"><GitBranch size={15} /> Epics</span>
      </div>

      {showNewForm && (
        <form onSubmit={(e) => void handleCreate(e)} className="bg-[var(--card)] rounded-sm border border-[rgba(var(--accent-red-rgb),.3)] p-4 flex gap-3">
          <input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="Epic-Titel" className="flex-1 px-3 py-1.5 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] bg-[var(--card)]" />
          <button type="submit" disabled={saving || !newTitle.trim()} className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--accent-red)] hover:bg-[var(--accent-red)] disabled:bg-[var(--ink-faintest)] text-white rounded-sm text-xs font-medium transition-colors"><Plus size={12} /> Erstellen</button>
          <button type="button" onClick={() => setShowNewForm(false)} className="px-3 py-1.5 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--card)] rounded-sm text-xs font-medium transition-colors">Abbrechen</button>
        </form>
      )}

      {isLoading && <div className="flex items-center justify-center py-16"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--accent-red)]" /></div>}
      {error && <div className="bg-[rgba(var(--accent-red-rgb),.08)] border border-[rgba(var(--accent-red-rgb),.3)] rounded-sm p-4 text-[var(--accent-red)] text-sm">Fehler beim Laden.</div>}

      {!isLoading && !error && epics && epics.length === 0 && !showNewForm && (
        <div className="text-center py-16 bg-[var(--card)] rounded-sm border border-[var(--paper-rule)]">
          <div className="text-4xl mb-4">🗺️</div>
          <h3 className="text-lg font-semibold text-[var(--ink-mid)] mb-2">Noch keine Epics</h3>
          <p className="text-[var(--ink-faint)] mb-6 text-sm">Epics bündeln verwandte User Stories.</p>
          <button onClick={() => setShowNewForm(true)} className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--accent-red)] hover:bg-[var(--accent-red)] text-white rounded-sm text-sm font-medium transition-colors">
            <Plus size={16} /> Erstes Epic erstellen
          </button>
        </div>
      )}

      {!isLoading && !error && epics && epics.length > 0 && (
        <div className="flex gap-3 overflow-x-auto pb-4 -mx-4 px-4 md:mx-0 md:px-0 flex-1">
          {COLUMNS.map((col) => {
            const colItems = byStatus(col.status);
            const isOver = dragOverStatus === col.status;
            return (
              <div key={col.status} className="flex flex-col min-w-[240px] w-[240px] shrink-0">
                <div className={`flex items-center justify-between px-3 py-2.5 rounded-t-sm border-x border-t ${col.color}`}>
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
                  className={`flex-1 rounded-b-sm border border-[var(--paper-rule)] p-2 space-y-2 min-h-[120px] transition-all ${isOver ? col.dropHighlight : "bg-[var(--card)]"}`}
                >
                  {isOver && dragId && <div className="border-2 border-dashed border-current rounded-sm h-12 opacity-40" />}
                  {colItems.length === 0 && !isOver && <p className="text-xs text-[var(--ink-faint)] text-center py-8">Keine Epics</p>}
                  {colItems.map((ep) => (
                    <EpicCard key={ep.id} epic={ep} dragging={dragId === ep.id}
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
        <p className="fixed bottom-4 left-1/2 -translate-x-1/2 text-xs bg-[var(--ink)] text-white px-3 py-1.5 rounded-full pointer-events-none z-50">
          Epic in eine andere Spalte ziehen
        </p>
      )}
    </div>
  );
}
