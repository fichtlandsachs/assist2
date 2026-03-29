"use client";

import { use, useState, useMemo } from "react";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher, getAccessToken } from "@/lib/api/client";
import useSWR from "swr";
import type { MailConnection, Message } from "@/types";
import { RefreshCw, Mail, Archive, Eye, Search, ChevronRight, Inbox } from "lucide-react";

// ── Helpers ─────────────────────────────────────────────────────────────────

/** Strip Re:/AW:/Fwd: prefixes to get the base subject for threading */
function normalizeSubject(subject: string | null): string {
  if (!subject) return "(Kein Betreff)";
  return subject
    .replace(/^(re|aw|fwd|fw|wg|sv):\s*/gi, "")
    .replace(/^(re|aw|fwd|fw|wg|sv):\s*/gi, "") // double pass
    .trim() || "(Kein Betreff)";
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const hours = diff / (1000 * 60 * 60);
  if (hours < 24) return date.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  if (hours < 48) return "Gestern";
  if (hours < 168) return date.toLocaleDateString("de-DE", { weekday: "short" });
  return date.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
}

function formatDateFull(dateStr: string | null): string {
  if (!dateStr) return "";
  return new Date(dateStr).toLocaleString("de-DE", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

interface ThreadGroup {
  key: string;           // normalized subject
  subject: string;       // display subject (original of first)
  messages: Message[];   // sorted oldest → newest
  unreadCount: number;
  latestDate: string | null;
  senders: string[];     // unique sender names/emails
}

export default function InboxPage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { org } = useOrg(resolvedParams.org);
  const [selectedThreadKey, setSelectedThreadKey] = useState<string | null>(null);
  const [selectedMessage, setSelectedMessage] = useState<Message | null>(null);
  const [search, setSearch] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [reclustering, setReclustering] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const { data: connections } = useSWR<MailConnection[]>(
    org ? `/api/v1/inbox/connections?org_id=${org.id}` : null,
    fetcher
  );

  const { data: allMessages, mutate: mutateAll } = useSWR<Message[]>(
    org ? `/api/v1/inbox/messages?org_id=${org.id}` : null,
    fetcher,
    { refreshInterval: 60000 }
  );
  const mutateMessages = mutateAll;

  const connectionMap = useMemo(() => {
    const m: Record<string, MailConnection> = {};
    (connections ?? []).forEach((c) => { m[c.id] = c; });
    return m;
  }, [connections]);

  // Build thread groups from all messages
  const threads = useMemo((): ThreadGroup[] => {
    const src = allMessages ?? [];
    const groups: Record<string, ThreadGroup> = {};

    for (const msg of src) {
      // Prefer AI topic_cluster, fall back to normalised subject
      const key = msg.topic_cluster ?? normalizeSubject(msg.subject);
      if (!groups[key]) {
        groups[key] = {
          key,
          subject: msg.topic_cluster ?? msg.subject ?? "(Kein Betreff)",
          messages: [],
          unreadCount: 0,
          latestDate: null,
          senders: [],
        };
      }
      const g = groups[key];
      g.messages.push(msg);
      if (msg.status === "unread") g.unreadCount++;
      if (!g.latestDate || (msg.received_at && msg.received_at > g.latestDate)) {
        g.latestDate = msg.received_at;
      }
      const sender = msg.sender_name || msg.sender_email;
      if (!g.senders.includes(sender)) g.senders.push(sender);
    }

    // Sort messages within each group oldest→newest
    for (const g of Object.values(groups)) {
      g.messages.sort((a, b) =>
        (a.received_at ?? "").localeCompare(b.received_at ?? "")
      );
    }

    // Filter by search
    const term = search.toLowerCase();
    return Object.values(groups)
      .filter((g) => {
        if (!term) return true;
        return (
          g.subject.toLowerCase().includes(term) ||
          g.senders.some((s) => s.toLowerCase().includes(term))
        );
      })
      .sort((a, b) => (b.latestDate ?? "").localeCompare(a.latestDate ?? ""));
  }, [allMessages, search]);

  const selectedThread = threads.find((t) => t.key === selectedThreadKey) ?? null;

  async function handleRecluster() {
    if (!org) return;
    setReclustering(true);
    try {
      await apiRequest(`/api/v1/inbox/recluster?org_id=${org.id}`, { method: "POST" });
      // Poll briefly then refresh
      setTimeout(() => { void mutateAll(); setReclustering(false); }, 8000);
    } catch { setReclustering(false); }
  }

  async function handleSyncAll() {
    if (!org || !connections) return;
    setSyncing(true);
    try {
      await Promise.all(
        connections.map((c) =>
          apiRequest(`/api/v1/inbox/connections/${c.id}/sync?org_id=${org.id}`, { method: "POST" })
            .catch(() => null)
        )
      );
      await Promise.all([mutateMessages(), mutateAll()]);
    } finally {
      setSyncing(false);
    }
  }

  async function handleMarkRead(msg: Message) {
    setActionLoading(msg.id + "_read");
    try {
      await apiRequest(`/api/v1/inbox/messages/${msg.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "read" }),
      });
      await Promise.all([mutateMessages(), mutateAll()]);
      setSelectedMessage({ ...msg, status: "read" });
    } finally {
      setActionLoading(null);
    }
  }

  async function handleArchive(msg: Message) {
    setActionLoading(msg.id + "_archive");
    try {
      await apiRequest(`/api/v1/inbox/messages/${msg.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "archived" }),
      });
      await Promise.all([mutateMessages(), mutateAll()]);
      setSelectedMessage(null);
    } finally {
      setActionLoading(null);
    }
  }

  const totalUnread = threads.reduce((n, t) => n + t.unreadCount, 0);

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)] gap-0 -m-4 md:-m-6">
      {/* Top bar */}
      <div className="flex items-center gap-3 px-4 md:px-6 py-3 bg-[#faf9f6] border-b border-[#e2ddd4] shrink-0">
        <div className="flex items-center gap-2 flex-1">
          <Inbox size={18} className="text-[#8b5e52] shrink-0" />
          <h1 className="text-base font-semibold text-[#1c1810]">Posteingang</h1>
          {totalUnread > 0 && (
            <span className="px-2 py-0.5 bg-[#5a5068] text-white text-xs font-semibold rounded-full">{totalUnread}</span>
          )}
        </div>
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#a09080]" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Suchen…"
            className="w-full pl-8 pr-3 py-1.5 text-sm border border-[#e2ddd4] rounded-sm outline-none focus:border-[#8b5e52] bg-[#faf9f6]"
          />
        </div>
        <button
          onClick={() => void handleRecluster()}
          disabled={reclustering}
          title="Themen neu gruppieren (KI)"
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-[#e2ddd4] text-[#5a5040] hover:bg-[#faf9f6] rounded-sm transition-colors disabled:opacity-50"
        >
          <RefreshCw size={14} className={reclustering ? "animate-spin text-[#8b5e52]" : ""} />
          <span className="hidden sm:inline">{reclustering ? "Gruppiere…" : "Neu gruppieren"}</span>
        </button>
        <button
          onClick={() => void handleSyncAll()}
          disabled={syncing || !connections?.length}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-[#e2ddd4] text-[#5a5040] hover:bg-[#faf9f6] rounded-sm transition-colors disabled:opacity-50"
        >
          <RefreshCw size={14} className={syncing ? "animate-spin" : ""} />
          <span className="hidden sm:inline">Aktualisieren</span>
        </button>
      </div>

      {/* Main 3-pane layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Thread list */}
        <div className="w-72 xl:w-80 shrink-0 border-r border-[#e2ddd4] overflow-y-auto bg-[#faf9f6]">
          {!allMessages ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[#8b5e52]" />
            </div>
          ) : threads.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
              <Mail size={36} className="text-[#cec8bc] mb-3" />
              <p className="text-sm text-[#a09080] font-medium">Keine Nachrichten</p>
              <p className="text-xs text-[#a09080] mt-1">
                {search ? "Keine Treffer für deine Suche." : "Klicke auf Aktualisieren, um E-Mails zu laden."}
              </p>
            </div>
          ) : (
            threads.map((thread) => {
              const isSelected = thread.key === selectedThreadKey;
              const hasUnread = thread.unreadCount > 0;
              return (
                <button
                  key={thread.key}
                  onClick={() => { setSelectedThreadKey(thread.key); setSelectedMessage(null); }}
                  className={`w-full text-left px-4 py-3 border-b border-[#e2ddd4] transition-colors hover:bg-[#f7f4ee] ${isSelected ? "bg-[rgba(139,94,82,.08)] border-l-2 border-l-[#8b5e52]" : ""}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className={`text-sm truncate ${hasUnread ? "font-bold text-[#1c1810]" : "font-medium text-[#5a5040]"}`}>
                        {normalizeSubject(thread.subject)}
                      </p>
                      <p className="text-xs text-[#a09080] truncate mt-0.5">
                        {thread.senders.slice(0, 2).join(", ")}
                        {thread.senders.length > 2 && ` +${thread.senders.length - 2}`}
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-1 shrink-0">
                      <span className="text-xs text-[#a09080]">{formatDate(thread.latestDate)}</span>
                      <div className="flex items-center gap-1">
                        {thread.messages.length > 1 && (
                          <span className="text-xs text-[#a09080] bg-[#f7f4ee] px-1.5 py-0.5 rounded-full">
                            {thread.messages.length}
                          </span>
                        )}
                        {hasUnread && (
                          <span className="w-2 h-2 bg-[#8b5e52] rounded-full" />
                        )}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* Middle: Message list for selected thread */}
        <div className={`w-64 xl:w-72 shrink-0 border-r border-[#e2ddd4] overflow-y-auto bg-[#faf9f6] ${!selectedThread ? "hidden md:block" : ""}`}>
          {!selectedThread ? (
            <div className="flex flex-col items-center justify-center h-full py-12 text-center px-4">
              <ChevronRight size={32} className="text-[#cec8bc] mb-2" />
              <p className="text-sm text-[#a09080]">Thema wählen</p>
            </div>
          ) : (
            <>
              <div className="px-3 py-2.5 border-b border-[#e2ddd4] bg-[#faf9f6]">
                <p className="text-xs font-semibold text-[#a09080] uppercase tracking-wide truncate">
                  {normalizeSubject(selectedThread.subject)}
                </p>
                <p className="text-xs text-[#a09080] mt-0.5">{selectedThread.messages.length} Nachrichten</p>
              </div>
              {selectedThread.messages.map((msg) => {
                const conn = connectionMap[msg.connection_id];
                const isActive = selectedMessage?.id === msg.id;
                return (
                  <button
                    key={msg.id}
                    onClick={() => setSelectedMessage(msg)}
                    className={`w-full text-left px-3 py-3 border-b border-[#e2ddd4] transition-colors hover:bg-[#faf9f6] ${isActive ? "bg-[#faf9f6] border-l-2 border-l-[#8b5e52]" : ""}`}
                  >
                    <div className="flex items-start justify-between gap-1">
                      <p className={`text-xs flex-1 truncate ${msg.status === "unread" ? "font-bold text-[#1c1810]" : "font-medium text-[#5a5040]"}`}>
                        {msg.sender_name ?? msg.sender_email}
                      </p>
                      <span className="text-xs text-[#a09080] shrink-0">{formatDate(msg.received_at)}</span>
                    </div>
                    {conn && (
                      <p className="text-xs text-[#8b5e52] truncate mt-0.5">→ {conn.email_address}</p>
                    )}
                    {msg.snippet && (
                      <p className="text-xs text-[#a09080] truncate mt-0.5">{msg.snippet}</p>
                    )}
                  </button>
                );
              })}
            </>
          )}
        </div>

        {/* Right: Message detail */}
        <div className="flex-1 overflow-y-auto bg-[#faf9f6]">
          {!selectedMessage ? (
            <div className="flex flex-col items-center justify-center h-full text-center p-8">
              <Mail size={40} className="text-[#cec8bc] mb-3" />
              <p className="text-sm font-medium text-[#a09080]">
                {selectedThread ? "Nachricht auswählen" : "Thema auswählen"}
              </p>
            </div>
          ) : (
            <div className="p-5 md:p-6 space-y-4">
              {/* Header */}
              <div className="flex items-start justify-between gap-4 pb-4 border-b border-[#e2ddd4]">
                <div className="flex-1 min-w-0">
                  <h2 className="text-base font-semibold text-[#1c1810] break-words">
                    {selectedMessage.subject ?? "(Kein Betreff)"}
                  </h2>
                  <div className="mt-2 space-y-1">
                    <div className="flex items-baseline gap-2">
                      <span className="text-xs font-medium text-[#a09080] w-16 shrink-0">Von</span>
                      <span className="text-sm text-[#5a5040]">
                        {selectedMessage.sender_name
                          ? `${selectedMessage.sender_name} <${selectedMessage.sender_email}>`
                          : selectedMessage.sender_email}
                      </span>
                    </div>
                    {connectionMap[selectedMessage.connection_id] && (
                      <div className="flex items-baseline gap-2">
                        <span className="text-xs font-medium text-[#a09080] w-16 shrink-0">Konto</span>
                        <span className="text-sm text-[#5a5040]">
                          {connectionMap[selectedMessage.connection_id].display_name ?? connectionMap[selectedMessage.connection_id].email_address}
                        </span>
                      </div>
                    )}
                    {connectionMap[selectedMessage.connection_id] && (
                      <div className="flex items-center gap-2 mt-2">
                        <label className="text-xs text-[#a09080] whitespace-nowrap">Sync-Intervall:</label>
                        <select
                          defaultValue={connectionMap[selectedMessage.connection_id].sync_interval_minutes ?? 15}
                          onChange={async (e) => {
                            const conn = connectionMap[selectedMessage.connection_id];
                            const interval = Number(e.target.value);
                            const token = getAccessToken() ?? "";
                            await fetch(`/api/v1/inbox/connections/${conn.id}`, {
                              method: "PATCH",
                              headers: {
                                "Content-Type": "application/json",
                                ...(token ? { Authorization: `Bearer ${token}` } : {}),
                              },
                              body: JSON.stringify({ sync_interval_minutes: interval }),
                            });
                          }}
                          className="text-xs border border-[#e2ddd4] rounded-sm px-2 py-1 bg-[#faf9f6] text-[#5a5040]"
                        >
                          <option value={5}>5 Minuten</option>
                          <option value={15}>15 Minuten</option>
                          <option value={30}>30 Minuten</option>
                          <option value={60}>60 Minuten</option>
                        </select>
                      </div>
                    )}
                    {selectedMessage.received_at && (
                      <div className="flex items-baseline gap-2">
                        <span className="text-xs font-medium text-[#a09080] w-16 shrink-0">Datum</span>
                        <span className="text-xs text-[#a09080]">{formatDateFull(selectedMessage.received_at)}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex gap-2 shrink-0 flex-wrap justify-end">
                  {selectedMessage.status === "unread" && (
                    <button
                      onClick={() => void handleMarkRead(selectedMessage)}
                      disabled={!!actionLoading}
                      className="flex items-center gap-1.5 px-3 py-1.5 border border-[#e2ddd4] text-[#5a5040] hover:bg-[#f7f4ee] rounded-sm text-xs font-medium transition-colors disabled:opacity-50"
                    >
                      <Eye size={12} /> Als gelesen
                    </button>
                  )}
                  <button
                    onClick={() => void handleArchive(selectedMessage)}
                    disabled={!!actionLoading}
                    className="flex items-center gap-1.5 px-3 py-1.5 border border-[#e2ddd4] text-[#5a5040] hover:bg-[#f7f4ee] rounded-sm text-xs font-medium transition-colors disabled:opacity-50"
                  >
                    <Archive size={12} /> Archivieren
                  </button>
                </div>
              </div>

              {/* Body */}
              <div className="text-sm text-[#5a5040] leading-relaxed">
                {selectedMessage.body_text ? (
                  <pre className="whitespace-pre-wrap font-sans">{selectedMessage.body_text}</pre>
                ) : selectedMessage.snippet ? (
                  <p>{selectedMessage.snippet}</p>
                ) : (
                  <p className="text-[#a09080] italic">Kein Nachrichteninhalt verfügbar.</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
