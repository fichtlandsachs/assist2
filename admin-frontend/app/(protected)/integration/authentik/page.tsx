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
  const [issuer, setIssuer] = useState("https://auth.heykarl.app/application/o/backend/");
  const [jwks, setJwks] = useState("https://auth.heykarl.app/application/o/backend/jwks/");
  const [adminClient, setAdminClient] = useState("heykarl-admin");
  const [backendClient, setBackendClient] = useState("heykarl-backend");

  async function load() {
    setLoading(true);
    try {
      setError(null);
      setComponents(await fetchComponentStatus());
    } catch (e: any) {
      setError(e?.message || "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const authentik = useMemo(() => {
    const exact = components.find((c) => c.name.toLowerCase() === "authentik");
    if (exact) return exact;
    return components.find((c) => c.name.toLowerCase().includes("auth"));
  }, [components]);

  const healthState: CheckState = authentik?.available ? "ok" : "fail";
  const jwksState: CheckState = jwks.trim().startsWith("http") ? "ok" : "warning";
  const clientState: CheckState = adminClient.trim() && backendClient.trim() ? "ok" : "warning";

  return (
    <div className="space-y-5 max-w-5xl">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--ink)" }}>Integration — Authentik</h1>
          <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>Identity Provider · SSO</p>
        </div>
        <button onClick={() => void load()} className="neo-btn neo-btn--outline neo-btn--sm">Neu laden</button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="neo-card p-3">
          <p className="text-xs" style={{ color: "var(--ink-faint)" }}>Service</p>
          <p className="text-sm font-semibold mt-1" style={{ color: "var(--ink)" }}>{authentik?.label ?? "Authentik"}</p>
        </div>
        <div className="neo-card p-3">
          <p className="text-xs" style={{ color: "var(--ink-faint)" }}>Verfuegbarkeit</p>
          <p className="text-sm font-semibold mt-1" style={{ color: healthState === "ok" ? "#16a34a" : "#dc2626" }}>
            {healthState === "ok" ? "Verfuegbar" : "Down/Unbekannt"}
          </p>
        </div>
        <div className="neo-card p-3">
          <p className="text-xs" style={{ color: "var(--ink-faint)" }}>Admin Client</p>
          <p className="text-sm font-mono mt-1" style={{ color: "var(--ink)" }}>{adminClient || "-"}</p>
        </div>
        <div className="neo-card p-3">
          <p className="text-xs" style={{ color: "var(--ink-faint)" }}>Backend Client</p>
          <p className="text-sm font-mono mt-1" style={{ color: "var(--ink)" }}>{backendClient || "-"}</p>
        </div>
      </div>

      {error && (
        <div className="neo-card p-4" style={{ background: "#fef3c7", border: "1px solid #f59e0b" }}>
          <p style={{ color: "#92400e" }}>⚠️ {error}</p>
        </div>
      )}

      <div className="neo-card p-4 space-y-3">
        <h2 className="text-base font-semibold" style={{ color: "var(--ink)" }}>OIDC Konfiguration</h2>

        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Issuer / Authorization Base</label>
          <input className="neo-input w-full text-sm font-mono" value={issuer} onChange={(e) => setIssuer(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>JWKS URL</label>
          <input className="neo-input w-full text-sm font-mono" value={jwks} onChange={(e) => setJwks(e.target.value)} />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Admin Client ID</label>
            <input className="neo-input w-full text-sm font-mono" value={adminClient} onChange={(e) => setAdminClient(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Backend Client ID</label>
            <input className="neo-input w-full text-sm font-mono" value={backendClient} onChange={(e) => setBackendClient(e.target.value)} />
          </div>
        </div>

        <p className="text-xs" style={{ color: "var(--ink-faint)" }}>
          Hinweis: Diese Seite dient der Betriebspruefung. Werte werden lokal in der Session genutzt und nicht serverseitig gespeichert.
        </p>
      </div>

      <div className="neo-card p-4 space-y-3">
        <h2 className="text-base font-semibold" style={{ color: "var(--ink)" }}>SSO Checkliste</h2>
        <CheckItem
          title="Authentik Dienststatus"
          state={healthState}
          detail={healthState === "ok" ? "Service wird als verfuegbar gemeldet." : "Service wird nicht als verfuegbar gemeldet oder nicht gefunden."}
        />
        <CheckItem
          title="JWKS Endpoint"
          state={jwksState}
          detail="Muss als gueltige HTTP(S)-URL gesetzt sein und zum aktiven Authentik-Provider passen."
        />
        <CheckItem
          title="Client Mapping (Admin + Backend)"
          state={clientState}
          detail="Beide Client IDs sollten gesetzt sein, damit Admin- und Backend-Tokens korrekt validiert werden koennen."
        />
        <CheckItem
          title="Redirect & Audience Konsistenz"
          state="warning"
          detail="Pruefe in Authentik Redirect URIs, Audience und Sub-Mode. Inkonsistenzen verursachen 401/403 Schleifen."
        />
      </div>

      <div className="neo-card p-4 space-y-2">
        <h2 className="text-base font-semibold" style={{ color: "var(--ink)" }}>Schnellaktionen</h2>
        <div className="flex flex-wrap gap-2">
          {authentik?.admin_url ? (
            <a href={authentik.admin_url} target="_blank" rel="noreferrer" className="neo-btn neo-btn--outline neo-btn--sm">
              Authentik Admin oeffnen
            </a>
          ) : (
            <button className="neo-btn neo-btn--outline neo-btn--sm" disabled>
              Kein Admin-Link vorhanden
            </button>
          )}
          <a href={jwks} target="_blank" rel="noreferrer" className="neo-btn neo-btn--outline neo-btn--sm">
            JWKS pruefen
          </a>
          <a href="/integration/logs" className="neo-btn neo-btn--outline neo-btn--sm">
            Logs analysieren
          </a>
          <a href="/integration/overview" className="neo-btn neo-btn--outline neo-btn--sm">
            Integration Overview
          </a>
        </div>
      </div>
    </div>
  );
}
