import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth/context";
import { ThemeProvider } from "@/lib/theme/context";

export const metadata: Metadata = {
  title: {
    default: "assist2 — Compliance-Dokumentation. Automatisiert. Auditierbar.",
    template: "%s | assist2",
  },
  description:
    "assist2 ist die Compliance-Dokumentationsplattform für NIS2, KRITIS und ISO27001. Automatisierte Prozessdokumentation, BCM-Management und auditierbare Nachweise — ohne Halluzinationen.",
  keywords: ["NIS2", "KRITIS", "BCM", "Business Continuity Management", "Compliance", "Dokumentation", "ISO27001", "IT-Sicherheit", "ISMS", "Auditierung"],
  authors: [{ name: "assist2 GmbH" }],
  creator: "assist2 GmbH",
  metadataBase: new URL("https://assist2.io"),
  openGraph: {
    type: "website", locale: "de_DE", url: "https://assist2.io", siteName: "assist2",
    title: "assist2 — Compliance-Dokumentation. Automatisiert. Auditierbar.",
    description: "Die Compliance-Plattform für NIS2 & KRITIS. Prozessdokumentation, BCM und Audit-Trail ohne Aufwand.",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "assist2 — Compliance Platform" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "assist2 — Compliance. Automatisiert.",
    description: "NIS2, KRITIS und ISO27001 Compliance-Dokumentation. Automatisiert und auditierbar.",
    images: ["/og-image.png"],
  },
  robots: {
    index: true, follow: true,
    googleBot: { index: true, follow: true, "max-video-preview": -1, "max-image-preview": "large", "max-snippet": -1 },
  },
  icons: {
    icon: [{ url: "/favicon.ico", sizes: "any" }, { url: "/icon.svg", type: "image/svg+xml" }],
    apple: "/apple-touch-icon.png",
  },
  manifest: "/site.webmanifest",
};

export const viewport: Viewport = {
  themeColor: "var(--paper)",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="de" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* Paperwork theme fonts */}
        <link
          href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;1,400;1,500&family=Crimson+Pro:ital,wght@0,300;0,400;1,300;1,400&family=JetBrains+Mono:wght@300;400;500&display=swap"
          rel="stylesheet"
        />
        {/* Agile theme fonts */}
        <link
          href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;1,400;1,600&family=Inter:wght@400;500;600&family=Architects+Daughter&family=Gochi+Hand&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen antialiased" style={{ fontFamily: "var(--font-body)", color: "var(--ink)" }}>
        <ThemeProvider>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
