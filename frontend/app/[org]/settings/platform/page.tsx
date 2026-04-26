"use client";

import { use, useState } from "react";
import useSWR from "swr";
import {
  Puzzle, Zap, Lock, Unlock, ToggleLeft, ToggleRight,
  CheckCircle2, Clock, AlertTriangle, ChevronDown, ChevronRight,
} from "lucide-react";
import { fetcher, authFetch } from "@/lib/api/client";
import { useOrg } from "@/lib/hooks/useOrg";

interface Props { params: Promise<{ org: string }> }

interface OrgComponentOut {
  component_slug: string; component_name: string;
  status: string; licensed_until: string | null;
}

interface EffectiveFeature {
  slug: string; enabled: boolean; config: Record<string, unknown>;
  policy: string; component_slug: string; component_active: boolean;
}

interface OrgFeatureOverrideOut {
  id: string; feature_slug: string; component_slug: string;
  is_enabled: boolean | null; config_override: Record<string, unknown> | null;
  approval_status: string; policy: string;
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
  overridable:       "Anpassbar",
  extend_only:       "Nur erweitern",
  disable_only:      "Nur deaktivieren",
  approval_required: "Freigabe erforderlich",
};

export default function OrgPlatformSettingsPage({ params }: Props) {
  const { org: orgSlug } = use(params);
  const { org } = useOrg(orgSlug);

  const { data: components } = useSWR<OrgComponentOut[]>(
    org ? `/api/v1/platform/my-org/${org.id}/components` : null,
    fetcher, { revalidateOnFocus: false }
  );

  const { data: features, mutate: mutateFeatures } = useSWR<EffectiveFeature[]>(
    org ? `/api/v1/platform/my-org/${org.id}/effective-features` : null,
    fetcher, { revalidateOnFocus: false }
  );

  const { data: overrides, mutate: mutateOverrides } = useSWR<OrgFeatureOverrideOut[]>(
    org ? `/api/v1/platform/my-org/${org.id}/feature-overrides` : null,
    fetcher, { revalidateOnFocus: false }
  );

  const [expandedComp, setExpandedComp] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState<string | null>(null);

  const toggleComp = (slug: string) => {
    setExpandedComp(prev => {
      const n = new Set(prev);
      if (n.has(slug)) n.delete(slug); else n.add(slug);
      return n;
    });
  };

  const toggleFeature = async (feat: EffectiveFeature) => {
    if (!org) return;
    if (feat.policy === "locked") return;
    if (feat.policy === "disable_only" && !feat.enabled) return;
    setSaving(feat.slug);
    try {
      await authFetch(`/api/v1/platform/my-org/${org.id}/feature-overrides`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feature_slug: feat.slug, is_enabled: !feat.enabled }),
      });
      mutateFeatures();
      mutateOverrides();
    } finally { setSaving(null); }
  };

  // Group features by component
  const featureGroups = (features ?? []).reduce((acc, f) => {
    if (!acc[f.component_slug]) acc[f.component_slug] = [];
    acc[f.component_slug].push(f);
    return acc;
  }, {} as Record<string, EffectiveFeature[]>);

  const activeCompSlugs = new Set(
    (components ?? []).filter(c => c.status === "active" || c.status === "trial").map(c => c.component_slug)
  );

  const pendingOverrides = (overrides ?? []).filter(o => o.approval_status === "pending");

  return (
    <div className="max-w-4xl mx-auto space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-[var(--ink-strong)] flex items-center gap-2">
          <Puzzle className="h-5 w-5 text-violet-500" />
          Plattform-Konfiguration
        </h1>
        <p className="text-sm text-[var(--ink-muted)] mt-0.5">
          Aktive Komponenten und Feature-Overrides für {org?.name ?? orgSlug}
        </p>
      </div>

      {/* Pending approvals */}
      {pendingOverrides.length > 0 && (
        <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <Clock className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-amber-800">
              {pendingOverrides.length} Feature-Override{pendingOverrides.length > 1 ? "s" : ""} wartet auf Superadmin-Freigabe
            </p>
            <p className="text-xs text-amber-700 mt-0.5">
              {pendingOverrides.map(o => o.feature_slug).join(", ")}
            </p>
          </div>
        </div>
      )}

      {/* Active components */}
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] overflow-hidden">
        <div className="px-5 py-4 border-b border-[var(--border-subtle)]">
          <h2 className="text-sm font-semibold text-[var(--ink-strong)] flex items-center gap-2">
            <Puzzle className="h-4 w-4 text-violet-400" />
            Lizenzierte Komponenten
          </h2>
        </div>
        <div className="p-5">
          {(components ?? []).length === 0 ? (
            <p className="text-sm text-[var(--ink-muted)]">Keine Komponenten freigeschaltet. Bitte den Superadmin kontaktieren.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {(components ?? []).map(c => (
                <div key={c.component_slug}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm ${
                    c.status === "active" ? "bg-green-50 border-green-200 text-green-800" :
                    c.status === "trial" ? "bg-amber-50 border-amber-200 text-amber-800" :
                    "bg-slate-50 border-slate-200 text-slate-500"
                  }`}>
                  {c.status === "active" ? <CheckCircle2 className="h-4 w-4" /> :
                   c.status === "trial" ? <Clock className="h-4 w-4" /> :
                   <AlertTriangle className="h-4 w-4" />}
                  <span className="font-medium">{c.component_name}</span>
                  <span className="text-xs opacity-70">{c.status}</span>
                  {c.licensed_until && (
                    <span className="text-xs opacity-60">
                      bis {new Date(c.licensed_until).toLocaleDateString("de-DE")}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Feature overrides by component */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-[var(--ink-strong)] flex items-center gap-2">
          <Zap className="h-4 w-4 text-amber-500" />
          Feature-Konfiguration
        </h2>

        {Object.entries(featureGroups).map(([comp, feats]) => {
          const compActive = activeCompSlugs.has(comp);
          const open = expandedComp.has(comp);
          const enabledCount = feats.filter(f => f.enabled).length;

          return (
            <div key={comp}
              className={`bg-[var(--bg-card)] rounded-xl border overflow-hidden ${compActive ? "border-[var(--border-subtle)]" : "border-slate-200 opacity-60"}`}>
              <button onClick={() => toggleComp(comp)}
                className="flex items-center gap-3 w-full px-5 py-3.5 text-left hover:bg-[var(--bg-hover)] transition-colors">
                {open ? <ChevronDown className="h-4 w-4 text-[var(--ink-muted)]" /> : <ChevronRight className="h-4 w-4 text-[var(--ink-muted)]" />}
                <span className="text-sm font-semibold text-[var(--ink-strong)] flex-1 capitalize">{comp}</span>
                <div className="flex items-center gap-2">
                  {!compActive && (
                    <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded">Nicht lizenziert</span>
                  )}
                  <span className="text-xs text-[var(--ink-muted)]">{enabledCount}/{feats.length} aktiv</span>
                </div>
              </button>

              {open && (
                <div className="divide-y divide-[var(--border-subtle)] border-t border-[var(--border-subtle)]">
                  {feats.map(feat => {
                    const canToggle = compActive && feat.policy !== "locked" &&
                      !(feat.policy === "disable_only" && !feat.enabled);
                    const isSaving = saving === feat.slug;

                    return (
                      <div key={feat.slug}
                        className={`flex items-center gap-3 px-5 py-3 ${!feat.component_active ? "opacity-50" : ""}`}>
                        {/* Toggle */}
                        <button
                          onClick={() => canToggle && void toggleFeature(feat)}
                          disabled={!canToggle || isSaving}
                          className={`shrink-0 ${canToggle ? "cursor-pointer" : "cursor-not-allowed"}`}
                          title={!canToggle ? POLICY_LABELS[feat.policy] : undefined}
                        >
                          {feat.enabled
                            ? <ToggleRight className={`h-5 w-5 ${isSaving ? "animate-pulse" : "text-green-500"}`} />
                            : <ToggleLeft className={`h-5 w-5 ${isSaving ? "animate-pulse" : "text-slate-400"}`} />}
                        </button>

                        {/* Name */}
                        <div className="flex-1 min-w-0">
                          <span className="text-sm font-medium text-[var(--ink-strong)]">
                            {feat.slug.split(".").slice(1).join(".")}
                          </span>
                          <p className="text-xs text-[var(--ink-muted)] font-mono">{feat.slug}</p>
                        </div>

                        {/* Policy badge */}
                        <span className={`shrink-0 px-2 py-0.5 text-[10px] rounded border font-medium flex items-center gap-1 ${POLICY_COLOR[feat.policy] ?? ""}`}>
                          {feat.policy === "locked" ? <Lock className="h-3 w-3" /> : <Unlock className="h-3 w-3" />}
                          {POLICY_LABELS[feat.policy] ?? feat.policy}
                        </span>

                        {/* Pending indicator */}
                        {overrides?.find(o => o.feature_slug === feat.slug && o.approval_status === "pending") && (
                          <span className="text-xs text-amber-600 flex items-center gap-1 shrink-0">
                            <Clock className="h-3.5 w-3.5" /> Wartet
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
