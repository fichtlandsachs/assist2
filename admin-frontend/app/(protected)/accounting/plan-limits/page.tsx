"use client";

import { useEffect, useState } from "react";
import { fetchConfig, patchConfig } from "@/lib/api";

const FIELDS = [
  { key: "plans.free.stories",       label: "Free – max. Stories",         placeholder: "50" },
  { key: "plans.free.members",        label: "Free – max. Mitglieder",      placeholder: "5" },
  { key: "plans.pro.stories",         label: "Pro – max. Stories",          placeholder: "500" },
  { key: "plans.pro.members",         label: "Pro – max. Mitglieder",       placeholder: "50" },
  { key: "plans.enterprise.stories",  label: "Enterprise – max. Stories",   placeholder: "9999 = unbegrenzt" },
  { key: "plans.enterprise.members",  label: "Enterprise – max. Mitglieder",placeholder: "9999 = unbegrenzt" },
];

export default function PlanLimitsPage() {
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchConfig().then((cfg) => {
      const init: Record<string, string> = {};
      for (const f of FIELDS) init[f.key] = cfg[f.key]?.value ?? "";
      setValues(init);
    }).catch(() => setError("Konfiguration konnte nicht geladen werden."));
  }, []);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      for (const f of FIELDS) {
        const val = values[f.key]?.trim() || null;
        if (val !== null && isNaN(Number(val))) {
          setError(`"${f.label}" muss eine Zahl sein.`);
          return;
        }
        await patchConfig(f.key, val);
      }
      setSavedMsg(true);
      setTimeout(() => setSavedMsg(false), 2500);
    } catch {
      setError("Speichern fehlgeschlagen.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="neo-card p-5 space-y-5 max-w-lg">
      <p className="text-sm" style={{ color: "var(--ink-faint)" }}>
        Leer lassen = Standardwert (Free 50/5 · Pro 500/50 · Enterprise unbegrenzt).
        9999 gilt als unbegrenzt.
      </p>

      <div className="space-y-3">
        {FIELDS.map((f) => (
          <div key={f.key}>
            <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>
              {f.label}
            </label>
            <input
              type="number"
              min={1}
              value={values[f.key] ?? ""}
              onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
              placeholder={f.placeholder}
              className="neo-input w-full text-sm"
            />
          </div>
        ))}
      </div>

      {error && (
        <p className="text-xs" style={{ color: "var(--accent-red)" }}>{error}</p>
      )}

      <div className="flex items-center gap-3">
        <button
          onClick={() => void handleSave()}
          disabled={saving}
          className="neo-btn neo-btn--default neo-btn--sm"
        >
          {saving ? "Speichern…" : "Speichern"}
        </button>
        {savedMsg && (
          <span className="text-xs" style={{ color: "var(--green)" }}>Gespeichert ✓</span>
        )}
      </div>
    </div>
  );
}
