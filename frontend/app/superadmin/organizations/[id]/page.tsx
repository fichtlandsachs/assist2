"use client";

import { useParams } from "next/navigation";
import useSWR from "swr";
import { fetcher, apiRequest } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Building2, ArrowLeft, UserCircle2, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState, useCallback } from "react";

interface OrgDetail {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  plan: string | null;
  created_at: string;
  member_count: number;
  story_count: number;
}

interface OrgMember {
  id: string;
  user: { id: string; email: string; display_name: string | null };
  organization_id: string;
  status: string;
  roles: { id: string; name: string }[];
  joined_at: string | null;
}

function ConfirmDialog({
  message, onConfirm, onCancel,
}: { message: string; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="w-full max-w-sm p-5 rounded-sm border" style={{ background: "var(--card)", borderColor: "var(--paper-rule)" }}>
        <p className="text-sm text-[var(--ink)] mb-4">{message}</p>
        <div className="flex gap-2 justify-end">
          <Button variant="outline" size="sm" onClick={onCancel}>Abbrechen</Button>
          <Button variant="destructive" size="sm" onClick={onConfirm}>Bestätigen</Button>
        </div>
      </div>
    </div>
  );
}

export default function SuperadminOrgDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [confirm, setConfirm] = useState<{ message: string; onConfirm: () => void } | null>(null);

  const { data: org } = useSWR<OrgDetail>(`/api/v1/superadmin/organizations/${id}`, fetcher);
  const { data: membersData, mutate: mutateMembers } = useSWR<{ items: OrgMember[]; total: number }>(
    `/api/v1/superadmin/organizations/${id}/members`,
    fetcher,
    { revalidateOnFocus: false }
  );
  const members = membersData?.items;

  const removeMember = useCallback(async (membershipId: string) => {
    await apiRequest(`/api/v1/organizations/${id}/members/${membershipId}`, { method: "DELETE" });
    await mutateMembers();
  }, [id, mutateMembers]);

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/superadmin/organizations" className="text-[var(--ink-faint)] hover:text-[var(--ink)] transition-colors">
          <ArrowLeft size={16} />
        </Link>
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-[var(--paper-warm)] border border-[var(--paper-rule)] flex items-center justify-center">
            <Building2 size={15} className="text-[var(--ink-faint)]" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-[var(--ink)]">{org?.name ?? "…"}</h1>
            <p className="text-xs text-[var(--ink-faint)]">{org?.slug}</p>
          </div>
        </div>
        {org && (
          <span
            className={`ml-2 text-[10px] px-2 py-0.5 rounded-full border font-medium ${
              org.is_active
                ? "text-[var(--green)] border-[var(--green)] bg-[rgba(var(--accent-red-rgb),.06)]"
                : "text-[var(--ink-faint)] border-[var(--paper-rule)]"
            }`}
          >
            {org.is_active ? "Aktiv" : "Inaktiv"}
          </span>
        )}
      </div>

      {org && (
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: "Plan", value: org.plan ?? "free" },
            { label: "Mitglieder", value: org.member_count },
            { label: "Stories", value: org.story_count },
            { label: "Erstellt", value: formatDate(org.created_at) },
          ].map(({ label, value }) => (
            <div key={label} className="p-3 rounded-sm border" style={{ background: "var(--card)", borderColor: "var(--paper-rule)" }}>
              <p className="text-xs text-[var(--ink-faint)]">{label}</p>
              <p className="text-sm font-semibold text-[var(--ink)] mt-0.5">{value}</p>
            </div>
          ))}
        </div>
      )}

      <div>
        <h2 className="text-sm font-semibold text-[var(--ink)] mb-3">Mitglieder</h2>
        <div className="border border-[var(--paper-rule)] rounded-sm overflow-hidden">
          <div
            className="grid grid-cols-[1fr_auto_auto_auto] gap-4 px-4 py-2 text-xs font-medium text-[var(--ink-faint)] border-b border-[var(--paper-rule)]"
            style={{ background: "var(--paper-warm)" }}
          >
            <span>Benutzer</span>
            <span>Rolle</span>
            <span>Beigetreten</span>
            <span>Aktion</span>
          </div>

          {!members ? (
            <div className="px-4 py-6 text-center text-sm text-[var(--ink-faint)]">Lade…</div>
          ) : members.length === 0 ? (
            <div className="px-4 py-6 text-center text-sm text-[var(--ink-faint)]">Keine Mitglieder.</div>
          ) : (
            members.map((m) => (
              <div
                key={m.id}
                className="grid grid-cols-[1fr_auto_auto_auto] gap-4 items-center px-4 py-2.5 border-b border-[var(--paper-rule)] last:border-0 hover:bg-[var(--paper-warm)]"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-7 h-7 rounded-full bg-[var(--paper-warm)] border border-[var(--paper-rule)] flex items-center justify-center flex-shrink-0">
                    <UserCircle2 size={14} className="text-[var(--ink-faint)]" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-[var(--ink)] truncate">{m.user.display_name ?? m.user.email}</p>
                    <p className="text-xs text-[var(--ink-faint)] truncate">{m.user.email}</p>
                  </div>
                </div>
                <span className="text-xs text-[var(--ink-mid)]">{m.roles.map((r) => r.name).join(", ") || m.status}</span>
                <span className="text-xs text-[var(--ink-faint)]">{m.joined_at ? formatDate(m.joined_at) : "—"}</span>
                <button
                  title="Entfernen"
                  onClick={() => setConfirm({
                    message: `"${m.user.display_name ?? m.user.email}" aus der Organisation entfernen?`,
                    onConfirm: () => { setConfirm(null); void removeMember(m.id); },
                  })}
                  className="p-1 rounded text-[var(--ink-faint)] hover:text-[var(--accent-red)] transition-colors"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {confirm && <ConfirmDialog message={confirm.message} onConfirm={confirm.onConfirm} onCancel={() => setConfirm(null)} />}
    </div>
  );
}
