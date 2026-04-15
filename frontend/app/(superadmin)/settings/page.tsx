"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, Eye, EyeOff, Loader2, Send, XCircle } from "lucide-react";
import { apiRequest } from "@/lib/api/client";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ConfigEntry {
  value: string | null;
  is_secret?: boolean;
  is_set?: boolean;
}

type ConfigMap = Record<string, ConfigEntry>;

interface Group {
  label: string;
  keys: { key: string; label: string; placeholder?: string; type?: "text" | "number" }[];
}

// ── Settings groups definition ────────────────────────────────────────────────

const GROUPS: Group[] = [
  {
    label: "SMTP / E-Mail",
    keys: [
      { key: "smtp.host",       label: "Host",           placeholder: "smtp.hostinger.com" },
      { key: "smtp.port",       label: "Port",           placeholder: "587", type: "number" },
      { key: "smtp.user",       label: "Benutzername",   placeholder: "info@heykarl.app" },
      { key: "smtp.pass",       label: "Passwort",       placeholder: "••••••••" },
      { key: "smtp.from",       label: "Absender",       placeholder: "noreply@heykarl.app" },
      { key: "smtp.contact_to", label: "Empfänger",      placeholder: "info@heykarl.app" },
    ],
  },
  {
    label: "AI Provider",
    keys: [
      { key: "ai.ionos_api_key",            label: "IONOS API Key" },
      { key: "ai.ionos_api_base",           label: "IONOS API Base URL",       placeholder: "https://openai.ionos.com/openai" },
      { key: "ai.anthropic_api_key",        label: "Anthropic API Key" },
      { key: "ai.openai_api_key",           label: "OpenAI API Key" },
      { key: "ai.provider_routing_suggest", label: "Routing: suggest",         placeholder: "auto" },
      { key: "ai.provider_routing_docs",    label: "Routing: docs",            placeholder: "claude-sonnet-4-6" },
      { key: "ai.provider_routing_fallback",label: "Routing: fallback",        placeholder: "ionos-fast" },
      { key: "ai.feature_flags",            label: "Feature Flags",            placeholder: "streaming,embeddings" },
    ],
  },
  {
    label: "LiteLLM",
    keys: [
      { key: "litellm.url",     label: "LiteLLM URL",   placeholder: "http://heykarl-litellm:4000" },
      { key: "litellm.api_key", label: "LiteLLM API Key" },
    ],
  },
  {
    label: "Nextcloud",
    keys: [
      { key: "nextcloud.url",            label: "URL",            placeholder: "https://nextcloud.heykarl.app" },
      { key: "nextcloud.admin_user",     label: "Admin-Benutzer", placeholder: "admin" },
      { key: "nextcloud.admin_password", label: "Admin-Passwort" },
    ],
  },
  {
    label: "n8n",
    keys: [
      { key: "n8n.url",     label: "Webhook URL", placeholder: "http://n8n:5678" },
      { key: "n8n.api_key", label: "API Key" },
    ],
  },
  {
    label: "OAuth SSO",
    keys: [
      { key: "atlassian.client_id",     label: "Atlassian Client ID" },
      { key: "atlassian.client_secret", label: "Atlassian Client Secret" },
      { key: "github.client_id",        label: "GitHub Client ID" },
      { key: "github.client_secret",    label: "GitHub Client Secret" },
    ],
  },
  {
    label: "Chat Policy",
    keys: [
      { key: "chat.policy_mode",          label: "Policy Mode",         placeholder: "strict_grounded" },
      { key: "chat.min_evidence_count",   label: "Min. Evidence Count", placeholder: "1", type: "number" },
      { key: "chat.min_relevance_score",  label: "Min. Relevance Score",placeholder: "0.50" },
      { key: "chat.fallback_message",     label: "Fallback-Nachricht" },
      { key: "chat.web_signal",           label: "Web-Signal",          placeholder: "/WEB" },
      { key: "chat.web_requires_signal",  label: "Web nur mit Signal",  placeholder: "true" },
    ],
  },
];

// ── Field component ───────────────────────────────────────────────────────────

function Field({
  cfgKey,
  label,
  placeholder,
  entry,
  onSave,
}: {
  cfgKey: string;
  label: string;
  placeholder?: string;
  entry: ConfigEntry | undefined;
  onSave: (key: string, value: string | null) => Promise<void>;
}) {
  const isSecret = entry?.is_secret ?? false;
  const initialValue = isSecret ? "" : (entry?.value ?? "");
  const [value, setValue] = useState(initialValue);
  const [show, setShow] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Reset when entry changes (initial load)
  useEffect(() => {
    if (!isSecret) setValue(entry?.value ?? "");
  }, [entry?.value, isSecret]);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave(cfgKey, value || null);
      setSaved(true);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setSaved(false), 2500);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler beim Speichern");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <label className="text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--ink-faint)]">
          {label}
          {isSecret && entry?.is_set && (
            <span className="ml-2 text-[9px] bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full font-semibold">gesetzt</span>
          )}
        </label>
        {saved && <CheckCircle2 size={12} className="text-emerald-500" />}
        {error && <span title={error}><XCircle size={12} className="text-red-500" /></span>}
      </div>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            type={isSecret && !show ? "password" : "text"}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void save()}
            placeholder={isSecret && entry?.is_set ? "Unverändert lassen (bereits gesetzt)" : placeholder}
            className="w-full px-3 py-2 text-[13px] border border-[var(--paper-rule)] rounded-lg outline-none focus:border-[var(--ink)] transition-colors bg-white pr-8"
          />
          {isSecret && (
            <button
              type="button"
              onClick={() => setShow((s) => !s)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--ink-faint)] hover:text-[var(--ink)]"
            >
              {show ? <EyeOff size={13} /> : <Eye size={13} />}
            </button>
          )}
        </div>
        <button
          onClick={() => void save()}
          disabled={saving}
          className="neo-btn neo-btn--default px-3 py-2 text-[12px] font-bold disabled:opacity-40"
        >
          {saving ? <Loader2 size={13} className="animate-spin" /> : "Speichern"}
        </button>
      </div>
      {error && <p className="text-[11px] text-red-500">{error}</p>}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [config, setConfig] = useState<ConfigMap>({});
  const [loading, setLoading] = useState(true);
  const [smtpTesting, setSmtpTesting] = useState(false);
  const [smtpResult, setSmtpResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiRequest<ConfigMap>("/api/v1/superadmin/config/");
      setConfig(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const save = useCallback(async (key: string, value: string | null) => {
    await apiRequest("/api/v1/superadmin/config/", {
      method: "PATCH",
      body: JSON.stringify({ key, value }),
    });
    // Refresh to pick up is_set changes for secrets
    const data = await apiRequest<ConfigMap>("/api/v1/superadmin/config/");
    setConfig(data);
  }, []);

  const testSmtp = async () => {
    setSmtpTesting(true);
    setSmtpResult(null);
    try {
      const res = await apiRequest<{ ok: boolean; sent_to: string }>("/api/v1/superadmin/config/test-smtp", { method: "POST" });
      setSmtpResult({ ok: true, msg: `Test-Mail gesendet an ${res.sent_to}` });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "SMTP-Test fehlgeschlagen";
      setSmtpResult({ ok: false, msg });
    } finally {
      setSmtpTesting(false);
    }
  };

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-black text-[var(--ink)]">System-Einstellungen</h1>
        <p className="text-[12px] text-[var(--ink-faint)] mt-1">
          Werte hier überschreiben die <code className="bg-[var(--paper-rule)] px-1 rounded">.env</code>-Konfiguration zur Laufzeit. Secrets werden verschlüsselt gespeichert.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-[var(--ink-faint)]">
          <Loader2 size={14} className="animate-spin" />
          <span className="text-sm">Lade Einstellungen …</span>
        </div>
      ) : (
        GROUPS.map((group) => (
          <section key={group.label} className="bg-white border border-[var(--paper-rule)] rounded-2xl p-6 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-[11px] font-bold uppercase tracking-[0.15em] text-[var(--ink-faint)]">{group.label}</h2>
              {group.label === "SMTP / E-Mail" && (
                <div className="flex items-center gap-3">
                  {smtpResult && (
                    <span className={`text-[11px] font-medium ${smtpResult.ok ? "text-emerald-600" : "text-red-500"}`}>
                      {smtpResult.ok ? "✓ " : "✗ "}{smtpResult.msg}
                    </span>
                  )}
                  <button
                    onClick={() => void testSmtp()}
                    disabled={smtpTesting}
                    className="flex items-center gap-1.5 text-[11px] font-bold px-3 py-1.5 rounded-lg border border-[var(--paper-rule)] hover:bg-[var(--paper-warm)] transition-colors disabled:opacity-40"
                  >
                    {smtpTesting ? <Loader2 size={11} className="animate-spin" /> : <Send size={11} />}
                    Test-Mail senden
                  </button>
                </div>
              )}
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {group.keys.map(({ key, label, placeholder }) => (
                <Field
                  key={key}
                  cfgKey={key}
                  label={label}
                  placeholder={placeholder}
                  entry={config[key]}
                  onSave={save}
                />
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}
