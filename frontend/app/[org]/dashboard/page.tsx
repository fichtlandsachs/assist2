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
  { status: "draft",       label: "Entwurf",         color: "bg-[var(--paper-warm)] text-[var(--ink-mid)]",              dot: "bg-[var(--paper-rule)]" },
  { status: "in_review",   label: "Überarbeitung",   color: "bg-[rgba(var(--btn-primary-rgb),.08)] text-[var(--btn-primary)]",  dot: "bg-[var(--btn-primary)]" },
  { status: "ready",       label: "Bereit",          color: "bg-[rgba(74,85,104,.06)] text-[var(--navy)]",   dot: "bg-[var(--navy)]" },
  { status: "in_progress", label: "In Arbeit",       color: "bg-[rgba(122,100,80,.1)] text-[var(--brown)]",   dot: "bg-[var(--brown)]" },
  { status: "testing",     label: "Test",            color: "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]",  dot: "bg-[var(--accent-red)]" },
  { status: "done",        label: "Fertig",          color: "bg-[rgba(82,107,94,.1)] text-[var(--green)]",   dot: "bg-[var(--green)]" },
  { status: "archived",    label: "Archiviert",      color: "bg-[var(--paper-warm)] text-[var(--ink-faint)]",              dot: "bg-[var(--paper-rule)]" },
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
        <h1 className="text-2xl font-bold text-[var(--ink)]">
          Willkommen{user ? `, ${user.display_name}` : ""}
        </h1>
        {org && <p className="text-[var(--ink-faint)] mt-1">{org.name}</p>}
      </div>

      {/* Inbox Stats */}
      <div>
        <h2 className="text-sm font-semibold text-[var(--ink-faint)] uppercase tracking-wide mb-3 flex items-center gap-2">
          <Inbox size={14} />
          Posteingang
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link
            href={`/${resolvedParams.org}/inbox`}
            className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-5 hover:border-[rgba(var(--accent-red-rgb),.3)] transition-all group"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-[var(--ink-faint)] mb-1">Aktive Themen</p>
                <p className="text-3xl font-bold text-[var(--ink)]">
                  {inboxStats ? inboxStats.topics : <span className="text-[var(--ink-faintest)]">—</span>}
                </p>
              </div>
              <span className="p-2 bg-[rgba(var(--accent-red-rgb),.08)] rounded-sm text-[var(--accent-red)] group-hover:bg-[rgba(var(--accent-red-rgb),.08)] transition-colors">
                <Layers size={18} />
              </span>
            </div>
            <p className="text-xs text-[var(--ink-faint)] mt-2">Gesprächs-/Bestellungsgruppen</p>
          </Link>

          <Link
            href={`/${resolvedParams.org}/inbox`}
            className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-5 hover:border-[rgba(var(--accent-red-rgb),.3)] transition-all group"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-[var(--ink-faint)] mb-1">Ungelesene Nachrichten</p>
                <p className="text-3xl font-bold text-[var(--ink)]">
                  {inboxStats ? (
                    <span className={inboxStats.unread > 0 ? "text-[var(--accent-red)]" : ""}>
                      {inboxStats.unread}
                    </span>
                  ) : (
                    <span className="text-[var(--ink-faintest)]">—</span>
                  )}
                </p>
              </div>
              <span className="p-2 bg-[var(--card)] rounded-sm text-[var(--ink-faint)] group-hover:bg-[var(--paper-warm)] transition-colors">
                <CircleDot size={18} />
              </span>
            </div>
            <p className="text-xs text-[var(--ink-faint)] mt-2">Noch nicht gelesene E-Mails</p>
          </Link>
        </div>
      </div>

      {/* Story Stats */}
      <div>
        <h2 className="text-sm font-semibold text-[var(--ink-faint)] uppercase tracking-wide mb-3 flex items-center gap-2">
          <LayoutList size={14} />
          User Stories
        </h2>
        <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] overflow-hidden">
          {/* Total bar */}
          {storyCounts && stories && stories.length > 0 && (
            <div className="px-5 pt-5 pb-3 border-b border-[var(--paper-rule)]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-[var(--ink-mid)]">Gesamt: {stories.length}</span>
                <Link
                  href={`/${resolvedParams.org}/stories/board`}
                  className="text-xs text-[var(--accent-red)] hover:text-[var(--accent-red)] font-medium"
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

          <div className="divide-y divide-[var(--paper)]">
            {STATUS_META.map((m) => {
              const count = storyCounts?.[m.status] ?? null;
              return (
                <Link
                  key={m.status}
                  href={`/${resolvedParams.org}/stories/list`}
                  className="flex items-center gap-3 px-5 py-3.5 hover:bg-[var(--card)] transition-colors"
                >
                  <span className={`w-2 h-2 rounded-full shrink-0 ${m.dot}`} />
                  <span className="flex-1 text-sm text-[var(--ink-mid)]">{m.label}</span>
                  <span className={`text-sm font-semibold px-2 py-0.5 rounded-full ${m.color}`}>
                    {count !== null ? count : "—"}
                  </span>
                </Link>
              );
            })}
          </div>

          {!stories && (
            <div className="flex items-center justify-center py-10">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--accent-red)]" />
            </div>
          )}

          {stories && stories.length === 0 && (
            <div className="text-center py-8">
              <p className="text-sm text-[var(--ink-faint)] mb-3">Noch keine User Stories vorhanden.</p>
              <Link
                href={`/${resolvedParams.org}/stories/new`}
                className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--btn-primary)] hover:bg-[var(--btn-primary-hover)] text-white rounded-sm text-sm font-medium transition-colors"
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
