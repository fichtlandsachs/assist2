"use client";

import Link from "next/link";
import useSWR from "swr";

import { fetcher } from "@/lib/api/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type StoryStatus =
  | "draft"
  | "ready"
  | "in_progress"
  | "in_review"
  | "done"
  | "cancelled";

interface PaginatedResponse {
  items: unknown[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

interface StoryDashboardWidgetProps {
  orgSlug: string;
}

// ---------------------------------------------------------------------------
// Stat Card
// ---------------------------------------------------------------------------

interface StatCardProps {
  label: string;
  count: number;
  colorClass: string;
}

function StatCard({ label, count, colorClass }: StatCardProps) {
  return (
    <div className={`rounded-lg p-3 ${colorClass}`}>
      <p className="text-2xl font-bold">{count}</p>
      <p className="text-xs font-medium mt-0.5">{label}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StoryDashboardWidget Component
// ---------------------------------------------------------------------------

export function StoryDashboardWidget({ orgSlug }: StoryDashboardWidgetProps) {
  // Fetch counts per status using page_size=1 to minimize payload
  const makeKey = (status: StoryStatus) =>
    `/api/v1/organizations/${orgSlug}/stories?status=${status}&page=1&page_size=1`;

  const { data: draftData } = useSWR<PaginatedResponse>(makeKey("draft"), fetcher);
  const { data: readyData } = useSWR<PaginatedResponse>(makeKey("ready"), fetcher);
  const { data: inProgressData } = useSWR<PaginatedResponse>(makeKey("in_progress"), fetcher);
  const { data: inReviewData } = useSWR<PaginatedResponse>(makeKey("in_review"), fetcher);
  const { data: doneData } = useSWR<PaginatedResponse>(makeKey("done"), fetcher);
  const { data: allData } = useSWR<PaginatedResponse>(
    `/api/v1/organizations/${orgSlug}/stories?page=1&page_size=1`,
    fetcher
  );

  const stats = [
    {
      label: "Entwurf",
      count: draftData?.total ?? 0,
      colorClass: "bg-gray-50 text-gray-700",
    },
    {
      label: "Bereit",
      count: readyData?.total ?? 0,
      colorClass: "bg-blue-50 text-blue-700",
    },
    {
      label: "In Arbeit",
      count: inProgressData?.total ?? 0,
      colorClass: "bg-yellow-50 text-yellow-800",
    },
    {
      label: "In Review",
      count: inReviewData?.total ?? 0,
      colorClass: "bg-purple-50 text-purple-700",
    },
    {
      label: "Fertig",
      count: doneData?.total ?? 0,
      colorClass: "bg-green-50 text-green-700",
    },
  ];

  const total = allData?.total ?? 0;

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
      {/* Widget Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-lg">📋</span>
          <h3 className="text-sm font-semibold text-gray-900">User Stories</h3>
        </div>
        <span className="text-xs text-gray-500">{total} gesamt</span>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-5 gap-2 mb-4">
        {stats.map((stat) => (
          <StatCard
            key={stat.label}
            label={stat.label}
            count={stat.count}
            colorClass={stat.colorClass}
          />
        ))}
      </div>

      {/* Progress Bar (done / total) */}
      {total > 0 && (
        <div className="mb-4">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Fortschritt</span>
            <span>
              {doneData?.total ?? 0} / {total} fertig
            </span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 rounded-full transition-all duration-500"
              style={{
                width: total > 0 ? `${Math.round(((doneData?.total ?? 0) / total) * 100)}%` : "0%",
              }}
            />
          </div>
        </div>
      )}

      {/* Link to full list */}
      <Link
        href={`/${orgSlug}/stories`}
        className="block text-center text-xs text-blue-600 hover:text-blue-700 font-medium transition-colors"
      >
        Alle Stories anzeigen →
      </Link>
    </div>
  );
}
