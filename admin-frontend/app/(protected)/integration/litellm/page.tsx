"use client";

import { useEffect, useState } from "react";
import { fetchConfig, patchConfig } from "@/lib/api";
import type { ConfigMap } from "@/types";

export default function LiteLLMPage() {
  const [config, setConfig] = useState<ConfigMap>({});
  const [url, setUrl] = useState("");
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [editKey, setEditKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchConfig().then(c => {
      setConfig(c);
      setUrl(c["litellm.url"]?.value ?? "");
    }).catch(() => {});
  }, []);

  const isKeySet = config["litellm.api_key"]?.is_set ?? false;

  async function handleSave() {
    setSaving(true);
    try {
      await patchConfig("litellm.url", url || null);
      if (editKey) await patchConfig("litellm.api_key", apiKey);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } finally { setSaving(false); }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white text-lg font-bold"
          style={{ background: "#0284c7" }}>L</div>
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--ink)" }}>LiteLLM</h1>
          <p className="text-sm" style={{ color: "var(--ink-faint)" }}>AI Model Gateway · Docker-Ressource · Integration Layer</p>
        </div>
      </div>

      <div className="neo-card p-5 space-y-4">
        <h2 className="text-sm font-bold" style={{ color: "var(--ink)" }}>Verbindungseinstellungen</h2>

        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>URL</label>
          <input type="text" value={url} onChange={e => setUrl(e.target.value)}
            placeholder="http://heykarl-litellm:4000"
            className="neo-input w-full text-sm" />
        </div>

        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Master API Key</label>
          {!editKey ? (
            <div className="flex items-center gap-2">
              <span className="flex-1 px-3 py-1.5 text-sm rounded-sm border"
                style={{ borderColor: "var(--paper-rule)", background: "var(--paper-warm)", color: "var(--ink-faint)" }}>
                {isKeySet ? "●●●● gesetzt" : "Nicht gesetzt"}
              </span>
              <button onClick={() => setEditKey(true)} className="neo-btn neo-btn--outline neo-btn--sm">Ändern</button>
            </div>
          ) : (
            <input type="password" value={apiKey ?? ""} onChange={e => setApiKey(e.target.value || null)}
              placeholder="sk-…" className="neo-input w-full text-sm" />
          )}
        </div>

        <div className="flex items-center gap-3 pt-1">
          <button onClick={() => void handleSave()} disabled={saving} className="neo-btn neo-btn--default neo-btn--sm">
            {saving ? "Speichern…" : "Speichern"}
          </button>
          {saved && <span className="text-xs" style={{ color: "var(--green)" }}>Gespeichert ✓</span>}
        </div>
      </div>

      <div className="neo-card p-4 text-xs space-y-1" style={{ color: "var(--ink-faint)" }}>
        <p className="font-semibold" style={{ color: "var(--ink-mid)" }}>Architektur-Hinweis</p>
        <p>LiteLLM ist eine Docker-Ressource und wird ausschließlich über den Integration Layer konfiguriert.</p>
        <p>Der Core und die Conversation Engine nutzen LiteLLM über definierte Service-Interfaces.</p>
      </div>
    </div>
  );
}
