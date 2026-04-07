"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import { useOrg } from "@/lib/hooks/useOrg";
import { API_BASE, getAccessToken } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Mic, MicOff, Send, Sparkles, FileText, CheckSquare, TestTube, Tag, GripVertical, ImagePlus, X, Plus } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ProjectSelector } from "@/components/stories/ProjectSelector";


// ── Types ──────────────────────────────────────────────────────────────────

interface Message {
  role: "user" | "assistant";
  content: string;
  images?: { mediaType: string; data: string }[];
}

interface StoryData {
  title: string;
  story: string[];
  accept: string[];
  tests: string[];
  release: string[];
  features: { title: string; description: string | null }[];
}

type ChatMode = "chat" | "docs" | "tasks" | "jira";
type WorkspaceTab = "story";

interface JiraStoryPanel {
  ticket_key: string;
  project: string;
  source_summary: string;
  generated_at: string;
  content: string;
}

interface SavedJiraStory {
  id: string;
  ticket_key: string;
  status: string;
}

function parseJiraPanel(text: string): JiraStoryPanel | null {
  const match = text.match(/<<<USERSTORY_PANEL\n([\s\S]*?)\nUSERSTORY_PANEL>>>/);
  if (!match) return null;
  const block = match[1];
  const getField = (key: string) => {
    const m = block.match(new RegExp(`^${key}:\\s*(.+)$`, "m"));
    return m ? m[1].trim() : "";
  };
  const contentStart = block.indexOf("\n\n");
  const content = contentStart >= 0 ? block.slice(contentStart + 2).trim() : block;
  return {
    ticket_key: getField("ticket_key"),
    project: getField("project"),
    source_summary: getField("source_summary"),
    generated_at: getField("generated_at"),
    content,
  };
}

function stripJiraPanel(text: string): string {
  return text.replace(/<<<USERSTORY_PANEL[\s\S]*?USERSTORY_PANEL>>>/g, "").trim();
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function AiWorkspacePage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { org } = useOrg(resolvedParams.org);
  const [tab] = useState<WorkspaceTab>("story");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<ChatMode>("chat");
  const [streaming, setStreaming] = useState(false);
  const [storyData, setStoryData] = useState<StoryData | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [creating, setCreating] = useState(false);
  const [saveProjectId, setSaveProjectId] = useState<string | null>(null);
  const [jiraPanel, setJiraPanel] = useState<JiraStoryPanel | null>(null);
  const [savedStory, setSavedStory] = useState<SavedJiraStory | null>(null);
  const [savingJira, setSavingJira] = useState(false);
  const [writingJira, setWritingJira] = useState(false);
  const [recording, setRecording] = useState(false);
  const [storyPct, setStoryPct] = useState(50);
  const [pendingImages, setPendingImages] = useState<{ mediaType: string; data: string }[]>([]);
  const [isMobile, setIsMobile] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const splitContainerRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const onDragStart = useCallback(() => {
    dragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  const onDragMove = useCallback((e: MouseEvent) => {
    if (!dragging.current || !splitContainerRef.current) return;
    const rect = splitContainerRef.current.getBoundingClientRect();
    const pct = Math.min(80, Math.max(20, ((e.clientX - rect.left) / rect.width) * 100));
    setStoryPct(100 - pct);
  }, []);

  const onDragEnd = useCallback(() => {
    dragging.current = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  }, []);

  useEffect(() => {
    window.addEventListener("mousemove", onDragMove);
    window.addEventListener("mouseup", onDragEnd);
    return () => {
      window.removeEventListener("mousemove", onDragMove);
      window.removeEventListener("mouseup", onDragEnd);
    };
  }, [onDragMove, onDragEnd]);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Send chat message ────────────────────────────────────────────────────

  const addImages = useCallback((files: FileList | File[]) => {
    Array.from(files).forEach(file => {
      if (!file.type.startsWith("image/")) return;
      const reader = new FileReader();
      reader.onload = e => {
        const dataUrl = e.target?.result as string;
        const data = dataUrl.split(",")[1];
        setPendingImages(prev => [...prev, { mediaType: file.type, data }]);
      };
      reader.readAsDataURL(file);
    });
  }, []);

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const imageFiles = Array.from(e.clipboardData.items)
      .filter(i => i.type.startsWith("image/"))
      .map(i => i.getAsFile())
      .filter(Boolean) as File[];
    if (imageFiles.length > 0) addImages(imageFiles);
  }, [addImages]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if ((!text && pendingImages.length === 0) || streaming) return;

    const userMsg: Message = { role: "user", content: text, images: pendingImages.length > 0 ? [...pendingImages] : undefined };
    const newMessages: Message[] = [...messages, userMsg];
    setMessages(newMessages);
    setInput("");
    setPendingImages([]);
    setStreaming(true);

    const assistantIdx = newMessages.length;
    setMessages(prev => [...prev, { role: "assistant", content: "" }]);

    try {
      const token = getAccessToken();
      const response = await fetch(`${API_BASE}/api/v1/ai/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          messages: newMessages.map(m => {
            if (!m.images?.length) return { role: m.role, content: m.content };
            const blocks: object[] = m.images.map(img => ({
              type: "image",
              source: { type: "base64", media_type: img.mediaType, data: img.data },
            }));
            if (m.content) blocks.push({ type: "text", text: m.content });
            return { role: m.role, content: blocks };
          }),
          mode,
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const chunk = line.slice(6);
          if (chunk === "[DONE]" || chunk === "[ERROR]") continue;
          setMessages(prev =>
            prev.map((m, i) =>
              i === assistantIdx ? { ...m, content: m.content + chunk } : m
            )
          );
        }
      }
    } catch (err) {
      console.error("Chat stream error:", err);
      setMessages(prev =>
        prev.map((m, i) =>
          i === assistantIdx
            ? { ...m, content: "Fehler beim Laden der Antwort." }
            : m
        )
      );
    } finally {
      setStreaming(false);
    }
  }, [input, messages, mode, streaming]);

  // ── Extract story from transcript ────────────────────────────────────────

  const extractStory = useCallback(async () => {
    if (messages.length < 2) return;

    setExtracting(true);
    try {
      const token = getAccessToken();
      const headers = {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      };

      // Schritt 1: Kontext kompaktieren
      const compactRes = await fetch(`${API_BASE}/api/v1/ai/compact-chat`, {
        method: "POST",
        headers,
        body: JSON.stringify({ messages: messages.map(m => ({ role: m.role, content: m.content })) }),
      });
      if (!compactRes.ok) throw new Error(`Compact HTTP ${compactRes.status}`);
      const { summary } = await compactRes.json();

      const transcript = summary?.trim()
        ? summary
        : messages.map(m => `${m.role === "user" ? "Nutzer" : "KI"}: ${m.content}`).join("\n");

      if (transcript.length < 80) return;

      // Schritt 2: Story aus kompaktiertem Kontext extrahieren
      const extractRes = await fetch(`${API_BASE}/api/v1/ai/extract-story`, {
        method: "POST",
        headers,
        body: JSON.stringify({ transcript }),
      });
      if (!extractRes.ok) throw new Error(`Extract HTTP ${extractRes.status}`);
      const data = await extractRes.json();
      setStoryData(data);
    } catch (err) {
      console.error("Extract story error:", err);
    } finally {
      setExtracting(false);
    }
  }, [messages]);

  // ── Parse <<<USERSTORY_PANEL markers in jira mode ───────────────────────

  useEffect(() => {
    if (mode !== "jira") return;
    const last = messages[messages.length - 1];
    if (!last || last.role !== "assistant") return;
    const panel = parseJiraPanel(last.content);
    if (panel) {
      setJiraPanel(panel);
      setSavedStory(null);
    }
  }, [messages, mode]);

  // ── Create story in DB ───────────────────────────────────────────────────

  const createStory = useCallback(async () => {
    if (!storyData || !org) return;
    setCreating(true);
    try {
      const token = getAccessToken();
      const resp = await fetch(`${API_BASE}/api/v1/user-stories?org_id=${org.id}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          title: storyData.title || storyData.story[0]?.slice(0, 80) || "Neue User Story",
          description: storyData.story.join("\n"),
          acceptance_criteria: storyData.accept.join("\n"),
          priority: "medium",
          project_id: saveProjectId || null,
        }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const created = await resp.json();
      window.location.href = `/${org.slug}/stories/${created.id}`;
    } catch (err) {
      console.error("Create story error:", err);
    } finally {
      setCreating(false);
    }
  }, [storyData, org]);

  // ── Jira story: save to workspace + write back ──────────────────────────

  const saveJiraStory = useCallback(async () => {
    if (!jiraPanel || !org) return;
    setSavingJira(true);
    try {
      const token = getAccessToken();
      const resp = await fetch(`${API_BASE}/api/v1/jira/stories`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          ticket_key: jiraPanel.ticket_key,
          project: jiraPanel.project,
          source_summary: jiraPanel.source_summary,
          content: jiraPanel.content,
          status: "draft",
          org_id: org.id,
        }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const created = await resp.json();
      setSavedStory({ id: created.id, ticket_key: created.ticket_key, status: created.status });
    } catch (err) {
      console.error("Save Jira story error:", err);
    } finally {
      setSavingJira(false);
    }
  }, [jiraPanel, org]);

  const writeToJira = useCallback(async () => {
    if (!jiraPanel || !savedStory) return;
    setWritingJira(true);
    try {
      const token = getAccessToken();
      const resp = await fetch(`${API_BASE}/api/v1/jira/write`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          ticket_key: jiraPanel.ticket_key,
          ticket_id: "",
          summary: "",
          description: jiraPanel.content,
        }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      if (savedStory.id) {
        const patchResp = await fetch(`${API_BASE}/api/v1/jira/stories/${savedStory.id}`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ status: "published" }),
        });
        if (patchResp.ok) {
          setSavedStory(prev => prev ? { ...prev, status: "published" } : prev);
        }
      }
    } catch (err) {
      console.error("Write to Jira error:", err);
    } finally {
      setWritingJira(false);
    }
  }, [jiraPanel, savedStory]);

  // ── Voice recording ──────────────────────────────────────────────────────

  const toggleRecording = useCallback(async () => {
    if (recording) {
      mediaRecorderRef.current?.stop();
      setRecording(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = e => chunksRef.current.push(e.data);
      mr.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const fd = new FormData();
        fd.append("file", blob, "recording.webm");
        try {
          const token = getAccessToken();
          const res = await fetch(`${API_BASE}/api/v1/ai/transcribe`, {
            method: "POST",
            headers: token ? { Authorization: `Bearer ${token}` } : {},
            body: fd,
          });
          if (res.ok) {
            const { text } = await res.json();
            setInput(prev => (prev ? prev + " " + text : text));
          }
        } catch (e) {
          console.error("Transcription error:", e);
        }
      };
      mr.start();
      mediaRecorderRef.current = mr;
      setRecording(true);
    } catch {
      console.error("Microphone access denied");
    }
  }, [recording]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden" style={{ background: "var(--paper)" }}>

      {/* ── Story-Assistent ── */}
      {tab === "story" && (
        <div ref={splitContainerRef} className={`flex-1 flex overflow-hidden min-w-0 ${isMobile ? "flex-col" : "flex-row"}`}>

          {/* Left: Chat panel */}
          <div
            className="flex flex-col min-w-0 overflow-hidden"
            style={{
              width: isMobile ? "100%" : `${100 - storyPct}%`,
              flex: isMobile ? "1 1 0" : "none",
              borderRight: !isMobile ? "1px solid var(--paper-rule)" : undefined,
              borderBottom: isMobile ? "1px solid var(--paper-rule)" : undefined,
            }}
          >

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full gap-3 opacity-40">
                  <Sparkles size={24} style={{ color: "var(--ink-faint)" }} />
                  <p style={{ fontFamily: "var(--font-body)", fontSize: "14px", color: "var(--ink-mid)" }}>
                    Starte ein Gespräch…
                  </p>
                </div>
              )}
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className="max-w-[90%] rounded-sm px-3 py-2 space-y-2"
                    style={{
                      background: m.role === "user" ? "var(--ink)" : "var(--paper-warm)",
                      color: m.role === "user" ? "var(--paper)" : "var(--ink)",
                      border: `0.5px solid ${m.role === "user" ? "var(--ink)" : "var(--paper-rule)"}`,
                      fontFamily: "var(--font-body)",
                      fontSize: "14px",
                      lineHeight: "1.6",
                      whiteSpace: m.role === "user" ? "pre-wrap" : "normal",
                    }}
                  >
                    {m.images?.map((img, j) => (
                      <img
                        key={j}
                        src={`data:${img.mediaType};base64,${img.data}`}
                        alt="Mockup"
                        className="rounded-sm max-w-full"
                        style={{ maxHeight: 200, border: "0.5px solid rgba(255,255,255,.2)" }}
                      />
                    ))}
                    {m.role === "assistant" ? (
                      <div style={{ fontSize: "14px", lineHeight: "1.6", fontFamily: "var(--font-body)" }}>
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            p: ({ children }) => <p style={{ margin: "0 0 0.5em" }}>{children}</p>,
                            strong: ({ children }) => <strong style={{ fontWeight: 600 }}>{children}</strong>,
                            ul: ({ children }) => <ul style={{ paddingLeft: "1.2em", margin: "0.3em 0" }}>{children}</ul>,
                            ol: ({ children }) => <ol style={{ paddingLeft: "1.2em", margin: "0.3em 0" }}>{children}</ol>,
                            li: ({ children }) => <li style={{ margin: "0.1em 0" }}>{children}</li>,
                            code: ({ children, className }) => className
                              ? <code style={{ display: "block", background: "rgba(0,0,0,.06)", borderRadius: 2, padding: "0.4em 0.6em", fontSize: "12px", fontFamily: "var(--font-mono)", whiteSpace: "pre-wrap" }}>{children}</code>
                              : <code style={{ background: "rgba(0,0,0,.06)", borderRadius: 2, padding: "0 0.3em", fontSize: "12px", fontFamily: "var(--font-mono)" }}>{children}</code>,
                            h1: ({ children }) => <p style={{ fontWeight: 600, margin: "0.4em 0 0.2em" }}>{children}</p>,
                            h2: ({ children }) => <p style={{ fontWeight: 600, margin: "0.4em 0 0.2em" }}>{children}</p>,
                            h3: ({ children }) => <p style={{ fontWeight: 600, margin: "0.3em 0 0.1em" }}>{children}</p>,
                          }}
                        >{mode === "jira" ? stripJiraPanel(m.content) : m.content}</ReactMarkdown>
                        {streaming && i === messages.length - 1 && (
                          <span className="inline-block w-1.5 h-3.5 ml-0.5 align-text-bottom animate-pulse"
                            style={{ background: "var(--ink-faint)" }} />
                        )}
                      </div>
                    ) : (
                      <>
                        {m.content}
                        {streaming && i === messages.length - 1 && (
                          <span className="inline-block w-1.5 h-3.5 ml-0.5 align-text-bottom animate-pulse"
                            style={{ background: "var(--ink-faint)" }} />
                        )}
                      </>
                    )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
            <div
              className="border-t px-4 py-3"
              style={{ borderColor: "var(--paper-rule)", background: "var(--paper-warm)" }}
            >
              {/* Pending image previews */}
              {pendingImages.length > 0 && (
                <div className="flex gap-2 mb-2 flex-wrap">
                  {pendingImages.map((img, i) => (
                    <div key={i} className="relative">
                      <img
                        src={`data:${img.mediaType};base64,${img.data}`}
                        alt="Mockup"
                        className="rounded-sm object-cover"
                        style={{ width: 56, height: 56, border: "0.5px solid var(--paper-rule)" }}
                      />
                      <button
                        onClick={() => setPendingImages(prev => prev.filter((_, j) => j !== i))}
                        className="absolute -top-1.5 -right-1.5 rounded-full flex items-center justify-center"
                        style={{ width: 16, height: 16, background: "var(--ink)", color: "var(--paper)" }}
                      >
                        <X size={9} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div className={isMobile ? "flex flex-col gap-2" : "flex items-end gap-2"}>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={e => e.target.files && addImages(e.target.files)}
                />
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  onPaste={handlePaste}
                  rows={2}
                  placeholder="Nachricht oder Bild einfügen… (Strg+V für Screenshot)"
                  className="flex-1 resize-none rounded-sm px-3 py-2 outline-none w-full"
                  style={{
                    fontFamily: "var(--font-body)",
                    fontSize: "14px",
                    background: "var(--paper)",
                    border: "0.5px solid var(--paper-rule)",
                    color: "var(--ink)",
                  }}
                />
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="p-2 rounded-sm transition-colors"
                    style={{
                      background: "transparent",
                      border: "0.5px solid var(--paper-rule)",
                      color: "var(--ink-faint)",
                    }}
                    title="Bild hochladen"
                  >
                    <ImagePlus size={14} />
                  </button>
                  <button
                    onClick={toggleRecording}
                    className="p-2 rounded-sm transition-colors"
                    style={{
                      background: recording ? "rgba(192,57,43,.1)" : "transparent",
                      border: `0.5px solid ${recording ? "var(--accent-red)" : "var(--paper-rule)"}`,
                      color: recording ? "var(--accent-red)" : "var(--ink-faint)",
                    }}
                    title={recording ? "Aufnahme stoppen" : "Sprachaufnahme starten"}
                  >
                    {recording ? <MicOff size={14} /> : <Mic size={14} />}
                  </button>
                  <Button
                    onClick={sendMessage}
                    disabled={(!input.trim() && pendingImages.length === 0) || streaming}
                    size="sm"
                    className={isMobile ? "flex-1" : ""}
                  >
                    <Send size={12} />
                    Senden
                  </Button>
                </div>
              </div>
            </div>
          </div>

          {/* Drag handle — desktop only */}
          {!isMobile && (
            <div
              className="relative flex items-center justify-center shrink-0 cursor-col-resize group"
              style={{ width: "1px", background: "var(--paper-rule)" }}
              onMouseDown={onDragStart}
            >
              <div
                className="absolute opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded-sm"
                style={{ width: "14px", height: "32px", background: "var(--paper-warm)", border: "0.5px solid var(--paper-rule)", zIndex: 10 }}
              >
                <GripVertical size={10} style={{ color: "var(--ink-faint)" }} />
              </div>
            </div>
          )}

          {/* Right: Story / Extraction panel */}
          <div
            className="flex flex-col overflow-hidden"
            style={{
              width: isMobile ? "100%" : `${storyPct}%`,
              flex: isMobile ? "1 1 0" : "none",
              background: "var(--paper-warm)",
            }}
          >
            {mode === "jira" ? (
              <>
                <div
                  className="flex items-center justify-between px-4 py-2 border-b"
                  style={{ borderColor: "var(--paper-rule)" }}
                >
                  <span style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "13px", color: "var(--ink)" }}>
                    Jira Story
                  </span>
                  {jiraPanel && (
                    <Badge variant="outline" style={{ fontFamily: "var(--font-mono)", fontSize: "10px" }}>
                      {jiraPanel.ticket_key}
                    </Badge>
                  )}
                </div>

                <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
                  {!jiraPanel ? (
                    <p
                      className="text-center opacity-40 mt-8"
                      style={{ fontFamily: "var(--font-body)", fontSize: "13px", color: "var(--ink-mid)" }}
                    >
                      Wähle ein Jira-Ticket und generiere eine User Story.
                    </p>
                  ) : (
                    <>
                      <p style={{ fontFamily: "var(--font-body)", fontSize: "12px", color: "var(--ink-faint)" }}>
                        {jiraPanel.source_summary}
                      </p>
                      <div style={{ fontSize: "13px", lineHeight: "1.6", fontFamily: "var(--font-body)", color: "var(--ink)" }}>
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            p: ({ children }) => <p style={{ margin: "0 0 0.5em" }}>{children}</p>,
                            strong: ({ children }) => <strong style={{ fontWeight: 600 }}>{children}</strong>,
                            ul: ({ children }) => <ul style={{ paddingLeft: "1.2em", margin: "0.3em 0" }}>{children}</ul>,
                            li: ({ children }) => <li style={{ margin: "0.1em 0" }}>{children}</li>,
                            h2: ({ children }) => <p style={{ fontWeight: 600, margin: "0.4em 0 0.2em" }}>{children}</p>,
                            h3: ({ children }) => <p style={{ fontWeight: 600, margin: "0.3em 0 0.1em" }}>{children}</p>,
                          }}
                        >{jiraPanel.content}</ReactMarkdown>
                      </div>
                      <div className="pt-2 flex flex-col gap-2">
                        {!savedStory ? (
                          <Button size="sm" onClick={saveJiraStory} disabled={savingJira} className="w-full">
                            <Plus size={10} />
                            {savingJira ? "Wird gespeichert…" : "In Workspace speichern"}
                          </Button>
                        ) : (
                          <>
                            <p style={{ fontFamily: "var(--font-mono)", fontSize: "10px", color: "var(--ink-faint)", textAlign: "center" }}>
                              {savedStory.status === "published" ? "✓ In Jira veröffentlicht" : `Gespeichert als ${savedStory.ticket_key}`}
                            </p>
                            {savedStory.status !== "published" && (
                              <Button size="sm" onClick={writeToJira} disabled={writingJira} className="w-full">
                                {writingJira ? "Wird übertragen…" : "In Jira schreiben"}
                              </Button>
                            )}
                          </>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </>
            ) : (
              <>
                <div
                  className="flex items-center justify-between px-4 py-2 border-b"
                  style={{ borderColor: "var(--paper-rule)" }}
                >
                  <span style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "13px", color: "var(--ink)" }}>
                    User Story
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={extractStory}
                    disabled={extracting || messages.length < 2}
                  >
                    <Sparkles size={10} />
                    {extracting ? "Extrahiere…" : "Extrahieren"}
                  </Button>
                </div>

                <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
                  {!storyData && (
                    <p
                      className="text-center opacity-40 mt-8"
                      style={{ fontFamily: "var(--font-body)", fontSize: "13px", color: "var(--ink-mid)" }}
                    >
                      Führe ein Gespräch und klicke auf „Extrahieren", um eine User Story zu generieren.
                    </p>
                  )}

                  {storyData && (
                    <>
                      {storyData.title && (
                        <p style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "14px", color: "var(--ink)", marginBottom: "0.5em" }}>
                          {storyData.title}
                        </p>
                      )}
                      <StorySection icon={<FileText size={11} />} label="User Story" variant="direct" items={storyData.story} />
                      <StorySection icon={<CheckSquare size={11} />} label="Akzeptanzkriterien" variant="open" items={storyData.accept} />
                      <StorySection icon={<TestTube size={11} />} label="Testfälle" variant="partial" items={storyData.tests} />
                      <StorySection icon={<Tag size={11} />} label="Release" variant="llm" items={storyData.release} />
                      {org && (
                        <div className="pt-1">
                          <ProjectSelector
                            orgId={org.id}
                            value={saveProjectId}
                            onChange={setSaveProjectId}
                            label="Projekt (optional)"
                          />
                        </div>
                      )}
                      <div className="pt-2">
                        <Button
                          size="sm"
                          onClick={createStory}
                          disabled={creating}
                          className="w-full"
                        >
                          <Plus size={10} />
                          {creating ? "Wird angelegt…" : "Story anlegen"}
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── StorySection sub-component ─────────────────────────────────────────────

function StorySection({
  icon, label, variant, items,
}: {
  icon: React.ReactNode;
  label: string;
  variant: "direct" | "open" | "partial" | "llm";
  items: string[];
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        <Badge variant={variant}>{icon}{label}</Badge>
      </div>
      {items.length === 0 ? (
        <p style={{ fontFamily: "var(--font-body)", fontSize: "12px", color: "var(--ink-faint)" }}>—</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((item, i) => (
            <li
              key={i}
              className="group relative pl-3 pr-6"
              style={{
                fontFamily: "var(--font-body)",
                fontSize: "13px",
                color: "var(--ink-mid)",
                lineHeight: "1.5",
                borderLeft: "1.5px solid var(--paper-rule)",
              }}
            >
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
