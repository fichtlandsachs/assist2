"use client";

import { useState } from "react";

interface TemplateUploadProps {
  label: string;
  accept: string;
  uploadUrl: string;
  deleteUrl: string;
  currentFilename: string | null;
  onSuccess: () => void;
}

export function TemplateUpload({
  label,
  accept,
  uploadUrl,
  deleteUrl,
  currentFilename,
  onSuccess,
}: TemplateUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(uploadUrl, { method: "POST", body: form });
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
      const res = await fetch(deleteUrl, { method: "DELETE" });
      if (!res.ok) throw new Error("Löschen fehlgeschlagen");
      onSuccess();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Löschen fehlgeschlagen");
    }
  };

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      {currentFilename ? (
        <div className="flex items-center gap-3 text-sm">
          <span className="text-green-600">✓ {currentFilename}</span>
          <button
            onClick={handleDelete}
            className="text-red-500 hover:underline text-xs"
          >
            Entfernen
          </button>
        </div>
      ) : (
        <div className="text-sm text-gray-400">Kein Template hochgeladen</div>
      )}
      <input
        type="file"
        accept={accept}
        onChange={handleUpload}
        disabled={uploading}
        className="block text-sm text-gray-600 file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200"
      />
      {uploading && <p className="text-xs text-gray-500">Wird hochgeladen…</p>}
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
