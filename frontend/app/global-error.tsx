"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[GlobalError boundary]", error);
  }, [error]);

  const isChunkError =
    error.message?.includes("Loading chunk") ||
    error.message?.includes("Failed to fetch") ||
    error.message?.includes("ChunkLoadError");

  return (
    <html lang="de">
      <body style={{ fontFamily: "system-ui, sans-serif", background: "#fafafa", color: "#111" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "100vh", padding: "2rem", textAlign: "center" }}>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "0.5rem" }}>
            {isChunkError ? "Seite veraltet" : "Anwendungsfehler"}
          </h1>
          <p style={{ color: "#666", maxWidth: 420, marginBottom: "1.5rem" }}>
            {isChunkError
              ? "Ein Update wurde eingespielt. Bitte lade die Seite neu (Strg+Umschalt+R)."
              : "Ein unerwarteter Fehler ist aufgetreten. Bitte lade die Seite neu."}
          </p>
          <div style={{ display: "flex", gap: "0.75rem" }}>
            <button
              onClick={() => window.location.reload()}
              style={{ padding: "0.5rem 1rem", background: "#FF5C00", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontWeight: 600 }}
            >
              Seite neu laden
            </button>
            {!isChunkError && (
              <button
                onClick={reset}
                style={{ padding: "0.5rem 1rem", background: "#fff", color: "#111", border: "1px solid #ddd", borderRadius: 4, cursor: "pointer" }}
              >
                Erneut versuchen
              </button>
            )}
          </div>
        </div>
      </body>
    </html>
  );
}
