"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchComponentStatus } from "@/lib/api";
import type { ComponentStatus } from "@/types";

type CheckState = "ok" | "warning" | "fail";

function pillClass(state: CheckState) {
  if (state === "ok") return "bg-green-100 text-green-700 border-green-200";
  if (state === "warning") return "bg-yellow-100 text-yellow-700 border-yellow-200";
  return "bg-red-50 text-red-700 border-red-200";
}

function CheckItem({
  title,
  state,
  detail,
}: {
  title: string;
  state: CheckState;
  detail: string;
}) {
  return (
    <div className="flex items-start justify-between gap-3 p-3 rounded-md border" style={{ borderColor: "var(--paper-rule)" }}>
      <div>
        <p className="text-sm font-medium" style={{ color: "var(--ink)" }}>{title}</p>
        <p className="text-xs mt-0.5" style={{ color: "var(--ink-faint)" }}>{detail}</p>
      </div>
      <span className={`text-xs px-2 py-0.5 rounded-full border ${pillClass(state)}`}>
        {state === "ok" ? "OK" : state === "warning" ? "Pruefen" : "Fehler"}
      </span>
    </div>
  );
}

export default function Page() {
  const [components, setComponents] = useState<ComponentStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      setError(null);
      setComponents(await fetchComponentStatus());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const stirling = useMemo(() => {
    const exact = components.find((c) => c.name.toLowerCase() === "stirling pdf");
    if (exact) return exact;
    return components.find((c) => c.name.toLowerCase().includes("stirling"));
  }, [components]);

  const healthState: CheckState = loading ? "warning" : stirling?.available ? "ok" : "fail";
  const adminLinkState: CheckState = stirling?.admin_url ? "ok" : "warning";

  return (
    <div className="space-y-5 max-w-5xl">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white text-lg font-bold shrink-0"
            style={{ background: "#475569" }}>S</div>
          <div>
            <h1 className="text-2xl font-bold" style={{ color: "var(--ink)" }}>Integration — Stirling PDF</h1>
            <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>PDF-Verarbeitung · Docker-Ressource · vom Core genutzt (HTML→PDF, Overlays)</p>
          </div>
        </div>
        <button type="button" onClick={() => void load()} className="neo-btn neo-btn--outline neo-btn--sm">Neu laden</button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="neo-card p-3">
          <p className="text-xs" style={{ color: "var(--ink-faint)" }}>Service</p>
          <p className="text-sm font-semibold mt-1" style={{ color: "var(--ink)" }}>{stirling?.name ?? "Stirling PDF"}</p>
        </div>
        <div className="neo-card p-3">
          <p className="text-xs" style={{ color: "var(--ink-faint)" }}>Erreichbarkeit</p>
          <p className="text-sm font-semibold mt-1" style={{ color: healthState === "ok" ? "#16a34a" : healthState === "warning" ? "var(--ink-faint)" : "#dc2626" }}>
            {loading ? "…" : healthState === "ok" ? "Verfuegbar" : "Down/Unbekannt"}
          </p>
        </div>
        <div className="neo-card p-3 md:col-span-2">
          <p className="text-xs" style={{ color: "var(--ink-faint)" }}>Intern (Backend)</p>
          <p className="text-xs font-mono mt-1 break-all" style={{ color: "var(--ink)" }}>
            HTTP-Basic gegen den Container; URL und Credentials kommen aus Backend-Umgebung (STIRLING_PDF_*), nicht aus dieser Oberflaeche.
          </p>
        </div>
      </div>

      {error && !loading && (
        <div className="neo-card p-4" style={{ background: "#fef3c7", border: "1px solid #f59e0b" }}>
          <p style={{ color: "#92400e" }}>⚠️ {error}</p>
        </div>
      )}

      <div className="neo-card p-4 space-y-3">
        <h2 className="text-base font-semibold" style={{ color: "var(--ink)" }}>Betriebscheckliste</h2>
        <CheckItem
          title="Container-Health (interner Check)"
          state={healthState}
          detail={healthState === "ok" ? "Superadmin-Status meldet den Dienst als erreichbar." : "Keine Antwort oder HTTP-Fehler vom internen Health-Endpoint."}
        />
        <CheckItem
          title="Weboberflaeche unter admin-Host"
          state={adminLinkState}
          detail="Stirling laeuft typischerweise hinter dem gleichen Host wie andere Admin-UIs (z. B. /pdf). Zugang gemaess Traefik- und Stack-Konfiguration."
        />
        <CheckItem
          title="PDF-Pipeline im Produkt"
          state="warning"
          detail="Letterhead, HTML-Vorlagen und PDF-Ausgaben pruefen unter Systemeinstellungen / PDF, falls ihr das im Stack nutzt."
        />
      </div>

      <div className="neo-card p-4 space-y-2">
        <h2 className="text-base font-semibold" style={{ color: "var(--ink)" }}>Schnellaktionen</h2>
        <div className="flex flex-wrap gap-2">
          {stirling?.admin_url ? (
            <a href={stirling.admin_url} target="_blank" rel="noreferrer" className="neo-btn neo-btn--outline neo-btn--sm">
              Stirling Web-UI oeffnen
            </a>
          ) : (
            <button type="button" className="neo-btn neo-btn--outline neo-btn--sm" disabled>
              Kein Admin-Link im Status
            </button>
          )}
          <a href="https://github.com/Stirling-Tools/Stirling-PDF" target="_blank" rel="noreferrer" className="neo-btn neo-btn--outline neo-btn--sm">
            Projekt-Dokumentation (GitHub)
          </a>
          <a href="/integration/docker" className="neo-btn neo-btn--outline neo-btn--sm">
            Docker-Ressourcen
          </a>
          <a href="/integration/overview" className="neo-btn neo-btn--outline neo-btn--sm">
            Integration Overview
          </a>
        </div>
      </div>
    </div>
  );
}
