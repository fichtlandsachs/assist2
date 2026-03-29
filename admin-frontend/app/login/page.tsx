"use client";

import { startLogin } from "@/lib/auth";

export default function LoginPage() {
  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ background: "var(--paper)" }}
    >
      <div
        className="w-full max-w-sm p-8 border rounded-sm"
        style={{ borderColor: "var(--paper-rule)", background: "var(--paper-warm)" }}
      >
        <h1 className="text-xl font-semibold mb-2" style={{ color: "var(--ink)" }}>
          assist2 Admin
        </h1>
        <p className="text-sm mb-6" style={{ color: "var(--ink-faint)" }}>
          Zugang nur für autorisierte Administratoren.
        </p>
        <button
          onClick={() => void startLogin()}
          className="w-full py-2 px-4 rounded-sm text-sm font-medium transition-colors hover:opacity-90"
          style={{ background: "var(--ink)", color: "var(--paper)" }}
        >
          Mit Authentik anmelden
        </button>
      </div>
    </div>
  );
}
