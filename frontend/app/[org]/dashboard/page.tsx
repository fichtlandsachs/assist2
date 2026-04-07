"use client";

import { use, useMemo } from "react";
import { useAuth } from "@/lib/auth/context";
import { useOrg } from "@/lib/hooks/useOrg";
import { fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { UserStory } from "@/types";
import Link from "next/link";
import {
  CheckCircle2,
  Clock,
  Zap,
  ArrowUpRight,
  TrendingUp,
  Plus,
  LayoutGrid,
  Sparkles,
  Target,
} from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────
interface OrgStats {
  stories: Record<string, number>;
  story_points_total: number;
  story_points_done: number;
  velocity: { week: string; count: number; points: number }[];
}

// ── Static burndown data ───────────────────────────────────────────────────────
const burndown = [
  { d: "T1", r: 80, i: 80 },
  { d: "T2", r: 72, i: 70 },
  { d: "T3", r: 60, i: 60 },
  { d: "T4", r: 55, i: 50 },
  { d: "T5", r: 40, i: 40 },
  { d: "T6", r: 28, i: 30 },
  { d: "T7", r: 20, i: 20 },
  { d: "T8", r: 10, i: 10 },
  { d: "T9", r: 4,  i: 0  },
];

function MiniChart() {
  const W = 420, H = 140, P = 24;
  const xs = burndown.map((_, i) => P + (i / (burndown.length - 1)) * (W - P * 2));
  const y  = (v: number) => P + (1 - v / 80) * (H - P * 2);
  const rp = burndown.map((d, i) => `${i === 0 ? "M" : "L"}${xs[i]},${y(d.r)}`).join(" ");
  const ip = burndown.map((d, i) => `${i === 0 ? "M" : "L"}${xs[i]},${y(d.i)}`).join(" ");
  const ap = rp + ` L${xs[xs.length-1]},${H-P} L${xs[0]},${H-P} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-full">
      {[0,40,80].map(v => (
        <line key={v} x1={P} x2={W-P} y1={y(v)} y2={y(v)} stroke="rgba(0,0,0,0.06)" strokeDasharray="5 5"/>
      ))}
      <path d={ap} fill="rgba(244,63,94,0.08)" />
      <path d={ip} stroke="#cbd5e1" strokeWidth={1.5} strokeDasharray="8 5" fill="none"/>
      <path d={rp} stroke="#f43f5e" strokeWidth={2.5} fill="none" strokeLinecap="round" strokeLinejoin="round"/>
      {burndown.map((d, i) => (
        <circle key={i} cx={xs[i]} cy={y(d.r)} r={3.5} fill="#f43f5e" stroke="#fff" strokeWidth={2}/>
      ))}
      {burndown.map((d, i) => (
        <text key={i} x={xs[i]} y={H-2} textAnchor="middle" fontSize={9} fill="#94a3b8" fontFamily="Architects Daughter" fontWeight={700}>{d.d}</text>
      ))}
    </svg>
  );
}

// ── Story row ─────────────────────────────────────────────────────────────────
const STATUS_STYLE: Record<string, string> = {
  done:        "bg-emerald-100 text-emerald-700 border-emerald-200",
  in_progress: "bg-rose-100 text-rose-600 border-rose-200",
  in_review:   "bg-sky-100 text-sky-700 border-sky-200",
  ready:       "bg-teal-100 text-teal-700 border-teal-200",
  testing:     "bg-amber-100 text-amber-700 border-amber-200",
  draft:       "bg-slate-100 text-slate-500 border-slate-200",
};
const STATUS_LABEL: Record<string, string> = {
  done: "Done", in_progress: "In Arbeit", in_review: "Review",
  ready: "Ready", testing: "Testing", draft: "Draft",
};

function StoryRow({ story, orgSlug }: { story: UserStory; orgSlug: string }) {
  const cls = STATUS_STYLE[story.status] ?? STATUS_STYLE.draft;
  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-slate-100 last:border-0">
      <span className={`shrink-0 text-[8px] font-bold uppercase px-2 py-0.5 rounded-full border font-['Architects_Daughter'] ${cls}`}>
        {STATUS_LABEL[story.status] ?? story.status}
      </span>
      <Link
        href={`/${orgSlug}/stories/${story.id}`}
        className="flex-1 text-[12px] text-slate-700 font-['Architects_Daughter'] truncate hover:text-rose-500 hover:underline transition-colors"
      >
        {story.title}
      </Link>
      {story.story_points != null && (
        <span className="shrink-0 text-[10px] font-bold text-slate-400 font-['Architects_Daughter']">
          {story.story_points}P
        </span>
      )}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function DashboardPage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { user } = useAuth();
  const { org }  = useOrg(resolvedParams.org);

  const { data: stories }  = useSWR<UserStory[]>(
    org ? `/api/v1/user-stories?org_id=${org.id}&page_size=6` : null, fetcher
  );
  const { data: orgStats } = useSWR<OrgStats>(
    org ? `/api/v1/orgs/${org.id}/stats` : null, fetcher
  );

  const s = useMemo(() => {
    if (!stories) return null;
    const total = stories.length;
    const done  = stories.filter(x => x.status === "done").length;
    const active = stories.filter(x => ["in_progress","in_review","testing"].includes(x.status)).length;
    return { total, done, active, donePct: total > 0 ? Math.round(done / total * 100) : 0 };
  }, [stories]);

  const firstName = user?.display_name?.split(" ")[0] ?? "Team";
  const hour = new Date().getHours();
  const greeting = hour < 10 ? "Guten Morgen" : hour < 18 ? "Hallo" : "Guten Abend";

  const topStories = (stories ?? []).slice(0, 5);

  return (
    <div className="relative min-h-screen font-sans overflow-x-hidden">


      {/* ── Content — right padding so Karl doesn't overlap on large screens ── */}
      <div
        className="relative z-10 max-w-5xl mx-auto space-y-5 pb-16"
        style={{ paddingRight: "clamp(0px, 16vw, 240px)" }}
      >

        {/* ── 1. Header ──────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] font-bold tracking-[0.2em] text-rose-500 uppercase font-['Architects_Daughter']">
              {org?.name ?? "Workspace"}
            </p>
            <h1 className="text-2xl sm:text-3xl font-black text-slate-900 leading-tight">
              {greeting}, <span className="text-rose-500">{firstName}!</span>
            </h1>
          </div>
          <Link
            href={`/${resolvedParams.org}/stories/new`}
            className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 text-white text-[11px] font-bold font-['Architects_Daughter'] rounded-xl border-2 border-slate-900 shadow-[3px_3px_0_rgba(0,0,0,1)] hover:shadow-[1px_1px_0_rgba(0,0,0,1)] hover:translate-x-[2px] hover:translate-y-[2px] transition-all"
          >
            <Plus size={13} /> Neue Story
          </Link>
        </div>

        {/* ── 2. KPI row ─────────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            {
              icon: CheckCircle2,
              label: "Done",
              value: s ? `${s.donePct}%` : "—",
              sub: s ? `${s.done} von ${s.total}` : "Stories",
              color: "text-emerald-600",
              bg: "bg-emerald-50",
            },
            {
              icon: Zap,
              label: "Aktiv",
              value: s ? String(s.active) : "—",
              sub: "In Arbeit",
              color: "text-rose-500",
              bg: "bg-rose-50",
            },
            {
              icon: TrendingUp,
              label: "Velocity",
              value: orgStats?.story_points_done != null ? `${orgStats.story_points_done}P` : "—",
              sub: "Story Points",
              color: "text-amber-600",
              bg: "bg-amber-50",
            },
            {
              icon: Target,
              label: "Gesamt",
              value: orgStats?.story_points_total != null ? `${orgStats.story_points_total}P` : s ? String(s.total) : "—",
              sub: orgStats ? "Points im Sprint" : "Stories total",
              color: "text-sky-600",
              bg: "bg-sky-50",
            },
          ].map(({ icon: Icon, label, value, sub, color, bg }) => (
            <div
              key={label}
              className="bg-white border-2 border-slate-900 rounded-2xl p-4 shadow-[3px_3px_0_rgba(0,0,0,1)] hover:-translate-y-0.5 hover:shadow-[5px_5px_0_rgba(0,0,0,1)] transition-all"
            >
              <div className={`w-8 h-8 rounded-lg ${bg} ${color} flex items-center justify-center mb-3 border border-current/10`}>
                <Icon size={15} />
              </div>
              <div className="text-2xl font-black text-slate-900 leading-none">{value}</div>
              <div className="text-[9px] font-bold uppercase text-slate-400 mt-1 font-['Architects_Daughter']">{sub}</div>
            </div>
          ))}
        </div>

        {/* ── 3. Main grid ───────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">

          {/* Burndown – 3 cols */}
          <section className="lg:col-span-3 bg-white border-2 border-slate-900 rounded-2xl p-5 shadow-[4px_4px_0_rgba(0,0,0,1)]">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-[11px] font-bold tracking-[0.18em] text-slate-800 uppercase font-['Architects_Daughter']">Burndown</h2>
                <p className="text-[9px] text-slate-400 font-['Architects_Daughter'] mt-0.5">Sprint-Verlauf</p>
              </div>
              <div className="flex items-center gap-4 text-[9px] font-bold uppercase font-['Architects_Daughter']">
                <span className="flex items-center gap-1.5 text-rose-400">
                  <span className="w-3 h-0.5 bg-rose-400 rounded-full inline-block" />Real
                </span>
                <span className="flex items-center gap-1.5 text-slate-300">
                  <span className="w-3 h-0.5 bg-slate-300 rounded-full inline-block" />Plan
                </span>
              </div>
            </div>
            <div className="h-[140px] w-full">
              <MiniChart />
            </div>
          </section>

          {/* Quick actions – 2 cols */}
          <section className="lg:col-span-2 flex flex-col gap-3">
            <div className="bg-rose-500 border-2 border-slate-900 rounded-2xl p-5 shadow-[4px_4px_0_rgba(0,0,0,1)] flex-1 relative overflow-hidden">
              <div className="absolute -top-3 -right-3 opacity-10">
                <Sparkles size={80} />
              </div>
              <p className="text-[9px] font-bold text-white/70 uppercase tracking-widest font-['Architects_Daughter'] mb-2">Karls Tipp</p>
              <p className="text-[13px] font-['Architects_Daughter'] text-white leading-snug">
                {s?.donePct != null && s.donePct >= 70
                  ? "Stark! Ihr seid auf Kurs. Fokus auf die letzten offenen Stories."
                  : "Checkt die blockierten Stories — Karl hilft beim Formulieren!"}
              </p>
              <Link
                href={`/${resolvedParams.org}/ai-workspace`}
                className="mt-4 inline-flex items-center gap-1.5 text-[10px] font-bold bg-white text-slate-900 px-3 py-1.5 rounded-lg border-2 border-slate-900 shadow-[2px_2px_0_rgba(0,0,0,1)] hover:shadow-none hover:translate-x-px hover:translate-y-px transition-all font-['Architects_Daughter']"
              >
                Frag Karl <ArrowUpRight size={11} />
              </Link>
            </div>

            <div className="bg-slate-900 border-2 border-slate-900 rounded-2xl p-4 shadow-[4px_4px_0_rgba(0,0,0,1)] space-y-2">
              {[
                { label: "Stories Board", href: `/${resolvedParams.org}/stories/board`, icon: LayoutGrid, color: "text-rose-400" },
                { label: "Sprint planen", href: `/${resolvedParams.org}/stories/epics`, icon: Target, color: "text-amber-400" },
                { label: "Neue Story", href: `/${resolvedParams.org}/stories/new`, icon: Plus, color: "text-sky-400" },
              ].map(({ label, href, icon: Icon, color }) => (
                <Link
                  key={label}
                  href={href}
                  className="flex items-center justify-between px-3 py-2.5 rounded-xl hover:bg-white/5 transition-colors group"
                >
                  <div className="flex items-center gap-2.5">
                    <Icon size={13} className={color} />
                    <span className={`text-[11px] font-bold font-['Architects_Daughter'] ${color}`}>{label}</span>
                  </div>
                  <ArrowUpRight size={11} className="text-white/20 group-hover:text-white/60 transition-colors" />
                </Link>
              ))}
            </div>
          </section>
        </div>

        {/* ── 4. Recent Stories ──────────────────────────────────────────── */}
        {topStories.length > 0 && (
          <section className="bg-white border-2 border-slate-900 rounded-2xl p-5 shadow-[4px_4px_0_rgba(0,0,0,1)]">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[11px] font-bold tracking-[0.18em] text-slate-800 uppercase font-['Architects_Daughter']">Aktuelle Stories</h2>
              <Link
                href={`/${resolvedParams.org}/stories/list`}
                className="text-[9px] font-bold text-rose-500 uppercase font-['Architects_Daughter'] hover:underline flex items-center gap-1"
              >
                Alle <ArrowUpRight size={10} />
              </Link>
            </div>
            <div>
              {topStories.map(story => <StoryRow key={story.id} story={story} orgSlug={resolvedParams.org} />)}
            </div>
          </section>
        )}

        {/* Empty state */}
        {stories?.length === 0 && (
          <div className="bg-white border-2 border-slate-900 rounded-2xl p-10 shadow-[4px_4px_0_rgba(0,0,0,1)] text-center space-y-3">
            <p className="text-[14px] font-['Architects_Daughter'] text-slate-500">Noch keine Stories — leg gleich los!</p>
            <Link
              href={`/${resolvedParams.org}/stories/new`}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-slate-900 text-white text-[11px] font-bold rounded-xl border-2 border-slate-900 shadow-[3px_3px_0_rgba(0,0,0,1)] hover:shadow-none hover:translate-x-px hover:translate-y-px transition-all font-['Architects_Daughter']"
            >
              <Plus size={13} /> Erste Story anlegen
            </Link>
          </div>
        )}

      </div>

      {/* Bottom spacer so content doesn't hide behind Karl */}
      <div className="h-4 lg:h-0" />
    </div>
  );
}
