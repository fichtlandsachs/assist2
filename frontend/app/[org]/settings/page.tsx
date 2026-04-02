"use client";

import { use, useState, useEffect } from "react";
import { useOrg } from "@/lib/hooks/useOrg";
import { useAuth } from "@/lib/auth/context";
import { useTheme, type ThemeId } from "@/lib/theme/context";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { User, UserStory } from "@/types";
import {
  Building2, Mail, CalendarDays, AlertCircle,
  Layers, Cloud, CheckCircle, Trash2, Plus, Eye, EyeOff, RefreshCw,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────

interface MailConnection { id: string; provider: string; email_address: string; display_name: string | null; is_active: boolean; last_sync_at: string | null; imap_host?: string | null; imap_port?: number | null; imap_use_ssl?: boolean | null; }
interface CalendarConnection { id: string; provider: string; email_address: string; display_name: string | null; is_active: boolean; last_sync_at: string | null; }
interface IntegrationSettings {
  jira: { base_url: string; user: string; api_token_set: boolean };
  confluence: { base_url: string; user: string; api_token_set: boolean };
  ai: {
    ai_provider: string;
    anthropic_api_key_set: boolean;
    openai_api_key_set: boolean;
    model_override: string;
  };
}

// ── Helpers ────────────────────────────────────────────────────────────────

function SaveButton({ saving, label = "Speichern" }: { saving: boolean; label?: string }) {
  return (
    <button
      type="submit"
      disabled={saving}
      className="flex items-center gap-2 px-4 py-2 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--ink-faint)] text-white rounded-sm text-sm font-medium transition-colors"
    >
      {saving && <div className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white border-t-transparent" />}
      {saving ? "Speichern…" : label}
    </button>
  );
}

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${ok ? "bg-[rgba(82,107,94,.1)] text-[var(--green)]" : "bg-[var(--paper-warm)] text-[var(--ink-faint)]"}`}>
      {ok ? <CheckCircle size={11} /> : <AlertCircle size={11} />}
      {label}
    </span>
  );
}

function TokenField({
  id, label, placeholder, value, onChange, isSet, hint,
}: {
  id: string; label: string; placeholder: string;
  value: string; onChange: (v: string) => void;
  isSet: boolean; hint?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label htmlFor={id} className="block text-sm font-medium text-[var(--ink-mid)]">{label}</label>
        {isSet && <StatusBadge ok label="Gesetzt" />}
      </div>
      <div className="relative">
        <input
          id={id}
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={isSet ? "••••••••••••••••••••" : placeholder}
          className="w-full px-3 py-2 pr-9 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--card)]"
        />
        <button type="button" onClick={() => setShow((v) => !v)}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--ink-faint)] hover:text-[var(--ink-mid)]">
          {show ? <EyeOff size={15} /> : <Eye size={15} />}
        </button>
      </div>
      {hint && <p className="text-xs text-[var(--ink-faint)] mt-1">{hint}</p>}
    </div>
  );
}

function FormField({ id, label, value, onChange, placeholder, type = "text" }: {
  id: string; label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; type?: string;
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-[var(--ink-mid)] mb-1">{label}</label>
      <input id={id} type={type} value={value} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--card)]" />
    </div>
  );
}

function SectionMessage({ msg }: { msg: { type: "success" | "error"; text: string } | null }) {
  if (!msg) return null;
  return (
    <div className={`px-4 py-3 rounded-sm text-sm ${msg.type === "success" ? "bg-[rgba(82,107,94,.1)] border border-[var(--green)] text-[var(--green)]" : "bg-[rgba(var(--accent-red-rgb),.08)] border border-[var(--accent-red)] text-[var(--accent-red)]"}`}>
      {msg.text}
    </div>
  );
}

// ── Tab definitions ────────────────────────────────────────────────────────

const TABS = [
  { id: "general",    label: "Allgemein",  Icon: Building2 },
  { id: "email",      label: "E-Mail",     Icon: Mail },
  { id: "calendar",   label: "Kalender",   Icon: CalendarDays },
  { id: "jira",       label: "Jira",       Icon: Layers },
  { id: "confluence", label: "Confluence", Icon: Cloud },
] as const;
type TabId = typeof TABS[number]["id"];

// ── Section: General ───────────────────────────────────────────────────────

function GeneralSection({ org, mutateOrg }: { org: any; mutateOrg: () => void }) {
  const [name, setName] = useState(org.name);
  const [description, setDescription] = useState(org.description ?? "");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setMsg(null);
    try {
      await apiRequest(`/api/v1/organizations/${org.id}`, { method: "PATCH", body: JSON.stringify({ name, description }) });
      await mutateOrg();
      setMsg({ type: "success", text: "Einstellungen gespeichert." });
    } catch { setMsg({ type: "error", text: "Fehler beim Speichern." }); }
    finally { setSaving(false); }
  };

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 max-w-lg">
      <SectionMessage msg={msg} />
      <FormField id="name" label="Name" value={name} onChange={setName} />
      <div>
        <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1">Slug</label>
        <input value={org.slug} disabled className="w-full px-3 py-2 text-sm border border-[var(--paper-rule)] rounded-sm bg-[var(--paper-warm)] text-[var(--ink-faint)] cursor-not-allowed" />
      </div>
      <div>
        <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1">Beschreibung</label>
        <textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)}
          className="w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] resize-none" />
      </div>
      <div>
        <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1">Plan</label>
        <input value={org.plan} disabled className="w-full px-3 py-2 text-sm border border-[var(--paper-rule)] rounded-sm bg-[var(--paper-warm)] text-[var(--ink-faint)] cursor-not-allowed" />
      </div>
      <SaveButton saving={saving} />
    </form>
  );
}

// ── Section: Email ─────────────────────────────────────────────────────────

function EmailSection({ orgId }: { orgId: string }) {
  const { data: connections, mutate } = useSWR<MailConnection[]>(
    `/api/v1/inbox/connections?org_id=${orgId}`, fetcher
  );
  const [provider, setProvider] = useState("imap");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [imapHost, setImapHost] = useState("");
  const [imapPort, setImapPort] = useState("993");
  const [imapPassword, setImapPassword] = useState("");
  const [imapEncryption, setImapEncryption] = useState("ssl");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  function handleEncryptionChange(enc: string) {
    setImapEncryption(enc);
    if (enc === "ssl") setImapPort("993");
    else if (enc === "starttls") setImapPort("587");
    else setImapPort("143");
  }

  function resetForm() {
    setEmail(""); setDisplayName("");
    setImapHost(""); setImapPort("993"); setImapPassword(""); setImapEncryption("ssl");
    setProvider("imap");
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setMsg(null);
    try {
      const body: Record<string, unknown> = {
        provider,
        email_address: email,
        display_name: displayName || null,
      };
      if (provider === "imap") {
        if (!imapHost.trim()) { setMsg({ type: "error", text: "Bitte gib den IMAP-Server ein." }); setSaving(false); return; }
        if (!imapPassword) { setMsg({ type: "error", text: "Bitte gib das Passwort ein." }); setSaving(false); return; }
        body.imap_host = imapHost.trim();
        body.imap_port = parseInt(imapPort) || 993;
        body.imap_password = imapPassword;
        body.imap_use_ssl = imapEncryption === "ssl";
      }
      await apiRequest(`/api/v1/inbox/connections?org_id=${orgId}`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      await mutate();
      resetForm();
      setMsg({ type: "success", text: "Verbindung hergestellt." });
    } catch { setMsg({ type: "error", text: "Fehler beim Verbinden." }); }
    finally { setSaving(false); }
  }

  async function handleDelete(id: string) {
    setDeleting(id);
    try { await apiRequest(`/api/v1/inbox/connections/${id}`, { method: "DELETE" }); await mutate(); }
    catch { /* ignore */ }
    finally { setDeleting(null); }
  }

  const selectCls = "w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--card)]";

  return (
    <div className="space-y-5 max-w-xl">
      {/* Existing connections */}
      {connections && connections.length > 0 && (
        <div className="space-y-2">
          {connections.map((c) => (
            <div key={c.id} className="flex items-center justify-between p-3 border border-[var(--paper-rule)] rounded-sm bg-[var(--card)]">
              <div className="flex items-center gap-3">
                <Mail size={16} className="text-[var(--ink-faint)] shrink-0" />
                <div>
                  <p className="text-sm font-medium text-[var(--ink)]">{c.display_name ?? c.email_address}</p>
                  <p className="text-xs text-[var(--ink-faint)]">{c.email_address} · {c.provider.toUpperCase()}{c.provider === "imap" && c.imap_host ? ` · ${c.imap_host}:${c.imap_port ?? 993}` : ""}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge ok={c.is_active} label={c.is_active ? "Aktiv" : "Inaktiv"} />
                <button type="button" onClick={() => void handleDelete(c.id)} disabled={deleting === c.id}
                  className="p-1.5 text-[var(--ink-faint)] hover:text-[var(--accent-red)] hover:bg-[rgba(var(--accent-red-rgb),.08)] rounded transition-colors">
                  {deleting === c.id ? <div className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-[var(--accent-red)] border-t-transparent" /> : <Trash2 size={14} />}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add connection form — always visible */}
      <form onSubmit={(e) => void handleAdd(e)} className="border border-[var(--paper-rule)] rounded-sm bg-[var(--paper-warm)]">
        <div className="px-4 py-3 border-b border-[var(--paper-rule)]">
          <p className="text-sm font-semibold text-[var(--ink)]">Neues E-Mail-Konto verbinden</p>
        </div>

        <div className="p-4 space-y-3">
          <SectionMessage msg={msg} />

          {/* Provider */}
          <div>
            <label htmlFor="email-provider" className="block text-sm font-medium text-[var(--ink-mid)] mb-1">Protokoll</label>
            <select
              id="email-provider"
              value={provider}
              onChange={(e) => {
                setProvider(e.target.value);
                if (e.target.value === "imap") handleEncryptionChange("ssl");
              }}
              className={selectCls}
            >
              <option value="imap">IMAP</option>
              <option value="gmail">Gmail</option>
              <option value="outlook">Outlook</option>
            </select>
          </div>

          <FormField id="new-email-addr" label="E-Mail-Adresse" value={email} onChange={setEmail} placeholder="name@beispiel.de" type="email" />
          <FormField id="new-email-name" label="Anzeigename (optional)" value={displayName} onChange={setDisplayName} placeholder="Mein Postfach" />

          {/* IMAP-specific fields */}
          {provider === "imap" && (
            <div className="space-y-3 pt-3 mt-1 border-t border-[var(--paper-rule)]">
              <p className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide">Servereinstellungen</p>

              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <label htmlFor="imap-host" className="block text-sm font-medium text-[var(--ink-mid)] mb-1">Server</label>
                  <input
                    id="imap-host"
                    type="text"
                    value={imapHost}
                    onChange={(e) => setImapHost(e.target.value)}
                    placeholder="imap.beispiel.de"
                    className={selectCls}
                  />
                </div>
                <div>
                  <label htmlFor="imap-port" className="block text-sm font-medium text-[var(--ink-mid)] mb-1">Port</label>
                  <input
                    id="imap-port"
                    type="number"
                    value={imapPort}
                    onChange={(e) => setImapPort(e.target.value)}
                    placeholder="993"
                    className={selectCls}
                  />
                </div>
              </div>

              <div>
                <label htmlFor="imap-enc" className="block text-sm font-medium text-[var(--ink-mid)] mb-1">Verschlüsselung</label>
                <select
                  id="imap-enc"
                  value={imapEncryption}
                  onChange={(e) => handleEncryptionChange(e.target.value)}
                  className={selectCls}
                >
                  <option value="ssl">SSL / TLS (Port 993, empfohlen)</option>
                  <option value="starttls">STARTTLS (Port 587)</option>
                  <option value="none">Keine Verschlüsselung (Port 143)</option>
                </select>
              </div>

              <div>
                <label htmlFor="imap-pass" className="block text-sm font-medium text-[var(--ink-mid)] mb-1">Passwort</label>
                <TokenField id="imap-pass" label="" placeholder="••••••••" value={imapPassword} onChange={setImapPassword} isSet={false} />
              </div>
            </div>
          )}

          <div className="pt-1">
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--ink-faint)] text-white rounded-sm text-sm font-medium transition-colors"
            >
              {saving && <div className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white border-t-transparent" />}
              {saving ? "Verbinde…" : "Verbinden"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

// ── Section: Calendar ──────────────────────────────────────────────────────

function CalendarSection({ orgId }: { orgId: string }) {
  const { data: connections, mutate } = useSWR<CalendarConnection[]>(
    `/api/v1/calendar/connections?org_id=${orgId}`, fetcher
  );
  const [showForm, setShowForm] = useState(false);
  const [provider, setProvider] = useState("google");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setMsg(null);
    try {
      await apiRequest(`/api/v1/calendar/connections?org_id=${orgId}`, {
        method: "POST",
        body: JSON.stringify({ provider, email_address: email, display_name: displayName || null }),
      });
      await mutate();
      setEmail(""); setDisplayName(""); setShowForm(false);
      setMsg({ type: "success", text: "Kalender verbunden." });
    } catch { setMsg({ type: "error", text: "Fehler beim Hinzufügen." }); }
    finally { setSaving(false); }
  }

  async function handleDelete(id: string) {
    setDeleting(id);
    try { await apiRequest(`/api/v1/calendar/connections/${id}`, { method: "DELETE" }); await mutate(); }
    catch { /* ignore */ }
    finally { setDeleting(null); }
  }

  return (
    <div className="space-y-4 max-w-xl">
      <div className="flex items-center justify-between">
        <p className="text-sm text-[var(--ink-mid)]">Kalender-Konten für die Kalenderansicht verwalten.</p>
        <button onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] text-white rounded-sm text-xs font-medium transition-colors">
          <Plus size={13} /> Kalender hinzufügen
        </button>
      </div>

      <SectionMessage msg={msg} />

      {showForm && (
        <form onSubmit={(e) => void handleAdd(e)} className="border border-[var(--paper-rule)] rounded-sm p-4 space-y-3 bg-[var(--paper-warm)]">
          <div>
            <label className="block text-xs font-medium text-[var(--ink-mid)] mb-1">Anbieter</label>
            <select value={provider} onChange={(e) => setProvider(e.target.value)}
              className="w-full px-3 py-1.5 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] bg-[var(--card)]">
              <option value="google">Google Kalender</option>
              <option value="outlook">Outlook / Microsoft 365</option>
            </select>
          </div>
          <FormField id="cal-email" label="E-Mail-Adresse" value={email} onChange={setEmail} placeholder="name@beispiel.de" type="email" />
          <FormField id="cal-name" label="Anzeigename (optional)" value={displayName} onChange={setDisplayName} placeholder="Mein Kalender" />
          <div className="flex gap-2">
            <SaveButton saving={saving} label="Hinzufügen" />
            <button type="button" onClick={() => setShowForm(false)}
              className="px-3 py-2 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] rounded-sm text-sm font-medium transition-colors">
              Abbrechen
            </button>
          </div>
        </form>
      )}

      {!connections ? (
        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--accent-red)]" />
      ) : connections.length === 0 ? (
        <p className="text-sm text-[var(--ink-faint)] text-center py-6">Keine Kalender verbunden.</p>
      ) : (
        <div className="space-y-2">
          {connections.map((c) => (
            <div key={c.id} className="flex items-center justify-between p-3 border border-[var(--paper-rule)] rounded-sm bg-[var(--card)]">
              <div className="flex items-center gap-3">
                <CalendarDays size={16} className="text-[var(--ink-faint)] shrink-0" />
                <div>
                  <p className="text-sm font-medium text-[var(--ink)]">{c.display_name ?? c.email_address}</p>
                  <p className="text-xs text-[var(--ink-faint)]">{c.email_address} · {c.provider === "google" ? "Google" : "Outlook"}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge ok={c.is_active} label={c.is_active ? "Aktiv" : "Inaktiv"} />
                <button onClick={() => void handleDelete(c.id)} disabled={deleting === c.id}
                  className="p-1.5 text-[var(--ink-faint)] hover:text-[var(--accent-red)] hover:bg-[rgba(var(--accent-red-rgb),.08)] rounded transition-colors">
                  {deleting === c.id ? <div className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-[var(--accent-red)] border-t-transparent" /> : <Trash2 size={14} />}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Section: Jira ──────────────────────────────────────────────────────────

function JiraSection({ orgId, settings }: { orgId: string; settings: IntegrationSettings["jira"]; onSaved: () => void }) {
  const [baseUrl, setBaseUrl] = useState(settings.base_url);
  const [user, setUser] = useState(settings.user);
  const [token, setToken] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setMsg(null);
    try {
      await apiRequest(`/api/v1/organizations/${orgId}/integrations/jira`, {
        method: "PATCH",
        body: JSON.stringify({ base_url: baseUrl, user, api_token: token || null }),
      });
      setToken("");
      setMsg({ type: "success", text: "Jira-Einstellungen gespeichert." });
    } catch { setMsg({ type: "error", text: "Fehler beim Speichern." }); }
    finally { setSaving(false); }
  };

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 max-w-lg">
      <p className="text-sm text-[var(--ink-mid)]">
        Verbindet die Plattform mit Jira für Issue-Verlinkung und Workflow-Automatisierung.
      </p>
      <SectionMessage msg={msg} />
      <FormField id="jira-url" label="Jira-URL" value={baseUrl} onChange={setBaseUrl}
        placeholder="https://dein-org.atlassian.net" />
      <FormField id="jira-user" label="E-Mail / Benutzername" value={user} onChange={setUser}
        placeholder="user@beispiel.de" />
      <TokenField id="jira-token" label="API-Token" placeholder="Atlassian API-Token eingeben"
        value={token} onChange={setToken} isSet={settings.api_token_set}
        hint="Generiere einen Token unter atlassian.com → Konto → Sicherheit → API-Token" />
      <SaveButton saving={saving} />
    </form>
  );
}

// ── Section: Confluence ────────────────────────────────────────────────────

function ConfluenceSection({ orgId, settings }: { orgId: string; settings: IntegrationSettings["confluence"]; onSaved: () => void }) {
  const [baseUrl, setBaseUrl] = useState(settings.base_url);
  const [user, setUser] = useState(settings.user);
  const [token, setToken] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setMsg(null); setTestResult(null);
    try {
      await apiRequest(`/api/v1/organizations/${orgId}/integrations/confluence`, {
        method: "PATCH",
        body: JSON.stringify({ base_url: baseUrl, user, api_token: token || null }),
      });
      setToken("");
      setMsg({ type: "success", text: "Confluence-Einstellungen gespeichert." });
    } catch { setMsg({ type: "error", text: "Fehler beim Speichern." }); }
    finally { setSaving(false); }
  };

  const handleTest = async () => {
    setTestLoading(true); setTestResult(null);
    try {
      const res = await apiRequest<{ configured: boolean; spaces: { key: string; name: string }[]; error?: string }>(
        `/api/v1/confluence/spaces?org_id=${orgId}`, { method: "GET" }
      );
      if (res.configured && res.spaces.length > 0) {
        setTestResult(`✓ Verbindung erfolgreich. ${res.spaces.length} Space(s) gefunden: ${res.spaces.slice(0, 3).map((s) => s.name).join(", ")}${res.spaces.length > 3 ? "…" : ""}`);
      } else if (res.configured) {
        setTestResult("✓ Verbindung hergestellt, aber keine Spaces gefunden.");
      } else {
        setTestResult("✗ Nicht konfiguriert oder Verbindung fehlgeschlagen.");
      }
    } catch { setTestResult("✗ Verbindungstest fehlgeschlagen."); }
    finally { setTestLoading(false); }
  };

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 max-w-lg">
      <p className="text-sm text-[var(--ink-mid)]">
        Verbindet die Plattform mit Confluence für die Veröffentlichung von Dokumentation.
      </p>
      <SectionMessage msg={msg} />
      <FormField id="conf-url" label="Confluence-URL" value={baseUrl} onChange={setBaseUrl}
        placeholder="https://dein-org.atlassian.net/wiki" />
      <FormField id="conf-user" label="E-Mail / Benutzername" value={user} onChange={setUser}
        placeholder="user@beispiel.de" />
      <TokenField id="conf-token" label="API-Token" placeholder="Atlassian API-Token eingeben"
        value={token} onChange={setToken} isSet={settings.api_token_set}
        hint="Generiere einen Token unter atlassian.com → Konto → Sicherheit → API-Token" />
      {testResult && (
        <p className={`text-xs px-3 py-2 rounded-sm ${testResult.startsWith("✓") ? "bg-[rgba(82,107,94,.1)] text-[var(--green)]" : "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]"}`}>
          {testResult}
        </p>
      )}
      <div className="flex gap-2">
        <SaveButton saving={saving} />
        <button type="button" onClick={() => void handleTest()} disabled={testLoading}
          className="flex items-center gap-2 px-4 py-2 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] disabled:opacity-50 rounded-sm text-sm font-medium transition-colors">
          {testLoading ? <div className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-[var(--ink-faint)] border-t-transparent" /> : <RefreshCw size={14} />}
          Verbindung testen
        </button>
      </div>
    </form>
  );
}

// ── Section: AI ────────────────────────────────────────────────────────────

const ANTHROPIC_MODELS = [
  { value: "", label: "Automatisch (empfohlen)" },
  { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
  { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5" },
  { value: "claude-opus-4-6", label: "Claude Opus 4.6" },
];

const OPENAI_MODELS = [
  { value: "", label: "Automatisch (empfohlen)" },
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "gpt-4o-mini", label: "GPT-4o mini" },
  { value: "gpt-4-turbo", label: "GPT-4 Turbo" },
];

function AISection({ orgId, settings }: { orgId: string; settings: IntegrationSettings["ai"] }) {
  const [provider, setProvider] = useState(settings.ai_provider || "anthropic");
  const [anthropicKey, setAnthropicKey] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [modelOverride, setModelOverride] = useState(settings.model_override);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const modelOptions = provider === "openai" ? OPENAI_MODELS : ANTHROPIC_MODELS;

  // Reset model override when switching providers (avoid invalid model strings)
  function handleProviderChange(p: string) {
    setProvider(p);
    setModelOverride("");
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setMsg(null);
    try {
      await apiRequest(`/api/v1/organizations/${orgId}/integrations/ai`, {
        method: "PATCH",
        body: JSON.stringify({
          model_override: modelOverride,
          ai_provider: provider,
          anthropic_api_key: provider === "anthropic" ? (anthropicKey || null) : null,
          openai_api_key: provider === "openai" ? (openaiKey || null) : null,
        }),
      });
      setAnthropicKey("");
      setOpenaiKey("");
      setMsg({ type: "success", text: "Einstellungen gespeichert." });
    } catch { setMsg({ type: "error", text: "Fehler beim Speichern." }); }
    finally { setSaving(false); }
  };

  const selectCls = "w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--card)]";

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 max-w-lg">
      <p className="text-sm text-[var(--ink-mid)]">
        KI-Anbieter, API-Schlüssel und Modell-Einstellungen konfigurieren.
      </p>
      <SectionMessage msg={msg} />

      {/* Provider selector */}
      <div>
        <label className="block text-sm font-medium text-[var(--ink-mid)] mb-2">KI-Anbieter</label>
        <div className="flex gap-3">
          {[
            { value: "anthropic", label: "Anthropic (Claude)" },
            { value: "openai", label: "OpenAI (ChatGPT)" },
          ].map(({ value, label }) => (
            <label key={value} className={`flex items-center gap-2 px-4 py-2.5 rounded-sm border cursor-pointer text-sm font-medium transition-colors ${
              provider === value
                ? "border-[var(--accent-red)] bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]"
                : "border-[var(--paper-rule)] bg-[var(--card)] text-[var(--ink-mid)] hover:border-[var(--ink-faintest)]"
            }`}>
              <input
                type="radio"
                name="ai-provider"
                value={value}
                checked={provider === value}
                onChange={() => handleProviderChange(value)}
                className="sr-only"
              />
              {label}
            </label>
          ))}
        </div>
      </div>

      {/* API Key */}
      {provider === "anthropic" ? (
        <TokenField
          id="ai-anthropic-key"
          label="Anthropic API-Key"
          placeholder="sk-ant-api03-…"
          value={anthropicKey}
          onChange={setAnthropicKey}
          isSet={settings.anthropic_api_key_set}
          hint="Erhältlich unter console.anthropic.com → API Keys"
        />
      ) : (
        <TokenField
          id="ai-openai-key"
          label="OpenAI API-Key"
          placeholder="sk-proj-…"
          value={openaiKey}
          onChange={setOpenaiKey}
          isSet={settings.openai_api_key_set}
          hint="Erhältlich unter platform.openai.com → API Keys"
        />
      )}

      {/* Model override */}
      <div>
        <label htmlFor="model-override" className="block text-sm font-medium text-[var(--ink-mid)] mb-1">
          Modell-Override <span className="font-normal text-[var(--ink-faint)] text-xs ml-1">(leer = automatisches Routing)</span>
        </label>
        <select
          id="model-override"
          value={modelOverride}
          onChange={(e) => setModelOverride(e.target.value)}
          className={selectCls}
        >
          {modelOptions.map(({ value, label }) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>

      <SaveButton saving={saving} />
    </form>
  );
}

// ── Section: Atlassian Connection ─────────────────────────────────────────

function AtlassianConnectionSection({ user }: { user: User }) {
  const { loginWithAtlassian } = useAuth();
  const [disconnecting, setDisconnecting] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const isConnected = !!user.atlassian_account_id;

  const disconnect = async () => {
    setDisconnecting(true);
    setMsg(null);
    try {
      await apiRequest("/api/v1/auth/atlassian/disconnect", { method: "POST" });
      setMsg("Atlassian-Verbindung getrennt.");
      window.location.reload();
    } catch (e: unknown) {
      const err = e as { error?: string };
      setMsg(err?.error ?? "Fehler beim Trennen der Verbindung.");
    } finally {
      setDisconnecting(false);
    }
  };

  return (
    <div className="rounded-sm p-4 space-y-3" style={{ border: "0.5px solid var(--paper-rule)", background: "var(--paper-warm)" }}>
      <div className="flex items-center justify-between">
        <div>
          <p style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--ink-mid)" }}>Atlassian</p>
          <p style={{ fontFamily: "var(--font-body)", fontSize: "13px", color: "var(--ink-faint)", marginTop: "2px" }}>
            {isConnected
              ? `Verbunden als ${user.atlassian_email ?? user.email}`
              : "Nicht verbunden"}
          </p>
        </div>
        {isConnected ? (
          <button
            onClick={() => void disconnect()}
            disabled={disconnecting}
            className="px-3 py-1.5 rounded-sm transition-colors disabled:opacity-50"
            style={{ fontFamily: "var(--font-mono)", fontSize: "8px", letterSpacing: ".06em", textTransform: "uppercase", border: "0.5px solid var(--accent-red)", color: "var(--accent-red)" }}
          >
            {disconnecting ? "Trenne…" : "Trennen"}
          </button>
        ) : (
          <button
            onClick={loginWithAtlassian}
            className="px-3 py-1.5 rounded-sm transition-colors"
            style={{ fontFamily: "var(--font-mono)", fontSize: "8px", letterSpacing: ".06em", textTransform: "uppercase", border: "0.5px solid var(--paper-rule)", color: "var(--ink)" }}
          >
            Verbinden
          </button>
        )}
      </div>
      {msg && (
        <p style={{ fontFamily: "var(--font-body)", fontSize: "12px", color: "var(--ink-faint)" }}>{msg}</p>
      )}
    </div>
  );
}

// ── Section: GitHub Connection ────────────────────────────────────────────

function GitHubConnectionSection({ user }: { user: User }) {
  const { loginWithGitHub } = useAuth();
  const [disconnecting, setDisconnecting] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const isConnected = !!user.github_id;

  const disconnect = async () => {
    setDisconnecting(true);
    setMsg(null);
    try {
      await apiRequest("/api/v1/auth/github/disconnect", { method: "POST" });
      setMsg("GitHub-Verbindung getrennt.");
      window.location.reload();
    } catch (e: unknown) {
      const err = e as { error?: string };
      setMsg(err?.error ?? "Fehler beim Trennen der Verbindung.");
    } finally {
      setDisconnecting(false);
    }
  };

  return (
    <div className="rounded-sm p-4 space-y-3" style={{ border: "0.5px solid var(--paper-rule)", background: "var(--paper-warm)" }}>
      <div className="flex items-center justify-between">
        <div>
          <p style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--ink-mid)" }}>GitHub</p>
          <p style={{ fontFamily: "var(--font-body)", fontSize: "13px", color: "var(--ink-faint)", marginTop: "2px" }}>
            {isConnected
              ? `Verbunden als ${user.github_username ?? user.github_email ?? user.email}`
              : "Nicht verbunden"}
          </p>
        </div>
        {isConnected ? (
          <button
            onClick={() => void disconnect()}
            disabled={disconnecting}
            className="px-3 py-1.5 rounded-sm transition-colors disabled:opacity-50"
            style={{ fontFamily: "var(--font-mono)", fontSize: "8px", letterSpacing: ".06em", textTransform: "uppercase", border: "0.5px solid var(--accent-red)", color: "var(--accent-red)" }}
          >
            {disconnecting ? "Trenne…" : "Trennen"}
          </button>
        ) : (
          <button
            onClick={loginWithGitHub}
            className="px-3 py-1.5 rounded-sm transition-colors"
            style={{ fontFamily: "var(--font-mono)", fontSize: "8px", letterSpacing: ".06em", textTransform: "uppercase", border: "0.5px solid var(--paper-rule)", color: "var(--ink)" }}
          >
            Verbinden
          </button>
        )}
      </div>
      {msg && (
        <p style={{ fontFamily: "var(--font-body)", fontSize: "12px", color: "var(--ink-faint)" }}>{msg}</p>
      )}
    </div>
  );
}

// ── Theme Selector ────────────────────────────────────────────────────────

const THEMES: { id: ThemeId; name: string; desc: string; preview: { bg: string; sidebar: string; text: string; accent: string; font: string } }[] = [
  {
    id: "paperwork",
    name: "Paperwork",
    desc: "Analoges Papier-Ästhetik mit Serifenschrift und Karo-Hintergrund",
    preview: { bg: "var(--paper)", sidebar: "var(--binding)", text: "var(--ink)", accent: "var(--accent-red)", font: "Georgia, serif" },
  },
  {
    id: "agile",
    name: "Agile",
    desc: "Cleanes, modernes Interface mit kräftigen Kontrasten",
    preview: { bg: "#FDFBF7", sidebar: "#231F1F", text: "#231F1F", accent: "#534D5F", font: "Inter, sans-serif" },
  },
];

function ThemeSelector() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="space-y-3">
      <div className="flex gap-3">
        {THEMES.map((t) => {
          const active = theme === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setTheme(t.id)}
              className="flex-1 text-left rounded-sm transition-all focus-visible:outline-none"
              style={{
                border: active ? `1.5px solid var(--accent-red)` : "1px solid var(--paper-rule)",
                background: active ? "rgba(var(--accent-red-rgb),.04)" : "var(--paper-warm)",
                boxShadow: active ? "0 0 0 3px rgba(var(--accent-red-rgb),.1)" : "none",
              }}
            >
              {/* Mini-Vorschau */}
              <div
                className="rounded-t-sm overflow-hidden"
                style={{ height: "72px", background: t.preview.bg, display: "flex", borderBottom: "1px solid var(--paper-rule)" }}
              >
                {/* Fake-Sidebar */}
                <div style={{ width: "28px", background: t.preview.sidebar, flexShrink: 0, display: "flex", flexDirection: "column", gap: "4px", padding: "6px 4px" }}>
                  {[1, 2, 3].map(i => (
                    <div key={i} style={{ height: "3px", borderRadius: "1px", background: "rgba(255,255,255,.25)" }} />
                  ))}
                </div>
                {/* Fake-Content */}
                <div style={{ flex: 1, padding: "8px", display: "flex", flexDirection: "column", gap: "5px" }}>
                  <div style={{ height: "5px", width: "55%", borderRadius: "2px", background: t.preview.text, opacity: .7, fontFamily: t.preview.font }} />
                  <div style={{ height: "3px", width: "80%", borderRadius: "2px", background: t.preview.text, opacity: .2 }} />
                  <div style={{ height: "3px", width: "65%", borderRadius: "2px", background: t.preview.text, opacity: .2 }} />
                  <div style={{ marginTop: "4px", height: "14px", width: "40%", borderRadius: "2px", background: t.preview.accent, opacity: .8 }} />
                </div>
              </div>

              {/* Label */}
              <div className="px-3 py-2.5">
                <div className="flex items-center justify-between">
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: active ? "var(--accent-red)" : "var(--ink)", fontWeight: active ? 600 : 400 }}>
                    {t.name}
                  </span>
                  {active && (
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "7px", letterSpacing: ".06em", textTransform: "uppercase", color: "var(--accent-red)" }}>
                      Aktiv
                    </span>
                  )}
                </div>
                <p style={{ fontFamily: "var(--font-body)", fontSize: "11px", color: "var(--ink-faint)", marginTop: "2px", lineHeight: 1.4 }}>
                  {t.desc}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function SettingsPage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { org, mutate: mutateOrg } = useOrg(resolvedParams.org);
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<TabId>("general");

  const { data: integrationSettings, mutate: mutateIntegrations } = useSWR<IntegrationSettings>(
    org ? `/api/v1/organizations/${org.id}/integrations` : null,
    fetcher,
    { revalidateOnFocus: false }
  );

  if (!org) {
    return (
      <div className="flex items-center justify-center h-48">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--accent-red)]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--ink)]">Einstellungen</h1>
        <p className="text-[var(--ink-faint)] mt-1 text-sm">Organisation und Integrationen konfigurieren</p>
      </div>

      <div className="flex flex-col md:flex-row gap-4 md:gap-6">
        {/* Tab nav — horizontal scroll on mobile, vertical sidebar on md+ */}
        <nav className="flex md:flex-col md:w-48 md:shrink-0 gap-1 overflow-x-auto pb-1 md:pb-0">
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-sm text-sm font-medium transition-colors whitespace-nowrap md:w-full md:text-left ${
                activeTab === id
                  ? "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)] font-semibold"
                  : "text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] hover:text-[var(--ink)]"
              }`}
            >
              <Icon size={16} className={activeTab === id ? "text-[var(--accent-red)]" : "text-[var(--ink-faint)]"} />
              {label}
            </button>
          ))}
        </nav>

        {/* Tab content */}
        <div className="flex-1 rounded-sm p-4 md:p-6 min-w-0" style={{ background: "var(--paper)", border: "1px solid var(--paper-rule)" }}>
          {activeTab === "general" && (
            <>
              <h2 className="text-base font-semibold text-[var(--ink)] mb-5">Allgemeine Einstellungen</h2>
              <GeneralSection org={org} mutateOrg={mutateOrg} />
              <div className="mt-6 max-w-lg space-y-2">
                <h3 className="text-sm font-semibold text-[var(--ink)]">Erscheinungsbild</h3>
                <ThemeSelector />
              </div>
              {user && (
                <div className="mt-6 max-w-lg space-y-2">
                  <h3 className="text-sm font-semibold text-[var(--ink)]">Verknüpfte Konten</h3>
                  <AtlassianConnectionSection user={user} />
                  <GitHubConnectionSection user={user} />
                </div>
              )}
            </>
          )}
          {activeTab === "email" && (
            <>
              <h2 className="text-base font-semibold text-[var(--ink)] mb-5">E-Mail-Konten</h2>
              <EmailSection orgId={org.id} />
            </>
          )}
          {activeTab === "calendar" && (
            <>
              <h2 className="text-base font-semibold text-[var(--ink)] mb-5">Kalender-Verbindungen</h2>
              <CalendarSection orgId={org.id} />
            </>
          )}
          {activeTab === "jira" && (
            <>
              <h2 className="text-base font-semibold text-[var(--ink)] mb-5">Jira-Integration</h2>
              {integrationSettings ? (
                <JiraSection orgId={org.id} settings={integrationSettings.jira} onSaved={mutateIntegrations} />
              ) : (
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--accent-red)]" />
              )}
            </>
          )}
          {activeTab === "confluence" && (
            <>
              <h2 className="text-base font-semibold text-[var(--ink)] mb-5">Confluence-Integration</h2>
              {integrationSettings ? (
                <ConfluenceSection orgId={org.id} settings={integrationSettings.confluence} onSaved={mutateIntegrations} />
              ) : (
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--accent-red)]" />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
