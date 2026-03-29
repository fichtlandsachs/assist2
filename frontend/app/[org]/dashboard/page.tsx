"use client";

import { use, useMemo } from "react";
import { useAuth } from "@/lib/auth/context";
import { useOrg } from "@/lib/hooks/useOrg";
import { SlotRenderer } from "@/lib/plugins/slots";
import { fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { UserStory, StoryStatus, Message } from "@/types";
import Link from "next/link";
import { LayoutList, Inbox, Layers, CheckCircle2, Clock, Archive, CircleDot } from "lucide-react";

const STATUS_META: { status: StoryStatus; label: string; color: string; dot: string }[] = [
  { status: "draft",       label: "Entwurf",         color: "bg-[#f7f4ee] text-[#5a5040]",              dot: "bg-[#e2ddd4]" },
  { status: "in_review",   label: "Überarbeitung",   color: "bg-[rgba(90,80,104,.08)] text-[#5a5068]",  dot: "bg-[#5a5068]" },
  { status: "ready",       label: "Bereit",          color: "bg-[rgba(74,85,104,.06)] text-[#4a5568]",   dot: "bg-[#4a5568]" },
  { status: "in_progress", label: "In Arbeit",       color: "bg-[rgba(122,100,80,.1)] text-[#7a6450]",   dot: "bg-[#7a6450]" },
  { status: "testing",     label: "Test",            color: "bg-[rgba(139,94,82,.08)] text-[#8b5e52]",  dot: "bg-[#8b5e52]" },
  { status: "done",        label: "Fertig",          color: "bg-[rgba(82,107,94,.1)] text-[#526b5e]",   dot: "bg-[#526b5e]" },
  { status: "archived",    label: "Archiviert",      color: "bg-[#f7f4ee] text-[#a09080]",              dot: "bg-[#e2ddd4]" },
];

export default function DashboardPage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { user } = useAuth();
  const { org } = useOrg(resolvedParams.org);

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
        <h1 className="text-2xl font-bold text-[#1c1810]">
          Willkommen{user ? `, ${user.display_name}` : ""}
        </h1>
        {org && <p className="text-[#a09080] mt-1">{org.name}</p>}
      </div>

      {/* Inbox Stats */}
      <div>
        <h2 className="text-sm font-semibold text-[#a09080] uppercase tracking-wide mb-3 flex items-center gap-2">
          <Inbox size={14} />
          Posteingang
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link
            href={`/${resolvedParams.org}/inbox`}
            className="bg-[#faf9f6] rounded-sm border border-[#e2ddd4] p-5 hover:border-[rgba(139,94,82,.3)] transition-all group"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-[#a09080] mb-1">Aktive Themen</p>
                <p className="text-3xl font-bold text-[#1c1810]">
                  {inboxStats ? inboxStats.topics : <span className="text-[#cec8bc]">—</span>}
                </p>
              </div>
              <span className="p-2 bg-[rgba(139,94,82,.08)] rounded-sm text-[#8b5e52] group-hover:bg-[rgba(139,94,82,.08)] transition-colors">
                <Layers size={18} />
              </span>
            </div>
            <p className="text-xs text-[#a09080] mt-2">Gesprächs-/Bestellungsgruppen</p>
          </Link>

          <Link
            href={`/${resolvedParams.org}/inbox`}
            className="bg-[#faf9f6] rounded-sm border border-[#e2ddd4] p-5 hover:border-[rgba(139,94,82,.3)] transition-all group"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-[#a09080] mb-1">Ungelesene Nachrichten</p>
                <p className="text-3xl font-bold text-[#1c1810]">
                  {inboxStats ? (
                    <span className={inboxStats.unread > 0 ? "text-[#8b5e52]" : ""}>
                      {inboxStats.unread}
                    </span>
                  ) : (
                    <span className="text-[#cec8bc]">—</span>
                  )}
                </p>
              </div>
              <span className="p-2 bg-[#faf9f6] rounded-sm text-[#a09080] group-hover:bg-[#f7f4ee] transition-colors">
                <CircleDot size={18} />
              </span>
            </div>
            <p className="text-xs text-[#a09080] mt-2">Noch nicht gelesene E-Mails</p>
          </Link>
        </div>
      </div>

      {/* Story Stats */}
      <div>
        <h2 className="text-sm font-semibold text-[#a09080] uppercase tracking-wide mb-3 flex items-center gap-2">
          <LayoutList size={14} />
          User Stories
        </h2>
        <div className="bg-[#faf9f6] rounded-sm border border-[#e2ddd4] overflow-hidden">
          {/* Total bar */}
          {storyCounts && stories && stories.length > 0 && (
            <div className="px-5 pt-5 pb-3 border-b border-[#e2ddd4]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-[#5a5040]">Gesamt: {stories.length}</span>
                <Link
                  href={`/${resolvedParams.org}/stories/board`}
                  className="text-xs text-[#8b5e52] hover:text-[#8b5e52] font-medium"
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

          <div className="divide-y divide-[#faf9f6]">
            {STATUS_META.map((m) => {
              const count = storyCounts?.[m.status] ?? null;
              return (
                <Link
                  key={m.status}
                  href={`/${resolvedParams.org}/stories/list`}
                  className="flex items-center gap-3 px-5 py-3.5 hover:bg-[#faf9f6] transition-colors"
                >
                  <span className={`w-2 h-2 rounded-full shrink-0 ${m.dot}`} />
                  <span className="flex-1 text-sm text-[#5a5040]">{m.label}</span>
                  <span className={`text-sm font-semibold px-2 py-0.5 rounded-full ${m.color}`}>
                    {count !== null ? count : "—"}
                  </span>
                </Link>
              );
            })}
          </div>

          {!stories && (
            <div className="flex items-center justify-center py-10">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[#8b5e52]" />
            </div>
          )}

          {stories && stories.length === 0 && (
            <div className="text-center py-8">
              <p className="text-sm text-[#a09080] mb-3">Noch keine User Stories vorhanden.</p>
              <Link
                href={`/${resolvedParams.org}/stories/new`}
                className="inline-flex items-center gap-2 px-4 py-2 bg-[#5a5068] hover:bg-[#5a5068] text-white rounded-sm text-sm font-medium transition-colors"
              >
                Erste Story erstellen
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Plugin Dashboard Widgets */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <SlotRenderer slotId="dashboard_widget" orgSlug={resolvedParams.org} />
      </div>
    </div>
  );
}
