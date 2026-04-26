"use client";

import { use, useMemo, useState } from "react";
import { useOrg } from "@/lib/hooks/useOrg";
import { fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { UserStory } from "@/types";
import Link from "next/link";
import {
  ShieldCheck, AlertTriangle, CheckCircle2, XCircle,
  TrendingUp, Star, ArrowUpRight, Target, Layers,
} from "lucide-react";
import { useT } from "@/lib/i18n/context";
import { ControlCapabilityMap } from "@/components/governance/ControlCapabilityMap";

function GaugeMeter({ pct, color }: { pct: number; color: string }) {
  const R = 40;
  const C = 2 * Math.PI * R;
  const dash = (pct / 100) * C;
  return (
    <svg viewBox="0 0 100 55" className="w-full h-full">
      <path d="M 10,50 A 40,40 0 0 1 90,50" fill="none" stroke="rgba(0,0,0,.06)" strokeWidth={10} strokeLinecap="round" />
      <path
        d="M 10,50 A 40,40 0 0 1 90,50"
        fill="none"
        stroke={color}
        strokeWidth={10}
        strokeLinecap="round"
        strokeDasharray={`${(dash / C) * (C / 2)} ${C}`}
        transform="rotate(0 50 50)"
        style={{ transition: "stroke-dasharray .6s ease" }}
      />
      <text x="50" y="46" textAnchor="middle" fontSize={14} fontFamily="Architects Daughter" fontWeight={700} fill="currentColor">
        {pct}%
      </text>
    </svg>
  );
}

function StatCard({ label, value, sub, icon: Icon, accent }: {
  label: string; value: string | number; sub?: string;
  icon: React.ElementType; accent: string;
}) {
  return (
    <div className="bg-[var(--card)] border-2 border-[var(--ink)]/8 rounded-2xl p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-bold tracking-[0.15em] text-[var(--ink-faint)] uppercase">{label}</span>
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${accent}`}>
          <Icon size={14} />
        </div>
      </div>
      <div>
        <p className="text-3xl font-black text-[var(--ink)]">{value}</p>
        {sub && <p className="text-[11px] text-[var(--ink-faint)] mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

type ComplianceTab = "quality" | "controls";

export default function CompliancePage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { org } = useOrg(resolvedParams.org);
  const { t } = useT();
  const [activeTab, setActiveTab] = useState<ComplianceTab>("quality");

  const { data: stories, isLoading } = useSWR<UserStory[]>(
    org ? `/api/v1/user-stories?org_id=${org.id}&page_size=500` : null,
    fetcher
  );

  const metrics = useMemo(() => {
    if (!stories) return null;
    const total = stories.length;
    const scored = stories.filter(s => s.quality_score !== null);
    const highScore = scored.filter(s => (s.quality_score ?? 0) >= 80);
    const midScore = scored.filter(s => (s.quality_score ?? 0) >= 60 && (s.quality_score ?? 0) < 80);
    const lowScore = scored.filter(s => (s.quality_score ?? 0) < 60);
    const unscored = stories.filter(s => s.quality_score === null);
    const dorPassed = stories.filter(s => s.dor_passed);
    const avgScore = scored.length > 0
      ? Math.round(scored.reduce((sum, s) => sum + (s.quality_score ?? 0), 0) / scored.length)
      : 0;
    const compliancePct = total > 0 ? Math.round((highScore.length / total) * 100) : 0;
    const dorPct = total > 0 ? Math.round((dorPassed.length / total) * 100) : 0;
    const scoredPct = total > 0 ? Math.round((scored.length / total) * 100) : 0;

    return {
      total, scored, highScore, midScore, lowScore, unscored, dorPassed,
      avgScore, compliancePct, dorPct, scoredPct,
    };
  }, [stories]);

  const worstStories = useMemo(() =>
    (stories ?? [])
      .filter(s => s.quality_score !== null && s.quality_score < 80)
      .sort((a, b) => (a.quality_score ?? 0) - (b.quality_score ?? 0))
      .slice(0, 8),
    [stories]
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-black text-[var(--ink)]">{t("nav_compliance")}</h1>
          <p className="text-[12px] text-[var(--ink-faint)] mt-1">
            {t("compliance_subtitle")}
          </p>
        </div>
        <Link
          href={`/${resolvedParams.org}/stories/board`}
          className="flex items-center gap-1.5 px-3 py-1.5 border-2 border-[var(--ink)]/10 rounded-xl text-[11px] font-bold text-[var(--ink-mid)] hover:border-[var(--ink)]/30 transition-colors"
        >
          {t("nav_stories")} <ArrowUpRight size={12} />
        </Link>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-[var(--paper-rule)]">
        {([
          { id: "quality" as ComplianceTab, label: "Story-Qualität", icon: Star },
          { id: "controls" as ComplianceTab, label: "Controls & Capabilities", icon: Layers },
        ] as const).map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-1.5 px-4 py-2 text-[12px] font-bold border-b-2 transition-colors -mb-px whitespace-nowrap ${
              activeTab === id
                ? "border-[var(--accent-red)] text-[var(--accent-red)]"
                : "border-transparent text-[var(--ink-faint)] hover:text-[var(--ink-mid)]"
            }`}
          >
            <Icon size={13} />
            {label}
          </button>
        ))}
      </div>

      {/* Controls & Capabilities tab */}
      {activeTab === "controls" && org && (
        <div className="space-y-4">
          <ControlCapabilityMap orgId={org.id} />
        </div>
      )}

      {/* Story quality tab — original content below */}
      {activeTab === "quality" && isLoading && (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--ink)]" />
        </div>
      )}

      {activeTab === "quality" && metrics && (
        <>
          {/* KPI row */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label={t("compliance_rate")}
              value={`${metrics.compliancePct}%`}
              sub={`${metrics.highScore.length} / ${metrics.total} Stories ≥ 80`}
              icon={ShieldCheck}
              accent="bg-emerald-50 text-emerald-600"
            />
            <StatCard
              label={t("compliance_avg_score")}
              value={metrics.avgScore > 0 ? metrics.avgScore : "—"}
              sub={`${metrics.scored.length} ${t("compliance_of")} ${metrics.total} ${t("compliance_scored")}`}
              icon={Star}
              accent="bg-amber-50 text-amber-600"
            />
            <StatCard
              label={t("compliance_dor_label")}
              value={`${metrics.dorPct}%`}
              sub={`${metrics.dorPassed.length} ${t("compliance_stories_passed")}`}
              icon={CheckCircle2}
              accent="bg-sky-50 text-sky-600"
            />
            <StatCard
              label={t("compliance_evaluated")}
              value={`${metrics.scoredPct}%`}
              sub={`${metrics.unscored.length} ${t("compliance_not_yet_reviewed")}`}
              icon={Target}
              accent="bg-violet-50 text-violet-600"
            />
          </div>

          {/* Score distribution + gauge */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Gauge */}
            <div className="bg-[var(--card)] border-2 border-[var(--ink)]/8 rounded-2xl p-6 flex flex-col items-center justify-center gap-2">
              <p className="text-[10px] font-bold tracking-[0.15em] text-[var(--ink-faint)] uppercase">
                {t("compliance_score_label")}
              </p>
              <div className="w-40 h-24">
                <GaugeMeter
                  pct={metrics.compliancePct}
                  color={metrics.compliancePct >= 80 ? "#10B981" : metrics.compliancePct >= 60 ? "#F59E0B" : "#EF4444"}
                />
              </div>
              <p className="text-[11px] text-[var(--ink-faint)] text-center">
                {metrics.compliancePct >= 80
                  ? t("compliance_goal_reached")
                  : `${t("compliance_goal_prefix")} 80% — ${t("compliance_goal_remaining_prefix")} ${80 - metrics.compliancePct}% ${t("compliance_goal_remaining_suffix")}`}
              </p>
            </div>

            {/* Distribution bars */}
            <div className="lg:col-span-2 bg-[var(--card)] border-2 border-[var(--ink)]/8 rounded-2xl p-6">
              <p className="text-[10px] font-bold tracking-[0.15em] text-[var(--ink-faint)] uppercase mb-4">
                {t("compliance_distribution")}
              </p>
              <div className="space-y-3">
                {[
                  { labelKey: "compliance_dist_high", count: metrics.highScore.length, color: "bg-emerald-500", icon: CheckCircle2, textColor: "text-emerald-700" },
                  { labelKey: "compliance_dist_mid", count: metrics.midScore.length, color: "bg-amber-400", icon: AlertTriangle, textColor: "text-amber-700" },
                  { labelKey: "compliance_dist_low", count: metrics.lowScore.length, color: "bg-red-500", icon: XCircle, textColor: "text-red-700" },
                  { labelKey: "compliance_dist_unscored", count: metrics.unscored.length, color: "bg-slate-200", icon: Star, textColor: "text-[var(--ink-faint)]" },
                ].map(({ labelKey, count, color, icon: Icon, textColor }) => {
                  const pct = metrics.total > 0 ? Math.round((count / metrics.total) * 100) : 0;
                  const label = t(labelKey as Parameters<typeof t>[0]);
                  return (
                    <div key={labelKey} className="flex items-center gap-3">
                      <Icon size={13} className={textColor} />
                      <span className="text-[11px] font-bold text-[var(--ink-mid)] w-32 flex-shrink-0">{label}</span>
                      <div className="flex-1 bg-[var(--paper-warm)] rounded-full h-2 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${color} transition-all duration-500`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-[11px] font-bold text-[var(--ink-mid)] w-12 text-right">{count} ({pct}%)</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Stories requiring attention */}
          {worstStories.length > 0 && (
            <div className="bg-white border-2 border-[var(--ink)]/8 rounded-2xl overflow-hidden">
              <div className="px-6 py-4 border-b border-[var(--ink)]/5 flex items-center gap-2">
                <AlertTriangle size={15} className="text-amber-500" />
                <h2 className="font-bold text-[var(--ink)]">{t("compliance_needs_attention")}</h2>
                <span className="ml-auto text-[10px] text-[var(--ink-faint)]">Score &lt; 80</span>
              </div>
              <div className="divide-y divide-slate-900/5">
                {worstStories.map(story => {
                  const score = story.quality_score ?? 0;
                  const scoreColor = score >= 60 ? "text-amber-600 bg-amber-50" : "text-red-600 bg-red-50";
                  return (
                    <div key={story.id} className="flex items-center gap-4 px-6 py-3 hover:bg-[var(--paper-warm)] transition-colors">
                      <span className={`text-[11px] font-black px-2 py-0.5 rounded-lg ${scoreColor}`}>
                        {score}
                      </span>
                      <Link
                        href={`/${resolvedParams.org}/stories/${story.id}`}
                        className="flex-1 text-[13px] font-bold text-[var(--ink)] hover:text-teal-600 transition-colors truncate"
                      >
                        {story.title}
                      </Link>
                      <span className="text-[10px] text-[var(--ink-faint)] flex-shrink-0">
                        {story.status}
                      </span>
                      <Link
                        href={`/${resolvedParams.org}/stories/${story.id}`}
                        className="p-1 text-[var(--ink-faintest)] hover:text-teal-600 transition-colors flex-shrink-0"
                      >
                        <ArrowUpRight size={14} />
                      </Link>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* DoR overview */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white border-2 border-[var(--ink)]/8 rounded-2xl p-6">
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp size={15} className="text-teal-500" />
                <p className="text-[10px] font-bold tracking-[0.15em] text-[var(--ink-faint)] uppercase">
                  {t("story_detail_dor")}
                </p>
              </div>
              <div className="flex items-center gap-6">
                <div className="text-center">
                  <p className="text-4xl font-black text-[var(--ink)]">{metrics.dorPassed.length}</p>
                  <p className="text-[10px] text-emerald-600 font-bold mt-0.5">{t("compliance_dor_passed")}</p>
                </div>
                <div className="text-center">
                  <p className="text-4xl font-black text-[var(--ink-faint)]">{metrics.total - metrics.dorPassed.length}</p>
                  <p className="text-[10px] text-[var(--ink-faint)] font-bold mt-0.5">{t("compliance_dor_failed")}</p>
                </div>
              </div>
            </div>

            <div className="bg-white border-2 border-[var(--ink)]/8 rounded-2xl p-6">
              <div className="flex items-center gap-2 mb-4">
                <Star size={15} className="text-violet-500" />
                <p className="text-[10px] font-bold tracking-[0.15em] text-[var(--ink-faint)] uppercase">
                  {t("compliance_review_status")}
                </p>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-[12px]">
                  <span className="text-[var(--ink-mid)] font-bold">{t("compliance_evaluated")}</span>
                  <span className="font-black text-[var(--ink)]">{metrics.scored.length}</span>
                </div>
                <div className="w-full bg-[var(--paper-warm)] rounded-full h-3">
                  <div
                    className="h-full rounded-full bg-violet-500 transition-all duration-500"
                    style={{ width: `${metrics.scoredPct}%` }}
                  />
                </div>
                <div className="flex items-center justify-between text-[11px] text-[var(--ink-faint)]">
                  <span>0</span>
                  <span>{metrics.total} {t("compliance_total")}</span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
