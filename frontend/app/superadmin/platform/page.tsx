"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  Puzzle, CheckCircle2, AlertTriangle, Clock, XCircle,
  ChevronRight, Plus, RefreshCw, Building2,
} from "lucide-react";
import { fetcher, authFetch } from "@/lib/api/client";

interface ComponentOut {
  id: string; slug: string; name: string; description: string | null;
  status: string; display_order: number; is_core: boolean; feature_count: number;
}

interface OrgComponentOut {
  component_slug: string; component_name: string;
  status: string; licensed_until: string | null; notes: string | null;
}

interface OrgInfo { id: string; name: string; slug: string; }

const STATUS_ICON: Record<string, React.ReactNode> = {
  active:     <CheckCircle2 className="h-4 w-4 text-green-500" />,
  beta:       <Clock className="h-4 w-4 text-amber-500" />,
  deprecated: <AlertTriangle className="h-4 w-4 text-orange-500" />,
  disabled:   <XCircle className="h-4 w-4 text-slate-400" />,
};

const COMPONENT_COLOR: Record<string, string> = {
  core:        "bg-violet-100 text-violet-700 border-violet-200",
  compliance:  "bg-blue-100 text-blue-700 border-blue-200",
  integration: "bg-emerald-100 text-emerald-700 border-emerald-200",
  knowledge:   "bg-amber-100 text-amber-700 border-amber-200",
  runtime:     "bg-slate-100 text-slate-600 border-slate-200",
  system:      "bg-rose-100 text-rose-700 border-rose-200",
};

export default function PlatformComponentsPage() {
  const { data: components, mutate: mutateComponents } = useSWR<ComponentOut[]>(
    "/api/v1/platform/components", fetcher, { revalidateOnFocus: false }
  );
  const { data: orgs } = useSWR<OrgInfo[]>("/api/v1/superadmin/organizations", fetcher);

  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState<string | null>(null);
  const [selectedOrg, setSelectedOrg] = useState("");
  const [orgComponents, setOrgComponents] = useState<OrgComponentOut[] | null>(null);
  const [loadingOrg, setLoadingOrg] = useState(false);
  const [grantingSlug, setGrantingSlug] = useState("");

  const handleSeed = async () => {
    setSeeding(true);
    try {
      const res = await authFetch("/api/v1/platform/seed", { method: "POST" });
      const d = await res.json();
      setSeedMsg(`${d.components_created} Komponenten, ${d.features_created} Features erstellt`);
      mutateComponents();
    } catch { setSeedMsg("Fehler"); }
    finally { setSeeding(false); }
  };

  const loadOrgComponents = async (orgId: string) => {
    setLoadingOrg(true);
    try {
      const res = await authFetch(`/api/v1/platform/orgs/${orgId}/components`);
      setOrgComponents(await res.json());
    } catch { setOrgComponents(null); }
    finally { setLoadingOrg(false); }
  };

  const grantComponent = async (orgId: string, slug: string) => {
    const res = await authFetch(`/api/v1/platform/orgs/${orgId}/components`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ component_slug: slug, status: "active" }),
    });
    if (res.ok) { await loadOrgComponents(orgId); }
    else { alert("Fehler beim Freischalten"); }
  };

  const revokeComponent = async (orgId: string, slug: string) => {
    if (!confirm(`Komponente "${slug}" für diese Org deaktivieren?`)) return;
    await authFetch(`/api/v1/platform/orgs/${orgId}/components/${slug}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "disabled" }),
    });
    await loadOrgComponents(orgId);
  };

  const activeComponents = new Set(
    orgComponents?.filter(c => c.status === "active" || c.status === "trial").map(c => c.component_slug)
  );

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-[var(--ink-strong)] flex items-center gap-2">
            <Puzzle className="h-5 w-5 text-violet-500" />
            Plattform-Komponenten
          </h1>
          <p className="text-sm text-[var(--ink-muted)] mt-0.5">
            Komponentenkatalog · Lizenzierung pro Organisation
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleSeed} disabled={seeding}
            className="flex items-center gap-2 px-3 py-1.5 text-xs bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-60">
            <RefreshCw className={`h-3.5 w-3.5 ${seeding ? "animate-spin" : ""}`} />
            Komponenten & Features seeden
          </button>
        </div>
      </div>

      {seedMsg && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-green-50 border border-green-200 text-xs text-green-800">
          <CheckCircle2 className="h-4 w-4" /> {seedMsg}
          <button onClick={() => setSeedMsg(null)} className="ml-auto">×</button>
        </div>
      )}

      {/* Component grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {(components ?? []).map(comp => (
          <div key={comp.id}
            className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-4 space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${COMPONENT_COLOR[comp.slug] ?? COMPONENT_COLOR.system}`}>
                    {comp.slug.toUpperCase()}
                  </span>
                  {STATUS_ICON[comp.status]}
                  {comp.is_core && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-500 border border-slate-200">
                      Core
                    </span>
                  )}
                </div>
                <h3 className="text-sm font-semibold text-[var(--ink-strong)] mt-1.5">{comp.name}</h3>
              </div>
              <span className="text-xs text-[var(--ink-muted)] shrink-0">{comp.feature_count} Features</span>
            </div>
            {comp.description && (
              <p className="text-xs text-[var(--ink-muted)] leading-relaxed">{comp.description}</p>
            )}
          </div>
        ))}
        {(!components || components.length === 0) && (
          <div className="col-span-full text-center py-16 text-[var(--ink-muted)]">
            <Puzzle className="h-10 w-10 mx-auto mb-3 text-slate-200" />
            <p className="text-sm">Noch keine Komponenten. Seede zuerst die Plattform-Daten.</p>
          </div>
        )}
      </div>

      {/* Org licensing section */}
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] overflow-hidden">
        <div className="flex items-center gap-3 px-5 py-4 border-b border-[var(--border-subtle)]">
          <Building2 className="h-4 w-4 text-[var(--ink-muted)]" />
          <h2 className="text-sm font-semibold text-[var(--ink-strong)] flex-1">Org-Lizenzierung</h2>
          <select
            value={selectedOrg}
            onChange={async e => {
              setSelectedOrg(e.target.value);
              if (e.target.value) await loadOrgComponents(e.target.value);
              else setOrgComponents(null);
            }}
            className="px-2.5 py-1.5 text-xs bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none"
          >
            <option value="">Organisation wählen…</option>
            {(orgs ?? []).map(o => (
              <option key={o.id} value={o.id}>{o.name}</option>
            ))}
          </select>
        </div>

        {selectedOrg && (
          <div className="p-5">
            {loadingOrg ? (
              <div className="flex justify-center py-8">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-violet-500" />
              </div>
            ) : (
              <div className="space-y-3">
                {/* Current licensed components */}
                {orgComponents && orgComponents.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-[var(--ink-muted)] uppercase tracking-wider">Aktive Komponenten</p>
                    {orgComponents.map(oc => (
                      <div key={oc.component_slug}
                        className="flex items-center gap-3 px-3 py-2 bg-[var(--bg-base)] rounded-lg border border-[var(--border-subtle)]">
                        <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${oc.status === "active" ? "bg-green-500" : oc.status === "trial" ? "bg-amber-500" : "bg-slate-300"}`} />
                        <span className="text-sm font-medium text-[var(--ink-strong)] flex-1">{oc.component_name}</span>
                        <span className="text-xs text-[var(--ink-muted)]">{oc.status}</span>
                        {oc.licensed_until && (
                          <span className="text-xs text-amber-600">
                            bis {new Date(oc.licensed_until).toLocaleDateString("de-DE")}
                          </span>
                        )}
                        <button onClick={() => revokeComponent(selectedOrg, oc.component_slug)}
                          className="text-xs text-red-500 hover:text-red-700 shrink-0">
                          Deaktivieren
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Grant new components */}
                <div className="space-y-2">
                  <p className="text-xs font-medium text-[var(--ink-muted)] uppercase tracking-wider mt-4">Komponente freischalten</p>
                  <div className="flex gap-2">
                    <select value={grantingSlug} onChange={e => setGrantingSlug(e.target.value)}
                      className="flex-1 px-2.5 py-1.5 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none">
                      <option value="">Komponente wählen…</option>
                      {(components ?? [])
                        .filter(c => !activeComponents.has(c.slug))
                        .map(c => (
                          <option key={c.slug} value={c.slug}>{c.name}</option>
                        ))}
                    </select>
                    <button
                      onClick={() => { if (grantingSlug) { void grantComponent(selectedOrg, grantingSlug); setGrantingSlug(""); } }}
                      disabled={!grantingSlug}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-40">
                      <Plus className="h-3.5 w-3.5" /> Freischalten
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
