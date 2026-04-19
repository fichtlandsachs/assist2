"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import type { StoryAssistantSession, UserStory } from "@/types";
import { useT } from "@/lib/i18n/context";
import { API_BASE, getAccessToken } from "@/lib/api/client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Sparkles, Send, RefreshCw, X, Plus, Globe, PenLine, BadgeEuro } from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ProposalItemRenderer {
  renderItem: (item: unknown, index: number, onAdd: () => void) => React.ReactNode;
  emptyLabel: string;
}

interface Props {
  storyId: string;
  orgId: string;
  story: UserStory;
  sessionType: "dod" | "features";
  panelTitle: string;
  emptyTitle: string;
  emptyDesc: string;
  startButtonLabel: string;
  consolidateMessage: string;
  proposalRenderer: ProposalItemRenderer;
  onProposalItemAdd: (item: unknown) => void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function stripMarkers(text: string): string {
  return text
    .replace(/<!--proposal[\s\S]*?-->/g, "")
    .replace(/<!--score:-?\d+-->/g, "")
    .trim();
}

async function authFetch(url: string, options: RequestInit = {}) {
  const token = getAccessToken();
  return fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers as Record<string, string> | undefined),
    },
  });
}

function WebCostBadge({ cost, provider }: { cost: number; provider: string }) {
  return (
    <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 mt-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium w-fit">
      <Globe size={9} />
      {provider} · ~${cost.toFixed(3)}
    </span>
  );
}

function TypingDots() {
  return (
    <div className="flex gap-1 py-1">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="w-1.5 h-1.5 rounded-full bg-[var(--ink-faint)] animate-bounce"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function StoryAssistantPanel({
  storyId,
  orgId,
  sessionType,
  panelTitle,
  emptyTitle,
  emptyDesc,
  startButtonLabel,
  consolidateMessage,
  proposalRenderer,
  onProposalItemAdd,
}: Props) {
  const { t } = useT();

  const [session, setSession] = useState<StoryAssistantSession | null | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingWebCost, setStreamingWebCost] = useState<{ cost: number; provider: string } | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const base = `${API_BASE}/api/v1/stories/${storyId}/assistant/${sessionType}`;

  // Load session on mount
  useEffect(() => {
    let cancelled = false;
    authFetch(`${base}?org_id=${orgId}`)
      .then((r) => (r.status === 404 ? null : r.json()))
      .then((data) => { if (!cancelled) setSession(data); })
      .catch(() => { if (!cancelled) setSession(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [storyId, orgId, base]);

  // Scroll to bottom on content changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.messages, session?.last_proposal, streamingContent]);

  const handleStart = async () => {
    const res = await authFetch(base, {
      method: "POST",
      body: JSON.stringify({ org_id: orgId }),
    });
    if (res.ok) setSession(await res.json());
  };

  const handleReset = async () => {
    await authFetch(`${base}?org_id=${orgId}`, { method: "DELETE" });
    setSession(null);
  };

  const handleDismiss = () => {
    setSession((prev) => prev ? { ...prev, last_proposal: null } : prev);
    authFetch(`${base}/dismiss`, {
      method: "POST",
      body: JSON.stringify({ org_id: orgId }),
    }).catch(() => {});
  };

  const handleAddItem = (item: unknown, index: number) => {
    onProposalItemAdd(item);
    setSession((prev) => {
      if (!prev?.last_proposal) return prev;
      const remaining = (prev.last_proposal as unknown[]).filter((_, i) => i !== index);
      return { ...prev, last_proposal: remaining.length > 0 ? remaining as typeof prev.last_proposal : null };
    });
  };

  const sendMessage = useCallback(async (overrideMsg?: string) => {
    const userMessage = overrideMsg ?? input.trim();
    if (!userMessage || streaming || !session) return;
    if (!overrideMsg) setInput("");
    setStreaming(true);
    setStreamingContent("");
    setStreamingWebCost(null);

    setSession((prev) => prev ? {
      ...prev,
      messages: [...prev.messages, { role: "user", content: userMessage, ts: new Date().toISOString() }],
    } : prev);

    try {
      const token = getAccessToken();
      const response = await fetch(`${base}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message: userMessage, org_id: orgId }),
      });

      if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let pendingLines: string[] = [];
      let fullText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            pendingLines.push(line.slice(6));
          } else if (line === "" && pendingLines.length > 0) {
            const chunk = pendingLines.join("\n");
            pendingLines = [];
            if (chunk === "[DONE]" || chunk === "[ERROR]") continue;
            if (chunk.startsWith("[WEBRESULT:")) {
              try {
                const json = chunk.slice("[WEBRESULT:".length, -1);
                setStreamingWebCost(JSON.parse(json));
              } catch {}
              continue;
            }
            fullText += chunk;
            setStreamingContent(fullText);
          }
        }
      }
    } catch (err) {
      console.error("Assistant stream error:", err);
    } finally {
      setStreaming(false);
      setStreamingContent("");
      authFetch(`${base}?org_id=${orgId}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => { if (data) setSession(data); })
        .catch(() => {});
    }
  }, [input, streaming, session, base, orgId]);

  const handleConsolidate = useCallback(() => {
    sendMessage(consolidateMessage);
  }, [sendMessage, consolidateMessage]);

  const handleRevise = useCallback(() => {
    sendMessage("Überarbeite und verbessere den letzten Vorschlag basierend auf allem, was wir besprochen haben.");
  }, [sendMessage]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ── Loading ───────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="rounded-xl border border-[var(--paper-rule2)] p-6 flex items-center justify-center">
        <div className="w-4 h-4 border-2 border-[var(--btn-primary)] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // ── Empty state ───────────────────────────────────────────────────────────
  if (!session) {
    return (
      <div className="rounded-xl border border-[var(--paper-rule2)] p-6 flex flex-col items-center gap-3 text-center">
        <div className="w-10 h-10 rounded-full bg-[rgba(var(--btn-primary-rgb),.08)] flex items-center justify-center">
          <Sparkles size={20} className="text-[var(--btn-primary)]" />
        </div>
        <div>
          <p className="font-semibold text-[var(--ink-body)]">{emptyTitle}</p>
          <p className="text-sm text-[var(--ink-mid)] mt-1">{emptyDesc}</p>
        </div>
        <button
          onClick={handleStart}
          className="px-4 py-1.5 rounded-lg bg-[var(--btn-primary)] text-white text-sm font-medium hover:opacity-90 transition-opacity"
        >
          {startButtonLabel}
        </button>
      </div>
    );
  }

  // ── Active session ────────────────────────────────────────────────────────
  const proposal = session.last_proposal as unknown[];

  return (
    <div
      className="rounded-xl border border-[var(--paper-rule2)] flex flex-col"
      style={{ minHeight: "400px", maxHeight: "600px" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--paper-rule2)] shrink-0">
        <div className="flex items-center gap-2">
          <Sparkles size={14} className="text-[var(--btn-primary)]" />
          <span className="text-sm font-semibold text-[var(--ink-body)]">{panelTitle}</span>
        </div>
        <button
          onClick={handleReset}
          title={t("refinement_reset_button")}
          className="text-[var(--ink-faint)] hover:text-[var(--ink-mid)] transition-colors"
        >
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0">
        {session.messages.map((msg, i) => {
          const hasWeb = msg.role === "user" && /\/WEB/i.test(msg.content);
          const displayContent = hasWeb ? msg.content.replace(/\/WEB/gi, "").trim() : msg.content;
          return (
            <div key={i} className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}>
              {hasWeb && (
                <span className="flex items-center gap-1 text-[10px] px-2 py-0.5 mb-0.5 rounded-full bg-blue-100 text-blue-600 font-medium">
                  <Globe size={9} /> Web-Suche
                </span>
              )}
              <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-[var(--btn-primary)] text-white"
                  : "bg-[var(--paper-warm)] text-[var(--ink-body)]"
              }`}>
                {msg.role === "assistant" ? (
                  <div className="prose prose-sm max-w-none dark:prose-invert">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {stripMarkers(msg.content)}
                    </ReactMarkdown>
                  </div>
                ) : (
                  displayContent || msg.content
                )}
              </div>
              {msg.web_cost_usd !== undefined && msg.web_provider && (
                <WebCostBadge cost={msg.web_cost_usd} provider={msg.web_provider} />
              )}
            </div>
          );
        })}

        {/* Proposal list */}
        {proposal && proposal.length > 0 && (
          <div className="rounded-lg border border-[var(--accent-blue,#3b82f6)] bg-blue-50 p-3 space-y-2 my-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[var(--accent-blue,#3b82f6)] uppercase tracking-wide">
                {t("assistant_proposal_title")}
              </span>
              <button
                onClick={handleDismiss}
                className="text-[var(--ink-faint)] hover:text-[var(--ink-mid)] transition-colors"
                aria-label={t("refinement_dismiss_button")}
              >
                <X size={14} />
              </button>
            </div>
            {proposal.map((item, idx) => (
              <div key={idx} className="flex items-start justify-between gap-2 bg-white rounded p-2 border border-blue-100">
                <div className="flex-1 text-xs text-[var(--ink-body)]">
                  {proposalRenderer.renderItem(item, idx, () => handleAddItem(item, idx))}
                </div>
                <button
                  onClick={() => handleAddItem(item, idx)}
                  className="shrink-0 flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-[var(--btn-primary)] text-white hover:opacity-90 transition-opacity"
                >
                  <Plus size={10} />
                  {t("assistant_add_button")}
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Streaming */}
        {streaming && streamingContent && (
          <div className="flex flex-col items-start">
            <div className="max-w-[85%] rounded-lg px-3 py-2 text-sm bg-[var(--paper-warm)] text-[var(--ink-body)]">
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {stripMarkers(streamingContent)}
                </ReactMarkdown>
              </div>
            </div>
            {streamingWebCost && (
              <WebCostBadge cost={streamingWebCost.cost} provider={streamingWebCost.provider} />
            )}
          </div>
        )}
        {streaming && !streamingContent && (
          <div className="flex justify-start">
            <div className="rounded-lg px-3 py-2 bg-[var(--paper-warm)]">
              <TypingDots />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-[var(--paper-rule2)] p-2 flex flex-col gap-2 shrink-0">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t("refinement_placeholder")}
          disabled={streaming}
          rows={2}
          className="w-full resize-none rounded-lg border border-[var(--paper-rule2)] px-3 py-2 text-sm text-[var(--ink-body)] placeholder:text-[var(--ink-faint)] bg-[var(--paper)] focus:outline-none focus:border-[var(--btn-primary)] disabled:opacity-50"
        />
        <div className="flex items-center justify-between gap-1 flex-wrap">
          <div className="flex items-center gap-1">
            <button
              onClick={handleConsolidate}
              disabled={streaming}
              className="flex items-center gap-1 text-xs px-2 py-1 rounded-lg border border-[var(--btn-primary)] text-[var(--btn-primary)] hover:bg-[var(--btn-primary)] hover:text-white disabled:opacity-40 transition-all"
            >
              <Sparkles size={11} />
              {t("refinement_consolidate_button")}
            </button>
            <button
              onClick={handleRevise}
              disabled={streaming || !session?.last_proposal?.length}
              className="flex items-center gap-1 text-xs px-2 py-1 rounded-lg border border-[var(--ink-faint)] text-[var(--ink-mid)] hover:border-[var(--btn-primary)] hover:text-[var(--btn-primary)] disabled:opacity-30 transition-all"
              title={t("assistant_revise_tooltip")}
            >
              <PenLine size={11} />
              {t("assistant_revise_button")}
            </button>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-[var(--ink-faint)] flex items-center gap-0.5">
              <Globe size={9} /> /WEB
            </span>
            <button
              onClick={() => sendMessage()}
              disabled={!input.trim() || streaming}
              className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg bg-[var(--btn-primary)] text-white disabled:opacity-40 hover:opacity-90 transition-opacity"
            >
              <Send size={11} />
              {t("refinement_send_button")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
