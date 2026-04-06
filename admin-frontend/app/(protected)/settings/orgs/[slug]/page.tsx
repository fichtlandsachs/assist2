"use client";

import { use } from "react";

export default function OrgSettingsPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h1 className="text-xl font-semibold" style={{ color: "var(--ink)" }}>
          {slug}
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>
          Organisationsspezifische Einstellungen
        </p>
      </div>

      <div
        className="p-6 rounded-sm border text-center"
        style={{ borderColor: "var(--paper-rule)", background: "var(--card)" }}
      >
        <p className="text-sm font-medium" style={{ color: "var(--ink-mid)" }}>
          Noch nicht verfügbar
        </p>
        <p className="text-xs mt-2" style={{ color: "var(--ink-faint)" }}>
          Pro-Org-Einstellungen (Jira, Confluence, SSO) folgen in Phase 2.
        </p>
      </div>
    </div>
  );
}
