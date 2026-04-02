"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { fetcher, getAccessToken } from "@/lib/api/client";
import { useOrg } from "@/lib/hooks/useOrg";
import { PdfSettingsForm } from "@/components/admin/PdfSettingsForm";
import { TemplateUpload } from "@/components/admin/TemplateUpload";

interface PdfSettings {
  id?: string;
  company_name?: string | null;
  page_format: string;
  language: string;
  header_text?: string | null;
  footer_text?: string | null;
  letterhead_filename?: string | null;
  logo_filename?: string | null;
}

export default function PdfAdminPage() {
  const params = useParams<{ org: string }>();
  const orgSlug = params.org;

  const { org } = useOrg(orgSlug);

  const { data: settings, mutate } = useSWR<PdfSettings>(
    org ? `/api/v1/organizations/${org.id}/pdf-settings` : null,
    fetcher
  );

  const [previewLoading, setPreviewLoading] = useState(false);

  const handlePreview = async () => {
    if (!org) return;
    setPreviewLoading(true);
    try {
      const token = getAccessToken();
      const res = await fetch(`/api/v1/organizations/${org.id}/pdf-settings/preview`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Vorschau fehlgeschlagen");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
    } catch {
      alert("Vorschau-Generierung fehlgeschlagen. Ist Stirling PDF erreichbar?");
    } finally {
      setPreviewLoading(false);
    }
  };

  if (!org || !settings) {
    return <div className="p-8 text-[var(--ink-faint)]">Lade Einstellungen…</div>;
  }

  const baseUrl = `/api/v1/organizations/${org.id}/pdf-settings`;

  return (
    <div className="max-w-2xl mx-auto p-8 space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-[var(--ink)]">PDF-Einstellungen</h1>
        <p className="mt-1 text-sm text-[var(--ink-faint)]">
          Konfiguriert das automatisch generierte PDF für Userstories (Status: Done).
        </p>
      </div>

      <section className="bg-[var(--paper)] border border-[var(--paper-rule)] rounded-sm p-6 space-y-6">
        <h2 className="text-lg font-semibold text-[var(--ink)]">Branding</h2>
        <PdfSettingsForm
          orgSlug={orgSlug}
          orgId={org.id}
          initialSettings={settings}
          onSaved={() => mutate()}
        />
      </section>

      <section className="bg-[var(--paper)] border border-[var(--paper-rule)] rounded-sm p-6 space-y-6">
        <h2 className="text-lg font-semibold text-[var(--ink)]">Templates</h2>
        <TemplateUpload
          label="Briefpapier (PDF, max. 5 MB)"
          accept="application/pdf"
          uploadUrl={`${baseUrl}/letterhead`}
          deleteUrl={`${baseUrl}/letterhead`}
          currentFilename={settings.letterhead_filename ?? null}
          onSuccess={() => mutate()}
        />
        <TemplateUpload
          label="Logo (PNG/JPG, max. 1 MB)"
          accept="image/png,image/jpeg"
          uploadUrl={`${baseUrl}/logo`}
          deleteUrl={`${baseUrl}/logo`}
          currentFilename={settings.logo_filename ?? null}
          onSuccess={() => mutate()}
        />
      </section>

      <section className="bg-[var(--paper)] border border-[var(--paper-rule)] rounded-sm p-6">
        <h2 className="text-lg font-semibold text-[var(--ink)] mb-3">Vorschau</h2>
        <p className="text-sm text-[var(--ink-faint)] mb-4">
          Generiert ein Beispiel-PDF mit den aktuellen Einstellungen.
        </p>
        <button
          onClick={handlePreview}
          disabled={previewLoading}
          className="px-4 py-2 bg-[var(--ink)] text-white text-sm rounded-sm hover:bg-[var(--ink-mid)] disabled:opacity-50"
        >
          {previewLoading ? "Wird generiert…" : "PDF-Vorschau öffnen"}
        </button>
      </section>
    </div>
  );
}
