import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HeyKarl Admin",
  description: "Zentrales Admin-Portal für HeyKarl",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;1,400;1,600&family=Architects+Daughter&display=swap"
          rel="stylesheet"
        />
      </head>
      <body style={{ fontFamily: "var(--font-body)", color: "var(--ink)" }}>
        {children}
      </body>
    </html>
  );
}
