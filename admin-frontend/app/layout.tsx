import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HeyKarl Admin",
  description: "Zentrales Admin-Portal für HeyKarl",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de" data-theme="karl">
      <body style={{ fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", color: "var(--ink)" }}>
        {children}
      </body>
    </html>
  );
}
