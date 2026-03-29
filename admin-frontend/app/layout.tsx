import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "assist2 Admin",
  description: "Zentrales Admin-Portal für assist2",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}
