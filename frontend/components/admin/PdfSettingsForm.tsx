"use client";

import { useState } from "react";
import { apiRequest } from "@/lib/api/client";
import { Button } from "@/components/ui/button";

interface PdfSettings {
  id?: string;
  company_name?: string | null;
  page_format: string;
  language: string;
  header_text?: string | null;
  footer_text?: string | null;
  letterhead_filename?: string | null;
  logo_filename?: string | null;
}

interface PdfSettingsFormProps {
  orgSlug: string;
  orgId: string;
  initialSettings: PdfSettings;
  onSaved: (settings: PdfSettings) => void;
}

const inputCls = "w-full px-3 py-2 text-sm outline-none transition-colors"
  + " bg-[var(--paper)] text-[var(--ink)] border border-[var(--paper-rule)]"
  + " rounded-sm focus:border-[var(--accent-red)] focus:ring-1 focus:ring-[var(--accent-red)]";

const labelCls = "block text-sm font-medium text-[var(--ink-mid)] mb-1";

export function PdfSettingsForm({ orgSlug: _orgSlug, orgId, initialSettings, onSaved }: PdfSettingsFormProps) {
  const [form, setForm] = useState({
    company_name: initialSettings.company_name ?? "",
    page_format:  initialSettings.page_format  ?? "a4",
    language:     initialSettings.language     ?? "de",
    header_text:  initialSettings.header_text  ?? "",
    footer_text:  initialSettings.footer_text  ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error,  setError]  = useState<string | null>(null);
  const [saved,  setSaved]  = useState(false);

  const handleSave = async () => {
    setSaving(true); setError(null); setSaved(false);
    try {
      const result = await apiRequest<PdfSettings>(
        `/api/v1/organizations/${orgId}/pdf-settings`,
        { method: "PUT", body: JSON.stringify(form) }
      );
      onSaved(result);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <label className={labelCls}>Firmenname</label>
        <input type="text" value={form.company_name} placeholder="Acme GmbH"
          onChange={e => setForm({ ...form, company_name: e.target.value })}
          className={inputCls} />
      </div>
      <div className="flex gap-4">
        <div className="flex-1">
          <label className={labelCls}>Seitenformat</label>
          <select value={form.page_format} onChange={e => setForm({ ...form, page_format: e.target.value })}
            className={inputCls}>
            <option value="a4">A4</option>
            <option value="letter">Letter</option>
          </select>
        </div>
        <div className="flex-1">
          <label className={labelCls}>Sprache</label>
          <select value={form.language} onChange={e => setForm({ ...form, language: e.target.value })}
            className={inputCls}>
            <option value="de">Deutsch</option>
            <option value="en">English</option>
          </select>
        </div>
      </div>
      <div>
        <label className={labelCls}>Kopfzeile (optional)</label>
        <input type="text" value={form.header_text} placeholder="z.B. Internes Dokument"
          onChange={e => setForm({ ...form, header_text: e.target.value })}
          className={inputCls} />
      </div>
      <div>
        <label className={labelCls}>Fußzeile (optional)</label>
        <input type="text" value={form.footer_text} placeholder="z.B. Vertraulich"
          onChange={e => setForm({ ...form, footer_text: e.target.value })}
          className={inputCls} />
      </div>
      {error && <p className="text-sm text-[var(--accent-red)]">{error}</p>}
      {saved  && <p className="text-sm text-[var(--green)]">Gespeichert ✓</p>}
      <Button onClick={handleSave} disabled={saving}>
        {saving ? "Wird gespeichert…" : "Einstellungen speichern"}
      </Button>
    </div>
  );
}
