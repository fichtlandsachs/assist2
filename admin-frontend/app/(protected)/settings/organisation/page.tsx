"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchOrganizations, fetchOrgIntegrations, patchOrgIntegration } from "@/lib/api";
import type { OrgIntegrationSettings, OrgMetrics } from "@/types";

// ── Shared field components ───────────────────────────────────────────────────

function TextField({
  label, value, onChange, placeholder,
}: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="neo-input w-full text-sm"
      />
    </div>
  );
}

function SecretField({
  label, isSet, value, editing, onEdit, onChange,
}: {
  label: string; isSet: boolean; value: string; editing: boolean;
  onEdit: () => void; onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>{label}</label>
      {!editing ? (
        <div className="flex items-center gap-2">
          <span className="text-sm" style={{ color: isSet ? "var(--green)" : "var(--ink-faint)" }}>
            {isSet ? "●●●● gesetzt" : "Nicht gesetzt"}
          </span>
          <button
            type="button"
            onClick={onEdit}
            className="neo-btn neo-btn--outline neo-btn--sm"
          >
            Ändern
          </button>
        </div>
      ) : (
        <input
          type="password"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Neuen Wert eingeben…"
          className="neo-input w-full text-sm"
        />
      )}
    </div>
  );
}

function SaveButton({ saving, saved }: { saving: boolean; saved: boolean }) {
  return (
    <button
      type="submit"
      disabled={saving}
      className="neo-btn neo-btn--default neo-btn--sm"
    >
      {saving ? "Speichert…" : saved ? "Gespeichert ✓" : "Speichern"}
    </button>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="neo-card">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-4 text-sm font-bold text-left"
        style={{ color: "var(--ink)" }}
      >
        <span>{title}</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          {open ? <polyline points="6 9 12 15 18 9" /> : <polyline points="9 18 15 12 9 6" />}
        </svg>
      </button>
      {open && (
        <div className="px-5 pb-5 pt-4 border-t-2 space-y-3" style={{ borderColor: "var(--paper-rule)" }}>
          {children}
        </div>
      )}
    </div>
  );
}

// ── Integration sections ──────────────────────────────────────────────────────

function JiraSection({ orgId, initial }: { orgId: string; initial: OrgIntegrationSettings["jira"] }) {
  const [baseUrl, setBaseUrl] = useState(initial.base_url);
  const [user, setUser] = useState(initial.user);
  const [token, setToken] = useState("");
  const [editingToken, setEditingToken] = useState(!initial.api_token_set);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await patchOrgIntegration(orgId, "jira", {
        base_url: baseUrl, user,
        api_token: editingToken && token ? token : null,
      });
      setSaved(true); setTimeout(() => setSaved(false), 2000);
    } finally { setSaving(false); }
  }

  return (
    <Section title="Jira">
      <form onSubmit={handleSubmit} className="space-y-3">
        <TextField label="Base URL" value={baseUrl} onChange={setBaseUrl} placeholder="https://acme.atlassian.net" />
        <TextField label="Benutzer (E-Mail)" value={user} onChange={setUser} placeholder="user@acme.com" />
        <SecretField label="API Token" isSet={initial.api_token_set} value={token}
          editing={editingToken} onEdit={() => setEditingToken(true)} onChange={setToken} />
        <SaveButton saving={saving} saved={saved} />
      </form>
    </Section>
  );
}

function ConfluenceSection({ orgId, initial }: { orgId: string; initial: OrgIntegrationSettings["confluence"] }) {
  const [baseUrl, setBaseUrl] = useState(initial.base_url);
  const [user, setUser] = useState(initial.user);
  const [token, setToken] = useState("");
  const [editingToken, setEditingToken] = useState(!initial.api_token_set);
  const [spaceKey, setSpaceKey] = useState(initial.default_space_key);
  const [parentPageId, setParentPageId] = useState(initial.default_parent_page_id);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await patchOrgIntegration(orgId, "confluence", {
        base_url: baseUrl, user,
        api_token: editingToken && token ? token : null,
        default_space_key: spaceKey,
        default_parent_page_id: parentPageId,
      });
      setSaved(true); setTimeout(() => setSaved(false), 2000);
    } finally { setSaving(false); }
  }

  return (
    <Section title="Confluence">
      <form onSubmit={handleSubmit} className="space-y-3">
        <TextField label="Base URL" value={baseUrl} onChange={setBaseUrl} placeholder="https://acme.atlassian.net/wiki" />
        <TextField label="Benutzer (E-Mail)" value={user} onChange={setUser} placeholder="user@acme.com" />
        <SecretField label="API Token" isSet={initial.api_token_set} value={token}
          editing={editingToken} onEdit={() => setEditingToken(true)} onChange={setToken} />
        <TextField label="Standard Space Key" value={spaceKey} onChange={setSpaceKey} placeholder="PROJ" />
        <TextField label="Standard Parent Page ID" value={parentPageId} onChange={setParentPageId} placeholder="123456" />
        <SaveButton saving={saving} saved={saved} />
      </form>
    </Section>
  );
}

function SSOSection({
  title, orgId, type, initial,
}: {
  title: string; orgId: string; type: "github" | "atlassian";
  initial: OrgIntegrationSettings["github"];
}) {
  const [enabled, setEnabled] = useState(initial.enabled);
  const [clientId, setClientId] = useState(initial.client_id);
  const [secret, setSecret] = useState("");
  const [editingSecret, setEditingSecret] = useState(!initial.client_secret_set);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await patchOrgIntegration(orgId, type, {
        enabled, client_id: clientId,
        client_secret: editingSecret && secret ? secret : null,
      });
      setSaved(true); setTimeout(() => setSaved(false), 2000);
    } finally { setSaving(false); }
  }

  return (
    <Section title={title}>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="flex items-center gap-2">
          <input type="checkbox" id={`${type}-enabled`} checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)} className="accent-[var(--accent-red)]" />
          <label htmlFor={`${type}-enabled`} className="text-sm" style={{ color: "var(--ink-mid)" }}>Aktiviert</label>
        </div>
        <TextField label="Client ID" value={clientId} onChange={setClientId} />
        <SecretField label="Client Secret" isSet={initial.client_secret_set} value={secret}
          editing={editingSecret} onEdit={() => setEditingSecret(true)} onChange={setSecret} />

        <SaveButton saving={saving} saved={saved} />
      </form>
    </Section>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function OrganisationSettingsPage() {
  const [orgs, setOrgs] = useState<OrgMetrics[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [integrations, setIntegrations] = useState<OrgIntegrationSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load org list once
  useEffect(() => {
    fetchOrganizations()
      .then((data) => {
        setOrgs(data);
        if (data.length > 0) setSelectedId(data[0].id);
      })
      .catch(() => setError("Organisationen konnten nicht geladen werden."));
  }, []);

  // Load integrations whenever selection changes
  const loadIntegrations = useCallback(async (id: string) => {
    if (!id) return;
    setLoading(true);
    setIntegrations(null);
    setError(null);
    try {
      const data = await fetchOrgIntegrations(id);
      setIntegrations(data);
    } catch {
      setError("Einstellungen konnten nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId) void loadIntegrations(selectedId);
  }, [selectedId, loadIntegrations]);

  const selectedOrg = orgs.find((o) => o.id === selectedId);

  return (
    <div className="space-y-5 max-w-2xl">
      {/* Org selector */}
      <div className="flex items-center gap-3">
        <span className="text-sm font-bold" style={{ color: "var(--ink-mid)" }}>Organisation:</span>
        <select
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          className="px-3 py-2 text-sm font-medium border-2 rounded-xl outline-none min-w-[220px]"
          style={{
            borderColor: "var(--ink)",
            background: "white",
            color: "var(--ink)",
            boxShadow: "3px 3px 0 rgba(0,0,0,0.85)",
          }}
        >
          {orgs.length === 0 && <option value="">Lade…</option>}
          {orgs.map((o) => (
            <option key={o.id} value={o.id}>{o.name}</option>
          ))}
        </select>
      </div>

      {/* Status indicators */}
      {error && (
        <p className="text-sm p-3 rounded-sm border"
          style={{ color: "var(--warn)", borderColor: "rgba(139,94,82,.3)", background: "rgba(139,94,82,.06)" }}>
          {error}
        </p>
      )}

      {loading && (
        <p className="text-sm" style={{ color: "var(--ink-faint)" }}>Lade…</p>
      )}

      {/* Settings sections */}
      {integrations && selectedOrg && (
        <>
          <JiraSection orgId={selectedOrg.id} initial={integrations.jira} />
          <ConfluenceSection orgId={selectedOrg.id} initial={integrations.confluence} />
          <SSOSection title="Atlassian SSO" orgId={selectedOrg.id} type="atlassian" initial={integrations.atlassian} />
          <SSOSection title="GitHub SSO" orgId={selectedOrg.id} type="github" initial={integrations.github} />
        </>
      )}
    </div>
  );
}
