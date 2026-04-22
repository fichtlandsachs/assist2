"use client";

import { useState, useEffect, useRef } from "react";
import { Upload, Layers, Sparkles, CheckCircle, AlertTriangle, ChevronRight } from "lucide-react";
import {
  importDemo,
  importTemplate,
  importExcel,
  fetchCapabilityTemplates,
  advanceOrgInitStatus,
} from "@/lib/api/capabilities";
import { CapabilityTreePreview } from "./CapabilityTreePreview";
import type { ImportValidationResult, CapabilityTemplate } from "@/types";

type TabId = "demo" | "template" | "excel";

interface Props {
  orgId: string;
  onDone: () => void;
}

export function CapabilitySetupScreen({ orgId, onDone }: Props) {
  const [tab, setTab] = useState<TabId>("demo");
  const [templates, setTemplates] = useState<CapabilityTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportValidationResult | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load templates
  useEffect(() => {
    fetchCapabilityTemplates()
      .then((items) => {
        setTemplates(items);
        if (items.length > 0) setSelectedTemplate(items[0].key);
      })
      .catch(() => {/* non-critical */});
  }, []);

  // Auto-preview for demo tab
  useEffect(() => {
    if (tab === "demo") {
      runDryRun();
    } else {
      setPreview(null);
    }
    setError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function runDryRun() {
    setLoadingPreview(true);
    setPreview(null);
    setError(null);
    try {
      let result: ImportValidationResult;
      if (tab === "demo") {
        result = await importDemo(orgId, true);
      } else if (tab === "template" && selectedTemplate) {
        result = await importTemplate(orgId, selectedTemplate, true);
      } else if (tab === "excel" && selectedFile) {
        result = await importExcel(orgId, selectedFile, true);
      } else {
        return;
      }
      setPreview(result);
    } catch (e: unknown) {
      const msg = (e as { error?: string })?.error ?? "Fehler bei der Vorschau.";
      setError(msg);
    } finally {
      setLoadingPreview(false);
    }
  }

  async function handleConfirm() {
    setConfirming(true);
    setError(null);
    try {
      let source: string;
      if (tab === "demo") {
        await importDemo(orgId, false);
        source = "demo";
      } else if (tab === "template" && selectedTemplate) {
        await importTemplate(orgId, selectedTemplate, false);
        source = "template";
      } else if (tab === "excel" && selectedFile) {
        await importExcel(orgId, selectedFile, false);
        source = "excel";
      } else {
        setError("Bitte wähle eine Option.");
        setConfirming(false);
        return;
      }
      await advanceOrgInitStatus(orgId, "capability_setup_validated", source);
      onDone();
    } catch (e: unknown) {
      const msg = (e as { error?: string })?.error ?? "Fehler beim Importieren.";
      setError(msg);
    } finally {
      setConfirming(false);
    }
  }

  const canConfirm = preview?.is_valid && !loadingPreview;

  return (
    <div className="flex-1 flex items-start justify-center p-6">
      <div className="w-full max-w-2xl space-y-4">
        {/* Header */}
        <div>
          <h1 className="text-xl font-bold" style={{ color: "var(--ink)" }}>
            Business Capability Map einrichten
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--ink-mid)" }}>
            Wähle eine Quelle für deine initiale Capability-Struktur.
          </p>
        </div>

        {/* Tab bar */}
        <div
          className="flex gap-1 p-1 rounded-xl border-2 border-[var(--ink)]"
          style={{ background: "var(--paper-warm)" }}
        >
          {([
            { id: "demo" as TabId, label: "Demo-Daten", icon: Sparkles },
            { id: "template" as TabId, label: "Vorlage", icon: Layers },
            { id: "excel" as TabId, label: "Excel-Upload", icon: Upload },
          ] as { id: TabId; label: string; icon: React.ElementType }[]).map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className="flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-sm font-medium transition-all"
              style={{
                background: tab === id ? "var(--card)" : "transparent",
                color: tab === id ? "var(--ink)" : "var(--ink-faint)",
                boxShadow: tab === id ? "2px 2px 0 rgba(0,0,0,.8)" : "none",
                border: tab === id ? "1.5px solid var(--ink)" : "1.5px solid transparent",
              }}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="bg-[var(--card)] border-2 border-[var(--ink)] rounded-2xl p-5 shadow-[4px_4px_0_rgba(0,0,0,1)]">
          {tab === "demo" && (
            <p className="text-sm mb-4" style={{ color: "var(--ink-mid)" }}>
              Wir laden eine Beispiel-Capability-Map mit drei Hauptbereichen (Digitale Transformation, Produkt &amp; Entwicklung, Betrieb &amp; Infrastruktur) — ideal zum Ausprobieren.
            </p>
          )}

          {tab === "template" && (
            <div className="space-y-2 mb-4">
              <p className="text-sm mb-3" style={{ color: "var(--ink-mid)" }}>
                Wähle eine vorgefertigte Vorlage als Ausgangspunkt:
              </p>
              {templates.map((tpl) => (
                <button
                  key={tpl.key}
                  onClick={() => {
                    setSelectedTemplate(tpl.key);
                    setPreview(null);
                  }}
                  className="w-full text-left p-3 rounded-xl border-2 transition-all"
                  style={{
                    borderColor: selectedTemplate === tpl.key ? "var(--accent-orange)" : "var(--paper-rule2)",
                    background: selectedTemplate === tpl.key ? "rgba(255,165,0,.06)" : "var(--paper-warm)",
                  }}
                >
                  <div className="font-medium text-sm" style={{ color: "var(--ink)" }}>{tpl.label}</div>
                  <div className="text-xs mt-0.5" style={{ color: "var(--ink-faint)" }}>{tpl.description} · {tpl.node_count} Knoten</div>
                </button>
              ))}
              {selectedTemplate && (
                <button
                  onClick={runDryRun}
                  disabled={loadingPreview}
                  className="mt-2 px-4 py-2 text-sm rounded-lg border-2 border-[var(--ink)] font-medium shadow-[2px_2px_0_rgba(0,0,0,1)] hover:shadow-none hover:translate-x-px hover:translate-y-px transition-all disabled:opacity-50"
                  style={{ background: "var(--paper-warm)", color: "var(--ink)" }}
                >
                  {loadingPreview ? "Lade Vorschau…" : "Vorschau laden"}
                </button>
              )}
            </div>
          )}

          {tab === "excel" && (
            <div className="mb-4">
              <p className="text-sm mb-3" style={{ color: "var(--ink-mid)" }}>
                Lade eine Excel-Datei (.xlsx) hoch. Benötigte Spalten:{" "}
                <code className="text-xs bg-[var(--paper-warm)] px-1 rounded">Capability</code>,{" "}
                <code className="text-xs bg-[var(--paper-warm)] px-1 rounded">Level 1</code>,{" "}
                <code className="text-xs bg-[var(--paper-warm)] px-1 rounded">Level 2</code>{" "}
                (optional: <code className="text-xs bg-[var(--paper-warm)] px-1 rounded">Level 3</code>).
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0] ?? null;
                  setSelectedFile(f);
                  setPreview(null);
                }}
              />
              <div className="flex items-center gap-3">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="px-4 py-2 text-sm rounded-lg border-2 border-[var(--ink)] font-medium shadow-[2px_2px_0_rgba(0,0,0,1)] hover:shadow-none hover:translate-x-px hover:translate-y-px transition-all"
                  style={{ background: "var(--paper-warm)", color: "var(--ink)" }}
                >
                  Datei wählen
                </button>
                {selectedFile && (
                  <span className="text-sm" style={{ color: "var(--ink-mid)" }}>{selectedFile.name}</span>
                )}
              </div>
              {selectedFile && (
                <button
                  onClick={runDryRun}
                  disabled={loadingPreview}
                  className="mt-3 px-4 py-2 text-sm rounded-lg border-2 border-[var(--ink)] font-medium shadow-[2px_2px_0_rgba(0,0,0,1)] hover:shadow-none hover:translate-x-px hover:translate-y-px transition-all disabled:opacity-50"
                  style={{ background: "var(--paper-warm)", color: "var(--ink)" }}
                >
                  {loadingPreview ? "Validiere…" : "Prüfen & Vorschau"}
                </button>
              )}
            </div>
          )}

          {/* Validation result summary */}
          {preview && (
            <div className="mb-4 space-y-3">
              <div className="flex items-center gap-3 flex-wrap">
                <div
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium"
                  style={{
                    background: preview.is_valid ? "rgba(16,185,129,.08)" : "rgba(239,68,68,.08)",
                    borderColor: preview.is_valid ? "rgba(16,185,129,.3)" : "rgba(239,68,68,.3)",
                    color: preview.is_valid ? "#059669" : "#dc2626",
                  }}
                >
                  {preview.is_valid ? <CheckCircle size={14} /> : <AlertTriangle size={14} />}
                  {preview.is_valid ? "Valide" : `${preview.error_count} Fehler`}
                </div>
                <span className="text-xs" style={{ color: "var(--ink-faint)" }}>
                  {preview.capability_count} Capabilities · {preview.node_count} Knoten gesamt
                </span>
                {preview.warning_count > 0 && (
                  <span className="text-xs text-amber-600">{preview.warning_count} Warnungen</span>
                )}
              </div>

              {preview.issues.filter((i) => i.level === "error").length > 0 && (
                <div className="space-y-1">
                  {preview.issues.filter((i) => i.level === "error").slice(0, 5).map((issue, idx) => (
                    <div key={idx} className="text-xs text-rose-600 flex gap-1.5">
                      <span>•</span>
                      <span>{issue.row != null ? `Zeile ${issue.row}: ` : ""}{issue.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Loading spinner */}
          {loadingPreview && (
            <div className="flex items-center gap-2 py-6 justify-center" style={{ color: "var(--ink-faint)" }}>
              <div className="w-4 h-4 rounded-full border-2 border-current border-t-transparent animate-spin" />
              <span className="text-sm">Lade Vorschau…</span>
            </div>
          )}

          {/* Tree preview */}
          {preview && preview.preview.length > 0 && (
            <div>
              <p className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: "var(--ink-faint)" }}>
                Vorschau
              </p>
              <CapabilityTreePreview nodes={preview.preview} />
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="text-sm text-rose-600 px-1">{error}</div>
        )}

        {/* Confirm button */}
        <div className="flex justify-end">
          <button
            onClick={handleConfirm}
            disabled={!canConfirm || confirming}
            className="flex items-center gap-2 px-6 py-3 rounded-xl border-2 border-[var(--ink)] font-bold text-sm shadow-[3px_3px_0_rgba(0,0,0,1)] hover:shadow-none hover:translate-x-px hover:translate-y-px transition-all disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-[3px_3px_0_rgba(0,0,0,1)] disabled:translate-x-0 disabled:translate-y-0"
            style={{ background: canConfirm ? "var(--accent-orange)" : "var(--paper-warm)", color: "var(--ink)" }}
          >
            {confirming ? "Wird übernommen…" : "Capability Map bestätigen"}
            {!confirming && <ChevronRight size={16} />}
          </button>
        </div>
      </div>
    </div>
  );
}
