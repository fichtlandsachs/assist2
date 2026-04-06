"use client";

import { useState } from "react";
import useSWR from "swr";
import { apiRequest, fetcher } from "@/lib/api/client";
import type { Epic } from "@/types";
import { Plus, X } from "lucide-react";

interface Props {
  orgId: string;
  value: string | null;
  onChange: (epicId: string | null) => void;
  disabled?: boolean;
}

export function EpicSelector({ orgId, value, onChange, disabled }: Props) {
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [saving, setSaving] = useState(false);

  const { data: epics, mutate } = useSWR<Epic[]>(
    orgId ? `/api/v1/epics?org_id=${orgId}` : null,
    fetcher
  );

  async function handleCreate() {
    if (!newTitle.trim()) return;
    setSaving(true);
    try {
      const epic = await apiRequest<Epic>(`/api/v1/epics?org_id=${orgId}`, {
        method: "POST",
        body: JSON.stringify({ title: newTitle.trim() }),
      });
      mutate((current) => [...(current ?? []), epic], false);
      onChange(epic.id);
      setCreating(false);
      setNewTitle("");
    } finally {
      setSaving(false);
    }
  }

  const inputCls =
    "px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[rgba(var(--accent-red-rgb),.08)] bg-[var(--card)]";

  const selected = epics?.find(e => e.id === value);

  return (
    <div>
      <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">Epic</label>
      {disabled ? (
        <div className="px-3 py-2 text-sm text-[var(--ink-mid)] bg-[var(--paper-warm)] rounded-sm border border-[var(--paper-rule)]">
          {selected?.title ?? "—"}
        </div>
      ) : creating ? (
        <div className="flex gap-2">
          <input
            autoFocus
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") { e.preventDefault(); void handleCreate(); }
              if (e.key === "Escape") { setCreating(false); setNewTitle(""); }
            }}
            placeholder="Neues Epic"
            className={`flex-1 ${inputCls}`}
          />
          <button
            onClick={() => void handleCreate()}
            disabled={saving || !newTitle.trim()}
            className="px-3 py-2 bg-[var(--btn-primary)] hover:bg-[var(--btn-primary-hover)] disabled:opacity-50 text-white rounded-sm text-sm font-medium transition-colors"
          >
            {saving ? (
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
            ) : (
              "Erstellen"
            )}
          </button>
          <button
            onClick={() => { setCreating(false); setNewTitle(""); }}
            className="px-3 py-2 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] rounded-sm text-sm transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      ) : (
        <div className="flex gap-2">
          <select
            value={value ?? ""}
            onChange={(e) => onChange(e.target.value || null)}
            className={`flex-1 ${inputCls}`}
          >
            <option value="">— Kein Epic —</option>
            {(epics ?? []).map((epic) => (
              <option key={epic.id} value={epic.id}>
                {epic.title}
              </option>
            ))}
          </select>
          <button
            onClick={() => setCreating(true)}
            className="flex items-center gap-1.5 px-3 py-2 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] rounded-sm text-sm transition-colors whitespace-nowrap"
          >
            <Plus size={14} />
            Neu
          </button>
        </div>
      )}
    </div>
  );
}
