"use client";

import { use, useState, useRef } from "react";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { Epic, EpicStatus } from "@/types";
import Link from "next/link";
import { LayoutList, Columns, Plus, Layers, GitBranch } from "lucide-react";

const COLUMNS: { status: EpicStatus; label: string; color: string; dot: string; dropHighlight: string }[] = [
  { status: "planning",    label: "Planung",    color: "bg-[#f7f4ee] text-[#5a5040] border-[#e2ddd4]",                        dot: "bg-[#cec8bc]",  dropHighlight: "ring-2 ring-[#a09080] bg-[#f7f4ee]" },
  { status: "in_progress", label: "In Arbeit",  color: "bg-[rgba(122,100,80,.1)] text-[#7a6450] border-[rgba(122,100,80,.3)]",  dot: "bg-[#7a6450]",  dropHighlight: "ring-2 ring-[#7a6450] bg-[rgba(122,100,80,.1)]" },
  { status: "done",        label: "Fertig",     color: "bg-[rgba(82,107,94,.1)] text-[#526b5e] border-[rgba(82,107,94,.3)]",  dot: "bg-[#526b5e]",  dropHighlight: "ring-2 ring-[#526b5e] bg-[rgba(82,107,94,.1)]" },
  { status: "archived",    label: "Archiviert", color: "bg-[#f7f4ee] text-[#a09080] border-[#e2ddd4]",                        dot: "bg-[#cec8bc]",  dropHighlight: "ring-2 ring-[#a09080] bg-[#f7f4ee]" },
];

function EpicCard({ epic, dragging, onDragStart, onDragEnd }: {
  epic: Epic; dragging: boolean; onDragStart: (id: string) => void; onDragEnd: () => void;
}) {
  return (
    <div
      draggable
      onDragStart={(e) => { e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", epic.id); onDragStart(epic.id); }}
      onDragEnd={onDragEnd}
      className={`bg-[#faf9f6] rounded-sm border border-[#e2ddd4] p-3.5 hover:border-[rgba(139,94,82,.3)] transition-all cursor-grab active:cursor-grabbing select-none ${dragging ? "opacity-40 scale-95" : ""}`}
    >
      <p className="text-sm font-semibold text-[#1c1810] line-clamp-2 mb-1.5 leading-snug">{epic.title}</p>
      {epic.description && <p className="text-xs text-[#a09080] line-clamp-2 leading-relaxed">{epic.description}</p>}
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

  const { data: epics, isLoading, error, mutate } = useSWR<Epic[]>(
    org ? `/api/v1/epics?org_id=${org.id}` : null,
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
          <h1 className="text-2xl font-bold text-[#1c1810]">Epics</h1>
          {total > 0 && <p className="text-[#a09080] mt-0.5 text-sm">{total} Epics</p>}
        </div>
        <button onClick={() => setShowNewForm(true)} className="inline-flex items-center gap-2 px-4 py-2 bg-[#8b5e52] hover:bg-[#8b5e52] text-white rounded-sm text-sm font-medium transition-colors">
          <Plus size={16} /> Neues Epic
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[#e2ddd4] shrink-0 overflow-x-auto">
        <Link href={`/${resolvedParams.org}/stories/list`} className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-[#a09080] hover:text-[#5a5040] transition-colors whitespace-nowrap"><LayoutList size={15} /> Liste</Link>
        <Link href={`/${resolvedParams.org}/stories/board`} className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-[#a09080] hover:text-[#5a5040] transition-colors whitespace-nowrap"><Columns size={15} /> Board</Link>
        <Link href={`/${resolvedParams.org}/stories/features/board`} className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-[#a09080] hover:text-[#5a5040] transition-colors whitespace-nowrap"><Layers size={15} /> Features</Link>
        <span className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-[#8b5e52] text-[#8b5e52] whitespace-nowrap"><GitBranch size={15} /> Epics</span>
      </div>

      {showNewForm && (
        <form onSubmit={(e) => void handleCreate(e)} className="bg-[#faf9f6] rounded-sm border border-[rgba(139,94,82,.3)] p-4 flex gap-3">
          <input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="Epic-Titel" className="flex-1 px-3 py-1.5 text-sm border border-[#cec8bc] rounded-sm outline-none focus:border-[#8b5e52] bg-[#faf9f6]" />
          <button type="submit" disabled={saving || !newTitle.trim()} className="flex items-center gap-1.5 px-3 py-1.5 bg-[#8b5e52] hover:bg-[#8b5e52] disabled:bg-[#cec8bc] text-white rounded-sm text-xs font-medium transition-colors"><Plus size={12} /> Erstellen</button>
          <button type="button" onClick={() => setShowNewForm(false)} className="px-3 py-1.5 border border-[#cec8bc] text-[#5a5040] hover:bg-[#faf9f6] rounded-sm text-xs font-medium transition-colors">Abbrechen</button>
        </form>
      )}

      {isLoading && <div className="flex items-center justify-center py-16"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#8b5e52]" /></div>}
      {error && <div className="bg-[rgba(139,94,82,.08)] border border-[rgba(139,94,82,.3)] rounded-sm p-4 text-[#8b5e52] text-sm">Fehler beim Laden.</div>}

      {!isLoading && !error && epics && epics.length === 0 && !showNewForm && (
        <div className="text-center py-16 bg-[#faf9f6] rounded-sm border border-[#e2ddd4]">
          <div className="text-4xl mb-4">🗺️</div>
          <h3 className="text-lg font-semibold text-[#5a5040] mb-2">Noch keine Epics</h3>
          <p className="text-[#a09080] mb-6 text-sm">Epics bündeln verwandte User Stories.</p>
          <button onClick={() => setShowNewForm(true)} className="inline-flex items-center gap-2 px-4 py-2 bg-[#8b5e52] hover:bg-[#8b5e52] text-white rounded-sm text-sm font-medium transition-colors">
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
                  className={`flex-1 rounded-b-sm border border-[#e2ddd4] p-2 space-y-2 min-h-[120px] transition-all ${isOver ? col.dropHighlight : "bg-[#faf9f6]"}`}
                >
                  {isOver && dragId && <div className="border-2 border-dashed border-current rounded-sm h-12 opacity-40" />}
                  {colItems.length === 0 && !isOver && <p className="text-xs text-[#a09080] text-center py-8">Keine Epics</p>}
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
        <p className="fixed bottom-4 left-1/2 -translate-x-1/2 text-xs bg-[#1c1810] text-white px-3 py-1.5 rounded-full pointer-events-none z-50">
          Epic in eine andere Spalte ziehen
        </p>
      )}
    </div>
  );
}
