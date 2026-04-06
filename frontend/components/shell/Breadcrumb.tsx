"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { ChevronRight, Home } from "lucide-react";

const SEGMENT_LABELS: Record<string, string> = {
  dashboard:     "Dashboard",
  "ai-workspace": "Workspace",
  project:       "Projekte",
  stories:       "User Stories",
  inbox:         "Posteingang",
  calendar:      "Kalender",
  dateien:       "Dateien",
  workflows:     "Workflows",
  docs:          "Dokumentation",
  settings:      "Einstellungen",
  admin:         "Administration",
  board:         "Board",
  list:          "Liste",
  new:           "Neu",
  epics:         "Epics",
  features:      "Features",
};

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isUUID(s: string) {
  return UUID_RE.test(s);
}

export function Breadcrumb({ orgSlug }: { orgSlug: string }) {
  const pathname = usePathname();

  // Split path: /{org}/a/b/c → ["a", "b", "c"]
  const segments = pathname
    .split("/")
    .filter(Boolean)
    .slice(1); // drop org slug

  if (segments.length === 0) return null;

  // Build crumb chain
  const crumbs: { label: string; href: string }[] = [
    { label: "Home", href: `/${orgSlug}/dashboard` },
  ];

  let currentPath = `/${orgSlug}`;
  for (const seg of segments) {
    currentPath += `/${seg}`;
    const label = SEGMENT_LABELS[seg] ?? (isUUID(seg) ? "Detail" : seg);
    crumbs.push({ label, href: currentPath });
  }

  // Don't render if just Home
  if (crumbs.length <= 1) return null;

  return (
    <nav className="flex items-center gap-1 text-xs text-[var(--ink-faint)] mb-3 flex-wrap">
      {crumbs.map((crumb, i) => {
        const isLast = i === crumbs.length - 1;
        return (
          <span key={crumb.href} className="flex items-center gap-1">
            {i === 0 ? (
              <Link
                href={crumb.href}
                className="flex items-center gap-1 hover:text-[var(--ink-mid)] transition-colors"
              >
                <Home size={11} />
              </Link>
            ) : isLast ? (
              <span className="font-medium text-[var(--ink-mid)]">{crumb.label}</span>
            ) : (
              <Link
                href={crumb.href}
                className="hover:text-[var(--ink-mid)] transition-colors"
              >
                {crumb.label}
              </Link>
            )}
            {!isLast && <ChevronRight size={10} className="opacity-40 shrink-0" />}
          </span>
        );
      })}
    </nav>
  );
}
