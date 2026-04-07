"use client";

import { use } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

interface Props {
  children: React.ReactNode;
  params: Promise<{ org: string }>;
}

export default function StoriesLayout({ children, params }: Props) {
  const { org } = use(params);
  const pathname = usePathname();

  const tabs = [
    { label: "Epics",        href: `/${org}/stories/epics/board` },
    { label: "User Stories", href: `/${org}/stories/board` },
    { label: "Features",     href: `/${org}/stories/features/board` },
  ];

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-1 mb-4 border-b-2 border-[var(--ink)]/5 pb-0">
        {tabs.map(tab => {
          const segment = tab.href.split("/")[3];
          const isActive = pathname.includes(`/stories/${segment}`) ||
            (segment === "board" && pathname.endsWith("/stories/board")) ||
            (segment === "board" && pathname.includes("/stories/board/"));
          // Special case: "stories/board" vs "stories/epics/board"
          const isEpics = tab.label === "Epics" && pathname.includes("/stories/epics");
          const isFeatures = tab.label === "Features" && pathname.includes("/stories/features");
          const isStories = tab.label === "User Stories" && !pathname.includes("/stories/epics") && !pathname.includes("/stories/features") && (pathname.includes("/stories/board") || pathname.includes("/stories/list") || pathname.includes("/stories/new") || /\/stories\/[^/]+$/.test(pathname));
          const active = isEpics || isFeatures || isStories;
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`px-4 py-2 text-[12px] font-bold tracking-wide transition-colors border-b-2 -mb-[2px] ${
                active
                  ? "text-[var(--ink)] border-[var(--ink)]"
                  : "text-[var(--ink-faint)] border-transparent hover:text-[var(--ink-mid)] hover:border-slate-300"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>
      <div className="flex-1 min-h-0">{children}</div>
    </div>
  );
}
