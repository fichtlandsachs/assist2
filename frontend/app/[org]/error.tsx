"use client";

import { useEffect } from "react";
import { RefreshCw } from "lucide-react";

export default function OrgError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[OrgError boundary]", error);
  }, [error]);

  const isChunkError =
    error.message?.includes("Loading chunk") ||
    error.message?.includes("Failed to fetch") ||
    error.message?.includes("ChunkLoadError");

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] p-8 text-center">
      <div className="max-w-md">
        <div className="w-12 h-12 rounded-full bg-[rgba(var(--accent-red-rgb),.1)] flex items-center justify-center mx-auto mb-4">
          <span className="text-[var(--accent-red)] text-xl font-bold">!</span>
        </div>
        <h2 className="text-lg font-semibold text-[var(--ink)] mb-2">
          {isChunkError ? "Seite veraltet — bitte neu laden" : "Etwas ist schiefgelaufen"}
        </h2>
        <p className="text-sm text-[var(--ink-faint)] mb-6">
          {isChunkError
            ? "Ein Update wurde eingespielt. Bitte lade die Seite neu, um fortzufahren."
            : "Ein unerwarteter Fehler ist aufgetreten. Versuche es erneut oder lade die Seite neu."}
        </p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={() => window.location.reload()}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-[var(--accent-red)] rounded-sm hover:opacity-90 transition-opacity"
          >
            <RefreshCw className="w-4 h-4" />
            Seite neu laden
          </button>
          {!isChunkError && (
            <button
              onClick={reset}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-[var(--ink)] border border-[var(--paper-rule)] rounded-sm hover:bg-[var(--paper-warm)] transition-colors"
            >
              Erneut versuchen
            </button>
          )}
        </div>
        {error.digest && (
          <p className="mt-4 text-xs text-[var(--ink-faint)] font-mono">
            Error ID: {error.digest}
          </p>
        )}
      </div>
    </div>
  );
}
