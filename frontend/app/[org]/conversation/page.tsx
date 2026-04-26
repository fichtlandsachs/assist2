"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import { authFetch, API_BASE } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/context";

// ── Types ─────────────────────────────────────────────────────────────────────
interface ConversationFact {
  id: string;
  category: string;
  value: string;
  confidence: number;
  status: string;
  source_turn: number | null;
}

interface SizingState {
  score: number;
  size_label: string;
  stories_suggested: number;
  recommendation: string;
  breakdown: Record<string, number>;
}

interface ReadinessState {
  status: string;
  score: number;
  missing: string[];
  blockers: string[];
}

interface ProtocolSection {
  id: string;
  value: string;
  confidence: number;
  status: string;
}

interface Protocol {
  context: ProtocolSection[];
  user_groups: ProtocolSection[];
  problem: ProtocolSection[];
  benefit: ProtocolSection[];
  scope: ProtocolSection[];
  out_of_scope: ProtocolSection[];
  acceptance_criteria: ProtocolSection[];
  risks: ProtocolSection[];
  compliance: ProtocolSection[];
  dependencies: ProtocolSection[];
  evidence: ProtocolSection[];
  open_questions: ProtocolSection[];
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  ts: string;
}

interface Session {
  id: string;
  mode: string;
  status: string;
  protocol_json: Protocol;
  sizing_json: SizingState;
  readiness_json: ReadinessState;
  messages: ChatMessage[];
  facts: ConversationFact[];
  story_id: string | null;
}

// ── Constants ─────────────────────────────────────────────────────────────────
const PROTOCOL_LABELS: Record<string, string> = {
  context: "Kontext",
  user_groups: "Nutzergruppen",
  problem: "Problem",
  benefit: "Nutzen",
  scope: "Scope",
  out_of_scope: "Out of Scope",
  acceptance_criteria: "Akzeptanzkriterien",
  risks: "Risiken",
  compliance: "Compliance",
  dependencies: "Abh\u00e4ngigkeiten",
  evidence: "Nachweise",
  open_questions: "Offene Punkte",
};

const CATEGORY_LABELS: Record<string, string> = {
  context: "Kontext", user_group: "Nutzergruppe", problem: "Problem",
  benefit: "Nutzen", scope: "Scope", out_of_scope: "Out of Scope",
  acceptance_criterion: "Akzeptanzkriterium", risk: "Risiko",
  compliance: "Compliance", dependency: "Abh\u00e4ngigkeit",
  evidence: "Nachweis", open_question: "Offen",
};

const STATUS_COLOR: Record<string, string> = {
  detected: "#94a3b8", suggested: "#f59e0b", confirmed: "#22c55e", rejected: "#ef4444",
};

const READINESS_COLOR: Record<string, string> = {
  ready: "#22c55e", incomplete: "#f59e0b", too_large: "#ef4444", epic_candidate: "#8b5cf6",
};

const SIZE_LABELS: Record<string, { fill: number; color: string }> = {
  XS: { fill: 1, color: "#22c55e" },
  S:  { fill: 2, color: "#4ade80" },
  M:  { fill: 4, color: "#f59e0b" },
  L:  { fill: 5, color: "#f97316" },
  XL: { fill: 7, color: "#ef4444" },
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function SizingBar({ sizing }: { sizing: SizingState }) {
  const config = SIZE_LABELS[sizing.size_label] ?? { fill: 3, color: "#94a3b8" };
  const total = 7;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span style={{ color: "var(--ink-faint)" }}>Story-Gr\u00f6\u00dfe</span>
        <span className="font-bold" style={{ color: config.color }}>
          {sizing.size_label} · {sizing.stories_suggested} {sizing.stories_suggested === 1 ? "Story" : "Stories"}
        </span>
      </div>
      <div className="flex gap-0.5">
        {Array.from({ length: total }).map((_, i) => (
          <div key={i} className="h-2.5 flex-1 rounded-sm transition-all"
            style={{ background: i < config.fill ? config.color : "var(--paper-rule2)" }} />
        ))}
      </div>
      <p className="text-[10px]" style={{ color: "var(--ink-faint)" }}>
        {sizing.recommendation === "single_story" ? "Eine Story ausreichend" :
         sizing.recommendation === "epic_candidate" ? "Epic + mehrere Stories empfohlen" :
         "Zu gro\u00df \u2192 Strukturierung notwendig"}
      </p>
    </div>
  );
}

function ReadinessBar({ readiness }: { readiness: ReadinessState }) {
  const color = READINESS_COLOR[readiness.status] ?? "#94a3b8";
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span style={{ color: "var(--ink-faint)" }}>Readiness</span>
        <span className="font-bold" style={{ color }}>
          {readiness.score}% · {readiness.status}
        </span>
      </div>
      <div className="h-2 rounded-full overflow-hidden" style={{ background: "var(--paper-rule2)" }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${readiness.score}%`, background: color }} />
      </div>
      {readiness.blockers.length > 0 && (
        <p className="text-[10px]" style={{ color: "#f59e0b" }}>
          Fehlend: {readiness.blockers.slice(0, 3).join(", ")}
        </p>
      )}
    </div>
  );
}

function FactBadge({ fact, onConfirm, onReject }: {
  fact: ConversationFact;
  onConfirm: (id: string) => void;
  onReject: (id: string) => void;
}) {
  const [hover, setHover] = useState(false);
  return (
    <div className="flex items-start gap-1.5 py-1 group"
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
      <span className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
        style={{ background: STATUS_COLOR[fact.status] ?? "#94a3b8" }} />
      <div className="flex-1 min-w-0">
        <p className="text-xs leading-snug" style={{ color: "var(--ink)" }}>{fact.value}</p>
        <p className="text-[10px]" style={{ color: "var(--ink-faint)" }}>
          {Math.round(fact.confidence * 100)}% Konfidenz
        </p>
      </div>
      {hover && fact.status === "detected" && (
        <div className="flex gap-1 shrink-0">
          <button onClick={() => onConfirm(fact.id)}
            className="text-[10px] px-1.5 py-0.5 rounded-sm"
            style={{ background: "#22c55e22", color: "#22c55e" }}>✓</button>
          <button onClick={() => onReject(fact.id)}
            className="text-[10px] px-1.5 py-0.5 rounded-sm"
            style={{ background: "#ef444422", color: "#ef4444" }}>✗</button>
        </div>
      )}
    </div>
  );
}

function ProtocolPanel({ protocol, sizing, readiness, facts, sessionId, onFactUpdate }: {
  protocol: Protocol;
  sizing: SizingState;
  readiness: ReadinessState;
  facts: ConversationFact[];
  sessionId: string;
  onFactUpdate: (factId: string, status: string) => void;
}) {
  const factsByCategory = facts.reduce<Record<string, ConversationFact[]>>((acc, f) => {
    acc[f.category] = acc[f.category] ?? [];
    acc[f.category].push(f);
    return acc;
  }, {});

  async function patchFact(id: string, status: string) {
    await authFetch(`/api/v1/conversation/sessions/${sessionId}/facts/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    onFactUpdate(id, status);
  }

  const protocolKeys = Object.keys(PROTOCOL_LABELS) as (keyof Protocol)[];
  const filledSections = protocolKeys.filter(k => protocol[k]?.length > 0);

  return (
    <div className="h-full flex flex-col gap-4 overflow-y-auto pb-6">
      {/* Sizing + Readiness */}
      <div className="neo-card p-4 space-y-4">
        {sizing.size_label && <SizingBar sizing={sizing} />}
        {readiness.status && <ReadinessBar readiness={readiness} />}
        {!sizing.size_label && !readiness.status && (
          <p className="text-xs text-center py-2" style={{ color: "var(--ink-faint)" }}>
            Starte ein Gespr\u00e4ch \u2192 Protokoll erscheint hier automatisch
          </p>
        )}
      </div>

      {/* Facts by category */}
      {facts.length > 0 && (
        <div className="neo-card p-4">
          <h3 className="text-xs font-bold mb-3" style={{ color: "var(--ink-mid)" }}>
            Erkannte Facts ({facts.filter(f => f.status !== "rejected").length})
          </h3>
          <div className="space-y-3">
            {Object.entries(factsByCategory).map(([cat, catFacts]) => (
              catFacts.some(f => f.status !== "rejected") && (
                <div key={cat}>
                  <p className="text-[10px] font-bold mb-1 uppercase tracking-wide"
                    style={{ color: "var(--ink-faint)" }}>
                    {CATEGORY_LABELS[cat] ?? cat}
                  </p>
                  {catFacts.filter(f => f.status !== "rejected").map(f => (
                    <FactBadge key={f.id} fact={f}
                      onConfirm={() => void patchFact(f.id, "confirmed")}
                      onReject={() => void patchFact(f.id, "rejected")} />
                  ))}
                </div>
              )
            ))}
          </div>
        </div>
      )}

      {/* Living protocol */}
      {filledSections.length > 0 && (
        <div className="neo-card p-4">
          <h3 className="text-xs font-bold mb-3" style={{ color: "var(--ink-mid)" }}>
            Arbeitsprotokoll
          </h3>
          <div className="space-y-4">
            {filledSections.map(k => (
              <div key={k}>
                <p className="text-[10px] font-bold mb-1 uppercase tracking-wide"
                  style={{ color: "var(--ink-faint)" }}>
                  {PROTOCOL_LABELS[k]}
                </p>
                {(protocol[k] as ProtocolSection[]).map((item, i) => (
                  <p key={i} className="text-xs py-0.5 pl-2 border-l-2"
                    style={{ borderColor: "var(--paper-rule)", color: "var(--ink-mid)" }}>
                    {item.value}
                  </p>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function ConversationEnginePage({ params }: { params: Promise<{ org: string }> }) {
  const { org } = use(params);
  const { user } = useAuth();

  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [mode, setMode] = useState<"exploration_mode" | "story_mode">("story_mode");
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamBuffer, setStreamBuffer] = useState("");
  const [facts, setFacts] = useState<ConversationFact[]>([]);
  const [sizing, setSizing] = useState<SizingState>({ score: 0, size_label: "", stories_suggested: 1, recommendation: "single_story", breakdown: {} });
  const [readiness, setReadiness] = useState<ReadinessState>({ status: "", score: 0, missing: [], blockers: [] });
  const [protocol, setProtocol] = useState<Protocol>({
    context: [], user_groups: [], problem: [], benefit: [], scope: [],
    out_of_scope: [], acceptance_criteria: [], risks: [], compliance: [],
    dependencies: [], evidence: [], open_questions: [],
  });

  const messagesRef = useRef<ChatMessage[]>([]);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ── Start session ──────────────────────────────────────────────────────────
  async function startSession() {
    setStarting(true);
    try {
      // Get org UUID
      const orgRes = await authFetch(`/api/v1/organizations/?slug=${org}`);
      const orgData = await orgRes.json();
      const orgId = orgData?.items?.[0]?.id ?? orgData?.id;
      if (!orgId) throw new Error("Org not found");

      const res = await authFetch("/api/v1/conversation/sessions", {
        method: "POST",
        body: JSON.stringify({ organization_id: orgId, mode }),
      });
      if (!res.ok) throw new Error("Session creation failed");
      const data = await res.json() as Session;
      setSession(data);
      messagesRef.current = data.messages ?? [];
    } catch (e) {
      console.error(e);
    } finally {
      setStarting(false);
    }
  }

  // ── Send message ───────────────────────────────────────────────────────────
  async function sendMessage() {
    if (!session || !input.trim() || streaming) return;
    const text = input.trim();
    setInput("");

    // Add user message to local state immediately
    const userMsg: ChatMessage = { role: "user", content: text, ts: new Date().toISOString() };
    messagesRef.current = [...messagesRef.current, userMsg];

    setStreaming(true);
    setStreamBuffer("");

    const token = (await authFetch("/api/v1/auth/me")).headers.get("Authorization") ??
      typeof window !== "undefined" ? (localStorage.getItem("access_token") ?? "") : "";

    // Get auth headers by making a test request
    const testRes = await authFetch("/api/v1/auth/me");
    const authHeader = testRes.headers.get("Authorization") ?? `Bearer ${localStorage.getItem("access_token") ?? ""}`;

    const res = await fetch(`${API_BASE}/api/v1/conversation/sessions/${session.id}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: authHeader,
      },
      body: JSON.stringify({ message: text, stream: true }),
    });

    if (!res.ok || !res.body) {
      setStreaming(false);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let assistantContent = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split("\n");
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6);
        if (data === "[DONE]") continue;
        if (data.startsWith("[META]")) {
          try {
            const meta = JSON.parse(data.slice(6));
            if (meta.sizing) setSizing(meta.sizing);
            if (meta.readiness) setReadiness(meta.readiness);
            if (meta.protocol) setProtocol(meta.protocol);
            if (meta.new_facts) {
              setFacts(prev => {
                const existing = new Set(prev.map(f => f.id));
                const added = (meta.new_facts as ConversationFact[]).filter(f => !existing.has(f.id));
                return [...prev, ...added];
              });
            }
          } catch { /* ignore parse errors */ }
          continue;
        }
        assistantContent += data;
        setStreamBuffer(assistantContent);
      }
    }

    const assistantMsg: ChatMessage = {
      role: "assistant",
      content: assistantContent,
      ts: new Date().toISOString(),
    };
    messagesRef.current = [...messagesRef.current, assistantMsg];
    setStreamBuffer("");
    setStreaming(false);

    // Refresh facts from server
    const factsRes = await authFetch(`/api/v1/conversation/sessions/${session.id}/facts`);
    if (factsRes.ok) {
      const factsData = await factsRes.json() as ConversationFact[];
      setFacts(factsData);
    }

    setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }

  // ── Handle Cmd+Enter ───────────────────────────────────────────────────────
  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      void sendMessage();
    }
  }

  // ── Switch mode ────────────────────────────────────────────────────────────
  async function switchMode(newMode: string) {
    if (!session) return;
    await authFetch(`/api/v1/conversation/sessions/${session.id}/switch-mode`, {
      method: "POST",
      body: JSON.stringify({ mode: newMode }),
    });
    setSession(s => s ? { ...s, mode: newMode } : s);
  }

  // ── Fact update ────────────────────────────────────────────────────────────
  function handleFactUpdate(factId: string, status: string) {
    setFacts(prev => prev.map(f => f.id === factId ? { ...f, status } : f));
  }

  const allMessages = [
    ...messagesRef.current,
    ...(streaming && streamBuffer ? [{ role: "assistant" as const, content: streamBuffer, ts: "" }] : []),
  ];

  // ── No session: show start screen ─────────────────────────────────────────
  if (!session) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6 max-w-lg mx-auto">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--ink)" }}>
            Conversation Engine
          </h1>
          <p className="text-sm" style={{ color: "var(--ink-faint)" }}>
            Dialogbasierte Erstellung von User Stories, Epics und Artefakten
          </p>
        </div>

        <div className="neo-card w-full p-6 space-y-5">
          <div>
            <p className="text-xs font-medium mb-2" style={{ color: "var(--ink-mid)" }}>Wie m\u00f6chtest du starten?</p>
            <div className="grid grid-cols-2 gap-3">
              {[
                { mode: "story_mode", icon: "📋", label: "User Story erstellen", desc: "Gef\u00fchrter Dialog" },
                { mode: "exploration_mode", icon: "💡", label: "Explorativ durchdenken", desc: "Freier Dialog" },
              ].map(o => (
                <button key={o.mode} onClick={() => setMode(o.mode as typeof mode)}
                  className="text-left p-4 rounded-sm border-2 transition-all"
                  style={{
                    borderColor: mode === o.mode ? "var(--accent-red)" : "var(--paper-rule)",
                    background: mode === o.mode ? "rgba(var(--accent-red-rgb),.04)" : "var(--paper)",
                  }}>
                  <span className="text-xl block mb-1">{o.icon}</span>
                  <p className="text-sm font-semibold" style={{ color: "var(--ink)" }}>{o.label}</p>
                  <p className="text-xs mt-0.5" style={{ color: "var(--ink-faint)" }}>{o.desc}</p>
                </button>
              ))}
            </div>
          </div>

          <button onClick={() => void startSession()} disabled={starting}
            className="neo-btn neo-btn--default w-full flex items-center justify-center gap-2">
            {starting ? (
              <><div className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
              Starte Session…</>
            ) : "Session starten →"}
          </button>
        </div>
      </div>
    );
  }

  // ── Active session: split panel ────────────────────────────────────────────
  return (
    <div className="flex gap-0 h-[calc(100vh-120px)] max-w-7xl mx-auto">
      {/* LEFT: Chat */}
      <div className="flex flex-col flex-1 min-w-0 border-r-2" style={{ borderColor: "var(--paper-rule)" }}>
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b shrink-0"
          style={{ borderColor: "var(--paper-rule)" }}>
          <div className="flex-1">
            <h2 className="text-sm font-bold" style={{ color: "var(--ink)" }}>Karl · Conversation Engine</h2>
          </div>
          {/* Mode selector */}
          <div className="flex gap-1">
            {[
              { key: "exploration_mode", label: "Explorativ" },
              { key: "story_mode", label: "Story" },
            ].map(m => (
              <button key={m.key} onClick={() => void switchMode(m.key)}
                className="px-2.5 py-1 text-xs font-medium rounded-sm transition-all"
                style={{
                  background: session.mode === m.key ? "var(--accent-red)" : "var(--paper-warm)",
                  color: session.mode === m.key ? "#fff" : "var(--ink-faint)",
                }}>
                {m.label}
              </button>
            ))}
          </div>
          <button onClick={async () => {
            await authFetch(`/api/v1/conversation/sessions/${session.id}/close`, { method: "POST" });
            setSession(null);
          }} className="text-xs px-2 py-1 rounded-sm" style={{ color: "var(--ink-faint)" }}>
            ✕ Beenden
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {allMessages.length === 0 && (
            <div className="text-center py-8" style={{ color: "var(--ink-faint)" }}>
              <p className="text-3xl mb-2">👋</p>
              <p className="text-sm font-medium" style={{ color: "var(--ink)" }}>Hallo! Ich bin Karl.</p>
              <p className="text-xs mt-1">
                {session.mode === "story_mode"
                  ? "Lass uns eine User Story gemeinsam erarbeiten. Was m\u00f6chtest du umsetzen?"
                  : "Was besch\u00e4ftigt dich? Wir k\u00f6nnen gerne erstmal erkunden."}
              </p>
            </div>
          )}

          {allMessages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[75%] px-4 py-3 rounded-lg text-sm leading-relaxed`}
                style={{
                  background: msg.role === "user" ? "var(--accent-red)" : "var(--paper-warm)",
                  color: msg.role === "user" ? "#fff" : "var(--ink)",
                  borderRadius: msg.role === "user" ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
                }}>
                {msg.content}
                {streaming && i === allMessages.length - 1 && msg.role === "assistant" && (
                  <span className="inline-block w-0.5 h-4 ml-0.5 bg-current animate-pulse" />
                )}
              </div>
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>

        {/* Input */}
        <div className="shrink-0 px-4 py-3 border-t" style={{ borderColor: "var(--paper-rule)" }}>
          <div className="flex gap-3 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Nachricht eingeben… (Strg+Enter zum Senden)"
              rows={2}
              disabled={streaming}
              className="flex-1 neo-input resize-none text-sm"
              style={{ minHeight: 60, maxHeight: 120 }}
            />
            <button onClick={() => void sendMessage()} disabled={!input.trim() || streaming}
              className="neo-btn neo-btn--default px-4 py-3 shrink-0 disabled:opacity-40">
              {streaming ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : "→"}
            </button>
          </div>
          <p className="text-[10px] mt-1.5" style={{ color: "var(--ink-faint)" }}>
            Strg+Enter zum Senden · Facts werden automatisch extrahiert
          </p>
        </div>
      </div>

      {/* RIGHT: Protocol panel */}
      <div className="w-[340px] shrink-0 overflow-hidden flex flex-col">
        <div className="px-4 py-3 border-b shrink-0" style={{ borderColor: "var(--paper-rule)" }}>
          <h3 className="text-xs font-bold" style={{ color: "var(--ink-mid)" }}>Arbeitsprotokoll</h3>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-3">
          <ProtocolPanel
            protocol={protocol}
            sizing={sizing}
            readiness={readiness}
            facts={facts}
            sessionId={session.id}
            onFactUpdate={handleFactUpdate}
          />
        </div>
      </div>
    </div>
  );
}
