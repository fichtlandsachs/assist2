"use client";

import { use, useState, useCallback } from "react";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import {
  UserCircle2, Plus, MoreHorizontal, Trash2,
  UserX, UserCheck, Users, Link2, Check, Copy,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────────────────

interface RoleItem { id: string; name: string }
interface MemberItem {
  id: string;
  user: { id: string; display_name: string; email: string };
  status: "active" | "invited" | "suspended";
  roles: RoleItem[];
  joined_at: string | null;
}

// ── InviteModal ──────────────────────────────────────────────────────────────

function InviteModal({
  orgId,
  roles,
  onClose,
  onSuccess,
}: {
  orgId: string;
  roles: RoleItem[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [email, setEmail] = useState("");
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await apiRequest(`/api/v1/organizations/${orgId}/members/invite`, {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), role_ids: selectedRoles }),
      });
      onSuccess();
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Einladung fehlgeschlagen";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  const toggleRole = (id: string) =>
    setSelectedRoles((prev) =>
      prev.includes(id) ? prev.filter((r) => r !== id) : [...prev, id]
    );

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div
        className="w-full max-w-md p-6 rounded-sm border"
        style={{ background: "var(--card)", borderColor: "var(--paper-rule)" }}
      >
        <h2 className="text-base font-semibold text-[var(--ink)] mb-4">Mitglied einladen</h2>
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1">
              E-Mail-Adresse
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="user@example.com"
              className="w-full px-3 py-2 text-sm border border-[var(--paper-rule)] rounded-sm outline-none focus:border-[var(--accent-red)] bg-[var(--card)]"
            />
          </div>
          {roles.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-[var(--ink-mid)] mb-2">
                Rollen (optional)
              </label>
              <div className="flex flex-wrap gap-2">
                {roles.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => toggleRole(r.id)}
                    className={`text-xs px-2 py-1 rounded border transition-colors ${
                      selectedRoles.includes(r.id)
                        ? "bg-[var(--accent-red)] text-white border-[var(--accent-red)]"
                        : "border-[var(--paper-rule)] text-[var(--ink-mid)]"
                    }`}
                  >
                    {r.name}
                  </button>
                ))}
              </div>
            </div>
          )}
          {error && <p className="text-xs text-red-600">{error}</p>}
          <div className="flex gap-2 justify-end pt-1">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 text-sm border border-[var(--paper-rule)] rounded-sm text-[var(--ink-mid)]"
            >
              Abbrechen
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-3 py-1.5 text-sm rounded-sm text-white bg-[var(--accent-red)] disabled:opacity-50"
            >
              {saving ? "…" : "Einladen"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── ConfirmDialog ─────────────────────────────────────────────────────────────

function ConfirmDialog({
  message,
  onConfirm,
  onCancel,
}: {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div
        className="w-full max-w-sm p-5 rounded-sm border"
        style={{ background: "var(--card)", borderColor: "var(--paper-rule)" }}
      >
        <p className="text-sm text-[var(--ink)] mb-4">{message}</p>
        <div className="flex gap-2 justify-end">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-sm border border-[var(--paper-rule)] rounded-sm text-[var(--ink-mid)]"
          >
            Abbrechen
          </button>
          <button
            onClick={onConfirm}
            className="px-3 py-1.5 text-sm rounded-sm text-white bg-red-600"
          >
            Bestätigen
          </button>
        </div>
      </div>
    </div>
  );
}

// ── StatusBadge ───────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; color: string }> = {
    active:    { label: "Aktiv",       color: "text-[var(--green)]" },
    invited:   { label: "Eingeladen",  color: "text-amber-600" },
    suspended: { label: "Suspendiert", color: "text-[var(--ink-faint)]" },
  };
  const { label, color } = map[status] ?? { label: status, color: "" };
  return <span className={`text-xs ${color}`}>{label}</span>;
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function MembersPage({ params }: { params: Promise<{ org: string }> }) {
  const { org: orgSlug } = use(params);
  const { org } = useOrg(orgSlug);
  const orgId = org?.id ?? "";

  const { data, mutate } = useSWR<{ items: MemberItem[]; total: number }>(
    orgId ? `/api/v1/organizations/${orgId}/members?page_size=100` : null,
    fetcher,
    { revalidateOnFocus: false }
  );
  const { data: rolesData } = useSWR<RoleItem[]>(
    orgId ? `/api/v1/organizations/${orgId}/roles` : null,
    fetcher,
    { revalidateOnFocus: false }
  );

  const [showInvite, setShowInvite] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ message: string; onConfirm: () => void } | null>(null);
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const members = data?.items ?? [];
  const roles = rolesData ?? [];

  const toggleSelect = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const toggleAll = () =>
    setSelected(selected.size === members.length ? new Set() : new Set(members.map((m) => m.id)));

  const removeMember = useCallback(
    async (membershipId: string) => {
      await apiRequest(`/api/v1/organizations/${orgId}/members/${membershipId}`, { method: "DELETE" });
      await mutate();
    },
    [orgId, mutate]
  );

  const updateStatus = useCallback(
    async (membershipId: string, status: "active" | "suspended") => {
      await apiRequest(`/api/v1/organizations/${orgId}/members/${membershipId}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await mutate();
    },
    [orgId, mutate]
  );

  const bulkAction = async (action: "active" | "suspended" | "remove") => {
    for (const id of selected) {
      try {
        if (action === "remove") {
          await apiRequest(`/api/v1/organizations/${orgId}/members/${id}`, { method: "DELETE" });
        } else {
          await apiRequest(`/api/v1/organizations/${orgId}/members/${id}`, {
            method: "PATCH",
            body: JSON.stringify({ status: action }),
          });
        }
      } catch {
        // continue on partial failure
      }
    }
    setSelected(new Set());
    await mutate();
  };

  const generateInviteLink = async () => {
    const res = await apiRequest<{ url: string }>(`/api/v1/organizations/${orgId}/invite-link`, {
      method: "POST",
    });
    setInviteLink(res.url);
  };

  const copyLink = () => {
    if (!inviteLink) return;
    void navigator.clipboard.writeText(inviteLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!orgId || !data) {
    return (
      <div className="flex items-center justify-center h-40">
        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--accent-red)]" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users size={16} className="text-[var(--ink-mid)]" />
          <h1 className="text-base font-semibold text-[var(--ink)]">
            Mitglieder <span className="text-[var(--ink-faint)] font-normal">({data.total})</span>
          </h1>
        </div>
        <button
          onClick={() => setShowInvite(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-sm text-white bg-[var(--accent-red)] hover:opacity-90 transition-opacity"
        >
          <Plus size={13} />
          Mitglied einladen
        </button>
      </div>

      {/* Table */}
      <div className="border border-[var(--paper-rule)] rounded-sm overflow-hidden">
        <div
          className="grid grid-cols-[2rem_1fr_auto_auto_auto_2.5rem] gap-3 px-4 py-2 text-xs font-medium text-[var(--ink-faint)] border-b border-[var(--paper-rule)]"
          style={{ background: "var(--paper-warm)" }}
        >
          <input
            type="checkbox"
            checked={selected.size === members.length && members.length > 0}
            onChange={toggleAll}
            className="mt-0.5"
          />
          <span>Name / E-Mail</span>
          <span>Rollen</span>
          <span>Status</span>
          <span>Beigetreten</span>
          <span />
        </div>

        {members.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-[var(--ink-faint)]">
            Keine Mitglieder gefunden.
          </div>
        ) : (
          members.map((m) => (
            <div
              key={m.id}
              className="grid grid-cols-[2rem_1fr_auto_auto_auto_2.5rem] gap-3 items-center px-4 py-2.5 border-b border-[var(--paper-rule)] last:border-0 hover:bg-[var(--paper-warm)] transition-colors"
            >
              <input
                type="checkbox"
                checked={selected.has(m.id)}
                onChange={() => toggleSelect(m.id)}
              />
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-7 h-7 rounded-full bg-[var(--paper-warm)] border border-[var(--paper-rule)] flex items-center justify-center flex-shrink-0">
                  <UserCircle2 size={14} className="text-[var(--ink-faint)]" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-[var(--ink)] truncate">{m.user.display_name}</p>
                  <p className="text-xs text-[var(--ink-faint)] truncate">{m.user.email}</p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                {m.roles.map((r) => (
                  <span
                    key={r.id}
                    className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--paper-warm)] border border-[var(--paper-rule)] text-[var(--ink-mid)]"
                  >
                    {r.name}
                  </span>
                ))}
              </div>
              <StatusBadge status={m.status} />
              <span className="text-xs text-[var(--ink-faint)]">
                {m.joined_at ? new Date(m.joined_at).toLocaleDateString("de-DE") : "—"}
              </span>

              {/* Actions menu */}
              <div className="relative">
                <button
                  onClick={() => setOpenMenu(openMenu === m.id ? null : m.id)}
                  className="p-1 rounded hover:bg-[var(--paper-rule)] text-[var(--ink-faint)]"
                >
                  <MoreHorizontal size={14} />
                </button>
                {openMenu === m.id && (
                  <div
                    className="absolute right-0 top-7 w-44 rounded-sm border shadow-sm z-20 text-sm"
                    style={{ background: "var(--card)", borderColor: "var(--paper-rule)" }}
                  >
                    {m.status === "active" ? (
                      <button
                        onClick={() => {
                          setOpenMenu(null);
                          setConfirm({
                            message: `${m.user.display_name} suspendieren?`,
                            onConfirm: () => { setConfirm(null); void updateStatus(m.id, "suspended"); },
                          });
                        }}
                        className="flex items-center gap-2 w-full px-3 py-2 hover:bg-[var(--paper-warm)] text-[var(--ink-mid)]"
                      >
                        <UserX size={13} /> Suspendieren
                      </button>
                    ) : (
                      <button
                        onClick={() => { setOpenMenu(null); void updateStatus(m.id, "active"); }}
                        className="flex items-center gap-2 w-full px-3 py-2 hover:bg-[var(--paper-warm)] text-[var(--ink-mid)]"
                      >
                        <UserCheck size={13} /> Reaktivieren
                      </button>
                    )}
                    <button
                      onClick={() => {
                        setOpenMenu(null);
                        setConfirm({
                          message: `${m.user.display_name} aus der Organisation entfernen?`,
                          onConfirm: () => { setConfirm(null); void removeMember(m.id); },
                        });
                      }}
                      className="flex items-center gap-2 w-full px-3 py-2 hover:bg-[var(--paper-warm)] text-red-600"
                    >
                      <Trash2 size={13} /> Entfernen
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div
          className="fixed bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-3 px-4 py-2.5 rounded-sm border shadow-lg z-30"
          style={{ background: "var(--card)", borderColor: "var(--paper-rule)" }}
        >
          <span className="text-sm text-[var(--ink-mid)]">{selected.size} ausgewählt</span>
          <button
            onClick={() => void bulkAction("suspended")}
            className="text-xs px-2.5 py-1.5 rounded border border-[var(--paper-rule)] text-[var(--ink-mid)] hover:bg-[var(--paper-warm)]"
          >
            Suspendieren
          </button>
          <button
            onClick={() => void bulkAction("active")}
            className="text-xs px-2.5 py-1.5 rounded border border-[var(--paper-rule)] text-[var(--ink-mid)] hover:bg-[var(--paper-warm)]"
          >
            Reaktivieren
          </button>
          <button
            onClick={() =>
              setConfirm({
                message: `${selected.size} Mitglieder entfernen?`,
                onConfirm: () => { setConfirm(null); void bulkAction("remove"); },
              })
            }
            className="text-xs px-2.5 py-1.5 rounded text-white bg-red-600"
          >
            Entfernen
          </button>
        </div>
      )}

      {/* Invite link */}
      <div
        className="border border-[var(--paper-rule)] rounded-sm p-4 space-y-3"
        style={{ background: "var(--paper-warm)" }}
      >
        <div className="flex items-center gap-2">
          <Link2 size={14} className="text-[var(--ink-mid)]" />
          <h3 className="text-sm font-semibold text-[var(--ink)]">Einladungslink</h3>
        </div>
        <p className="text-xs text-[var(--ink-faint)]">
          Generiere einen Link, den neue Mitglieder direkt aufrufen können. Gültig für 24 Stunden.
        </p>
        {inviteLink ? (
          <div className="flex items-center gap-2">
            <input
              readOnly
              value={inviteLink}
              className="flex-1 px-2 py-1.5 text-xs border border-[var(--paper-rule)] rounded-sm bg-[var(--card)] text-[var(--ink-faint)]"
            />
            <button
              onClick={copyLink}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs border border-[var(--paper-rule)] rounded-sm text-[var(--ink-mid)] hover:bg-[var(--paper-warm)]"
            >
              {copied ? <Check size={12} className="text-[var(--green)]" /> : <Copy size={12} />}
              {copied ? "Kopiert" : "Kopieren"}
            </button>
          </div>
        ) : (
          <button
            onClick={() => void generateInviteLink()}
            className="text-xs px-3 py-1.5 rounded-sm border border-[var(--paper-rule)] text-[var(--ink-mid)] hover:bg-[var(--paper-warm)]"
          >
            Link generieren
          </button>
        )}
      </div>

      {/* Modals */}
      {showInvite && (
        <InviteModal
          orgId={orgId}
          roles={roles}
          onClose={() => setShowInvite(false)}
          onSuccess={() => void mutate()}
        />
      )}
      {confirm && (
        <ConfirmDialog
          message={confirm.message}
          onConfirm={confirm.onConfirm}
          onCancel={() => setConfirm(null)}
        />
      )}

      {/* Close menus on outside click */}
      {openMenu && (
        <div className="fixed inset-0 z-10" onClick={() => setOpenMenu(null)} />
      )}
    </div>
  );
}
