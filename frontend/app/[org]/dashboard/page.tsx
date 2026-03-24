"use client";

import { useMemo } from "react";
import { useAuth } from "@/lib/auth/context";
import { useOrg } from "@/lib/hooks/useOrg";
import { SlotRenderer } from "@/lib/plugins/slots";
import { fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { UserStory, StoryStatus, Message } from "@/types";
import Link from "next/link";
import { LayoutList, Inbox, Layers, CheckCircle2, Clock, Archive, CircleDot } from "lucide-react";

const STATUS_META: { status: StoryStatus; label: string; color: string; dot: string }[] = [
  { status: "draft",       label: "Entwurf",         color: "bg-slate-100 text-slate-600",   dot: "bg-slate-400" },
  { status: "in_review",   label: "Überarbeitung",   color: "bg-violet-50 text-violet-700",  dot: "bg-violet-500" },
  { status: "ready",       label: "Bereit",          color: "bg-blue-50 text-blue-700",      dot: "bg-blue-500" },
  { status: "in_progress", label: "In Arbeit",       color: "bg-amber-50 text-amber-700",    dot: "bg-amber-500" },
  { status: "testing",     label: "Test",            color: "bg-orange-50 text-orange-700",  dot: "bg-orange-500" },
  { status: "done",        label: "Fertig",          color: "bg-green-50 text-green-700",    dot: "bg-green-500" },
  { status: "archived",    label: "Archiviert",      color: "bg-slate-100 text-slate-400",   dot: "bg-slate-300" },
];

export default function DashboardPage({ params }: { params: { org: string } }) {
  const { user } = useAuth();
  const { org } = useOrg(params.org);

  const { data: stories } = useSWR<UserStory[]>(
    org ? `/api/v1/user-stories?org_id=${org.id}` : null,
    fetcher
  );

  const { data: messages } = useSWR<Message[]>(
    org ? `/api/v1/inbox/messages?org_id=${org.id}` : null,
    fetcher
  );

  const storyCounts = useMemo(() => {
    if (!stories) return null;
    const counts: Record<StoryStatus, number> = {
      draft: 0, in_review: 0, ready: 0, in_progress: 0, testing: 0, done: 0, archived: 0,
    };
    for (const s of stories) counts[s.status] = (counts[s.status] ?? 0) + 1;
    return counts;
  }, [stories]);

  const inboxStats = useMemo(() => {
    if (!messages) return null;
    const topics = new Set<string>();
    let unread = 0;
    for (const m of messages) {
      if (m.topic_cluster) topics.add(m.topic_cluster);
      if (m.status === "unread") unread++;
    }
    return { topics: topics.size, unread };
  }, [messages]);

  return (
    <div className="space-y-6">
      {/* Welcome Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">
          Willkommen{user ? `, ${user.display_name}` : ""}
        </h1>
        {org && <p className="text-slate-500 mt-1">{org.name}</p>}
      </div>

      {/* Inbox Stats */}
      <div>
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-2">
          <Inbox size={14} />
          Posteingang
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link
            href={`/${params.org}/inbox`}
            className="bg-white rounded-xl border border-slate-200 p-5 hover:border-brand-300 hover:shadow-sm transition-all group"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-slate-500 mb-1">Aktive Themen</p>
                <p className="text-3xl font-bold text-slate-900">
                  {inboxStats ? inboxStats.topics : <span className="text-slate-300">—</span>}
                </p>
              </div>
              <span className="p-2 bg-brand-50 rounded-lg text-brand-600 group-hover:bg-brand-100 transition-colors">
                <Layers size={18} />
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-2">Gesprächs-/Bestellungsgruppen</p>
          </Link>

          <Link
            href={`/${params.org}/inbox`}
            className="bg-white rounded-xl border border-slate-200 p-5 hover:border-brand-300 hover:shadow-sm transition-all group"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-slate-500 mb-1">Ungelesene Nachrichten</p>
                <p className="text-3xl font-bold text-slate-900">
                  {inboxStats ? (
                    <span className={inboxStats.unread > 0 ? "text-brand-600" : ""}>
                      {inboxStats.unread}
                    </span>
                  ) : (
                    <span className="text-slate-300">—</span>
                  )}
                </p>
              </div>
              <span className="p-2 bg-slate-50 rounded-lg text-slate-500 group-hover:bg-slate-100 transition-colors">
                <CircleDot size={18} />
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-2">Noch nicht gelesene E-Mails</p>
          </Link>
        </div>
      </div>

      {/* Story Stats */}
      <div>
        <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-2">
          <LayoutList size={14} />
          User Stories
        </h2>
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          {/* Total bar */}
          {storyCounts && stories && stories.length > 0 && (
            <div className="px-5 pt-5 pb-3 border-b border-slate-100">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-slate-700">Gesamt: {stories.length}</span>
                <Link
                  href={`/${params.org}/stories/board`}
                  className="text-xs text-brand-600 hover:text-brand-700 font-medium"
                >
                  Board öffnen →
                </Link>
              </div>
              <div className="flex h-2 rounded-full overflow-hidden gap-0.5">
                {STATUS_META.map((m) =>
                  storyCounts[m.status] > 0 ? (
                    <div
                      key={m.status}
                      className={`${m.dot} rounded-full`}
                      style={{ flex: storyCounts[m.status] }}
                      title={`${m.label}: ${storyCounts[m.status]}`}
                    />
                  ) : null
                )}
              </div>
            </div>
          )}

          <div className="divide-y divide-slate-50">
            {STATUS_META.map((m) => {
              const count = storyCounts?.[m.status] ?? null;
              return (
                <Link
                  key={m.status}
                  href={`/${params.org}/stories/list`}
                  className="flex items-center gap-3 px-5 py-3.5 hover:bg-slate-50 transition-colors"
                >
                  <span className={`w-2 h-2 rounded-full shrink-0 ${m.dot}`} />
                  <span className="flex-1 text-sm text-slate-700">{m.label}</span>
                  <span className={`text-sm font-semibold px-2 py-0.5 rounded-full ${m.color}`}>
                    {count !== null ? count : "—"}
                  </span>
                </Link>
              );
            })}
          </div>

          {!stories && (
            <div className="flex items-center justify-center py-10">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-brand-500" />
            </div>
          )}

          {stories && stories.length === 0 && (
            <div className="text-center py-8">
              <p className="text-sm text-slate-400 mb-3">Noch keine User Stories vorhanden.</p>
              <Link
                href={`/${params.org}/stories/new`}
                className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                Erste Story erstellen
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Plugin Dashboard Widgets */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <SlotRenderer slotId="dashboard_widget" orgSlug={params.org} />
      </div>
    </div>
  );
}
