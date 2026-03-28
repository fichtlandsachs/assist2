"use client";
export const dynamic = "force-dynamic";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/context";
import { apiRequest } from "@/lib/api/client";
import { Building2, ArrowRight } from "lucide-react";

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/[\s]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 60);
}

export default function SetupPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugManual, setSlugManual] = useState(false);
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) router.replace("/login");
  }, [isAuthenticated, isLoading, router]);

  function handleNameChange(value: string) {
    setName(value);
    if (!slugManual) {
      setSlug(slugify(value));
    }
  }

  function handleSlugChange(value: string) {
    setSlugManual(true);
    setSlug(slugify(value));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError("Bitte gib einen Namen ein.");
      return;
    }
    if (slug.length < 3) {
      setError("Der Slug muss mindestens 3 Zeichen lang sein.");
      return;
    }

    setSaving(true);
    try {
      const org = await apiRequest<{ slug: string }>("/api/v1/organizations", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          slug,
          description: description.trim() || null,
        }),
      });
      router.replace(`/${org.slug}/dashboard`);
    } catch (err: unknown) {
      const msg = (err as { error?: string })?.error;
      setError(msg ?? "Fehler beim Erstellen. Bitte versuche es erneut.");
    } finally {
      setSaving(false);
    }
  }

  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-brand-900 to-slate-800 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="mb-8 text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-brand-100 rounded-xl mb-4">
              <Building2 size={24} className="text-brand-600" />
            </div>
            <h1 className="text-2xl font-bold text-slate-900">Workspace einrichten</h1>
            <p className="text-slate-500 mt-1 text-sm">
              Erstelle deine erste Organisation, um loszulegen.
            </p>
          </div>

          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-5">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
                {error}
              </div>
            )}

            <div>
              <label htmlFor="name" className="block text-sm font-medium text-slate-700 mb-1">
                Name der Organisation <span className="text-red-500">*</span>
              </label>
              <input
                id="name"
                type="text"
                required
                value={name}
                onChange={(e) => handleNameChange(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                placeholder="Mein Unternehmen"
                autoFocus
              />
            </div>

            <div>
              <label htmlFor="slug" className="block text-sm font-medium text-slate-700 mb-1">
                URL-Kürzel <span className="text-red-500">*</span>
              </label>
              <div className="flex items-center border border-slate-300 rounded-lg focus-within:ring-2 focus-within:ring-brand-500 focus-within:border-transparent overflow-hidden">
                <span className="px-3 py-2 text-sm text-slate-400 bg-slate-50 border-r border-slate-300 shrink-0">
                  assist2.fichtlworks.com/
                </span>
                <input
                  id="slug"
                  type="text"
                  required
                  value={slug}
                  onChange={(e) => handleSlugChange(e.target.value)}
                  className="flex-1 px-3 py-2 text-sm outline-none bg-white"
                  placeholder="mein-unternehmen"
                />
              </div>
              <p className="mt-1 text-xs text-slate-400">
                Nur Kleinbuchstaben, Zahlen und Bindestriche. Mindestens 3 Zeichen.
              </p>
            </div>

            <div>
              <label htmlFor="description" className="block text-sm font-medium text-slate-700 mb-1">
                Beschreibung <span className="text-slate-400 font-normal">(optional)</span>
              </label>
              <textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent resize-none"
                placeholder="Kurze Beschreibung deiner Organisation…"
              />
            </div>

            <button
              type="submit"
              disabled={saving || slug.length < 3}
              className="w-full flex items-center justify-center gap-2 bg-brand-600 hover:bg-brand-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-medium py-2.5 px-4 rounded-lg text-sm transition-colors"
            >
              {saving ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                  Erstellt…
                </>
              ) : (
                <>
                  Organisation erstellen
                  <ArrowRight size={16} />
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
