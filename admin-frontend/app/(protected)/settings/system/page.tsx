"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { fetchConfig, patchConfig } from "@/lib/api";
import type { ConfigMap } from "@/types";

// ── ToolSection ───────────────────────────────────────────────────────────────

interface FieldDef {
  key: string;
  label: string;
  placeholder?: string;
}

function ToolSection({
  title,
  fields,
  config,
  onSaved,
}: {
  title: string;
  fields: FieldDef[];
  config: ConfigMap;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(true);
  const [values, setValues] = useState<Record<string, string | null>>({});
  const [editing, setEditing] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState(false);

  useEffect(() => {
    const init: Record<string, string | null> = {};
    const editInit: Record<string, boolean> = {};
    for (const f of fields) {
      const entry = config[f.key];
      if (entry?.is_secret) {
        init[f.key] = null;
        editInit[f.key] = false;
      } else {
        init[f.key] = entry?.value ?? null;
        editInit[f.key] = true;
      }
    }
    setValues(init);
    setEditing(editInit);
  }, [config, fields]);

  async function handleSave() {
    setSaving(true);
    try {
      for (const f of fields) {
        const entry = config[f.key];
        if (entry?.is_secret && !editing[f.key]) continue;
        await patchConfig(f.key, values[f.key] ?? null);
      }
      setSavedMsg(true);
      setTimeout(() => setSavedMsg(false), 2000);
      onSaved();
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="rounded-sm border"
      style={{ borderColor: "var(--paper-rule)", background: "var(--card)" }}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-4 text-sm font-semibold text-left"
        style={{ color: "var(--ink)" }}
      >
        <span>{title}</span>
        {open ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
      </button>

      {open && (
        <div className="px-5 pb-5 space-y-4 border-t" style={{ borderColor: "var(--paper-rule)" }}>
          <div className="pt-4 space-y-3">
            {fields.map((f) => {
              const entry = config[f.key];
              const isSecret = entry?.is_secret ?? false;
              const isSet = isSecret && (entry?.is_set ?? false);
              const isLocked = isSecret && !editing[f.key];

              return (
                <div key={f.key}>
                  <label
                    className="block text-xs font-medium mb-1"
                    style={{ color: "var(--ink-mid)" }}
                  >
                    {f.label}
                  </label>
                  {isLocked ? (
                    <div className="flex items-center gap-2">
                      <span
                        className="flex-1 px-3 py-1.5 text-sm rounded-sm border"
                        style={{
                          borderColor: "var(--paper-rule)",
                          background: "var(--paper-warm)",
                          color: "var(--ink-faint)",
                        }}
                      >
                        {isSet ? "●●●● gesetzt" : "Nicht gesetzt"}
                      </span>
                      <button
                        type="button"
                        onClick={() => setEditing((e) => ({ ...e, [f.key]: true }))}
                        className="text-xs px-2 py-1.5 rounded-sm border transition-colors"
                        style={{ borderColor: "var(--paper-rule)", color: "var(--ink-mid)" }}
                      >
                        Ändern
                      </button>
                    </div>
                  ) : (
                    <input
                      type={isSecret ? "password" : "text"}
                      value={values[f.key] ?? ""}
                      onChange={(e) =>
                        setValues((v) => ({ ...v, [f.key]: e.target.value || null }))
                      }
                      placeholder={f.placeholder ?? ""}
                      className="w-full px-3 py-1.5 text-sm border rounded-sm outline-none"
                      style={{
                        borderColor: "var(--paper-rule)",
                        background: "var(--card)",
                        color: "var(--ink)",
                      }}
                      onFocus={(e) => (e.target.style.borderColor = "var(--accent-red)")}
                      onBlur={(e) => (e.target.style.borderColor = "var(--paper-rule)")}
                    />
                  )}
                </div>
              );
            })}
          </div>

          <div className="flex items-center gap-3 pt-1">
            <button
              onClick={() => void handleSave()}
              disabled={saving}
              className="px-4 py-1.5 text-xs font-medium rounded-sm text-white transition-colors disabled:opacity-50"
              style={{ background: "var(--accent-red)" }}
            >
              {saving ? "Speichern…" : "Speichern"}
            </button>
            {savedMsg && (
              <span className="text-xs" style={{ color: "#526b5e" }}>
                Gespeichert
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── SSO subsection (toggle + clientId + clientSecret) ────────────────────────

function SSOSubsection({
  title,
  enabledKey,
  clientIdKey,
  clientSecretKey,
  config,
  onSaved,
}: {
  title: string;
  enabledKey: string;
  clientIdKey: string;
  clientSecretKey: string;
  config: ConfigMap;
  onSaved: () => void;
}) {
  const [enabled, setEnabled] = useState(config[enabledKey]?.value === "true");
  const [clientId, setClientId] = useState(config[clientIdKey]?.value ?? "");
  const [editSecret, setEditSecret] = useState(false);
  const [secret, setSecret] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState(false);
  const isSet = config[clientSecretKey]?.is_set ?? false;

  useEffect(() => {
    setEnabled(config[enabledKey]?.value === "true");
    setClientId(config[clientIdKey]?.value ?? "");
  }, [config, enabledKey, clientIdKey]);

  async function handleSave() {
    setSaving(true);
    try {
      await patchConfig(enabledKey, enabled ? "true" : "false");
      await patchConfig(clientIdKey, clientId || null);
      if (editSecret) await patchConfig(clientSecretKey, secret);
      setSavedMsg(true);
      setTimeout(() => setSavedMsg(false), 2000);
      onSaved();
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="p-4 rounded-sm border space-y-3"
      style={{ borderColor: "var(--paper-rule)" }}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium" style={{ color: "var(--ink)" }}>
          {title}
        </span>
        <button
          type="button"
          onClick={() => setEnabled((e) => !e)}
          className="relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 transition-colors"
          style={{
            borderColor: enabled ? "var(--accent-red)" : "var(--paper-rule)",
            background: enabled ? "var(--accent-red)" : "var(--paper-rule)",
          }}
          aria-checked={enabled}
          role="switch"
        >
          <span
            className="pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform"
            style={{ transform: enabled ? "translateX(16px)" : "translateX(0)" }}
          />
        </button>
      </div>

      <div>
        <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>
          Client ID
        </label>
        <input
          type="text"
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          className="w-full px-3 py-1.5 text-sm border rounded-sm outline-none"
          style={{ borderColor: "var(--paper-rule)", background: "var(--card)", color: "var(--ink)" }}
        />
      </div>

      <div>
        <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>
          Client Secret
        </label>
        {!editSecret ? (
          <div className="flex items-center gap-2">
            <span
              className="flex-1 px-3 py-1.5 text-sm rounded-sm border"
              style={{
                borderColor: "var(--paper-rule)",
                background: "var(--paper-warm)",
                color: "var(--ink-faint)",
              }}
            >
              {isSet ? "●●●● gesetzt" : "Nicht gesetzt"}
            </span>
            <button
              type="button"
              onClick={() => setEditSecret(true)}
              className="text-xs px-2 py-1.5 rounded-sm border"
              style={{ borderColor: "var(--paper-rule)", color: "var(--ink-mid)" }}
            >
              Ändern
            </button>
          </div>
        ) : (
          <input
            type="password"
            value={secret ?? ""}
            onChange={(e) => setSecret(e.target.value || null)}
            placeholder="Neues Secret eingeben"
            className="w-full px-3 py-1.5 text-sm border rounded-sm outline-none"
            style={{ borderColor: "var(--paper-rule)", background: "var(--card)", color: "var(--ink)" }}
          />
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => void handleSave()}
          disabled={saving}
          className="px-4 py-1.5 text-xs font-medium rounded-sm text-white disabled:opacity-50"
          style={{ background: "var(--accent-red)" }}
        >
          {saving ? "Speichern…" : "Speichern"}
        </button>
        {savedMsg && (
          <span className="text-xs" style={{ color: "#526b5e" }}>
            Gespeichert
          </span>
        )}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SystemSettingsPage() {
  const [config, setConfig] = useState<ConfigMap>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadConfig() {
    try {
      const data = await fetchConfig();
      setConfig(data);
    } catch {
      setError("Konfiguration konnte nicht geladen werden.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadConfig();
  }, []);

  if (loading) {
    return <p className="text-sm" style={{ color: "var(--ink-faint)" }}>Lade…</p>;
  }

  if (error) {
    return (
      <p
        className="text-sm p-3 rounded-sm border"
        style={{
          color: "var(--warn)",
          borderColor: "rgba(139,94,82,.3)",
          background: "rgba(139,94,82,.06)",
        }}
      >
        {error}
      </p>
    );
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="mb-6">
        <h1 className="text-xl font-semibold" style={{ color: "var(--ink)" }}>
          Systemkonfiguration
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>
          Globale Einstellungen für alle integrierten Dienste
        </p>
      </div>

      <ToolSection
        title="LiteLLM"
        fields={[
          { key: "litellm.url", label: "URL", placeholder: "http://assist2-litellm:4000" },
          { key: "litellm.api_key", label: "Master API Key" },
        ]}
        config={config}
        onSaved={() => void loadConfig()}
      />

      <ToolSection
        title="Nextcloud"
        fields={[
          { key: "nextcloud.url", label: "URL", placeholder: "http://assist2-nextcloud" },
          { key: "nextcloud.admin_user", label: "Admin-Benutzer", placeholder: "admin" },
          { key: "nextcloud.admin_password", label: "Admin-Passwort" },
        ]}
        config={config}
        onSaved={() => void loadConfig()}
      />

      <ToolSection
        title="n8n"
        fields={[
          { key: "n8n.url", label: "URL", placeholder: "http://assist2-n8n:5678" },
          { key: "n8n.api_key", label: "API Key" },
        ]}
        config={config}
        onSaved={() => void loadConfig()}
      />

      <div
        className="rounded-sm border"
        style={{ borderColor: "var(--paper-rule)", background: "var(--card)" }}
      >
        <div className="px-5 py-4 border-b" style={{ borderColor: "var(--paper-rule)" }}>
          <span className="text-sm font-semibold" style={{ color: "var(--ink)" }}>
            Auth-Provider
          </span>
        </div>
        <div className="px-5 py-4 space-y-4">
          <SSOSubsection
            title="Atlassian SSO"
            enabledKey="atlassian.sso_enabled"
            clientIdKey="atlassian.client_id"
            clientSecretKey="atlassian.client_secret"
            config={config}
            onSaved={() => void loadConfig()}
          />
          <SSOSubsection
            title="GitHub SSO"
            enabledKey="github.sso_enabled"
            clientIdKey="github.client_id"
            clientSecretKey="github.client_secret"
            config={config}
            onSaved={() => void loadConfig()}
          />
        </div>
      </div>

      <ToolSection
        title="KI-Provider"
        fields={[
          { key: "ai.anthropic_api_key", label: "Anthropic API Key" },
          { key: "ai.openai_api_key", label: "OpenAI API Key" },
          { key: "ai.ionos_api_key", label: "IONOS AI Key" },
        ]}
        config={config}
        onSaved={() => void loadConfig()}
      />
    </div>
  );
}
