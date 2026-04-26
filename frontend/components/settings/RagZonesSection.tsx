"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import {
  Shield, Plus, Trash2, ChevronDown, ChevronRight, X,
  Users, Database, Settings, AlertCircle, CheckCircle,
} from "lucide-react";
import { apiRequest, fetcher } from "@/lib/api/client";
import type { Membership } from "@/types";

// ── Types ──────────────────────────────────────────────────────────────────────

interface RagZone {
  id: string; name: string; slug: string; description: string | null;
  is_active: boolean; ad_group_only: boolean; created_at: string;
}
interface ZoneMembership { id: string; zone_id: string; ad_group_name: string; }
interface UserZoneAccess {
  id: string; user_id: string; zone_id: string; org_id: string;
  project_scope: string | null; granted_via: string; granted_at: string;
  revoked_at: string | null;
}
interface HkRoleAssignment {
  id: string; user_id: string; org_id: string; role_name: string;
  scope_type: string | null; scope_id: string | null;
  valid_from: string; valid_to: string | null;
}
interface HkRoleZoneGrant { id: string; org_id: string; role_name: string; zone_id: string; }
interface IngestionZoneConfig {
  nextcloud?: string; karl_story?: string; jira?: string;
  confluence?: string; user_action?: string;
}

// ── Shared helpers ─────────────────────────────────────────────────────────────

function Spinner() {
  return <div className="animate-spin rounded-full h-4 w-4 border-2 border-[var(--accent-red)] border-t-transparent" />;
}

function Msg({ msg }: { msg: { type: "success" | "error"; text: string } | null }) {
  if (!msg) return null;
  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-sm text-sm ${msg.type === "success" ? "bg-[rgba(82,107,94,.1)] border border-[var(--green)] text-[var(--green)]" : "bg-[rgba(220,38,38,.08)] border border-[var(--accent-red)] text-[var(--accent-red)]"}`}>
      {msg.type === "success" ? <CheckCircle size={13} /> : <AlertCircle size={13} />}
      {msg.text}
    </div>
  );
}

function Badge({ label, variant }: { label: string; variant: "green" | "red" | "gray" }) {
  const cls = {
    green: "bg-[rgba(82,107,94,.1)] text-[var(--green)]",
    red: "bg-[rgba(220,38,38,.08)] text-[var(--accent-red)]",
    gray: "bg-[var(--paper-warm)] text-[var(--ink-faint)]",
  }[variant];
  return <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>{label}</span>;
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-sm shadow-xl" style={{ background: "var(--card)", border: "1px solid var(--paper-rule)" }}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--paper-rule)]">
          <span className="text-sm font-semibold text-[var(--ink)]">{title}</span>
          <button onClick={onClose} className="text-[var(--ink-faint)] hover:text-[var(--ink)] transition-colors"><X size={16} /></button>
        </div>
        <div className="px-5 py-4 space-y-4">{children}</div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-[var(--ink-mid)] mb-1">{label}</label>
      {children}
    </div>
  );
}

const inputCls = "w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-1 focus:ring-[var(--accent-red)] bg-[var(--card)]";
const btnPrimary = "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] text-white rounded-sm transition-colors disabled:opacity-50";
const btnOutline = "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:text-[var(--ink)] hover:border-[var(--ink-mid)] rounded-sm transition-colors";
const btnDanger = "flex items-center gap-1 px-2 py-1 text-xs text-[var(--ink-faint)] hover:text-[var(--accent-red)] rounded-sm transition-colors";

// ── Sub-tab bar ────────────────────────────────────────────────────────────────

const SUB_TABS = [
  { id: "zones" as const,     label: "Zonen",            Icon: Database },
  { id: "roles" as const,     label: "Rollen",           Icon: Shield },
  { id: "access" as const,    label: "Nutzerzugriff",    Icon: Users },
  { id: "ingestion" as const, label: "Ingestion-Config", Icon: Settings },
];

// ── Main export ────────────────────────────────────────────────────────────────

export function RagZonesSection({ orgId }: { orgId: string }) {
  const [subTab, setSubTab] = useState<"zones" | "roles" | "access" | "ingestion">("zones");
  return (
    <div className="space-y-5">
      <div className="flex gap-0 border-b border-[var(--paper-rule)]">
        {SUB_TABS.map(({ id, label, Icon }) => (
          <button key={id} onClick={() => setSubTab(id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${subTab === id ? "border-[var(--accent-red)] text-[var(--ink)]" : "border-transparent text-[var(--ink-faint)] hover:text-[var(--ink-mid)]"}`}>
            <Icon size={14} />{label}
          </button>
        ))}
      </div>
      {subTab === "zones"     && <ZonesTab orgId={orgId} />}
      {subTab === "roles"     && <RolesTab orgId={orgId} />}
      {subTab === "access"    && <AccessTab orgId={orgId} />}
      {subTab === "ingestion" && <IngestionTab orgId={orgId} />}
    </div>
  );
}

// ── Tab: Zonen ─────────────────────────────────────────────────────────────────

function ZonesTab({ orgId }: { orgId: string }) {
  const { data: zones, mutate } = useSWR<RagZone[]>(`/api/v1/organizations/${orgId}/rag-zones`, fetcher);
  const [creating, setCreating] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [form, setForm] = useState({ name: "", slug: "", description: "", ad_group_only: false });

  const handleCreate = async () => {
    setSaving(true); setMsg(null);
    try {
      await apiRequest(`/api/v1/organizations/${orgId}/rag-zones`, {
        method: "POST", body: JSON.stringify(form),
      });
      await mutate();
      setCreating(false);
      setForm({ name: "", slug: "", description: "", ad_group_only: false });
    } catch (e: any) {
      setMsg({ type: "error", text: e?.error ?? "Fehler beim Erstellen" });
    } finally { setSaving(false); }
  };

  const handleDelete = async (zoneId: string) => {
    if (!confirm("Zone löschen? Alle verknüpften Dokumente verlieren ihre Zonenzuweisung.")) return;
    try {
      await apiRequest(`/api/v1/organizations/${orgId}/rag-zones/${zoneId}`, { method: "DELETE" });
      await mutate();
    } catch (e: any) {
      setMsg({ type: "error", text: e?.error ?? "Fehler beim Löschen" });
    }
  };

  if (!zones) return <div className="flex justify-center py-8"><Spinner /></div>;

  return (
    <div className="space-y-4">
      <Msg msg={msg} />
      <div className="flex justify-end">
        <button onClick={() => setCreating(true)} className={btnPrimary}><Plus size={13} />Neue Zone</button>
      </div>

      {zones.length === 0 && (
        <p className="text-sm text-center text-[var(--ink-faint)] py-8">Noch keine Zonen angelegt.</p>
      )}

      <div className="space-y-2">
        {zones.map(zone => (
          <div key={zone.id} className="rounded-sm border border-[var(--paper-rule)]" style={{ background: "var(--paper-warm)" }}>
            <div className="flex items-center gap-3 px-4 py-3">
              <button onClick={() => setExpanded(expanded === zone.id ? null : zone.id)}
                className="text-[var(--ink-faint)] hover:text-[var(--ink)] transition-colors">
                {expanded === zone.id ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
              </button>
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-[var(--ink)]">{zone.name}</span>
                <span className="ml-2 text-xs text-[var(--ink-faint)] font-mono">{zone.slug}</span>
              </div>
              <div className="flex items-center gap-2">
                {zone.ad_group_only && <Badge label="AD only" variant="red" />}
                <Badge label={zone.is_active ? "aktiv" : "inaktiv"} variant={zone.is_active ? "green" : "gray"} />
                <button onClick={() => handleDelete(zone.id)} className={btnDanger}><Trash2 size={13} /></button>
              </div>
            </div>
            {expanded === zone.id && (
              <div className="border-t border-[var(--paper-rule)] px-4 py-3">
                <ZoneMemberships orgId={orgId} zone={zone} />
              </div>
            )}
          </div>
        ))}
      </div>

      {creating && (
        <Modal title="Neue Zone anlegen" onClose={() => setCreating(false)}>
          <Msg msg={msg} />
          <Field label="Name">
            <input className={inputCls} value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Product Zone" />
          </Field>
          <Field label="Slug (eindeutig je Org)">
            <input className={inputCls} value={form.slug} onChange={e => setForm(f => ({ ...f, slug: e.target.value.toLowerCase().replace(/\s+/g, "-") }))} placeholder="product" />
          </Field>
          <Field label="Beschreibung (optional)">
            <input className={inputCls} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Produktstrategie und ADRs" />
          </Field>
          <label className="flex items-center gap-2 text-sm text-[var(--ink-mid)] cursor-pointer">
            <input type="checkbox" checked={form.ad_group_only} onChange={e => setForm(f => ({ ...f, ad_group_only: e.target.checked }))} className="accent-[var(--accent-red)]" />
            Nur über AD-Gruppen zugänglich (keine heyKarl-Rollenvergabe)
          </label>
          <div className="flex justify-end gap-2 pt-1">
            <button onClick={() => setCreating(false)} className={btnOutline}>Abbrechen</button>
            <button onClick={() => void handleCreate()} disabled={saving || !form.name || !form.slug} className={btnPrimary}>
              {saving && <Spinner />}Zone erstellen
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function ZoneMemberships({ orgId, zone }: { orgId: string; zone: RagZone }) {
  const { data: memberships, mutate } = useSWR<ZoneMembership[]>(
    `/api/v1/organizations/${orgId}/rag-zones/${zone.id}/memberships`, fetcher
  );
  const [newGroup, setNewGroup] = useState("");
  const [saving, setSaving] = useState(false);

  const handleAdd = async () => {
    if (!newGroup.trim()) return;
    setSaving(true);
    try {
      await apiRequest(`/api/v1/organizations/${orgId}/rag-zones/${zone.id}/memberships`, {
        method: "POST", body: JSON.stringify({ ad_group_name: newGroup.trim() }),
      });
      await mutate(); setNewGroup("");
    } finally { setSaving(false); }
  };

  const handleRemove = async (id: string) => {
    await apiRequest(`/api/v1/organizations/${orgId}/rag-zones/${zone.id}/memberships/${id}`, { method: "DELETE" });
    await mutate();
  };

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-[var(--ink-mid)] uppercase tracking-wide">AD-Gruppen</p>
      {!memberships ? <Spinner /> : (
        <>
          {memberships.length === 0 && <p className="text-xs text-[var(--ink-faint)]">Keine AD-Gruppen zugeordnet.</p>}
          <div className="space-y-1">
            {memberships.map(m => (
              <div key={m.id} className="flex items-center gap-2">
                <code className="text-xs px-2 py-0.5 rounded bg-[var(--card)] border border-[var(--paper-rule)] text-[var(--ink-mid)] font-mono">{m.ad_group_name}</code>
                <button onClick={() => void handleRemove(m.id)} className={btnDanger}><Trash2 size={11} /></button>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-2 pt-1">
            <input className={`${inputCls} flex-1`} value={newGroup} onChange={e => setNewGroup(e.target.value)}
              onKeyDown={e => e.key === "Enter" && void handleAdd()}
              placeholder="cn=product-team,ou=groups,dc=example,dc=com" />
            <button onClick={() => void handleAdd()} disabled={saving || !newGroup.trim()} className={btnPrimary}>
              <Plus size={12} />Hinzufügen
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ── Tab: Rollen ────────────────────────────────────────────────────────────────

function RolesTab({ orgId }: { orgId: string }) {
  const { data: assignments, mutate: mutateAssignments } = useSWR<HkRoleAssignment[]>(
    `/api/v1/organizations/${orgId}/rag-roles/assignments`, fetcher
  );
  const { data: zones } = useSWR<RagZone[]>(`/api/v1/organizations/${orgId}/rag-zones`, fetcher);
  const { data: members } = useSWR<Membership[]>(`/api/v1/organizations/${orgId}/memberships`, fetcher);
  const [creatingAssignment, setCreatingAssignment] = useState(false);
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [aForm, setAForm] = useState({ user_id: "", role_name: "", scope_type: "", scope_id: "", valid_to: "" });
  const [saving, setSaving] = useState(false);

  const roleNames = Array.from(new Set(assignments?.map(a => a.role_name) ?? []));

  const handleCreateAssignment = async () => {
    setSaving(true); setMsg(null);
    try {
      await apiRequest(`/api/v1/organizations/${orgId}/rag-roles/assignments`, {
        method: "POST",
        body: JSON.stringify({
          user_id: aForm.user_id,
          role_name: aForm.role_name,
          scope_type: aForm.scope_type || null,
          scope_id: aForm.scope_id || null,
          valid_to: aForm.valid_to || null,
        }),
      });
      await mutateAssignments();
      setCreatingAssignment(false);
      setAForm({ user_id: "", role_name: "", scope_type: "", scope_id: "", valid_to: "" });
    } catch (e: any) {
      setMsg({ type: "error", text: e?.error ?? "Fehler" });
    } finally { setSaving(false); }
  };

  const handleDeleteAssignment = async (id: string) => {
    await apiRequest(`/api/v1/organizations/${orgId}/rag-roles/assignments/${id}`, { method: "DELETE" });
    await mutateAssignments();
  };

  if (!assignments || !zones) return <div className="flex justify-center py-8"><Spinner /></div>;

  const memberMap = Object.fromEntries(members?.map(m => [m.user.id, m.user]) ?? []);

  return (
    <div className="space-y-6">
      <Msg msg={msg} />

      {/* Role assignments */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-[var(--ink)]">Rollenzuweisungen</p>
          <button onClick={() => setCreatingAssignment(true)} className={btnPrimary}><Plus size={13} />Zuweisung</button>
        </div>
        {assignments.length === 0 && <p className="text-sm text-[var(--ink-faint)] py-4 text-center">Noch keine Rollenzuweisungen.</p>}
        <div className="space-y-1">
          {assignments.map(a => {
            const u = memberMap[a.user_id];
            return (
              <div key={a.id} className="flex items-center gap-3 px-4 py-2.5 rounded-sm border border-[var(--paper-rule)]" style={{ background: "var(--paper-warm)" }}>
                <div className="flex-1 min-w-0">
                  <span className="text-sm text-[var(--ink)]">{u?.display_name ?? u?.email ?? a.user_id.slice(0, 8)}</span>
                  <span className="mx-2 text-[var(--ink-faint)]">→</span>
                  <code className="text-sm font-mono text-[var(--ink-mid)]">{a.role_name}</code>
                  {a.scope_type && <span className="ml-2 text-xs text-[var(--ink-faint)]">({a.scope_type})</span>}
                  {a.valid_to && <span className="ml-2 text-xs text-[var(--ink-faint)]">bis {new Date(a.valid_to).toLocaleDateString("de")}</span>}
                </div>
                <button onClick={() => void handleDeleteAssignment(a.id)} className={btnDanger}><Trash2 size={13} /></button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Role → Zone grants */}
      <div className="space-y-3 pt-4 border-t border-[var(--paper-rule)]">
        <p className="text-sm font-semibold text-[var(--ink)]">Rollen-Zonen-Konfiguration</p>
        {roleNames.length === 0 && <p className="text-sm text-[var(--ink-faint)]">Erst Rollenzuweisungen anlegen, dann hier Zonen konfigurieren.</p>}
        {roleNames.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {roleNames.map(r => (
              <button key={r} onClick={() => setSelectedRole(selectedRole === r ? null : r)}
                className={`px-3 py-1.5 text-xs font-mono rounded-sm border transition-colors ${selectedRole === r ? "bg-[var(--accent-red)] border-[var(--accent-red)] text-white" : "border-[var(--paper-rule)] text-[var(--ink-mid)] hover:border-[var(--ink-mid)]"}`}>
                {r}
              </button>
            ))}
          </div>
        )}
        {selectedRole && <RoleZoneGrants orgId={orgId} roleName={selectedRole} zones={zones} />}
      </div>

      {creatingAssignment && (
        <Modal title="Rollenzuweisung erstellen" onClose={() => setCreatingAssignment(false)}>
          <Msg msg={msg} />
          <Field label="Nutzer">
            <select className={inputCls} value={aForm.user_id} onChange={e => setAForm(f => ({ ...f, user_id: e.target.value }))}>
              <option value="">Nutzer wählen…</option>
              {members?.map(m => (
                <option key={m.user.id} value={m.user.id}>{m.user.display_name || m.user.email}</option>
              ))}
            </select>
          </Field>
          <Field label="Rollenname">
            <input className={inputCls} value={aForm.role_name} onChange={e => setAForm(f => ({ ...f, role_name: e.target.value }))}
              placeholder="product_lead" list="common-roles" />
            <datalist id="common-roles">
              {["product_lead","tech_lead","compliance_reviewer","security_reviewer","refinement_facilitator","release_manager","external_consultant"].map(r => (
                <option key={r} value={r} />
              ))}
            </datalist>
          </Field>
          <Field label="Scope-Typ (optional)">
            <select className={inputCls} value={aForm.scope_type} onChange={e => setAForm(f => ({ ...f, scope_type: e.target.value }))}>
              <option value="">Org-weit</option>
              <option value="project">Projekt</option>
              <option value="epic">Epic</option>
            </select>
          </Field>
          {aForm.scope_type && (
            <Field label="Scope-ID (UUID des Projekts/Epics)">
              <input className={inputCls} value={aForm.scope_id} onChange={e => setAForm(f => ({ ...f, scope_id: e.target.value }))} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" />
            </Field>
          )}
          <Field label="Gültig bis (optional)">
            <input type="datetime-local" className={inputCls} value={aForm.valid_to} onChange={e => setAForm(f => ({ ...f, valid_to: e.target.value }))} />
          </Field>
          <div className="flex justify-end gap-2 pt-1">
            <button onClick={() => setCreatingAssignment(false)} className={btnOutline}>Abbrechen</button>
            <button onClick={() => void handleCreateAssignment()} disabled={saving || !aForm.user_id || !aForm.role_name} className={btnPrimary}>
              {saving && <Spinner />}Zuweisen
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function RoleZoneGrants({ orgId, roleName, zones }: { orgId: string; roleName: string; zones: RagZone[] }) {
  const { data: grants, mutate } = useSWR<HkRoleZoneGrant[]>(
    `/api/v1/organizations/${orgId}/rag-roles/${roleName}/zone-grants`, fetcher
  );
  const [addZoneId, setAddZoneId] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const grantedIds = new Set(grants?.map(g => g.zone_id) ?? []);
  const available = zones.filter(z => !z.ad_group_only && !grantedIds.has(z.id));

  const handleAdd = async () => {
    if (!addZoneId) return;
    setSaving(true); setMsg(null);
    try {
      await apiRequest(`/api/v1/organizations/${orgId}/rag-roles/${roleName}/zone-grants`, {
        method: "POST", body: JSON.stringify({ zone_id: addZoneId }),
      });
      await mutate(); setAddZoneId("");
    } catch (e: any) {
      setMsg({ type: "error", text: e?.error ?? "Fehler" });
    } finally { setSaving(false); }
  };

  const handleRemove = async (id: string) => {
    await apiRequest(`/api/v1/organizations/${orgId}/rag-roles/${roleName}/zone-grants/${id}`, { method: "DELETE" });
    await mutate();
  };

  const zoneMap = Object.fromEntries(zones.map(z => [z.id, z]));

  if (!grants) return <Spinner />;

  return (
    <div className="rounded-sm border border-[var(--paper-rule)] p-4 space-y-3" style={{ background: "var(--paper-warm)" }}>
      <Msg msg={msg} />
      <p className="text-xs font-medium text-[var(--ink-mid)] uppercase tracking-wide">Zonen für <code className="font-mono normal-case">{roleName}</code></p>
      {grants.length === 0 && <p className="text-xs text-[var(--ink-faint)]">Noch keine Zonen zugeordnet.</p>}
      <div className="flex flex-wrap gap-2">
        {grants.map(g => (
          <span key={g.id} className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-sm border border-[var(--paper-rule)] bg-[var(--card)] text-[var(--ink-mid)]">
            {zoneMap[g.zone_id]?.name ?? g.zone_id.slice(0, 8)}
            <button onClick={() => void handleRemove(g.id)} className="text-[var(--ink-faint)] hover:text-[var(--accent-red)] transition-colors"><X size={10} /></button>
          </span>
        ))}
      </div>
      {available.length > 0 && (
        <div className="flex items-center gap-2 pt-1">
          <select className={`${inputCls} flex-1`} value={addZoneId} onChange={e => setAddZoneId(e.target.value)}>
            <option value="">Zone hinzufügen…</option>
            {available.map(z => <option key={z.id} value={z.id}>{z.name} ({z.slug})</option>)}
          </select>
          <button onClick={() => void handleAdd()} disabled={saving || !addZoneId} className={btnPrimary}><Plus size={12} />Hinzufügen</button>
        </div>
      )}
      {available.length === 0 && grants.length > 0 && (
        <p className="text-xs text-[var(--ink-faint)]">Alle verfügbaren Zonen sind zugeordnet.</p>
      )}
    </div>
  );
}

// ── Tab: Nutzerzugriff ─────────────────────────────────────────────────────────

function AccessTab({ orgId }: { orgId: string }) {
  const { data: grants, mutate } = useSWR<UserZoneAccess[]>(
    `/api/v1/organizations/${orgId}/rag-zones/access`, fetcher
  );
  const { data: zones } = useSWR<RagZone[]>(`/api/v1/organizations/${orgId}/rag-zones`, fetcher);
  const { data: members } = useSWR<Membership[]>(`/api/v1/organizations/${orgId}/memberships`, fetcher);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [form, setForm] = useState({ user_id: "", zone_id: "", project_scope: "", valid_to: "" });

  const handleGrant = async () => {
    setSaving(true); setMsg(null);
    try {
      await apiRequest(`/api/v1/organizations/${orgId}/rag-zones/${form.zone_id}/access`, {
        method: "POST",
        body: JSON.stringify({
          user_id: form.user_id,
          project_scope: form.project_scope || null,
          valid_to: form.valid_to || null,
        }),
      });
      await mutate(); setCreating(false); setForm({ user_id: "", zone_id: "", project_scope: "", valid_to: "" });
    } catch (e: any) {
      setMsg({ type: "error", text: e?.error ?? "Fehler" });
    } finally { setSaving(false); }
  };

  const handleRevoke = async (zoneId: string, accessId: string) => {
    if (!confirm("Zugriff widerrufen? Der Nutzer sieht weiterhin Dokumente, die er vor dem Widerruf hatte.")) return;
    try {
      await apiRequest(`/api/v1/organizations/${orgId}/rag-zones/${zoneId}/access/${accessId}`, { method: "DELETE" });
      await mutate();
    } catch (e: any) {
      setMsg({ type: "error", text: e?.error ?? "Fehler" });
    }
  };

  if (!grants || !zones) return <div className="flex justify-center py-8"><Spinner /></div>;

  const zoneMap = Object.fromEntries(zones.map(z => [z.id, z]));
  const memberMap = Object.fromEntries(members?.map(m => [m.user.id, m.user]) ?? []);
  const now = new Date();

  return (
    <div className="space-y-4">
      <Msg msg={msg} />
      <div className="flex justify-end">
        <button onClick={() => setCreating(true)} className={btnPrimary}><Plus size={13} />Zugriff gewähren</button>
      </div>

      {grants.length === 0 && <p className="text-sm text-[var(--ink-faint)] text-center py-8">Noch keine direkten Nutzerzugriffe.</p>}

      <div className="space-y-1">
        {grants.map(g => {
          const zone = zoneMap[g.zone_id];
          const user = memberMap[g.user_id];
          const isActive = !g.revoked_at || new Date(g.revoked_at) > now;
          return (
            <div key={g.id} className="flex items-center gap-3 px-4 py-2.5 rounded-sm border border-[var(--paper-rule)]" style={{ background: "var(--paper-warm)" }}>
              <div className="flex-1 min-w-0 space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-[var(--ink)]">{user?.display_name ?? user?.email ?? g.user_id.slice(0, 8)}</span>
                  <span className="text-[var(--ink-faint)]">→</span>
                  <span className="text-sm font-medium text-[var(--ink-mid)]">{zone?.name ?? g.zone_id.slice(0, 8)}</span>
                  <Badge label={isActive ? "aktiv" : "widerrufen"} variant={isActive ? "green" : "gray"} />
                </div>
                <div className="flex items-center gap-3 text-xs text-[var(--ink-faint)]">
                  <span>gewährt {new Date(g.granted_at).toLocaleDateString("de")}</span>
                  {g.revoked_at && <span>widerrufen {new Date(g.revoked_at).toLocaleDateString("de")}</span>}
                  {g.project_scope && <span>Projekt: {g.project_scope.slice(0, 8)}</span>}
                </div>
              </div>
              {isActive && (
                <button onClick={() => void handleRevoke(g.zone_id, g.id)} className={`${btnDanger} text-[var(--ink-faint)]`}>
                  <X size={13} />Widerrufen
                </button>
              )}
            </div>
          );
        })}
      </div>

      {creating && zones && (
        <Modal title="Zonenzugriff gewähren" onClose={() => setCreating(false)}>
          <Msg msg={msg} />
          <Field label="Nutzer">
            <select className={inputCls} value={form.user_id} onChange={e => setForm(f => ({ ...f, user_id: e.target.value }))}>
              <option value="">Nutzer wählen…</option>
              {members?.map(m => <option key={m.user.id} value={m.user.id}>{m.user.display_name || m.user.email}</option>)}
            </select>
          </Field>
          <Field label="Zone">
            <select className={inputCls} value={form.zone_id} onChange={e => setForm(f => ({ ...f, zone_id: e.target.value }))}>
              <option value="">Zone wählen…</option>
              {zones.filter(z => !z.ad_group_only).map(z => <option key={z.id} value={z.id}>{z.name} ({z.slug})</option>)}
            </select>
          </Field>
          <Field label="Projekt-Scope (UUID, optional)">
            <input className={inputCls} value={form.project_scope} onChange={e => setForm(f => ({ ...f, project_scope: e.target.value }))} placeholder="Leer = org-weit" />
          </Field>
          <Field label="Gültig bis (optional — leer = permanent)">
            <input type="datetime-local" className={inputCls} value={form.valid_to} onChange={e => setForm(f => ({ ...f, valid_to: e.target.value }))} />
          </Field>
          <div className="flex justify-end gap-2 pt-1">
            <button onClick={() => setCreating(false)} className={btnOutline}>Abbrechen</button>
            <button onClick={() => void handleGrant()} disabled={saving || !form.user_id || !form.zone_id} className={btnPrimary}>
              {saving && <Spinner />}Zugriff gewähren
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ── Tab: Ingestion-Config ──────────────────────────────────────────────────────

const SOURCE_LABELS: Record<string, string> = {
  nextcloud: "Nextcloud / Dokumente",
  karl_story: "heyKarl Stories",
  jira: "Jira Tickets",
  confluence: "Confluence",
  user_action: "Team-Aktionen",
};

function IngestionTab({ orgId }: { orgId: string }) {
  const { data: config, mutate } = useSWR<IngestionZoneConfig>(
    `/api/v1/organizations/${orgId}/rag-zones/ingestion-config`, fetcher
  );
  const { data: zones } = useSWR<RagZone[]>(`/api/v1/organizations/${orgId}/rag-zones`, fetcher);
  const [form, setForm] = useState<IngestionZoneConfig>({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (config && Object.keys(config).length > 0) {
      setForm(prev => Object.keys(prev).length === 0 ? config : prev);
    }
  }, [config]);

  const handleSave = async () => {
    setSaving(true); setMsg(null);
    try {
      await apiRequest(`/api/v1/organizations/${orgId}/rag-zones/ingestion-config`, {
        method: "PATCH", body: JSON.stringify(form),
      });
      await mutate();
      setMsg({ type: "success", text: "Ingestion-Konfiguration gespeichert." });
      setTimeout(() => setMsg(null), 3000);
    } catch (e: any) {
      setMsg({ type: "error", text: e?.error ?? "Fehler" });
    } finally { setSaving(false); }
  };

  if (!config || !zones) return <div className="flex justify-center py-8"><Spinner /></div>;

  return (
    <div className="space-y-5 max-w-lg">
      <p className="text-sm text-[var(--ink-faint)]">
        Legt fest, in welche Zone neue Dokumente je Quelltyp beim Indizieren eingeordnet werden. Leer = öffentlich (keine Zonenzuweisung).
      </p>
      <Msg msg={msg} />
      <div className="space-y-3">
        {Object.keys(SOURCE_LABELS).map(key => (
          <Field key={key} label={SOURCE_LABELS[key]}>
            <select
              className={inputCls}
              value={(form as any)[key] ?? ""}
              onChange={e => setForm(f => ({ ...f, [key]: e.target.value || undefined }))}
            >
              <option value="">— keine Zone (öffentlich) —</option>
              {zones.filter(z => z.is_active).map(z => (
                <option key={z.id} value={z.slug}>{z.name} ({z.slug})</option>
              ))}
            </select>
          </Field>
        ))}
      </div>
      <button onClick={() => void handleSave()} disabled={saving} className={btnPrimary}>
        {saving && <Spinner />}Konfiguration speichern
      </button>
    </div>
  );
}
