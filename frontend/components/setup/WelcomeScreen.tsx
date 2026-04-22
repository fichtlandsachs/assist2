"use client";

import { useState } from "react";
import { Map, ArrowRight } from "lucide-react";
import { advanceOrgInitStatus } from "@/lib/api/capabilities";

interface Props {
  orgId: string;
  orgName: string;
  onNext: () => void;
}

export function WelcomeScreen({ orgId, orgName, onNext }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStart() {
    setLoading(true);
    setError(null);
    try {
      await advanceOrgInitStatus(orgId, "capability_setup_in_progress");
      onNext();
    } catch {
      setError("Fehler beim Starten. Bitte versuche es erneut.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex-1 flex items-center justify-center p-6">
      <div
        className="w-full max-w-lg bg-[var(--card)] border-2 border-[var(--ink)] rounded-2xl p-8 shadow-[6px_6px_0_rgba(0,0,0,1)]"
        style={{ background: "var(--card)" }}
      >
        {/* Icon */}
        <div className="w-14 h-14 rounded-2xl bg-rose-500 border-2 border-[var(--ink)] flex items-center justify-center mb-6 shadow-[3px_3px_0_rgba(0,0,0,1)]">
          <Map size={26} className="text-white" />
        </div>

        {/* Heading */}
        <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--ink)" }}>
          Willkommen bei {orgName}
        </h1>
        <p className="text-sm mb-6" style={{ color: "var(--ink-mid)" }}>
          Bevor du loslegen kannst, richten wir kurz deine <strong>Business Capability Map</strong> ein.
          Sie bildet die Grundlage für alle Projekte, Epics und User Stories in deinem Workspace.
        </p>

        {/* Steps overview */}
        <div className="space-y-3 mb-8">
          {[
            { n: "1", text: "Capability Map hochladen oder Vorlage wählen" },
            { n: "2", text: "Vorschau prüfen und bestätigen" },
            { n: "3", text: "Ersten Eintrag per Chat anlegen" },
          ].map(({ n, text }) => (
            <div key={n} className="flex items-start gap-3">
              <span
                className="w-6 h-6 rounded-full border-2 border-[var(--ink)] flex items-center justify-center text-[11px] font-bold flex-shrink-0"
                style={{ background: "var(--accent-orange)", color: "var(--ink)" }}
              >
                {n}
              </span>
              <span className="text-sm pt-0.5" style={{ color: "var(--ink-mid)" }}>{text}</span>
            </div>
          ))}
        </div>

        {error && (
          <p className="text-sm text-rose-600 mb-4">{error}</p>
        )}

        <button
          onClick={handleStart}
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 px-6 py-3 rounded-xl border-2 border-[var(--ink)] font-bold text-sm shadow-[3px_3px_0_rgba(0,0,0,1)] hover:shadow-none hover:translate-x-px hover:translate-y-px transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ background: "var(--accent-orange)", color: "var(--ink)" }}
        >
          {loading ? "Wird gestartet…" : "Setup starten"}
          {!loading && <ArrowRight size={16} />}
        </button>
      </div>
    </div>
  );
}
