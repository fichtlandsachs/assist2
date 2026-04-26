"use client";

/**
 * ProcessRequestChatPanel
 *
 * Shown after a user requests a new process that doesn't exist yet.
 * The chat guides the user to describe:
 *   1. What the process is about (Epic description)
 *   2. What this specific story should cover (Story description)
 *   3. Acceptance criteria
 *
 * On completion, calls PATCH /process-requests/{id}/describe to persist
 * the descriptions and shows links to the created Epic and Story.
 */

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, GitBranch, FileText, CheckCircle2, Loader2, ExternalLink, X } from "lucide-react";
import { authFetch } from "@/lib/api/client";
import Link from "next/link";

interface ProcessRequestResult {
  id: string;
  proposed_name: string;
  capability_node_id: string | null;
  epic_id: string;
  story_id: string;
  status: string;
}

interface ChatMessage {
  role: "assistant" | "user";
  content: string;
}

interface Props {
  orgSlug: string;
  processRequest: ProcessRequestResult;
  onClose: () => void;
  onDone: () => void;
}

// ── Guided conversation stages ────────────────────────────────────────────────

type Stage = "epic_desc" | "story_desc" | "acceptance" | "done";

const STAGE_QUESTIONS: Record<Stage, string> = {
  epic_desc:
    "Super, ich habe das Epic und eine User Story für dich angelegt. " +
    "Lass uns jetzt die Beschreibungen ergänzen, damit das Team sofort loslegen kann.\n\n" +
    "**Frage 1 von 3: Was soll der neue Prozess leisten?**\n" +
    "Beschreibe kurz den Zweck und das Ziel – z. B. welches Problem er löst, wer ihn durchführt und wann er angewendet wird.",
  story_desc:
    "Danke! Jetzt zur User Story.\n\n" +
    "**Frage 2 von 3: Was soll in dieser Story konkret erarbeitet werden?**\n" +
    "Z. B. welche Schritte definiert, welche Dokumente erstellt oder welche Abstimmungen geführt werden sollen.",
  acceptance:
    "Fast fertig!\n\n" +
    "**Frage 3 von 3: Wie wissen wir, dass die Story fertig ist?**\n" +
    "Nenne 1\u20133 Akzeptanzkriterien \u2013 konkrete, pr\u00fcfbare Bedingungen. (Optional, du kannst auch einfach 'fertig' sagen.)",
  done: "",
};

export function ProcessRequestChatPanel({ orgSlug, processRequest, onClose, onDone }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", content: STAGE_QUESTIONS.epic_desc },
  ]);
  const [input, setInput] = useState("");
  const [stage, setStage] = useState<Stage>("epic_desc");
  const [epicDesc, setEpicDesc] = useState("");
  const [storyDesc, setStoryDesc] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const addAssistant = (content: string) => {
    setMessages(prev => [...prev, { role: "assistant", content }]);
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || saving) return;

    setInput("");
    setMessages(prev => [...prev, { role: "user", content: text }]);

    if (stage === "epic_desc") {
      setEpicDesc(text);
      setStage("story_desc");
      setTimeout(() => addAssistant(STAGE_QUESTIONS.story_desc), 300);
    } else if (stage === "story_desc") {
      setStoryDesc(text);
      setStage("acceptance");
      setTimeout(() => addAssistant(STAGE_QUESTIONS.acceptance), 300);
    } else if (stage === "acceptance") {
      // text = acceptance criteria (or "fertig")
      const criteria = text.toLowerCase() === "fertig" ? "" : text;

      setSaving(true);
      try {
        const res = await authFetch(
          `/api/v1/process-requests/${processRequest.id}/describe?org_id=${processRequest.capability_node_id ?? ""}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              epic_description: epicDesc,
              story_description: storyDesc,
              story_acceptance_criteria: criteria || null,
            }),
          }
        );
        if (!res.ok) throw new Error("Fehler beim Speichern");

        setStage("done");
        addAssistant(
          `Perfekt! Ich habe alles gespeichert. 🎉\n\n` +
          `Das **Epic** und die **User Story** sind jetzt mit deinen Beschreibungen hinterlegt. ` +
          `Du kannst sie jetzt im Team weiter ausarbeiten, Akzeptanzkriterien ergänzen und die Story in einen Sprint einplanen.`
        );
        setSaved(true);
        setTimeout(() => onDone(), 2000);
      } catch {
        addAssistant("Es gab einen Fehler beim Speichern. Bitte versuche es nochmal.");
      } finally {
        setSaving(false);
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full bg-[var(--bg-card)] rounded-lg border border-[var(--border-subtle)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-subtle)] bg-violet-50">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-violet-600" />
          <div>
            <p className="text-sm font-semibold text-violet-800">Neuer Prozess: {processRequest.proposed_name}</p>
            <p className="text-xs text-violet-500">Epic & Story wurden angelegt – Beschreibung ergänzen</p>
          </div>
        </div>
        <button onClick={onClose} className="text-[var(--ink-muted)] hover:text-[var(--ink-mid)]">
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Created artifacts badges */}
      <div className="flex gap-2 px-4 py-2 border-b border-[var(--border-subtle)] bg-violet-50/50 flex-wrap">
        <Link
          href={`/${orgSlug}/stories/epics/${processRequest.epic_id}`}
          target="_blank"
          className="flex items-center gap-1.5 px-2.5 py-1 text-xs bg-violet-100 text-violet-700 rounded-full hover:bg-violet-200 transition-colors"
        >
          <GitBranch className="h-3 w-3" />
          Epic anzeigen
          <ExternalLink className="h-3 w-3 opacity-60" />
        </Link>
        <Link
          href={`/${orgSlug}/stories/${processRequest.story_id}`}
          target="_blank"
          className="flex items-center gap-1.5 px-2.5 py-1 text-xs bg-blue-100 text-blue-700 rounded-full hover:bg-blue-200 transition-colors"
        >
          <FileText className="h-3 w-3" />
          Story anzeigen
          <ExternalLink className="h-3 w-3 opacity-60" />
        </Link>
      </div>

      {/* Progress steps */}
      <div className="flex gap-0 px-4 py-2 border-b border-[var(--border-subtle)]">
        {(["epic_desc", "story_desc", "acceptance", "done"] as Stage[]).map((s, i) => {
          const labels = ["Epic", "Story", "Kriterien", "Fertig"];
          const stageIdx = ["epic_desc", "story_desc", "acceptance", "done"].indexOf(stage);
          const isCompleted = i < stageIdx;
          const isCurrent = i === stageIdx;
          return (
            <div key={s} className="flex items-center flex-1 min-w-0">
              <div className={`flex items-center gap-1 text-xs flex-1 min-w-0 ${
                isCurrent ? "text-violet-700 font-medium" :
                isCompleted ? "text-green-600" : "text-[var(--ink-muted)]"
              }`}>
                {isCompleted
                  ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                  : <span className={`w-4 h-4 rounded-full text-[10px] flex items-center justify-center shrink-0 font-bold ${
                      isCurrent ? "bg-violet-600 text-white" : "bg-[var(--border-subtle)] text-[var(--ink-muted)]"
                    }`}>{i + 1}</span>
                }
                <span className="truncate">{labels[i]}</span>
              </div>
              {i < 3 && <div className="w-3 h-px bg-[var(--border-subtle)] shrink-0 mx-1" />}
            </div>
          );
        })}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-2.5 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
            <div className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${
              msg.role === "assistant" ? "bg-violet-100" : "bg-[var(--border-subtle)]"
            }`}>
              {msg.role === "assistant"
                ? <Bot className="h-4 w-4 text-violet-600" />
                : <User className="h-4 w-4 text-[var(--ink-mid)]" />}
            </div>
            <div className={`max-w-[85%] px-3 py-2 rounded-lg text-sm leading-relaxed ${
              msg.role === "assistant"
                ? "bg-[var(--bg-base)] border border-[var(--border-subtle)] text-[var(--ink-strong)]"
                : "bg-violet-600 text-white"
            }`}>
              {msg.content.split("\n").map((line, j) => {
                // Simple bold markdown
                const parts = line.split(/\*\*(.*?)\*\*/g);
                return (
                  <p key={j} className={j > 0 ? "mt-1" : ""}>
                    {parts.map((part, k) =>
                      k % 2 === 1 ? <strong key={k}>{part}</strong> : part
                    )}
                  </p>
                );
              })}
            </div>
          </div>
        ))}
        {saving && (
          <div className="flex gap-2.5">
            <div className="w-7 h-7 rounded-full bg-violet-100 flex items-center justify-center shrink-0">
              <Bot className="h-4 w-4 text-violet-600" />
            </div>
            <div className="px-3 py-2 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)]">
              <Loader2 className="h-4 w-4 animate-spin text-violet-500" />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      {stage !== "done" && (
        <div className="p-3 border-t border-[var(--border-subtle)]">
          <div className="flex gap-2">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={saving}
              rows={2}
              placeholder="Deine Antwort…"
              className="flex-1 px-3 py-2 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg resize-none focus:outline-none focus:border-violet-400 disabled:opacity-60"
            />
            <button
              onClick={() => void handleSend()}
              disabled={!input.trim() || saving}
              className="px-3 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-40 shrink-0 self-end"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
          <p className="text-[10px] text-[var(--ink-muted)] mt-1.5">Enter zum Senden · Shift+Enter für neue Zeile</p>
        </div>
      )}

      {stage === "done" && saved && (
        <div className="p-4 border-t border-[var(--border-subtle)] flex items-center justify-center gap-2 text-sm text-green-700 bg-green-50">
          <CheckCircle2 className="h-4 w-4" />
          Beschreibungen gespeichert
        </div>
      )}
    </div>
  );
}
