"use client";

import { useState, useRef } from "react";
import { useOrg } from "@/lib/hooks/useOrg";
import useSWR from "swr";
import { fetcher } from "@/lib/api/client";
import {
  Folder,
  FileText,
  FileSpreadsheet,
  File,
  Upload,
  Download,
  RefreshCw,
  X,
  CheckCircle,
  AlertCircle,
} from "lucide-react";
import { getAccessToken } from "@/lib/api/client";

interface NextcloudFile {
  name: string;
  href: string;
  content_type: string;
  last_modified: string | null;
  size: number;
}

interface NextcloudFileList {
  files: NextcloudFile[];
  nextcloud_url: string;
}

function FileIcon({ contentType }: { contentType: string }) {
  if (contentType.includes("spreadsheet") || contentType.includes("excel"))
    return <FileSpreadsheet className="w-4 h-4 text-green-600 flex-shrink-0" />;
  if (contentType.includes("word") || contentType.includes("document"))
    return <FileText className="w-4 h-4 text-blue-600 flex-shrink-0" />;
  return <File className="w-4 h-4 text-slate-500 flex-shrink-0" />;
}

function formatSize(bytes: number): string {
  if (bytes === 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const diff = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (diff === 0) return "heute";
  if (diff === 1) return "gestern";
  if (diff < 7) return ["So.", "Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa."][d.getDay()];
  return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export default function NextcloudPage({ params }: { params: { org: string } }) {
  const { org } = useOrg(params.org);
  const { data, error, isLoading, mutate } = useSWR<NextcloudFileList>(
    org ? `/api/v1/organizations/${org.id}/nextcloud/files` : null,
    fetcher,
    { refreshInterval: 60000 }
  );

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const uploadFile = async (file: File) => {
    if (!org) return;
    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const token = getAccessToken() ?? "";
      const res = await fetch(`/api/v1/organizations/${org.id}/nextcloud/files/upload`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      if (!res.ok) throw new Error(await res.text());
      setUploadSuccess(`${file.name} hochgeladen`);
      mutate();
      setTimeout(() => setUploadSuccess(null), 3000);
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : "Upload fehlgeschlagen");
    } finally {
      setUploading(false);
    }
  };

  const downloadFile = async (file: NextcloudFile) => {
    if (!org) return;
    const token = getAccessToken() ?? "";
    const url = `/api/v1/organizations/${org.id}/nextcloud/files/download?path=Organizations/${org.slug}/${encodeURIComponent(file.name)}`;
    const res = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = file.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(objectUrl);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files[0]) uploadFile(files[0]);
  };

  return (
    <div className="max-w-3xl mx-auto py-8 px-4">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-blue-100 flex items-center justify-center">
            <Folder className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Dateien</h1>
            <p className="text-sm text-slate-500">Org-Ordner · {data?.files.length ?? 0} Dateien</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => mutate()}
            className="flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-800 px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Aktualisieren
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading || !org}
            className="flex items-center gap-1.5 text-sm text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 px-3 py-1.5 rounded-lg transition-colors"
          >
            <Upload className="w-3.5 h-3.5" />
            {uploading ? "Lädt…" : "Hochladen"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])}
          />
        </div>
      </div>

      {(uploadError || uploadSuccess) && (
        <div className={`flex items-center gap-2 px-4 py-3 rounded-lg mb-4 text-sm ${uploadError ? "bg-red-50 text-red-700 border border-red-200" : "bg-green-50 text-green-700 border border-green-200"}`}>
          {uploadError ? <AlertCircle className="w-4 h-4 flex-shrink-0" /> : <CheckCircle className="w-4 h-4 flex-shrink-0" />}
          <span className="flex-1">{uploadError ?? uploadSuccess}</span>
          <button onClick={() => { setUploadError(null); setUploadSuccess(null); }}><X className="w-4 h-4" /></button>
        </div>
      )}

      <div
        className={`relative bg-white border-2 ${dragging ? "border-blue-400 bg-blue-50" : "border-slate-200"} rounded-xl overflow-hidden transition-colors`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        {dragging && (
          <div className="absolute inset-0 flex items-center justify-center bg-blue-50/80 z-10 rounded-xl">
            <p className="text-blue-600 font-medium text-sm">Datei hier ablegen</p>
          </div>
        )}

        {isLoading && <div className="px-6 py-12 text-center text-sm text-slate-400">Lädt…</div>}

        {!isLoading && error && (
          <div className="px-6 py-12 text-center text-sm text-slate-500">
            Nextcloud momentan nicht erreichbar.
          </div>
        )}

        {!isLoading && !error && data && data.files.length === 0 && (
          <div className="px-6 py-12 text-center">
            <Folder className="w-8 h-8 text-slate-300 mx-auto mb-3" />
            <p className="text-sm text-slate-500">Noch keine Dateien.</p>
            <p className="text-xs text-slate-400 mt-1">Datei hochladen oder per Drag &amp; Drop ablegen.</p>
          </div>
        )}

        {!isLoading && !error && data && data.files.length > 0 && (
          <>
            <div className="grid grid-cols-[1fr_auto_auto_auto] gap-0 text-xs text-slate-400 px-4 py-2 border-b border-slate-100 font-medium">
              <span>Name</span>
              <span className="w-20 text-right pr-2">Größe</span>
              <span className="w-20 text-right pr-2">Geändert</span>
              <span className="w-10"></span>
            </div>
            <ul className="divide-y divide-slate-50">
              {data.files.map((file) => (
                <li key={file.href} className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-0 px-4 py-3 hover:bg-slate-50 transition-colors">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <FileIcon contentType={file.content_type} />
                    <span className="text-sm text-slate-800 truncate">{file.name}</span>
                  </div>
                  <span className="w-20 text-right text-xs text-slate-400 pr-2">{formatSize(file.size)}</span>
                  <span className="w-20 text-right text-xs text-slate-400 pr-2">{formatDate(file.last_modified)}</span>
                  <button
                    onClick={() => downloadFile(file)}
                    className="w-10 flex items-center justify-center text-slate-400 hover:text-blue-600 transition-colors"
                    title="Herunterladen"
                  >
                    <Download className="w-4 h-4" />
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}

        {data && (
          <div className="px-4 py-2.5 border-t border-slate-100 bg-slate-50">
            <p className="text-xs text-slate-400">Drag &amp; Drop zum Hochladen · {data.files.length} Datei{data.files.length !== 1 ? "en" : ""}</p>
          </div>
        )}
      </div>
    </div>
  );
}
