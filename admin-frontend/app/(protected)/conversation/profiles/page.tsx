"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listDialogProfiles,
  createDialogProfile,
  updateDialogProfile,
  type DialogProfile,
} from "@/lib/api";

const MODES = ["story_mode", "exploration_mode", "review_mode", "correction_mode"];
const TONES = ["friendly", "open", "analytical", "structured", "motivating"];

export default function ConversationProfilesPage() {
  const [profiles, setProfiles] = useState<DialogProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<DialogProfile | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    key: "",
    name: "",
    description: "",
    mode: "story_mode",
    tone: "friendly",
    is_default: false,
    is_active: true,
    config_json: "{}",
  });

  async function load() {
    try {
      setError(null);
      const data = await listDialogProfiles();
      setProfiles(data);
    } catch (e: any) {
      setError(e?.message || "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  function openEdit(p: DialogProfile) {
    setForm({
      key: p.key,
      name: p.name,
      description: p.description ?? "",
      mode: p.mode,
      tone: p.tone,
      is_default: p.is_default,
      is_active: p.is_active,
      config_json: JSON.stringify(p.config_json, null, 2),
    });
    setEditing(p);
    setOpen(true);
  }

  function openCreate() {
    setForm({
      key: "",
      name: "",
      description: "",
      mode: "story_mode",
      tone: "friendly",
      is_default: false,
      is_active: true,
      config_json: "{}",
    });
    setEditing(null);
    setOpen(true);
  }

  async function save() {
    setSaving(true);
    try {
      let config = {};
      try { config = JSON.parse(form.config_json); } catch { }
      const body = { ...form, config_json: config };
      if (editing) {
        await updateDialogProfile(editing.id, body);
      } else {
        await createDialogProfile(body);
      }
      await load();
      setOpen(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dialogprofile</h1>
          <p className="text-sm text-gray-500 mt-1">
            Konfiguriere den Ton und Modus der Conversation Engine
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/conversation/help#profiles"
            className="border px-3 py-2 rounded-md text-sm hover:bg-gray-50"
          >
            Hilfe
          </Link>
          <button
            onClick={openCreate}
            className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700"
          >
            + Neues Profil
          </button>
        </div>
      </div>

      {loading ? (
        <p className="text-gray-500">Lade…</p>
      ) : error ? (
        <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4">
          <p className="text-yellow-800">⚠️ {error}</p>
          <button
            onClick={() => { setLoading(true); void load(); }}
            className="mt-3 text-sm text-yellow-700 underline"
          >
            Erneut versuchen
          </button>
        </div>
      ) : profiles.length === 0 ? (
        <p className="text-gray-500">Keine Dialogprofile vorhanden.</p>
      ) : (
        <div className="grid gap-4">
          {profiles.map((p) => (
            <div
              key={p.id}
              className="bg-white border rounded-lg p-4 flex items-start justify-between"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold">{p.name}</h3>
                  {p.is_default && (
                    <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                      Standard
                    </span>
                  )}
                  {!p.is_active && (
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                      Inaktiv
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-400 font-mono">{p.key}</p>
                {p.description && (
                  <p className="text-sm text-gray-600">{p.description}</p>
                )}
                <div className="flex gap-4 text-xs text-gray-500">
                  <span>
                    Modus: <strong>{p.mode}</strong>
                  </span>
                  <span>
                    Ton: <strong>{p.tone}</strong>
                  </span>
                  <span>v{p.version}</span>
                </div>
              </div>
              <button
                onClick={() => openEdit(p)}
                className="text-sm border px-3 py-1.5 rounded-md hover:bg-gray-50"
              >
                Bearbeiten
              </button>
            </div>
          ))}
        </div>
      )}

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-lg w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <h2 className="font-semibold">
                {editing ? "Profil bearbeiten" : "Neues Profil"}
              </h2>
              <button onClick={() => setOpen(false)} className="text-2xl text-gray-400">
                ×
              </button>
            </div>
            <div className="px-6 py-4 space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Key</label>
                <input
                  type="text"
                  value={form.key}
                  onChange={(e) => setForm({ ...form, key: e.target.value })}
                  placeholder="default_story"
                  className="w-full border rounded-md px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Story-Erstellung (Standard)"
                  className="w-full border rounded-md px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Beschreibung</label>
                <input
                  type="text"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Freundlicher Dialog zur Story-Erstellung"
                  className="w-full border rounded-md px-3 py-2 text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Modus</label>
                  <select
                    value={form.mode}
                    onChange={(e) => setForm({ ...form, mode: e.target.value })}
                    className="w-full border rounded-md px-3 py-2 text-sm"
                  >
                    {MODES.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Ton</label>
                  <select
                    value={form.tone}
                    onChange={(e) => setForm({ ...form, tone: e.target.value })}
                    className="w-full border rounded-md px-3 py-2 text-sm"
                  >
                    {TONES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="flex gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={form.is_default}
                    onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                  />
                  <span className="text-sm">Standard-Profil</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                  />
                  <span className="text-sm">Aktiv</span>
                </label>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Konfiguration (JSON)</label>
                <textarea
                  value={form.config_json}
                  onChange={(e) => setForm({ ...form, config_json: e.target.value })}
                  rows={4}
                  className="w-full border rounded-md px-3 py-2 text-xs font-mono"
                />
              </div>
            </div>
            <div className="flex gap-3 px-6 py-4 border-t">
              <button
                onClick={() => void save()}
                disabled={saving}
                className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? "Speichern…" : "Speichern"}
              </button>
              <button
                onClick={() => setOpen(false)}
                className="border px-4 py-2 rounded-md text-sm hover:bg-gray-50"
              >
                Abbrechen
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
