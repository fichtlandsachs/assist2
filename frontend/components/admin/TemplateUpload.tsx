"use client";

import { useState } from "react";
import { getAccessToken } from "@/lib/api/client";
import { Button } from "@/components/ui/button";

interface TemplateUploadProps {
  label: string;
  accept: string;
  uploadUrl: string;
  deleteUrl: string;
  currentFilename: string | null;
  onSuccess: () => void;
}

export function TemplateUpload({ label, accept, uploadUrl, deleteUrl, currentFilename, onSuccess }: TemplateUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true); setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const token = getAccessToken();
      const res = await fetch(uploadUrl, {
        method: "POST", body: form,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail ?? "Upload fehlgeschlagen");
      }
      onSuccess();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload fehlgeschlagen");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async () => {
    setError(null);
    try {
      const token = getAccessToken();
      const res = await fetch(deleteUrl, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Löschen fehlgeschlagen");
      onSuccess();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Löschen fehlgeschlagen");
    }
  };

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-[var(--ink-mid)]">{label}</label>
      {currentFilename ? (
        <div className="flex items-center gap-3 text-sm">
          <span className="text-[var(--green)]">✓ {currentFilename}</span>
          <Button variant="ghost" size="sm" onClick={handleDelete}
            className="text-[var(--accent-red)] hover:text-[var(--accent-red)]">
            Entfernen
          </Button>
        </div>
      ) : (
        <div className="text-sm text-[var(--ink-faintest)]">Kein Template hochgeladen</div>
      )}
      <input
        type="file" accept={accept} onChange={handleUpload} disabled={uploading}
        className="block text-sm text-[var(--ink-faint)]
          file:mr-3 file:py-1 file:px-3 file:rounded-sm file:border file:border-[var(--paper-rule)]
          file:text-xs file:bg-[var(--paper-warm)] file:text-[var(--ink-mid)]
          hover:file:bg-[var(--paper-rule2)] file:cursor-pointer file:transition-colors"
      />
      {uploading && <p className="text-xs text-[var(--ink-faint)]">Wird hochgeladen…</p>}
      {error    && <p className="text-xs text-[var(--accent-red)]">{error}</p>}
    </div>
  );
}
