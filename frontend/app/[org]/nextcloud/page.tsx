"use client";

import { useOrg } from "@/lib/hooks/useOrg";
import useSWR from "swr";
import { fetcher } from "@/lib/api/client";
import {
  Folder,
  FileText,
  FileSpreadsheet,
  File,
  ExternalLink,
  RefreshCw,
} from "lucide-react";

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
  if (contentType.includes("spreadsheet") || contentType.includes("excel")) {
    return <FileSpreadsheet className="w-4 h-4 text-green-600 flex-shrink-0" />;
  }
  if (contentType.includes("word") || contentType.includes("document")) {
    return <FileText className="w-4 h-4 text-blue-600 flex-shrink-0" />;
  }
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
  const now = new Date();
  const diff = Math.floor((now.getTime() - d.getTime()) / 86400000);
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

  return (
    <div className="max-w-3xl mx-auto py-8 px-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-blue-100 flex items-center justify-center">
            <Folder className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Dateien</h1>
            <p className="text-sm text-slate-500">Nextcloud-Ordner der Organisation</p>
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

          {data?.nextcloud_url && (
            <a
              href={data.nextcloud_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-sm text-white bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded-lg transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              In Nextcloud öffnen
            </a>
          )}
        </div>
      </div>

      {/* File list */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        {isLoading && (
          <div className="px-6 py-12 text-center text-sm text-slate-400">Dateien werden geladen…</div>
        )}

        {!isLoading && error && (
          <div className="px-6 py-12 text-center">
            <p className="text-sm text-slate-500 mb-2">Nextcloud ist momentan nicht erreichbar.</p>
            <p className="text-xs text-slate-400">
              Öffne Nextcloud direkt unter{" "}
              <a
                href="https://nextcloud.fichtlworks.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                nextcloud.fichtlworks.com
              </a>
            </p>
          </div>
        )}

        {!isLoading && !error && data && data.files.length === 0 && (
          <div className="px-6 py-12 text-center">
            <Folder className="w-8 h-8 text-slate-300 mx-auto mb-3" />
            <p className="text-sm text-slate-500">Noch keine Dateien im Org-Ordner.</p>
            <p className="text-xs text-slate-400 mt-1">
              Lade Dateien in Nextcloud unter{" "}
              <code className="bg-slate-100 px-1 rounded">Organizations/{org?.slug}</code> hoch.
            </p>
          </div>
        )}

        {!isLoading && !error && data && data.files.length > 0 && (
          <>
            <div className="grid grid-cols-[1fr_auto_auto] gap-0 text-xs text-slate-400 px-4 py-2 border-b border-slate-100 font-medium">
              <span>Name</span>
              <span className="w-20 text-right">Größe</span>
              <span className="w-20 text-right">Geändert</span>
            </div>
            <ul className="divide-y divide-slate-50">
              {data.files.map((file) => (
                <li
                  key={file.href}
                  className="grid grid-cols-[1fr_auto_auto] items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <FileIcon contentType={file.content_type} />
                    <span className="text-sm text-slate-800 truncate">{file.name}</span>
                  </div>
                  <span className="w-20 text-right text-xs text-slate-400">
                    {formatSize(file.size)}
                  </span>
                  <span className="w-20 text-right text-xs text-slate-400">
                    {formatDate(file.last_modified)}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}

        {/* Footer */}
        {data && (
          <div className="px-4 py-3 border-t border-slate-100 bg-slate-50 flex items-center justify-between">
            <span className="text-xs text-slate-400">
              {data.files.length} Datei{data.files.length !== 1 ? "en" : ""} (zuletzt geändert)
            </span>
            <a
              href={data.nextcloud_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              <ExternalLink className="w-3 h-3" />
              Alle Dateien in Nextcloud anzeigen
            </a>
          </div>
        )}
      </div>

      {/* Info box */}
      <div className="mt-4 p-4 bg-slate-50 rounded-xl border border-slate-200 text-sm text-slate-600">
        <p className="font-medium mb-1">Wie Dateien hochladen?</p>
        <p className="text-slate-500 text-xs">
          Melde dich bei{" "}
          <a
            href="https://nextcloud.fichtlworks.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline"
          >
            Nextcloud
          </a>{" "}
          an und navigiere zu{" "}
          <strong>Organizations / {org?.slug}</strong>. Dateien dort erscheinen automatisch hier.
        </p>
      </div>
    </div>
  );
}
