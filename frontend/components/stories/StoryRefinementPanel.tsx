"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import type { StoryRefinementSession, RefinementProposal, UserStory } from "@/types";
import { useT } from "@/lib/i18n/context";
import { API_BASE, getAccessToken } from "@/lib/api/client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Sparkles, Send, RefreshCw, Lock, Check, X,
} from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Props {
  storyId: string;
  orgId: string;
  story: UserStory;
  onApply: (field: "title" | "description" | "acceptance_criteria", value: string) => void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function stripHiddenMarkers(text: string): string {
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

// ── Score badge ───────────────────────────────────────────────────────────────

function ScoreBadge({ score }: { score: number | null }) {
  const { t } = useT();
  if (score === null) return null;
  const color =
    score >= 75 ? "bg-green-100 text-green-700" :
    score >= 50 ? "bg-yellow-100 text-yellow-700" :
    "bg-red-100 text-red-700";
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {t("refinement_score_label")}: {score}/100
    </span>
  );
}

// ── Proposal card ─────────────────────────────────────────────────────────────

function ProposalCard({
  proposal,
  onApply,
  onDismiss,
}: {
  proposal: RefinementProposal;
  onApply: (field: "title" | "description" | "acceptance_criteria", value: string) => void;
  onDismiss: () => void;
}) {
  const { t } = useT();
  const fields = [
    { key: "title" as const, label: t("refinement_field_title"), value: proposal.title },
    { key: "description" as const, label: t("refinement_field_description"), value: proposal.description },
    { key: "acceptance_criteria" as const, label: t("refinement_field_ac"), value: proposal.acceptance_criteria },
  ].filter((f) => !!f.value);

  if (!fields.length) return null;

  return (
    <div className="rounded-lg border border-[var(--accent-blue,#3b82f6)] bg-blue-50 p-3 space-y-2 my-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-[var(--accent-blue,#3b82f6)] uppercase tracking-wide">
          {t("refinement_proposal_title")}
        </span>
        <button
          onClick={onDismiss}
          className="text-[var(--ink-faint)] hover:text-[var(--ink-mid)] transition-colors"
          aria-label={t("refinement_dismiss_button")}
        >
          <X size={14} />
        </button>
      </div>
      {fields.map(({ key, label, value }) => (
        <div key={key} className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[var(--ink-mid)] font-medium">{label}</span>
            <button
              onClick={() => onApply(key, value!)}
              className="flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-[var(--btn-primary)] text-white hover:opacity-90 transition-opacity"
            >
              <Check size={10} />
              {t("refinement_apply_button")}
            </button>
          </div>
          <p className="text-xs text-[var(--ink-body)] bg-white rounded p-1.5 border border-blue-100 whitespace-pre-wrap line-clamp-3">
            {value}
          </p>
        </div>
      ))}
    </div>
  );
}

// ── Stage tabs ────────────────────────────────────────────────────────────────

function StageTabs({ stage }: { stage: number }) {
  const { t } = useT();
  const stages = [
    { n: 1, label: t("refinement_stage1") },
    { n: 2, label: t("refinement_stage2") },
    { n: 3, label: t("refinement_stage3") },
  ];
  return (
    <div className="flex gap-1">
      {stages.map(({ n, label }) => (
        <div
          key={n}
          title={n > 1 ? t("refinement_stage_locked") : undefined}
          className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
            n === stage
              ? "bg-[var(--btn-primary)] text-white"
              : "bg-[var(--paper-warm)] text-[var(--ink-faint)]"
          }`}
        >
          {n > 1 && <Lock size={10} />}
          {label}
        </div>
      ))}
    </div>
  );
}

// ── Typing indicator ──────────────────────────────────────────────────────────

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

export function StoryRefinementPanel({ storyId, orgId, story, onApply }: Props) {
  const { t } = useT();

  const [session, setSession] = useState<StoryRefinementSession | null | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");

  const bottomRef = useRef<HTMLDivElement>(null);

  // Load session on mount
  useEffect(() => {
    let cancelled = false;
    authFetch(`${API_BASE}/api/v1/stories/${storyId}/refinement?org_id=${orgId}`)
      .then((r) => (r.status === 404 ? null : r.json()))
      .then((data) => { if (!cancelled) setSession(data); })
      .catch(() => { if (!cancelled) setSession(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [storyId, orgId]);

  // Scroll to bottom when messages update
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [session?.messages, streamingContent]);

  const handleStart = async () => {
    const res = await authFetch(`${API_BASE}/api/v1/stories/${storyId}/refinement`, {
      method: "POST",
      body: JSON.stringify({ org_id: orgId }),
    });
    if (res.ok) {
      const data = await res.json();
      setSession(data);
    }
  };

  const handleReset = async () => {
    await authFetch(
      `${API_BASE}/api/v1/stories/${storyId}/refinement?org_id=${orgId}`,
      { method: "DELETE" }
    );
    setSession(null);
  };

  const handleApply = async (
    field: "title" | "description" | "acceptance_criteria",
    value: string
  ) => {
    onApply(field, value);
    await authFetch(`${API_BASE}/api/v1/stories/${storyId}/refinement/apply`, {
      method: "POST",
      body: JSON.stringify({ field, value, org_id: orgId }),
    });
    // Clear proposal optimistically
    setSession((prev) => prev ? { ...prev, last_proposal: null } : prev);
  };

  const handleDismiss = () => {
    setSession((prev) => prev ? { ...prev, last_proposal: null } : prev);
    // Persist dismissal to backend so reload doesn't bring the proposal back
    authFetch(`${API_BASE}/api/v1/stories/${storyId}/refinement/dismiss`, {
      method: "POST",
      body: JSON.stringify({ org_id: orgId }),
    }).catch(() => {});
  };

  const sendMessage = useCallback(async () => {
    if (!input.trim() || streaming || !session) return;
    const userMessage = input.trim();
    setInput("");
    setStreaming(true);
    setStreamingContent("");

    // Optimistic: add user message + clear old proposal (backend will set new one if AI produces one)
    const optimisticSession: StoryRefinementSession = {
      ...session,
      messages: [
        ...session.messages,
        { role: "user", content: userMessage, ts: new Date().toISOString() },
      ],
      last_proposal: null,
    };
    setSession(optimisticSession);

    try {
      const token = getAccessToken();
      const response = await fetch(
        `${API_BASE}/api/v1/stories/${storyId}/refinement/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ message: userMessage, org_id: orgId }),
        }
      );

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
            fullText += chunk;
            setStreamingContent(fullText);
          }
        }
      }
    } catch (err) {
      console.error("Refinement stream error:", err);
    } finally {
      setStreaming(false);
      setStreamingContent("");
      // Reload session to get persisted messages + proposal + score
      authFetch(`${API_BASE}/api/v1/stories/${storyId}/refinement?org_id=${orgId}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => { if (data) setSession(data); })
        .catch(() => {});
    }
  }, [input, streaming, session, storyId, orgId]);

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
          <p className="font-semibold text-[var(--ink-body)]">{t("refinement_empty_title")}</p>
          <p className="text-sm text-[var(--ink-mid)] mt-1">{t("refinement_empty_desc")}</p>
        </div>
        <button
          onClick={handleStart}
          className="px-4 py-1.5 rounded-lg bg-[var(--btn-primary)] text-white text-sm font-medium hover:opacity-90 transition-opacity"
        >
          {t("refinement_start_button")}
        </button>
      </div>
    );
  }

  // ── Active session ────────────────────────────────────────────────────────
  return (
    <div
      className="rounded-xl border border-[var(--paper-rule2)] flex flex-col"
      style={{ minHeight: "400px", maxHeight: "600px" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--paper-rule2)] shrink-0">
        <div className="flex items-center gap-2 flex-wrap">
          <Sparkles size={14} className="text-[var(--btn-primary)]" />
          <span className="text-sm font-semibold text-[var(--ink-body)]">
            {t("refinement_panel_title")}
          </span>
          <StageTabs stage={session.stage} />
        </div>
        <div className="flex items-center gap-2">
          <ScoreBadge score={session.quality_score} />
          <button
            onClick={handleReset}
            title={t("refinement_reset_button")}
            className="text-[var(--ink-faint)] hover:text-[var(--ink-mid)] transition-colors"
          >
            <RefreshCw size={13} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0">
        {session.messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-[var(--btn-primary)] text-white"
                  : "bg-[var(--paper-warm)] text-[var(--ink-body)]"
              }`}
            >
              {msg.role === "assistant" ? (
                <div className="prose prose-sm max-w-none dark:prose-invert">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {stripHiddenMarkers(msg.content)}
                  </ReactMarkdown>
                </div>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}

        {/* Proposal card after messages */}
        {session.last_proposal &&
          Object.values(session.last_proposal).some(Boolean) && (
            <ProposalCard
              proposal={session.last_proposal}
              onApply={handleApply}
              onDismiss={handleDismiss}
            />
          )}

        {/* Streaming assistant response */}
        {streaming && streamingContent && (
          <div className="flex justify-start">
            <div className="max-w-[85%] rounded-lg px-3 py-2 text-sm bg-[var(--paper-warm)] text-[var(--ink-body)]">
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {stripHiddenMarkers(streamingContent)}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        )}

        {/* Typing indicator (before first content arrives) */}
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
      <div className="border-t border-[var(--paper-rule2)] p-2 flex gap-2 shrink-0">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t("refinement_placeholder")}
          disabled={streaming}
          rows={2}
          className="flex-1 resize-none rounded-lg border border-[var(--paper-rule2)] px-3 py-2 text-sm text-[var(--ink-body)] placeholder:text-[var(--ink-faint)] bg-[var(--paper)] focus:outline-none focus:border-[var(--btn-primary)] disabled:opacity-50"
        />
        <button
          onClick={sendMessage}
          disabled={!input.trim() || streaming}
          className="self-end p-2 rounded-lg bg-[var(--btn-primary)] text-white disabled:opacity-40 hover:opacity-90 transition-opacity"
        >
          <Send size={14} />
        </button>
      </div>
    </div>
  );
}
