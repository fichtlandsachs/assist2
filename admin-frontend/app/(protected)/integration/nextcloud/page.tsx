"use client";

import { useEffect, useState } from "react";
import { fetchConfig, patchConfig } from "@/lib/api";
import type { ConfigMap } from "@/types";

/** Same-origin login entry; avoids relative links resolving to /nextcloud/Nextcloud when base is …/nextcloud/. */
const WEB_UI_LOGIN = "/nextcloud/login";

export default function NextcloudPage() {
  const [config, setConfig] = useState<ConfigMap>({});
  const [url, setUrl] = useState("");
  const [user, setUser] = useState("");
  const [pass, setPass] = useState<string | null>(null);
  const [editPass, setEditPass] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchConfig().then(c => {
      setConfig(c);
      setUrl(c["nextcloud.url"]?.value ?? "");
      setUser(c["nextcloud.admin_user"]?.value ?? "");
    }).catch(() => {});
  }, []);

  const isPassSet = config["nextcloud.admin_password"]?.is_set ?? false;

  async function handleSave() {
    setSaving(true);
    try {
      await patchConfig("nextcloud.url", url || null);
      await patchConfig("nextcloud.admin_user", user || null);
      if (editPass) await patchConfig("nextcloud.admin_password", pass);
      setSaved(true); setTimeout(() => setSaved(false), 2500);
    } finally { setSaving(false); }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white text-lg font-bold"
          style={{ background: "#0082c9" }}>NC</div>
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--ink)" }}>Nextcloud</h1>
          <p className="text-sm" style={{ color: "var(--ink-faint)" }}>File Source · Docker-Ressource · Integration Layer</p>
        </div>
      </div>
      <div className="neo-card p-5 space-y-4">
        <h2 className="text-sm font-bold" style={{ color: "var(--ink)" }}>Weboberflaeche (dieser Host)</h2>
        <p className="text-xs" style={{ color: "var(--ink-faint)" }}>
          Nextcloud laeuft unter demselben Host wie das Admin-UI mit Praefix <span className="font-mono">/nextcloud</span>.
          Ein Login-Link ohne mehrdeutige Basis-URL vermeidet fehlerhafte Pfade wie{" "}
          <span className="font-mono">/nextcloud/Nextcloud</span>.
        </p>
        <a href={WEB_UI_LOGIN} target="_blank" rel="noreferrer" className="neo-btn neo-btn--outline neo-btn--sm inline-block">
          Nextcloud Login oeffnen
        </a>
      </div>

      <div className="neo-card p-5 space-y-4">
        <h2 className="text-sm font-bold" style={{ color: "var(--ink)" }}>Verbindungseinstellungen</h2>
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>URL</label>
          <input type="text" value={url} onChange={e => setUrl(e.target.value)}
            placeholder="http://heykarl-nextcloud" className="neo-input w-full text-sm" />
        </div>
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Admin-Benutzer</label>
          <input type="text" value={user} onChange={e => setUser(e.target.value)}
            placeholder="admin" className="neo-input w-full text-sm" />
        </div>
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Admin-Passwort</label>
          {!editPass ? (
            <div className="flex items-center gap-2">
              <span className="flex-1 px-3 py-1.5 text-sm rounded-sm border"
                style={{ borderColor: "var(--paper-rule)", background: "var(--paper-warm)", color: "var(--ink-faint)" }}>
                {isPassSet ? "●●●● gesetzt" : "Nicht gesetzt"}
              </span>
              <button onClick={() => setEditPass(true)} className="neo-btn neo-btn--outline neo-btn--sm">Ändern</button>
            </div>
          ) : (
            <input type="password" value={pass ?? ""} onChange={e => setPass(e.target.value || null)}
              placeholder="Passwort" className="neo-input w-full text-sm" />
          )}
        </div>
        <div className="flex items-center gap-3 pt-1">
          <button onClick={() => void handleSave()} disabled={saving} className="neo-btn neo-btn--default neo-btn--sm">
            {saving ? "Speichern…" : "Speichern"}
          </button>
          {saved && <span className="text-xs" style={{ color: "var(--green)" }}>Gespeichert ✓</span>}
        </div>
      </div>
    </div>
  );
}
