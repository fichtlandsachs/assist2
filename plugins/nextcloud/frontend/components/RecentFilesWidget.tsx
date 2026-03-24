"use client";

import useSWR from "swr";
import { Folder, FileText, FileSpreadsheet, File, ExternalLink } from "lucide-react";
import { fetcher } from "@/lib/api/client";

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

function formatDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const diff = Math.floor((now.getTime() - d.getTime()) / 86400000);
  if (diff === 0) return "heute";
  if (diff === 1) return "gestern";
  if (diff < 7) return ["So.", "Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa."][d.getDay()];
  return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
}

export function RecentFilesWidget({ orgId }: { orgId?: string }) {
  const { data, error, isLoading } = useSWR<NextcloudFileList>(
    orgId ? `/api/v1/organizations/${orgId}/nextcloud/files` : null,
    fetcher,
    { refreshInterval: 60000 }
  );

  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-100">
        <Folder className="w-4 h-4 text-blue-500" />
        <span className="text-sm font-semibold text-slate-700">Nextcloud — Org-Dateien</span>
      </div>

      {isLoading && (
        <div className="px-4 py-6 text-center text-sm text-slate-400">Lädt…</div>
      )}

      {!isLoading && error && (
        <div className="px-4 py-6 text-center text-sm text-slate-400">
          Dateien momentan nicht verfügbar
        </div>
      )}

      {!isLoading && !error && data && data.files.length === 0 && (
        <div className="px-4 py-6 text-center text-sm text-slate-400">
          Noch keine Dateien vorhanden
        </div>
      )}

      {!isLoading && !error && data && data.files.length > 0 && (
        <ul className="divide-y divide-slate-50">
          {data.files.map((file) => (
            <li
              key={file.href}
              className="flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 transition-colors"
            >
              <FileIcon contentType={file.content_type} />
              <span className="flex-1 text-sm text-slate-700 truncate">{file.name}</span>
              <span className="text-xs text-slate-400 flex-shrink-0">
                {formatDate(file.last_modified)}
              </span>
            </li>
          ))}
        </ul>
      )}

      {data && (
        <div className="px-4 py-2.5 border-t border-slate-100">
          <a
            href={data.nextcloud_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 font-medium"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            Alle Dateien öffnen
          </a>
        </div>
      )}
    </div>
  );
}
