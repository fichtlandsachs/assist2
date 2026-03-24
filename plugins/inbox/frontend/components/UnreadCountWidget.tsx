"use client";

import useSWR from "swr";
import { Mail, ExternalLink } from "lucide-react";
import { fetcher } from "@/lib/api/client";

interface Message {
  id: string;
  subject: string | null;
  sender_email: string;
  sender_name: string | null;
  received_at: string | null;
  status: string;
}

function formatSubject(subject: string | null): string {
  return subject || "(Kein Betreff)";
}

export function UnreadCountWidget({ orgId, orgSlug }: { orgId?: string; orgSlug?: string }) {
  const { data, error, isLoading } = useSWR<Message[]>(
    orgId
      ? `/api/v1/inbox/messages?org_id=${orgId}&message_status=unread`
      : null,
    fetcher,
    { refreshInterval: 60000 }
  );

  const unreadMessages = data ? data.slice(0, 3) : [];
  const unreadCount = data ? data.length : 0;
  const inboxHref = orgSlug ? `/${orgSlug}/inbox` : "/inbox";

  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-100">
        <Mail className="w-4 h-4 text-blue-500" />
        <span className="text-sm font-semibold text-slate-700">Inbox</span>
        {!isLoading && !error && unreadCount > 0 && (
          <span className="ml-auto inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-bold bg-blue-500 text-white">
            {unreadCount}
          </span>
        )}
      </div>

      {isLoading && (
        <div className="px-4 py-6 text-center text-sm text-slate-400">Lädt…</div>
      )}

      {!isLoading && error && (
        <div className="px-4 py-6 text-center text-sm text-slate-400">
          Inbox momentan nicht verfügbar
        </div>
      )}

      {!isLoading && !error && unreadCount === 0 && (
        <div className="px-4 py-6 text-center text-sm text-slate-400">
          Keine ungelesenen Nachrichten
        </div>
      )}

      {!isLoading && !error && unreadMessages.length > 0 && (
        <ul className="divide-y divide-slate-50">
          {unreadMessages.map((msg) => (
            <li
              key={msg.id}
              className="flex items-start gap-3 px-4 py-2.5 hover:bg-slate-50 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-700 truncate">
                  {formatSubject(msg.subject)}
                </p>
                <p className="text-xs text-slate-400 mt-0.5 truncate">
                  {msg.sender_name || msg.sender_email}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="px-4 py-2.5 border-t border-slate-100">
        <a
          href={inboxHref}
          className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 font-medium"
        >
          <ExternalLink className="w-3.5 h-3.5" />
          Inbox öffnen
        </a>
      </div>
    </div>
  );
}
