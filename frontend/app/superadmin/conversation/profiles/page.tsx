"use client";

import { useEffect, useState } from "react";
import { authFetch } from "@/lib/api/client";

interface DialogProfile {
  id: string;
  key: string;
  name: string;
  description: string | null;
  mode: string;
  tone: string;
  is_default: boolean;
  is_active: boolean;
  config_json: Record<string, unknown>;
  version: number;
}

const MODES = ["story_mode", "exploration_mode", "review_mode", "correction_mode"];
const TONES = ["friendly", "open", "analytical", "structured", "motivating"];

function ProfileCard({ profile, onEdit }: { profile: DialogProfile; onEdit: (p: DialogProfile) => void }) {
  return (
    <div className="neo-card p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-0.5">
            <h3 className="font-bold text-sm" style={{ color: "var(--ink)" }}>{profile.name}</h3>
            {profile.is_default && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full font-bold"
                style={{ background: "#22c55e22", color: "#22c55e" }}>Standard</span>
            )}
            {!profile.is_active && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full"
                style={{ background: "#94a3b822", color: "#94a3b8" }}>Inaktiv</span>
            )}
          </div>
          <p className="text-xs font-mono" style={{ color: "var(--ink-faint)" }}>{profile.key}</p>
        </div>
        <button onClick={() => onEdit(profile)} className="neo-btn neo-btn--outline neo-btn--sm">Bearbeiten</button>
      </div>
      {profile.description && (
        <p className="text-xs" style={{ color: "var(--ink-mid)" }}>{profile.description}</p>
      )}
      <div className="flex gap-3 text-xs" style={{ color: "var(--ink-faint)" }}>
        <span>Modus: <strong style={{ color: "var(--ink)" }}>{profile.mode}</strong></span>
        <span>Ton: <strong style={{ color: "var(--ink)" }}>{profile.tone}</strong></span>
        <span>v{profile.version}</span>
      </div>
    </div>
  );
}

export default function ConversationProfilesPage() {
  const [profiles, setProfiles] = useState<DialogProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<DialogProfile | null>(null);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    key: "", name: "", description: "", mode: "story_mode",
    tone: "friendly", is_default: false, is_active: true, config_json: "{}",
  });

  async function load() {
    setLoading(true);
    try {
      const res = await authFetch("/api/v1/superadmin/conversation-engine/profiles");
      if (res.ok) {
        setProfiles(await res.json());
        setError(null);
      } else if (res.status === 401) {
        setError("No session");
        // Token abgelaufen oder ungültig – zur Login-Seite weiterleiten
        if (typeof window !== "undefined") {
          setTimeout(() => { window.location.href = "/login"; }, 1500);
        }
      } else if (res.status === 403) {
        setError("Zugriff verweigert. Superadmin-Rechte erforderlich.");
      } else {
        const err = await res.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        setError(typeof err.detail === "string" ? err.detail : err.error || `Fehler ${res.status}`);
      }
    } catch (e) {
      setError("Netzwerkfehler. Bitte prüfen Sie die Verbindung.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  function openCreate() {
    setForm({ key: "", name: "", description: "", mode: "story_mode", tone: "friendly", is_default: false, is_active: true, config_json: "{}" });
    setEditing(null);
    setCreating(true);
  }

  function openEdit(p: DialogProfile) {
    setForm({
      key: p.key, name: p.name, description: p.description ?? "",
      mode: p.mode, tone: p.tone, is_default: p.is_default,
      is_active: p.is_active, config_json: JSON.stringify(p.config_json, null, 2),
    });
    setEditing(p);
    setCreating(true);
  }

  async function save() {
    setSaving(true);
    let config = {};
    try { config = JSON.parse(form.config_json); } catch { /* keep empty */ }
    const body = { ...form, config_json: config };
    const url = editing
      ? `/api/v1/superadmin/conversation-engine/profiles/${editing.id}`
      : "/api/v1/superadmin/conversation-engine/profiles";
    const res = await authFetch(url, {
      method: editing ? "PATCH" : "POST",
      body: JSON.stringify(body),
    });
    if (res.ok) { await load(); setCreating(false); }
    setSaving(false);
  }

  return (
    <div className="max-w-3xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold" style={{ color: "var(--ink)" }}>Dialogprofile</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--ink-faint)" }}>
            Konfiguriere den Ton und Modus der Conversation Engine
          </p>
        </div>
        <button onClick={openCreate} className="neo-btn neo-btn--default neo-btn--sm">+ Neues Profil</button>
      </div>

      {loading ? <p style={{ color: "var(--ink-faint)" }}>Lade…</p> : error ? (
        <div className="neo-card p-4" style={{ background: "#fef3c7", border: "1px solid #f59e0b" }}>
          <p style={{ color: "#92400e" }}>⚠️ {error}</p>
          <button onClick={() => { setLoading(true); void load(); }} className="neo-btn neo-btn--sm neo-btn--outline mt-3">
            Erneut versuchen
          </button>
        </div>
      ) : profiles.length === 0 ? (
        <p style={{ color: "var(--ink-faint)" }}>Keine Dialogprofile vorhanden. Erstellen Sie das erste Profil.</p>
      ) : (
        <div className="space-y-3">
          {profiles.map(p => <ProfileCard key={p.id} profile={p} onEdit={openEdit} />)}
        </div>
      )}

      {/* Create/Edit drawer */}
      {creating && (
        <div className="fixed inset-0 z-50 flex" style={{ background: "rgba(0,0,0,0.4)" }}>
          <div className="ml-auto w-[480px] h-full overflow-y-auto shadow-2xl flex flex-col"
            style={{ background: "var(--paper)", borderLeft: "2px solid var(--paper-rule)" }}>
            <div className="flex items-center justify-between px-5 py-4 border-b"
              style={{ borderColor: "var(--paper-rule)" }}>
              <h2 className="font-bold text-sm" style={{ color: "var(--ink)" }}>
                {editing ? "Profil bearbeiten" : "Neues Profil"}
              </h2>
              <button onClick={() => setCreating(false)} style={{ fontSize: 20, color: "var(--ink-faint)" }}>×</button>
            </div>
            <div className="flex-1 px-5 py-4 space-y-4 overflow-y-auto">
              {[
                { label: "Key", key: "key", ph: "default_story" },
                { label: "Name", key: "name", ph: "Story-Erstellung (Standard)" },
                { label: "Beschreibung", key: "description", ph: "Freundlicher Dialog zur Story-Erstellung" },
              ].map(f => (
                <div key={f.key}>
                  <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>{f.label}</label>
                  <input type="text" value={(form as Record<string, unknown>)[f.key] as string}
                    onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                    placeholder={f.ph} className="neo-input w-full text-sm" />
                </div>
              ))}
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Modus</label>
                <select value={form.mode} onChange={e => setForm(p => ({ ...p, mode: e.target.value }))} className="neo-input w-full text-sm">
                  {MODES.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Ton</label>
                <select value={form.tone} onChange={e => setForm(p => ({ ...p, tone: e.target.value }))} className="neo-input w-full text-sm">
                  {TONES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="flex gap-4">
                {[
                  { key: "is_default", label: "Standard-Profil" },
                  { key: "is_active", label: "Aktiv" },
                ].map(f => (
                  <label key={f.key} className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={(form as Record<string, unknown>)[f.key] as boolean}
                      onChange={e => setForm(p => ({ ...p, [f.key]: e.target.checked }))} />
                    <span style={{ color: "var(--ink)" }}>{f.label}</span>
                  </label>
                ))}
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Konfiguration (JSON)</label>
                <textarea value={form.config_json}
                  onChange={e => setForm(p => ({ ...p, config_json: e.target.value }))}
                  rows={5} className="neo-input w-full text-xs font-mono resize-none"
                  style={{ background: "var(--paper-warm)" }} />
              </div>
            </div>
            <div className="px-5 py-4 border-t flex gap-3" style={{ borderColor: "var(--paper-rule)" }}>
              <button onClick={() => void save()} disabled={saving} className="neo-btn neo-btn--default">
                {saving ? "Speichern…" : "Speichern"}
              </button>
              <button onClick={() => setCreating(false)} className="neo-btn neo-btn--outline">Abbrechen</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
