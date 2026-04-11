"use client";

import { use } from "react";
import { useOrg } from "@/lib/hooks/useOrg";
import { MembersSection } from "@/components/settings/MembersSection";

export default function MembersPage({ params }: { params: Promise<{ org: string }> }) {
  const { org: orgSlug } = use(params);
  const { org } = useOrg(orgSlug);

  if (!org) {
    return (
      <div className="flex items-center justify-center h-40">
        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--accent-red)]" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <MembersSection orgId={org.id} />
    </div>
  );
}
