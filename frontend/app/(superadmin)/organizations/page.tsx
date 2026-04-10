"use client";

import { useState, useCallback } from "react";
import useSWR from "swr";
import { fetcher, apiRequest } from "@/lib/api/client";
import { Building2, Search, Trash2, ToggleLeft, ToggleRight, Plus, Users, BookOpen } from "lucide-react";

interface OrgMetric {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  member_count: number;
  story_count: number;
  plan: string | null;
  created_at: string;
}

function ConfirmDialog({
  message, onConfirm, onCancel,
}: { message: string; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="w-full max-w-sm p-5 rounded-sm border" style={{ background: "var(--card)", borderColor: "var(--paper-rule)" }}>
        <p className="text-sm text-[var(--ink)] mb-4">{message}</p>
        <div className="flex gap-2 justify-end">
          <button onClick={onCancel} className="px-3 py-1.5 text-sm border border-[var(--paper-rule)] rounded-sm text-[var(--ink-mid)]">Abbrechen</button>
          <button onClick={onConfirm} className="px-3 py-1.5 text-sm rounded-sm text-white bg-red-600">Bestätigen</button>
        </div>
      </div>
    </div>
  );
}

function CreateOrgModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [plan, setPlan] = useState("free");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await apiRequest("/api/v1/superadmin/organizations", {
        method: "POST",
        body: JSON.stringify({ name, slug, plan }),
      });
      onCreated();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Fehler beim Erstellen");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="w-full max-w-sm p-5 rounded-sm border" style={{ background: "var(--card)", borderColor: "var(--paper-rule)" }}>
        <h3 className="text-sm font-semibold text-[var(--ink)] mb-4">Organisation erstellen</h3>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-xs text-[var(--ink-faint)] mb-1">Name</label>
            <input
              required
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (!slug) setSlug(e.target.value.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, ""));
              }}
              className="w-full px-3 py-1.5 text-sm border border-[var(--paper-rule)] rounded-sm outline-none focus:border-[var(--accent-red)] bg-[var(--card)]"
            />
          </div>
          <div>
            <label className="block text-xs text-[var(--ink-faint)] mb-1">Slug</label>
            <input
              required
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              className="w-full px-3 py-1.5 text-sm border border-[var(--paper-rule)] rounded-sm outline-none focus:border-[var(--accent-red)] bg-[var(--card)]"
            />
          </div>
          <div>
            <label className="block text-xs text-[var(--ink-faint)] mb-1">Plan</label>
            <select
              value={plan}
              onChange={(e) => setPlan(e.target.value)}
              className="w-full px-3 py-1.5 text-sm border border-[var(--paper-rule)] rounded-sm outline-none focus:border-[var(--accent-red)] bg-[var(--card)]"
            >
              <option value="free">Free</option>
              <option value="starter">Starter</option>
              <option value="pro">Pro</option>
              <option value="enterprise">Enterprise</option>
            </select>
          </div>
          {error && <p className="text-xs text-red-600">{error}</p>}
          <div className="flex gap-2 justify-end pt-1">
            <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm border border-[var(--paper-rule)] rounded-sm text-[var(--ink-mid)]">Abbrechen</button>
            <button type="submit" disabled={loading} className="px-3 py-1.5 text-sm rounded-sm text-white bg-[var(--accent-red)] disabled:opacity-60">
              {loading ? "…" : "Erstellen"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const PLANS = ["free", "starter", "pro", "enterprise"];

export default function SuperadminOrganizationsPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [confirm, setConfirm] = useState<{ message: string; onConfirm: () => void } | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (search) params.set("search", search);

  const { data, mutate } = useSWR<{ items: OrgMetric[]; total: number; page: number; page_size: number }>(
    `/api/v1/superadmin/organizations?${params}`,
    fetcher,
    { revalidateOnFocus: false }
  );

  const patchOrg = useCallback(async (orgId: string, payload: Partial<Pick<OrgMetric, "is_active" | "plan">>) => {
    await apiRequest(`/api/v1/superadmin/organizations/${orgId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    await mutate();
  }, [mutate]);

  const deleteOrg = useCallback(async (orgId: string) => {
    await apiRequest(`/api/v1/superadmin/organizations/${orgId}`, { method: "DELETE" });
    await mutate();
  }, [mutate]);

  const orgs = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / (data?.page_size ?? 20));

  return (
    <div className="max-w-5xl mx-auto px-6 py-8 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[var(--ink)]">
          Organisationen <span className="text-[var(--ink-faint)] font-normal text-base">({total})</span>
        </h1>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--ink-faint)]" />
            <input
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              placeholder="Name oder Slug…"
              className="pl-7 pr-3 py-1.5 text-sm border border-[var(--paper-rule)] rounded-sm outline-none focus:border-[var(--accent-red)] bg-[var(--card)] w-52"
            />
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-sm text-white bg-[var(--accent-red)]"
          >
            <Plus size={13} /> Neu
          </button>
        </div>
      </div>

      <div className="border border-[var(--paper-rule)] rounded-sm overflow-hidden">
        <div
          className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-4 px-4 py-2 text-xs font-medium text-[var(--ink-faint)] border-b border-[var(--paper-rule)]"
          style={{ background: "var(--paper-warm)" }}
        >
          <span>Organisation</span>
          <span>Mitglieder</span>
          <span>Stories</span>
          <span>Plan</span>
          <span>Status</span>
          <span>Aktionen</span>
        </div>

        {!data ? (
          <div className="px-4 py-8 text-center text-sm text-[var(--ink-faint)]">Lade…</div>
        ) : orgs.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-[var(--ink-faint)]">Keine Organisationen gefunden.</div>
        ) : (
          orgs.map((o) => (
            <div
              key={o.id}
              className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-4 items-center px-4 py-2.5 border-b border-[var(--paper-rule)] last:border-0 hover:bg-[var(--paper-warm)]"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-7 h-7 rounded-full bg-[var(--paper-warm)] border border-[var(--paper-rule)] flex items-center justify-center flex-shrink-0">
                  <Building2 size={14} className="text-[var(--ink-faint)]" />
                </div>
                <div className="min-w-0">
                  <a href={`/superadmin/organizations/${o.id}`} className="text-sm font-medium text-[var(--ink)] truncate hover:underline block">{o.name}</a>
                  <p className="text-xs text-[var(--ink-faint)] truncate">{o.slug}</p>
                </div>
              </div>
              <div className="flex items-center gap-1 text-xs text-[var(--ink-mid)]">
                <Users size={11} className="text-[var(--ink-faint)]" /> {o.member_count}
              </div>
              <div className="flex items-center gap-1 text-xs text-[var(--ink-mid)]">
                <BookOpen size={11} className="text-[var(--ink-faint)]" /> {o.story_count}
              </div>
              <select
                value={o.plan ?? "free"}
                onChange={(e) => void patchOrg(o.id, { plan: e.target.value })}
                className="text-xs px-1.5 py-0.5 border border-[var(--paper-rule)] rounded bg-[var(--card)] text-[var(--ink-mid)]"
              >
                {PLANS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
              <button
                title={o.is_active ? "Deaktivieren" : "Aktivieren"}
                onClick={() => void patchOrg(o.id, { is_active: !o.is_active })}
                className={`p-1 rounded transition-colors ${o.is_active ? "text-[var(--green)]" : "text-[var(--ink-faint)]"}`}
              >
                {o.is_active ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
              </button>
              <button
                title="Löschen"
                onClick={() => setConfirm({
                  message: `Organisation "${o.name}" endgültig löschen?`,
                  onConfirm: () => { setConfirm(null); void deleteOrg(o.id); },
                })}
                className="p-1 rounded text-[var(--ink-faint)] hover:text-red-600 transition-colors"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-end gap-2">
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="px-3 py-1 text-sm border border-[var(--paper-rule)] rounded-sm disabled:opacity-40">←</button>
          <span className="text-xs text-[var(--ink-faint)]">{page} / {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} className="px-3 py-1 text-sm border border-[var(--paper-rule)] rounded-sm disabled:opacity-40">→</button>
        </div>
      )}

      {confirm && <ConfirmDialog message={confirm.message} onConfirm={confirm.onConfirm} onCancel={() => setConfirm(null)} />}
      {showCreate && <CreateOrgModal onClose={() => setShowCreate(false)} onCreated={() => void mutate()} />}
    </div>
  );
}
