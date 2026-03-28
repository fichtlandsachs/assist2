"use client";

import { useAuth } from "@/lib/auth/context";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import { Sidebar } from "@/components/shell/Sidebar";
import { Topbar } from "@/components/shell/Topbar";
import { useOrg } from "@/lib/hooks/useOrg";

export default function OrgLayout({
  children,
  params
}: {
  children: React.ReactNode;
  params: Promise<{ org: string }>;
}) {
  const resolvedParams = use(params);
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const { org } = useOrg(resolvedParams.org);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8" style={{ borderBottom: "2px solid var(--ink-mid)" }} />
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--paper)" }}>
      <Sidebar
        orgSlug={resolvedParams.org}
        orgId={org?.id}
        mobileOpen={mobileSidebarOpen}
        onMobileClose={() => setMobileSidebarOpen(false)}
      />
      <div className="flex flex-col flex-1 overflow-hidden min-w-0">
        <Topbar
          orgSlug={resolvedParams.org}
          orgId={org?.id}
          onMenuClick={() => setMobileSidebarOpen(true)}
        />
        <main
          className="flex-1 overflow-y-auto overflow-x-hidden p-4 md:p-6"
          style={{
            background: `var(--paper) repeating-linear-gradient(180deg, transparent, transparent calc(var(--line-h) - 1px), var(--paper-rule) calc(var(--line-h) - 1px), var(--paper-rule) var(--line-h))`
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
