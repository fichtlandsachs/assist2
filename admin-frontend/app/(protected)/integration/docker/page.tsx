"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchComponentStatus } from "@/lib/api";
import type { ComponentStatus } from "@/types";

const DOCKER_SERVICE_CATALOG = [
  { key: "backend", label: "Backend API", critical: true, description: "FastAPI Kernservice inkl. Superadmin-API" },
  { key: "frontend", label: "Frontend", critical: true, description: "Haupt-UI fuer Endnutzer" },
  { key: "admin", label: "Admin Frontend", critical: true, description: "Superadmin/Admin Oberflaeche" },
  { key: "postgres", label: "PostgreSQL", critical: true, description: "Primäre relationale Datenbank" },
  { key: "redis", label: "Redis", critical: true, description: "Cache, Queue und Session-nahe Daten" },
  { key: "worker", label: "Worker", critical: false, description: "Asynchrone Background-Jobs und Ingest Tasks" },
  { key: "litellm", label: "LiteLLM", critical: false, description: "LLM-Gateway fuer Embeddings und Modelle" },
  { key: "authentik", label: "Authentik", critical: false, description: "SSO/Identity Provider" },
  { key: "nextcloud", label: "Nextcloud", critical: false, description: "Dokumentenquelle fuer RAG/Inhalte" },
  { key: "n8n", label: "n8n", critical: false, description: "Workflow-/Automationsplattform" },
  { key: "stirling", label: "Stirling PDF", critical: false, description: "PDF-Aufbereitung und Transformationsdienste" },
] as const;

function statusPill(ok: boolean) {
  return ok
    ? "bg-green-100 text-green-700 border-green-200"
    : "bg-red-50 text-red-700 border-red-200";
}

export default function Page() {
  const [items, setItems] = useState<ComponentStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      setError(null);
      setItems(await fetchComponentStatus());
    } catch (e: any) {
      setError(e?.message || "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const normalized = useMemo(() => {
    const map = new Map<string, ComponentStatus>();
    for (const i of items) map.set(i.name.toLowerCase(), i);
    return map;
  }, [items]);

  const rows = useMemo(() => {
    return DOCKER_SERVICE_CATALOG.map((svc) => {
      const exact = normalized.get(svc.key.toLowerCase());
      const fuzzy = !exact
        ? Array.from(normalized.entries()).find(([k]) => k.includes(svc.key.toLowerCase()))?.[1]
        : undefined;
      const hit = exact ?? fuzzy ?? null;
      return {
        ...svc,
        available: hit?.available ?? false,
        adminUrl: hit?.admin_url ?? null,
        runtimeLabel: hit?.label ?? null,
      };
    });
  }, [normalized]);

  const healthy = rows.filter((r) => r.available).length;
  const criticalDown = rows.filter((r) => r.critical && !r.available).length;

  return (
    <div className="space-y-5 max-w-6xl">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--ink)" }}>Integration — Docker-Ressourcen</h1>
          <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>Alle Docker-basierten Dienste</p>
        </div>
        <button onClick={() => void load()} className="neo-btn neo-btn--outline neo-btn--sm">Neu laden</button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="neo-card p-3">
          <p className="text-xs" style={{ color: "var(--ink-faint)" }}>Dienste gesamt</p>
          <p className="text-2xl font-bold mt-1" style={{ color: "var(--ink)" }}>{rows.length}</p>
        </div>
        <div className="neo-card p-3">
          <p className="text-xs" style={{ color: "var(--ink-faint)" }}>Healthy</p>
          <p className="text-2xl font-bold mt-1" style={{ color: "var(--ink)" }}>{healthy}</p>
        </div>
        <div className="neo-card p-3">
          <p className="text-xs" style={{ color: "var(--ink-faint)" }}>Nicht verfuegbar</p>
          <p className="text-2xl font-bold mt-1" style={{ color: "var(--ink)" }}>{rows.length - healthy}</p>
        </div>
        <div className="neo-card p-3">
          <p className="text-xs" style={{ color: "var(--ink-faint)" }}>Kritische Ausfaelle</p>
          <p className="text-2xl font-bold mt-1" style={{ color: criticalDown > 0 ? "#ef4444" : "var(--ink)" }}>{criticalDown}</p>
        </div>
      </div>

      {loading ? (
        <div className="neo-card p-6 text-center" style={{ color: "var(--ink-faint)" }}>
          <p className="text-sm">Lade Docker-Ressourcen…</p>
        </div>
      ) : error ? (
        <div className="neo-card p-4" style={{ background: "#fef3c7", border: "1px solid #f59e0b" }}>
          <p style={{ color: "#92400e" }}>⚠️ {error}</p>
          <button onClick={() => void load()} className="neo-btn neo-btn--sm neo-btn--outline mt-3">
            Erneut versuchen
          </button>
        </div>
      ) : (
        <div className="neo-card p-0 overflow-hidden">
          <table className="neo-table text-sm">
            <thead>
              <tr>
                <th>Dienst</th>
                <th>Beschreibung</th>
                <th>Kritisch</th>
                <th>Status</th>
                <th>Runtime Label</th>
                <th>Aktion</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key}>
                  <td style={{ color: "var(--ink)" }}>
                    <div className="font-semibold">{r.label}</div>
                    <div className="text-xs font-mono" style={{ color: "var(--ink-faint)" }}>{r.key}</div>
                  </td>
                  <td className="text-xs" style={{ color: "var(--ink-faint)" }}>{r.description}</td>
                  <td>{r.critical ? <span style={{ color: "#ef4444" }}>Ja</span> : <span style={{ color: "var(--ink-faint)" }}>Nein</span>}</td>
                  <td>
                    <span className={`text-xs px-2 py-0.5 rounded-full border ${statusPill(r.available)}`}>
                      {r.available ? "Verfuegbar" : "Down/Unbekannt"}
                    </span>
                  </td>
                  <td className="text-xs font-mono" style={{ color: "var(--ink-faint)" }}>{r.runtimeLabel ?? "-"}</td>
                  <td>
                    {r.adminUrl ? (
                      <a href={r.adminUrl} target="_blank" rel="noreferrer" className="neo-btn neo-btn--outline neo-btn--sm">
                        Oeffnen
                      </a>
                    ) : (
                      <span className="text-xs" style={{ color: "var(--ink-faint)" }}>-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="neo-card p-4 space-y-2">
        <p className="text-sm font-semibold" style={{ color: "var(--ink)" }}>Betriebshinweise</p>
        <ul className="space-y-1">
          <li className="text-xs" style={{ color: "var(--ink-faint)" }}>
            - Kritische Dienste (Backend, Frontend, Admin, Postgres, Redis) sollten dauerhaft verfuegbar sein.
          </li>
          <li className="text-xs" style={{ color: "var(--ink-faint)" }}>
            - Bei "Down/Unbekannt" zuerst Container-Status und Healthchecks im Infrastruktur-Stack pruefen.
          </li>
          <li className="text-xs" style={{ color: "var(--ink-faint)" }}>
            - Runtime Label zeigt den zuletzt gemeldeten Dienstnamen aus dem Status-Endpoint.
          </li>
        </ul>
      </div>
    </div>
  );
}
