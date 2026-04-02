import type { ReactNode } from "react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div
      className="min-h-screen flex items-center justify-center p-4"
      style={{
        background:
          "repeating-linear-gradient(0deg, transparent, transparent 27px, rgba(0,0,0,.04) 27px, rgba(0,0,0,.04) 28px), var(--paper-warm)",
      }}
    >
      {children}
    </div>
  );
}
