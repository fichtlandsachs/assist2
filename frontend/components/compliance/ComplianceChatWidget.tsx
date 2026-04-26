"use client";

import { useEffect, useRef, useState } from "react";
import {
  Send, Bot, User, AlertTriangle, CheckCircle2,
  ChevronRight, RefreshCw, X, Loader2, Info,
} from "lucide-react";
import { authFetch } from "@/lib/api/client";
import type { AssessmentSummary } from "@/lib/hooks/useCompliance";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ChatTurn {
  role: "user" | "assistant" | "system";
  content: string;
  created_at?: string;
  extracted_params?: Record<string, unknown>;
}

interface GapItem {
  control_id: string;
  control_slug: string;
  label: string;
  is_critical: boolean;
  gate_phases: string[];
}

interface SessionState {
  id: string;
  status: string;
  addressed_count: number;
  remaining_count: number;
  next_question: { text: string; type: string; control_ids: string[]; is_closing?: boolean } | null;
  conversation_summary: string | null;
}

interface TurnResult {
  reply: string;
  next_question: SessionState["next_question"];
  gap_summary: GapItem[];
  addressed_count: number;
  remaining_count: number;
  extracted_params: Record<string, unknown>;
  session_id: string;
}

interface Props {
  assessment: AssessmentSummary;
  orgId: string;
  onAssessmentUpdated?: () => void;
}

// ── Helper ────────────────────────────────────────────────────────────────────

function GapBadge({ gap }: { gap: GapItem }) {
  return (
    <div className={`flex items-start gap-2 p-2.5 rounded-lg border text-xs ${
      gap.is_critical
        ? "bg-red-50 border-red-200 text-red-800"
        : "bg-amber-50 border-amber-200 text-amber-800"
    }`}>
      {gap.is_critical
        ? <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
        : <Info className="h-3.5 w-3.5 shrink-0 mt-0.5" />
      }
      <span>{gap.label}</span>
    </div>
  );
}

function ProgressBar({ addressed, remaining }: { addressed: number; remaining: number }) {
  const total = addressed + remaining;
  const pct = total > 0 ? Math.round((addressed / total) * 100) : 0;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs text-[var(--ink-muted)]">
        <span>{addressed} bewertet</span>
        <span>{remaining} offen</span>
      </div>
      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-violet-500 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function AssistantBubble({ content }: { content: string }) {
  // Simple markdown renderer: bold, italic, bullet points
  const lines = content.split("\n");
  return (
    <div className="prose prose-sm max-w-none text-sm text-[var(--ink-mid)]">
      {lines.map((line, i) => {
        const bold = line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
        const withItalic = bold.replace(/\*(.+?)\*/g, "<em>$1</em>");
        if (line.startsWith("- ") || line.startsWith("• ")) {
          return (
            <div key={i} className="flex gap-2 mt-0.5">
              <span className="text-violet-500 shrink-0">•</span>
              <span dangerouslySetInnerHTML={{ __html: withItalic.replace(/^[-•]\s/, "") }} />
            </div>
          );
        }
        if (!line.trim()) return <div key={i} className="mt-2" />;
        return <p key={i} className="mt-1" dangerouslySetInnerHTML={{ __html: withItalic }} />;
      })}
    </div>
  );
}

// ── Main Widget ───────────────────────────────────────────────────────────────

export function ComplianceChatWidget({ assessment, orgId, onAssessmentUpdated }: Props) {
  const [session, setSession] = useState<SessionState | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [gaps, setGaps] = useState<GapItem[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [initializing, setInitializing] = useState(false);
  const [applyingMappings, setApplyingMappings] = useState(false);
  const [showGaps, setShowGaps] = useState(true);
  const [pendingMappingCount, setPendingMappingCount] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  const initSession = async () => {
    setInitializing(true);
    try {
      const res = await authFetch("/api/v1/compliance/chat/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assessment_id: assessment.id }),
      });
      if (!res.ok) throw new Error("Session error");
      const sessionData = await res.json();
      setSession(sessionData);

      // Load existing turns
      const turnsRes = await authFetch(`/api/v1/compliance/chat/sessions/${sessionData.id}/turns`);
      if (turnsRes.ok) {
        const turnsData = await turnsRes.json();
        setTurns(turnsData);
      }

      // If no turns yet, show the opening question
      if (!turns.length && sessionData.next_question) {
        setTurns([{
          role: "assistant",
          content: buildOpeningMessage(assessment, sessionData.next_question.text),
        }]);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setInitializing(false);
    }
  };

  function buildOpeningMessage(a: AssessmentSummary, firstQuestion: string): string {
    const unassessed = a.not_assessed_controls;
    const critical = a.hard_stop_critical;
    let intro = `Ich helfe dir, alle wichtigen Aspekte für **${a.object_name}** durchzudenken, bevor ihr in die Freigabe geht.`;
    if (critical > 0) {
      intro += ` Es gibt noch **${critical} kritische Punkte**, die für eine Freigabe zwingend geklärt sein müssen.`;
    } else if (unassessed > 0) {
      intro += ` Ich habe **${unassessed} Bereiche** identifiziert, zu denen wir noch keine Einschätzung haben.`;
    }
    intro += `\n\n${firstQuestion}`;
    return intro;
  }

  const handleSend = async () => {
    if (!input.trim() || !session || sending) return;
    const userMsg = input.trim();
    setInput("");

    // Optimistic UI
    setTurns(prev => [...prev, { role: "user", content: userMsg }]);
    setSending(true);

    try {
      const res = await authFetch(`/api/v1/compliance/chat/sessions/${session.id}/turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg }),
      });

      if (!res.ok) throw new Error("Turn error");
      const result: TurnResult = await res.json();

      setTurns(prev => [...prev, { role: "assistant", content: result.reply }]);
      setSession(prev => prev ? {
        ...prev,
        addressed_count: result.addressed_count,
        remaining_count: result.remaining_count,
        next_question: result.next_question,
      } : prev);
      setGaps(result.gap_summary);

      // Check if we have pending mappings
      const newMappingsEstimate = result.addressed_count - (session.addressed_count || 0);
      if (newMappingsEstimate > 0) {
        setPendingMappingCount(c => c + newMappingsEstimate);
      }
    } catch (e) {
      setTurns(prev => [...prev, {
        role: "assistant",
        content: "Entschuldigung, da ist etwas schiefgelaufen. Bitte versuche es nochmal.",
      }]);
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  };

  const handleApplyMappings = async () => {
    if (!session) return;
    setApplyingMappings(true);
    try {
      const res = await authFetch(`/api/v1/compliance/chat/sessions/${session.id}/apply-mappings`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Apply error");
      const result = await res.json();
      setPendingMappingCount(0);
      onAssessmentUpdated?.();
      setTurns(prev => [...prev, {
        role: "assistant",
        content: `Ich habe **${result.applied} Bewertungen** aus unserem Gespräch in die Compliance-Übersicht übertragen. Du kannst die Details im Compliance-Tab einsehen.`,
      }]);
    } catch (e) {
      alert("Übertragen fehlgeschlagen");
    } finally {
      setApplyingMappings(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ── Not started ─────────────────────────────────────────────────────────────

  if (!session) {
    return (
      <div className="flex flex-col items-center justify-center py-10 gap-4 text-center">
        <div className="w-14 h-14 rounded-2xl bg-violet-100 flex items-center justify-center">
          <Bot className="h-7 w-7 text-violet-600" />
        </div>
        <div>
          <p className="text-sm font-medium text-[var(--ink-strong)]">Compliance-Assistent</p>
          <p className="text-xs text-[var(--ink-muted)] mt-1 max-w-64">
            Ich stelle dir gezielte Rückfragen und helfe, alle relevanten Aspekte vor der Freigabe zu klären.
            Kein Fragebogen — ein Gespräch.
          </p>
        </div>
        <button
          onClick={initSession}
          disabled={initializing}
          className="flex items-center gap-2 px-5 py-2.5 bg-violet-600 text-white rounded-xl text-sm hover:bg-violet-700 disabled:opacity-60"
        >
          {initializing
            ? <><Loader2 className="h-4 w-4 animate-spin" /> Starte…</>
            : <><Bot className="h-4 w-4" /> Gespräch starten</>
          }
        </button>
      </div>
    );
  }

  const isComplete = session.remaining_count === 0 ||
    (session.next_question as { is_closing?: boolean } | null)?.is_closing;

  return (
    <div className="flex flex-col h-[560px]">
      {/* Progress + meta */}
      <div className="px-4 py-3 border-b border-[var(--border-subtle)] bg-[var(--bg-base)] space-y-2 shrink-0">
        <ProgressBar
          addressed={session.addressed_count}
          remaining={session.remaining_count}
        />
        {pendingMappingCount > 0 && (
          <div className="flex items-center justify-between">
            <p className="text-xs text-violet-700">
              {pendingMappingCount} Bewertungen aus dem Gespräch noch nicht übertragen
            </p>
            <button
              onClick={handleApplyMappings}
              disabled={applyingMappings}
              className="flex items-center gap-1 px-2.5 py-1 text-xs bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-60"
            >
              {applyingMappings ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCircle2 className="h-3 w-3" />}
              Übernehmen
            </button>
          </div>
        )}
      </div>

      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {turns.map((turn, i) => (
          <div key={i} className={`flex gap-3 ${turn.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
            {/* Avatar */}
            <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${
              turn.role === "assistant" ? "bg-violet-100" : "bg-slate-100"
            }`}>
              {turn.role === "assistant"
                ? <Bot className="h-4 w-4 text-violet-600" />
                : <User className="h-4 w-4 text-slate-500" />
              }
            </div>

            {/* Bubble */}
            <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 ${
              turn.role === "user"
                ? "bg-violet-600 text-white text-sm"
                : "bg-[var(--bg-base)] border border-[var(--border-subtle)]"
            }`}>
              {turn.role === "user"
                ? <p className="text-sm">{turn.content}</p>
                : <AssistantBubble content={turn.content} />
              }
            </div>
          </div>
        ))}

        {sending && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-full bg-violet-100 flex items-center justify-center shrink-0">
              <Bot className="h-4 w-4 text-violet-600" />
            </div>
            <div className="bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-2xl px-4 py-3">
              <div className="flex gap-1">
                {[0, 1, 2].map(d => (
                  <div key={d} className="w-2 h-2 rounded-full bg-violet-400 animate-bounce"
                    style={{ animationDelay: `${d * 0.15}s` }} />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Gap summary (collapsible) */}
      {gaps.length > 0 && (
        <div className="border-t border-[var(--border-subtle)] bg-[var(--bg-base)] shrink-0">
          <button
            onClick={() => setShowGaps(g => !g)}
            className="w-full flex items-center justify-between px-4 py-2 text-xs text-[var(--ink-muted)] hover:text-[var(--ink-mid)]"
          >
            <span>{gaps.length} offene Bereiche</span>
            <ChevronRight className={`h-3.5 w-3.5 transition-transform ${showGaps ? "rotate-90" : ""}`} />
          </button>
          {showGaps && (
            <div className="px-4 pb-3 space-y-1.5 max-h-36 overflow-y-auto">
              {gaps.map(g => <GapBadge key={g.control_id} gap={g} />)}
            </div>
          )}
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-[var(--border-subtle)] px-4 py-3 shrink-0">
        {isComplete ? (
          <div className="flex items-center gap-3 p-3 rounded-xl bg-green-50 border border-green-200">
            <CheckCircle2 className="h-5 w-5 text-green-600 shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-green-800">Alle wichtigen Punkte besprochen</p>
              <p className="text-xs text-green-700">Übertrage die Erkenntnisse in die Compliance-Ansicht.</p>
            </div>
            {pendingMappingCount > 0 && (
              <button onClick={handleApplyMappings} disabled={applyingMappings}
                className="px-3 py-1.5 text-xs bg-green-700 text-white rounded-lg hover:bg-green-800 disabled:opacity-60">
                {applyingMappings ? "…" : "Übernehmen"}
              </button>
            )}
          </div>
        ) : (
          <div className="flex gap-2 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={sending}
              rows={1}
              placeholder="Antworten…"
              className="flex-1 px-3 py-2 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-xl resize-none focus:outline-none focus:border-violet-400 disabled:opacity-50 max-h-32"
              style={{ minHeight: "40px" }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || sending}
              className="w-10 h-10 rounded-xl bg-violet-600 text-white flex items-center justify-center hover:bg-violet-700 disabled:opacity-40 transition-colors shrink-0"
            >
              {sending
                ? <Loader2 className="h-4 w-4 animate-spin" />
                : <Send className="h-4 w-4" />
              }
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
