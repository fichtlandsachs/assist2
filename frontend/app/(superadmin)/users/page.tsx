"use client";

import { useState, useCallback } from "react";
import useSWR from "swr";
import { fetcher, apiRequest } from "@/lib/api/client";
import { UserCircle2, Search, Trash2, ShieldCheck, ShieldOff, UserCheck, UserX } from "lucide-react";

interface OrgRef { id: string; name: string; slug: string }
interface SuperUser {
  id: string;
  email: string;
  display_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  organizations: OrgRef[];
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

export default function SuperadminUsersPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [confirm, setConfirm] = useState<{ message: string; onConfirm: () => void } | null>(null);

  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (search) params.set("search", search);

  const { data, mutate } = useSWR<{ items: SuperUser[]; total: number; page: number; page_size: number }>(
    `/api/v1/superadmin/users?${params}`,
    fetcher,
    { revalidateOnFocus: false }
  );

  const patch = useCallback(async (userId: string, payload: Partial<Pick<SuperUser, "is_active" | "is_superuser">>) => {
    await apiRequest(`/api/v1/superadmin/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    await mutate();
  }, [mutate]);

  const deleteUser = useCallback(async (userId: string) => {
    await apiRequest(`/api/v1/superadmin/users/${userId}`, { method: "DELETE" });
    await mutate();
  }, [mutate]);

  const users = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / (data?.page_size ?? 20));

  return (
    <div className="max-w-5xl mx-auto px-6 py-8 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[var(--ink)]">
          Benutzer <span className="text-[var(--ink-faint)] font-normal text-base">({total})</span>
        </h1>
        <div className="relative">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--ink-faint)]" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="Name oder E-Mail…"
            className="pl-7 pr-3 py-1.5 text-sm border border-[var(--paper-rule)] rounded-sm outline-none focus:border-[var(--accent-red)] bg-[var(--card)] w-60"
          />
        </div>
      </div>

      <div className="border border-[var(--paper-rule)] rounded-sm overflow-hidden">
        <div
          className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-4 px-4 py-2 text-xs font-medium text-[var(--ink-faint)] border-b border-[var(--paper-rule)]"
          style={{ background: "var(--paper-warm)" }}
        >
          <span>Benutzer</span>
          <span>Orgs</span>
          <span>Superuser</span>
          <span>Status</span>
          <span>Aktionen</span>
        </div>

        {!data ? (
          <div className="px-4 py-8 text-center text-sm text-[var(--ink-faint)]">Lade…</div>
        ) : users.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-[var(--ink-faint)]">Keine Benutzer gefunden.</div>
        ) : (
          users.map((u) => (
            <div
              key={u.id}
              className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-4 items-center px-4 py-2.5 border-b border-[var(--paper-rule)] last:border-0 hover:bg-[var(--paper-warm)]"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-7 h-7 rounded-full bg-[var(--paper-warm)] border border-[var(--paper-rule)] flex items-center justify-center flex-shrink-0">
                  <UserCircle2 size={14} className="text-[var(--ink-faint)]" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[var(--ink)] truncate">{u.display_name ?? u.email}</p>
                  <p className="text-xs text-[var(--ink-faint)] truncate">{u.email}</p>
                </div>
              </div>
              <div className="flex gap-1">
                {u.organizations.slice(0, 2).map((o) => (
                  <span key={o.id} className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--paper-warm)] border border-[var(--paper-rule)] text-[var(--ink-mid)]">
                    {o.name}
                  </span>
                ))}
                {u.organizations.length > 2 && (
                  <span className="text-[10px] text-[var(--ink-faint)]">+{u.organizations.length - 2}</span>
                )}
              </div>
              <button
                title={u.is_superuser ? "Superuser entfernen" : "Zum Superuser machen"}
                onClick={() => void patch(u.id, { is_superuser: !u.is_superuser })}
                className={`p-1 rounded transition-colors ${u.is_superuser ? "text-[var(--accent-red)]" : "text-[var(--ink-faint)] hover:text-[var(--ink-mid)]"}`}
              >
                {u.is_superuser ? <ShieldCheck size={15} /> : <ShieldOff size={15} />}
              </button>
              <button
                title={u.is_active ? "Deaktivieren" : "Aktivieren"}
                onClick={() => void patch(u.id, { is_active: !u.is_active })}
                className={`p-1 rounded transition-colors ${u.is_active ? "text-[var(--green)]" : "text-[var(--ink-faint)]"}`}
              >
                {u.is_active ? <UserCheck size={15} /> : <UserX size={15} />}
              </button>
              <button
                title="Löschen"
                onClick={() => setConfirm({
                  message: `Benutzer "${u.display_name ?? u.email}" endgültig löschen?`,
                  onConfirm: () => { setConfirm(null); void deleteUser(u.id); },
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
    </div>
  );
}
