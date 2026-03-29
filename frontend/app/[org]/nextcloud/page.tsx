"use client";

import { use, useState, useRef } from "react";
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
  User,
  Building2,
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

type Tab = "org" | "personal";

function FileIcon({ contentType }: { contentType: string }) {
  if (contentType.includes("spreadsheet") || contentType.includes("excel"))
    return <FileSpreadsheet className="w-4 h-4 text-[#526b5e] flex-shrink-0" />;
  if (contentType.includes("word") || contentType.includes("document"))
    return <FileText className="w-4 h-4 text-[#4a5568] flex-shrink-0" />;
  if (contentType.includes("pdf"))
    return <FileText className="w-4 h-4 text-[#8b5e52] flex-shrink-0" />;
  return <File className="w-4 h-4 text-[#a09080] flex-shrink-0" />;
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

function FileList({
  data,
  error,
  isLoading,
  onDownload,
  onMutate,
  onDrop,
  onFileSelect,
  uploading,
  uploadError,
  uploadSuccess,
  onClearStatus,
  fileInputRef,
}: {
  data: NextcloudFileList | undefined;
  error: unknown;
  isLoading: boolean;
  onDownload: (file: NextcloudFile) => void;
  onMutate: () => void;
  onDrop: (e: React.DragEvent) => void;
  onFileSelect: (file: File) => void;
  uploading: boolean;
  uploadError: string | null;
  uploadSuccess: string | null;
  onClearStatus: () => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
}) {
  const [dragging, setDragging] = useState(false);

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex items-center justify-end gap-2">
        <button
          onClick={onMutate}
          className="flex items-center gap-1.5 text-sm text-[#5a5040] hover:text-[#1c1810] px-3 py-1.5 rounded-sm border border-[#e2ddd4] hover:bg-[#f7f4ee] transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Aktualisieren
        </button>
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="flex items-center gap-1.5 text-sm text-white bg-[#4a5568] hover:bg-[#4a5568] disabled:opacity-50 px-3 py-1.5 rounded-sm transition-colors"
        >
          <Upload className="w-3.5 h-3.5" />
          {uploading ? "Lädt…" : "Hochladen"}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && onFileSelect(e.target.files[0])}
        />
      </div>

      {/* Status */}
      {(uploadError || uploadSuccess) && (
        <div className={`flex items-center gap-2 px-4 py-3 rounded-sm text-sm ${uploadError ? "bg-[rgba(139,94,82,.08)] text-[#8b5e52] border border-[#8b5e52]" : "bg-[rgba(82,107,94,.1)] text-[#526b5e] border border-[#526b5e]"}`}>
          {uploadError ? <AlertCircle className="w-4 h-4 flex-shrink-0" /> : <CheckCircle className="w-4 h-4 flex-shrink-0" />}
          <span className="flex-1">{uploadError ?? uploadSuccess}</span>
          <button onClick={onClearStatus}><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* Drop zone */}
      <div
        className={`relative bg-[#faf9f6] border-2 ${dragging ? "border-[#4a5568] bg-[rgba(74,85,104,.06)]" : "border-[#e2ddd4]"} rounded-sm overflow-hidden transition-colors`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { setDragging(false); onDrop(e); }}
      >
        {dragging && (
          <div className="absolute inset-0 flex items-center justify-center bg-[rgba(74,85,104,.06)] z-10 rounded-sm">
            <p className="text-[#4a5568] font-medium text-sm">Datei hier ablegen</p>
          </div>
        )}

        {isLoading && <div className="px-6 py-12 text-center text-sm text-[#a09080]">Lädt…</div>}

        {!isLoading && !!error && (
          <div className="px-6 py-12 text-center text-sm text-[#a09080]">
            Nextcloud momentan nicht erreichbar.
          </div>
        )}

        {!isLoading && !error && data && data.files.length === 0 && (
          <div className="px-6 py-12 text-center">
            <Folder className="w-8 h-8 text-[#a09080] mx-auto mb-3" />
            <p className="text-sm text-[#a09080]">Noch keine Dateien.</p>
            <p className="text-xs text-[#a09080] mt-1">Datei hochladen oder per Drag &amp; Drop ablegen.</p>
          </div>
        )}

        {!isLoading && !error && data && data.files.length > 0 && (
          <>
            <div className="grid grid-cols-[1fr_auto_auto_auto] gap-0 text-xs text-[#a09080] px-4 py-2 border-b border-[#e2ddd4] font-medium">
              <span>Name</span>
              <span className="w-20 text-right pr-2">Größe</span>
              <span className="w-20 text-right pr-2">Geändert</span>
              <span className="w-10"></span>
            </div>
            <ul className="divide-y divide-[#f7f4ee]">
              {data.files.map((file) => (
                <li key={file.href} className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-0 px-4 py-3 hover:bg-[#f7f4ee] transition-colors">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <FileIcon contentType={file.content_type} />
                    <span className="text-sm text-[#1c1810] truncate">{file.name}</span>
                  </div>
                  <span className="w-20 text-right text-xs text-[#a09080] pr-2">{formatSize(file.size)}</span>
                  <span className="w-20 text-right text-xs text-[#a09080] pr-2">{formatDate(file.last_modified)}</span>
                  <button
                    onClick={() => onDownload(file)}
                    className="w-10 flex items-center justify-center text-[#a09080] hover:text-[#4a5568] transition-colors"
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
          <div className="px-4 py-2.5 border-t border-[#e2ddd4] bg-[#f7f4ee]">
            <p className="text-xs text-[#a09080]">Drag &amp; Drop zum Hochladen · {data.files.length} Datei{data.files.length !== 1 ? "en" : ""}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function NextcloudPage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { org } = useOrg(resolvedParams.org);
  const [tab, setTab] = useState<Tab>("org");

  const orgFiles = useSWR<NextcloudFileList>(
    org ? `/api/v1/organizations/${org.id}/nextcloud/files` : null,
    fetcher,
    { refreshInterval: 60000 }
  );

  const personalFiles = useSWR<NextcloudFileList>(
    org && tab === "personal" ? `/api/v1/organizations/${org.id}/nextcloud/files/personal` : null,
    fetcher,
    { refreshInterval: 60000 }
  );

  const orgFileInput = useRef<HTMLInputElement>(null);
  const personalFileInput = useRef<HTMLInputElement>(null);

  const [orgUploading, setOrgUploading] = useState(false);
  const [orgUploadError, setOrgUploadError] = useState<string | null>(null);
  const [orgUploadSuccess, setOrgUploadSuccess] = useState<string | null>(null);

  const [personalUploading, setPersonalUploading] = useState(false);
  const [personalUploadError, setPersonalUploadError] = useState<string | null>(null);
  const [personalUploadSuccess, setPersonalUploadSuccess] = useState<string | null>(null);

  const uploadFile = async (file: File, target: "org" | "personal") => {
    if (!org) return;
    const setUploading = target === "org" ? setOrgUploading : setPersonalUploading;
    const setError = target === "org" ? setOrgUploadError : setPersonalUploadError;
    const setSuccess = target === "org" ? setOrgUploadSuccess : setPersonalUploadSuccess;
    const mutate = target === "org" ? orgFiles.mutate : personalFiles.mutate;
    const uploadPath = target === "org"
      ? `/api/v1/organizations/${org.id}/nextcloud/files/upload`
      : `/api/v1/organizations/${org.id}/nextcloud/files/personal/upload`;

    setUploading(true);
    setError(null);
    setSuccess(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const token = getAccessToken() ?? "";
      const res = await fetch(uploadPath, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      if (!res.ok) throw new Error(await res.text());
      setSuccess(`${file.name} hochgeladen`);
      mutate();
      setTimeout(() => setSuccess(null), 3000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload fehlgeschlagen");
    } finally {
      setUploading(false);
    }
  };

  const downloadFile = async (file: NextcloudFile) => {
    if (!org) return;
    const token = getAccessToken() ?? "";
    // Extract relative path from WebDAV href
    const hrefParts = file.href.split("/dav/files/");
    const rawPath = hrefParts[1]?.split("/").slice(1).join("/") ?? file.name;
    const url = `/api/v1/organizations/${org.id}/nextcloud/files/download?path=${encodeURIComponent(decodeURIComponent(rawPath))}`;
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

  const tabs = [
    { id: "org" as Tab, label: "Organisation", icon: Building2 },
    { id: "personal" as Tab, label: "Persönlich", icon: User },
  ];

  const activeData = tab === "org" ? orgFiles.data : personalFiles.data;
  const activeError = tab === "org" ? orgFiles.error : personalFiles.error;
  const activeLoading = tab === "org" ? orgFiles.isLoading : personalFiles.isLoading;
  const activeMutate = tab === "org" ? orgFiles.mutate : personalFiles.mutate;
  const activeFileInput = tab === "org" ? orgFileInput : personalFileInput;
  const activeUploading = tab === "org" ? orgUploading : personalUploading;
  const activeUploadError = tab === "org" ? orgUploadError : personalUploadError;
  const activeUploadSuccess = tab === "org" ? orgUploadSuccess : personalUploadSuccess;
  const activeClearStatus = tab === "org"
    ? () => { setOrgUploadError(null); setOrgUploadSuccess(null); }
    : () => { setPersonalUploadError(null); setPersonalUploadSuccess(null); };

  return (
    <div className="max-w-3xl mx-auto py-8 px-4">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="w-9 h-9 rounded-sm bg-[rgba(74,85,104,.06)] flex items-center justify-center">
          <Folder className="w-5 h-5 text-[#4a5568]" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-[#1c1810]">Dateien</h1>
          <p className="text-sm text-[#a09080]">{activeData?.files.length ?? 0} Dateien</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-[#f7f4ee] rounded-sm mb-6 w-fit">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-sm text-sm font-medium transition-colors ${
              tab === id
                ? "bg-[#faf9f6] text-[#1c1810]"
                : "text-[#a09080] hover:text-[#5a5040]"
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* File list for active tab */}
      <FileList
        data={activeData}
        error={activeError}
        isLoading={activeLoading}
        onDownload={downloadFile}
        onMutate={activeMutate}
        onDrop={(e) => {
          e.preventDefault();
          const files = Array.from(e.dataTransfer.files);
          if (files[0]) void uploadFile(files[0], tab);
        }}
        onFileSelect={(file) => void uploadFile(file, tab)}
        uploading={activeUploading}
        uploadError={activeUploadError}
        uploadSuccess={activeUploadSuccess}
        onClearStatus={activeClearStatus}
        fileInputRef={activeFileInput}
      />
    </div>
  );
}
