"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { handleCallback } from "@/lib/auth";

function CallbackInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = params.get("code");
    const state = params.get("state");
    if (!code || !state) {
      setError("Ungültige Callback-Parameter.");
      return;
    }
    handleCallback(code, state)
      .then(() => router.replace("/dashboard"))
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Login fehlgeschlagen.")
      );
  }, [params, router]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-3">
          <p className="text-sm" style={{ color: "var(--warn)" }}>{error}</p>
          <a
            href="/login"
            className="text-sm underline"
            style={{ color: "var(--ink-mid)" }}
          >
            Zurück zum Login
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <p className="text-sm" style={{ color: "var(--ink-faint)" }}>
        Anmeldung wird verarbeitet…
      </p>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <Suspense>
      <CallbackInner />
    </Suspense>
  );
}
