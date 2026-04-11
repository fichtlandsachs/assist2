"use client";

import { use, useEffect, useState, useCallback } from "react";
import { fetchOrganizations, fetchOrgIntegrations, patchOrgIntegration } from "@/lib/api";
import type { OrgIntegrationSettings, OrgMetrics } from "@/types";

// ── SecretField ───────────────────────────────────────────────────────────────

function SecretField({
  label,
  isSet,
  value,
  editing,
  onEdit,
  onChange,
}: {
  label: string;
  isSet: boolean;
  value: string;
  editing: boolean;
  onEdit: () => void;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>
        {label}
      </label>
      {!editing ? (
        <div className="flex items-center gap-2">
          <span className="text-sm" style={{ color: isSet ? "var(--green)" : "var(--ink-faint)" }}>
            {isSet ? "●●●● gesetzt" : "Nicht gesetzt"}
          </span>
          <button
            onClick={onEdit}
            className="text-xs px-2 py-0.5 rounded-sm border"
            style={{ borderColor: "var(--paper-rule)", color: "var(--ink-mid)" }}
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
          className="w-full px-3 py-1.5 text-sm rounded-sm border outline-none"
          style={{
            borderColor: "var(--paper-rule)",
            background: "var(--card)",
            color: "var(--ink)",
          }}
        />
      )}
    </div>
  );
}

// ── TextField ─────────────────────────────────────────────────────────────────

function TextField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>
        {label}
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-1.5 text-sm rounded-sm border outline-none"
        style={{
          borderColor: "var(--paper-rule)",
          background: "var(--card)",
          color: "var(--ink)",
        }}
      />
    </div>
  );
}

// ── SaveButton ────────────────────────────────────────────────────────────────

function SaveButton({ saving, saved }: { saving: boolean; saved: boolean }) {
  return (
    <button
      type="submit"
      disabled={saving}
      className="px-4 py-1.5 text-sm rounded-sm text-white disabled:opacity-60"
      style={{ background: "var(--accent-red)" }}
    >
      {saving ? "Speichert…" : saved ? "Gespeichert ✓" : "Speichern"}
    </button>
  );
}

// ── JiraSection ───────────────────────────────────────────────────────────────

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
        base_url: baseUrl,
        user,
        api_token: editingToken && token ? token : null,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Section title="Jira">
      <form onSubmit={handleSubmit} className="space-y-3">
        <TextField label="Base URL" value={baseUrl} onChange={setBaseUrl} placeholder="https://acme.atlassian.net" />
        <TextField label="Benutzer (E-Mail)" value={user} onChange={setUser} placeholder="user@acme.com" />
        <SecretField
          label="API Token"
          isSet={initial.api_token_set}
          value={token}
          editing={editingToken}
          onEdit={() => setEditingToken(true)}
          onChange={setToken}
        />
        <div className="pt-1">
          <SaveButton saving={saving} saved={saved} />
        </div>
      </form>
    </Section>
  );
}

// ── ConfluenceSection ─────────────────────────────────────────────────────────

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
        base_url: baseUrl,
        user,
        api_token: editingToken && token ? token : null,
        default_space_key: spaceKey,
        default_parent_page_id: parentPageId,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Section title="Confluence">
      <form onSubmit={handleSubmit} className="space-y-3">
        <TextField label="Base URL" value={baseUrl} onChange={setBaseUrl} placeholder="https://acme.atlassian.net/wiki" />
        <TextField label="Benutzer (E-Mail)" value={user} onChange={setUser} placeholder="user@acme.com" />
        <SecretField
          label="API Token"
          isSet={initial.api_token_set}
          value={token}
          editing={editingToken}
          onEdit={() => setEditingToken(true)}
          onChange={setToken}
        />
        <TextField label="Standard Space Key" value={spaceKey} onChange={setSpaceKey} placeholder="PROJ" />
        <TextField label="Standard Parent Page ID" value={parentPageId} onChange={setParentPageId} placeholder="123456" />
        <div className="pt-1">
          <SaveButton saving={saving} saved={saved} />
        </div>
      </form>
    </Section>
  );
}

// ── SSOSection ────────────────────────────────────────────────────────────────

function SSOSection({
  title,
  orgId,
  type,
  initial,
}: {
  title: string;
  orgId: string;
  type: "github" | "atlassian";
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
        enabled,
        client_id: clientId,
        client_secret: editingSecret && secret ? secret : null,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Section title={title}>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id={`${type}-enabled`}
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            className="accent-[var(--accent-red)]"
          />
          <label htmlFor={`${type}-enabled`} className="text-sm" style={{ color: "var(--ink-mid)" }}>
            Aktiviert
          </label>
        </div>
        <TextField label="Client ID" value={clientId} onChange={setClientId} />
        <SecretField
          label="Client Secret"
          isSet={initial.client_secret_set}
          value={secret}
          editing={editingSecret}
          onEdit={() => setEditingSecret(true)}
          onChange={setSecret}
        />
        <div className="pt-1">
          <SaveButton saving={saving} saved={saved} />
        </div>
      </form>
    </Section>
  );
}

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded-sm border" style={{ borderColor: "var(--paper-rule)", background: "var(--card)" }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-4 text-sm font-semibold text-left"
        style={{ color: "var(--ink)" }}
      >
        <span>{title}</span>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          {open
            ? <polyline points="6 9 12 15 18 9" />
            : <polyline points="9 18 15 12 9 6" />}
        </svg>
      </button>
      {open && (
        <div className="px-5 pb-5 pt-4 border-t space-y-0" style={{ borderColor: "var(--paper-rule)" }}>
          {children}
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function OrgSettingsPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const [org, setOrg] = useState<OrgMetrics | null>(null);
  const [integrations, setIntegrations] = useState<OrgIntegrationSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const orgs = await fetchOrganizations();
      const found = orgs.find((o) => o.slug === slug);
      if (!found) { setError("Organisation nicht gefunden"); return; }
      setOrg(found);
      const data = await fetchOrgIntegrations(found.id);
      setIntegrations(data);
    } catch {
      setError("Fehler beim Laden der Einstellungen");
    }
  }, [slug]);

  useEffect(() => { void load(); }, [load]);

  if (error) {
    return (
      <p className="text-sm p-3 rounded-sm border" style={{ color: "var(--warn)", borderColor: "rgba(139,94,82,.3)", background: "rgba(139,94,82,.06)" }}>
        {error}
      </p>
    );
  }

  if (!org || !integrations) {
    return <div className="text-sm" style={{ color: "var(--ink-faint)" }}>Lade…</div>;
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="mb-6">
        <h1 className="text-xl font-semibold" style={{ color: "var(--ink)" }}>{org.name}</h1>
        <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>
          Organisationsspezifische Integrationseinstellungen
        </p>
      </div>

      <JiraSection orgId={org.id} initial={integrations.jira} />
      <ConfluenceSection orgId={org.id} initial={integrations.confluence} />
      <SSOSection title="Atlassian SSO (org-spezifisch)" orgId={org.id} type="atlassian" initial={integrations.atlassian} />
      <SSOSection title="GitHub SSO (org-spezifisch)" orgId={org.id} type="github" initial={integrations.github} />
    </div>
  );
}
