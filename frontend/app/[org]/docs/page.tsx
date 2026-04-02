"use client";

import { use, useState, useEffect } from "react";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { UserStory } from "@/types";
import { Copy, FileText, Sparkles, Save, ExternalLink, CheckCircle, FileDown, Folder } from "lucide-react";

interface DocsResult {
  changelog_entry: string;
  pdf_outline: string[];
  summary: string;
  technical_notes: string;
  confluence_page_url?: string | null;
  nextcloud_path?: string | null;
}

interface ConfluenceConfig {
  configured: boolean;
  spaces: { key: string; name: string }[];
  error?: string;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={copy}
      className="flex items-center gap-1 text-xs text-[var(--ink-faint)] hover:text-[var(--ink-mid)] transition-colors"
    >
      <Copy size={12} />
      {copied ? "Kopiert!" : "Kopieren"}
    </button>
  );
}

export default function DocsPage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { org } = useOrg(resolvedParams.org);
  const { data: stories } = useSWR<UserStory[]>(
    org ? `/api/v1/user-stories?org_id=${org.id}` : null,
    fetcher
  );
  const { data: confluenceConfig } = useSWR<ConfluenceConfig>(
    "/api/v1/confluence/spaces",
    fetcher,
    { revalidateOnFocus: false }
  );

  const [selectedStoryId, setSelectedStoryId] = useState<string>("");
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [result, setResult] = useState<DocsResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  // PDF generation state
  const [pdfGenerating, setPdfGenerating] = useState(false);
  const [pdfPath, setPdfPath] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);

  // Confluence publish options
  const [confluenceSpaceKey, setConfluenceSpaceKey] = useState<string>("");
  const [confluenceParentPageId, setConfluenceParentPageId] = useState<string>("");

  const selectedStory = stories?.find((s) => s.id === selectedStoryId);

  const handleGeneratePdf = async () => {
    if (!selectedStoryId) return;
    setPdfGenerating(true);
    setPdfError(null);
    setPdfPath(null);
    try {
      const res = await apiRequest<{ ok: boolean; path: string; filename: string }>(
        `/api/v1/user-stories/${selectedStoryId}/docs/pdf`,
        { method: "POST" }
      );
      setPdfPath(res.filename);
    } catch (err: unknown) {
      setPdfError((err as { error?: string })?.error ?? "PDF-Erstellung fehlgeschlagen.");
    } finally {
      setPdfGenerating(false);
    }
  };

  // Load previously saved docs when story is selected
  useEffect(() => {
    if (!selectedStoryId) {
      setResult(null);
      setSaved(false);
      return;
    }
    void (async () => {
      try {
        const saved = await apiRequest<DocsResult | null>(
          `/api/v1/user-stories/${selectedStoryId}/docs`,
          { method: "GET" }
        );
        if (saved) {
          setResult(saved);
          setSaved(true);
        } else {
          setResult(null);
          setSaved(false);
        }
      } catch {
        setResult(null);
        setSaved(false);
      }
    })();
  }, [selectedStoryId]);

  const handleGenerate = async () => {
    if (!selectedStory) return;
    setGenerating(true);
    setError(null);
    setResult(null);
    setSaved(false);
    try {
      const docs = await apiRequest<DocsResult>("/api/v1/user-stories/ai-docs", {
        method: "POST",
        body: JSON.stringify({
          title: selectedStory.title,
          description: selectedStory.description,
          acceptance_criteria: selectedStory.acceptance_criteria,
        }),
      });
      setResult(docs);
    } catch {
      setError("Dokumentation konnte nicht generiert werden. Ist der ANTHROPIC_API_KEY gesetzt?");
    } finally {
      setGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!result || !selectedStoryId) return;
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await apiRequest<DocsResult>(
        `/api/v1/user-stories/${selectedStoryId}/docs/save`,
        {
          method: "POST",
          body: JSON.stringify({
            ...result,
            confluence_space_key: confluenceSpaceKey || null,
            confluence_parent_page_id: confluenceParentPageId || null,
          }),
        }
      );
      setResult(updated);
      setSaved(true);
    } catch (err: unknown) {
      setSaveError(
        (err as { error?: string })?.error ?? "Fehler beim Speichern."
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-[var(--ink)]">Dokumentation</h1>
        <p className="text-[var(--ink-faint)] mt-1 text-sm">
          Generierte Dokumentation für User Stories
        </p>
      </div>

      {/* Story selection + generate */}
      <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-6 space-y-4">
        <h2 className="text-base font-semibold text-[var(--ink)]">Story auswählen</h2>

        {!stories ? (
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[var(--accent-red)]" />
        ) : stories.length === 0 ? (
          <p className="text-sm text-[var(--ink-faint)]">Keine User Stories vorhanden. Erstelle zuerst eine Story.</p>
        ) : (
          <div className="flex gap-3">
            <select
              value={selectedStoryId}
              onChange={(e) => {
                setSelectedStoryId(e.target.value);
                setResult(null);
                setSaved(false);
                setError(null);
                setPdfPath(null);
                setPdfError(null);
              }}
              className="flex-1 px-3 py-2 border border-[var(--ink-faintest)] rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-red)]"
            >
              <option value="">-- Story wählen --</option>
              {stories.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title}
                </option>
              ))}
            </select>
            <button
              onClick={() => void handleGenerate()}
              disabled={!selectedStoryId || generating}
              className="flex items-center gap-2 px-4 py-2 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-sm text-sm font-medium transition-colors"
            >
              <Sparkles size={16} />
              {generating ? "Generiere…" : "Generieren"}
            </button>
          </div>
        )}

        {selectedStory && (
          <div className="bg-[var(--paper-warm)] rounded-sm p-3 text-sm text-[var(--ink-mid)] space-y-1">
            <p><span className="font-medium">Titel:</span> {selectedStory.title}</p>
            {selectedStory.description && (
              <p><span className="font-medium">Beschreibung:</span> {selectedStory.description}</p>
            )}
            <p>
              <span className="font-medium">Status:</span> {selectedStory.status} ·{" "}
              <span className="font-medium">Priorität:</span> {selectedStory.priority}
            </p>
          </div>
        )}

        {error && (
          <div className="bg-[rgba(var(--accent-red-rgb),.08)] border border-[rgba(var(--accent-red-rgb),.3)] text-[var(--accent-red)] text-sm rounded-sm px-4 py-3">
            {error}
          </div>
        )}
      </div>

      {/* Results */}
      {result && (
        <>
          <div className="space-y-4">
            {/* Summary */}
            <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-6">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-base font-semibold text-[var(--ink)] flex items-center gap-2">
                  <FileText size={18} className="text-[var(--accent-red)]" />
                  Zusammenfassung
                </h2>
                <CopyButton text={result.summary} />
              </div>
              <p className="text-sm text-[var(--ink-mid)] leading-relaxed">{result.summary}</p>
            </div>

            {/* Changelog */}
            <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-6">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-base font-semibold text-[var(--ink)]">Changelog-Eintrag</h2>
                <CopyButton text={result.changelog_entry} />
              </div>
              <pre className="text-sm text-[var(--ink-mid)] bg-[var(--paper-warm)] rounded-sm p-3 whitespace-pre-wrap font-mono">
                {result.changelog_entry}
              </pre>
            </div>

            {/* PDF Outline */}
            <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-6">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-base font-semibold text-[var(--ink)]">Dokumentgliederung</h2>
                <CopyButton text={result.pdf_outline.map((item, i) => `${i + 1}. ${item}`).join("\n")} />
              </div>
              <ol className="space-y-2">
                {result.pdf_outline.map((item, index) => (
                  <li key={index} className="flex items-center gap-3 text-sm text-[var(--ink-mid)]">
                    <span className="w-6 h-6 rounded-full bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)] flex items-center justify-center text-xs font-bold shrink-0">
                      {index + 1}
                    </span>
                    {item}
                  </li>
                ))}
              </ol>
            </div>

            {/* Technical Notes */}
            <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-6">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-base font-semibold text-[var(--ink)]">Technische Hinweise</h2>
                <CopyButton text={result.technical_notes} />
              </div>
              <p className="text-sm text-[var(--ink-mid)] leading-relaxed">{result.technical_notes}</p>
            </div>
          </div>

          {/* Save panel */}
          <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-6 space-y-4">
            <h2 className="text-base font-semibold text-[var(--ink)] flex items-center gap-2">
              <Save size={16} className="text-[var(--ink-faint)]" />
              Dokumentation speichern
            </h2>

            {/* Confluence option */}
            {confluenceConfig?.configured && (
              <div className="space-y-3 border border-[var(--paper-rule)] rounded-sm p-4 bg-[var(--paper-warm)]">
                <p className="text-sm font-medium text-[var(--ink-mid)] flex items-center gap-2">
                  <img
                    src="https://cdn.worldvectorlogo.com/logos/confluence-1.svg"
                    alt="Confluence"
                    className="w-4 h-4"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                  />
                  In Confluence veröffentlichen
                  <span className="text-xs font-normal text-[var(--ink-faint)]">(optional)</span>
                </p>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-[var(--ink-mid)] mb-1">
                      Space
                    </label>
                    <select
                      value={confluenceSpaceKey}
                      onChange={(e) => setConfluenceSpaceKey(e.target.value)}
                      className="w-full px-3 py-1.5 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-1 focus:ring-[var(--accent-red)] bg-[var(--card)]"
                    >
                      <option value="">— Kein Confluence —</option>
                      {confluenceConfig.spaces.map((sp) => (
                        <option key={sp.key} value={sp.key}>
                          {sp.name} ({sp.key})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-[var(--ink-mid)] mb-1">
                      Übergeordnete Seite ID
                      <span className="font-normal text-[var(--ink-faint)] ml-1">(optional)</span>
                    </label>
                    <input
                      type="text"
                      value={confluenceParentPageId}
                      onChange={(e) => setConfluenceParentPageId(e.target.value)}
                      placeholder="z.B. 12345678"
                      className="w-full px-3 py-1.5 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-1 focus:ring-[var(--accent-red)] bg-[var(--card)]"
                    />
                  </div>
                </div>
              </div>
            )}

            {confluenceConfig && !confluenceConfig.configured && (
              <p className="text-xs text-[var(--ink-faint)] flex items-center gap-1.5">
                Confluence nicht konfiguriert —
                setze <code className="bg-[var(--paper-warm)] px-1 rounded-sm">CONFLUENCE_BASE_URL</code>,{" "}
                <code className="bg-[var(--paper-warm)] px-1 rounded-sm">CONFLUENCE_USER</code> und{" "}
                <code className="bg-[var(--paper-warm)] px-1 rounded-sm">CONFLUENCE_API_TOKEN</code> in der <code className="bg-[var(--paper-warm)] px-1 rounded-sm">.env</code>.
              </p>
            )}

            {saveError && (
              <div className="p-3 bg-[rgba(var(--accent-red-rgb),.08)] border border-[rgba(var(--accent-red-rgb),.3)] rounded-sm text-[var(--accent-red)] text-sm">
                {saveError}
              </div>
            )}

            {result.nextcloud_path && (
              <div className="flex items-center gap-2 p-3 bg-[rgba(74,85,104,.06)] border border-[var(--paper-rule)] rounded-sm text-[var(--navy)] text-sm">
                <Folder size={16} className="shrink-0" />
                <span className="flex-1">PDF in Nextcloud: <span className="font-mono text-xs">{result.nextcloud_path.split("/").pop()}</span></span>
              </div>
            )}

            {saved && result.confluence_page_url && (
              <div className="flex items-center gap-2 p-3 bg-[rgba(82,107,94,.1)] border border-[var(--paper-rule)] rounded-sm text-[var(--green)] text-sm">
                <CheckCircle size={16} className="shrink-0" />
                <span>In Confluence veröffentlicht:</span>
                <a
                  href={result.confluence_page_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline flex items-center gap-1 truncate"
                >
                  Seite öffnen <ExternalLink size={12} />
                </a>
              </div>
            )}

            {saved && !result.confluence_page_url && (
              <div className="flex items-center gap-2 p-3 bg-[rgba(82,107,94,.1)] border border-[var(--paper-rule)] rounded-sm text-[var(--green)] text-sm">
                <CheckCircle size={16} className="shrink-0" />
                Dokumentation gespeichert.
              </div>
            )}

            {pdfError && (
              <div className="p-3 bg-[rgba(var(--accent-red-rgb),.08)] border border-[rgba(var(--accent-red-rgb),.3)] rounded-sm text-[var(--accent-red)] text-sm">
                {pdfError}
              </div>
            )}

            {pdfPath && (
              <div className="flex items-center gap-2 p-3 bg-[rgba(82,107,94,.1)] border border-[var(--paper-rule)] rounded-sm text-[var(--green)] text-sm">
                <CheckCircle size={16} className="shrink-0" />
                <span>PDF gespeichert in Nextcloud: <span className="font-mono text-xs">{pdfPath}</span></span>
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={() => void handleSave()}
                disabled={saving}
                className="flex items-center gap-2 px-5 py-2.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[rgba(var(--accent-red-rgb),.08)] text-white rounded-sm text-sm font-medium transition-colors"
              >
                {saving ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                ) : (
                  <Save size={16} />
                )}
                {confluenceSpaceKey ? "Speichern & in Confluence veröffentlichen" : "Speichern"}
              </button>
              <button
                onClick={() => void handleGeneratePdf()}
                disabled={pdfGenerating}
                className="flex items-center gap-2 px-5 py-2.5 bg-[var(--ink-mid)] hover:bg-[var(--ink)] disabled:opacity-50 text-white rounded-sm text-sm font-medium transition-colors"
              >
                {pdfGenerating ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                ) : (
                  <FileDown size={16} />
                )}
                {pdfGenerating ? "PDF wird erstellt…" : "PDF erstellen"}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
