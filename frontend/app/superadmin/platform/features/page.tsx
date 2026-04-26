"use client";

import { useState } from "react";
import useSWR from "swr";
import { Zap, Lock, Unlock, ChevronDown, ChevronRight, Search, ToggleLeft, ToggleRight } from "lucide-react";
import { fetcher, authFetch } from "@/lib/api/client";

interface FeatureOut {
  id: string; slug: string; name: string; description: string | null;
  component_slug: string; default_enabled: boolean; override_policy: string;
}

const POLICY_COLOR: Record<string, string> = {
  locked:            "bg-red-50 text-red-700 border-red-200",
  overridable:       "bg-green-50 text-green-700 border-green-200",
  extend_only:       "bg-blue-50 text-blue-700 border-blue-200",
  disable_only:      "bg-amber-50 text-amber-700 border-amber-200",
  approval_required: "bg-violet-50 text-violet-700 border-violet-200",
};

const POLICY_LABELS: Record<string, string> = {
  locked:            "Gesperrt",
  overridable:       "Org-Override erlaubt",
  extend_only:       "Nur erweitern",
  disable_only:      "Nur deaktivieren",
  approval_required: "Freigabe nötig",
};

const COMPONENT_COLOR: Record<string, string> = {
  core:        "text-violet-700 bg-violet-100",
  compliance:  "text-blue-700 bg-blue-100",
  integration: "text-emerald-700 bg-emerald-100",
  knowledge:   "text-amber-700 bg-amber-100",
  runtime:     "text-slate-600 bg-slate-100",
  system:      "text-rose-700 bg-rose-100",
};

export default function PlatformFeaturesPage() {
  const { data: features, mutate } = useSWR<FeatureOut[]>(
    "/api/v1/platform/features", fetcher, { revalidateOnFocus: false }
  );

  const [search, setSearch] = useState("");
  const [expandedComp, setExpandedComp] = useState<Set<string>>(new Set());
  const [editPolicy, setEditPolicy] = useState<{ slug: string; policy: string } | null>(null);
  const [saving, setSaving] = useState(false);

  const filtered = (features ?? []).filter(f =>
    !search || f.slug.includes(search.toLowerCase()) || f.name.toLowerCase().includes(search.toLowerCase())
  );

  // Group by component
  const groups = filtered.reduce((acc, f) => {
    if (!acc[f.component_slug]) acc[f.component_slug] = [];
    acc[f.component_slug].push(f);
    return acc;
  }, {} as Record<string, FeatureOut[]>);

  const toggleEnabled = async (slug: string, current: boolean) => {
    setSaving(true);
    try {
      await authFetch(`/api/v1/platform/features/${slug}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ default_enabled: !current }),
      });
      mutate();
    } finally { setSaving(false); }
  };

  const savePolicy = async () => {
    if (!editPolicy) return;
    setSaving(true);
    try {
      await authFetch(`/api/v1/platform/features/${editPolicy.slug}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ override_policy: editPolicy.policy }),
      });
      setEditPolicy(null);
      mutate();
    } finally { setSaving(false); }
  };

  const toggleComp = (slug: string) => {
    setExpandedComp(prev => {
      const n = new Set(prev);
      if (n.has(slug)) n.delete(slug); else n.add(slug);
      return n;
    });
  };

  return (
    <div className="space-y-5 p-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-[var(--ink-strong)] flex items-center gap-2">
            <Zap className="h-5 w-5 text-amber-500" />
            Feature Flags
          </h1>
          <p className="text-sm text-[var(--ink-muted)] mt-0.5">
            Globale Feature-Defaults und Override-Policies
          </p>
        </div>
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--ink-muted)]" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Suchen…"
            className="pl-8 pr-3 py-1.5 text-sm bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg focus:outline-none w-48" />
        </div>
      </div>

      {/* Policy legend */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(POLICY_LABELS).map(([k, v]) => (
          <span key={k} className={`px-2 py-0.5 text-[10px] rounded border font-medium ${POLICY_COLOR[k]}`}>{v}</span>
        ))}
      </div>

      {/* Feature groups by component */}
      <div className="space-y-3">
        {Object.entries(groups).map(([comp, feats]) => {
          const open = expandedComp.has(comp);
          return (
            <div key={comp} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] overflow-hidden">
              <button onClick={() => toggleComp(comp)}
                className="flex items-center gap-3 w-full px-5 py-3.5 text-left hover:bg-[var(--bg-hover)] transition-colors">
                {open ? <ChevronDown className="h-4 w-4 text-[var(--ink-muted)]" /> : <ChevronRight className="h-4 w-4 text-[var(--ink-muted)]" />}
                <span className={`px-2 py-0.5 rounded text-xs font-bold ${COMPONENT_COLOR[comp] ?? COMPONENT_COLOR.system}`}>
                  {comp.toUpperCase()}
                </span>
                <span className="text-sm font-semibold text-[var(--ink-strong)] flex-1">
                  {comp.charAt(0).toUpperCase() + comp.slice(1)}
                </span>
                <span className="text-xs text-[var(--ink-muted)]">{feats.length} Features</span>
              </button>

              {open && (
                <div className="divide-y divide-[var(--border-subtle)] border-t border-[var(--border-subtle)]">
                  {feats.map(f => (
                    <div key={f.id} className="flex items-center gap-3 px-5 py-3">
                      {/* Toggle */}
                      <button onClick={() => void toggleEnabled(f.slug, f.default_enabled)}
                        disabled={saving}
                        title={f.default_enabled ? "Global aktiv (klicken zum Deaktivieren)" : "Global inaktiv (klicken zum Aktivieren)"}
                        className="shrink-0 text-[var(--ink-muted)] hover:text-violet-600 disabled:opacity-50">
                        {f.default_enabled
                          ? <ToggleRight className="h-5 w-5 text-green-500" />
                          : <ToggleLeft className="h-5 w-5 text-slate-400" />}
                      </button>

                      {/* Name + slug */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-[var(--ink-strong)]">{f.name}</span>
                        </div>
                        <p className="text-xs text-[var(--ink-muted)] font-mono">{f.slug}</p>
                        {f.description && <p className="text-xs text-[var(--ink-muted)] mt-0.5">{f.description}</p>}
                      </div>

                      {/* Policy badge + edit */}
                      {editPolicy?.slug === f.slug ? (
                        <div className="flex items-center gap-2 shrink-0">
                          <select
                            value={editPolicy.policy}
                            onChange={e => setEditPolicy({ slug: f.slug, policy: e.target.value })}
                            className="px-2 py-1 text-xs border border-[var(--border-subtle)] rounded focus:outline-none"
                          >
                            {Object.entries(POLICY_LABELS).map(([k, v]) => (
                              <option key={k} value={k}>{v}</option>
                            ))}
                          </select>
                          <button onClick={() => void savePolicy()} disabled={saving}
                            className="px-2 py-1 text-xs bg-violet-600 text-white rounded disabled:opacity-50">
                            OK
                          </button>
                          <button onClick={() => setEditPolicy(null)}
                            className="text-xs text-[var(--ink-muted)]">×</button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setEditPolicy({ slug: f.slug, policy: f.override_policy })}
                          className={`shrink-0 px-2 py-0.5 text-[10px] rounded border font-medium ${POLICY_COLOR[f.override_policy] ?? ""} flex items-center gap-1`}>
                          {f.override_policy === "locked" ? <Lock className="h-3 w-3" /> : <Unlock className="h-3 w-3" />}
                          {POLICY_LABELS[f.override_policy] ?? f.override_policy}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
