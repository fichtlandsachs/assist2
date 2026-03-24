"use client";

import useSWR from "swr";
import { Calendar, ExternalLink } from "lucide-react";
import { fetcher } from "@/lib/api/client";

interface CalendarEvent {
  id: string;
  title: string;
  start_at: string;
  end_at: string;
  location: string | null;
  all_day: boolean;
}

function formatEventDate(iso: string, allDay: boolean): string {
  const d = new Date(iso);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const eventDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diffDays = Math.round((eventDay.getTime() - today.getTime()) / 86400000);

  const dateStr =
    diffDays === 0
      ? "Heute"
      : diffDays === 1
      ? "Morgen"
      : d.toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit" });

  if (allDay) return dateStr;
  const timeStr = d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  return `${dateStr}, ${timeStr}`;
}

export function UpcomingEventsWidget({ orgId, orgSlug }: { orgId?: string; orgSlug?: string }) {
  const now = new Date();
  const fromDt = now.toISOString();
  const toDt = new Date(now.getTime() + 14 * 24 * 60 * 60 * 1000).toISOString();

  const { data, error, isLoading } = useSWR<CalendarEvent[]>(
    orgId
      ? `/api/v1/calendar/events?org_id=${orgId}&from_dt=${encodeURIComponent(fromDt)}&to_dt=${encodeURIComponent(toDt)}`
      : null,
    fetcher,
    { refreshInterval: 120000 }
  );

  const events = data ? data.slice(0, 5) : [];
  const calendarHref = orgSlug ? `/${orgSlug}/calendar` : "/calendar";

  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-100">
        <Calendar className="w-4 h-4 text-blue-500" />
        <span className="text-sm font-semibold text-slate-700">Bevorstehende Termine</span>
      </div>

      {isLoading && (
        <div className="px-4 py-6 text-center text-sm text-slate-400">Lädt…</div>
      )}

      {!isLoading && error && (
        <div className="px-4 py-6 text-center text-sm text-slate-400">
          Kalender momentan nicht verfügbar
        </div>
      )}

      {!isLoading && !error && events.length === 0 && (
        <div className="px-4 py-6 text-center text-sm text-slate-400">
          Keine bevorstehenden Termine
        </div>
      )}

      {!isLoading && !error && events.length > 0 && (
        <ul className="divide-y divide-slate-50">
          {events.map((event) => (
            <li
              key={event.id}
              className="flex items-start gap-3 px-4 py-2.5 hover:bg-slate-50 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-700 truncate">{event.title}</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {formatEventDate(event.start_at, event.all_day)}
                  {event.location && (
                    <span className="ml-1 text-slate-300">· {event.location}</span>
                  )}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="px-4 py-2.5 border-t border-slate-100">
        <a
          href={calendarHref}
          className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 font-medium"
        >
          <ExternalLink className="w-3.5 h-3.5" />
          Kalender öffnen
        </a>
      </div>
    </div>
  );
}
