import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth/context";
import { ThemeProvider } from "@/lib/theme/context";

export const metadata: Metadata = {
  title: {
    default: "Karl — KI-Workspace für agile Teams",
    template: "%s | Karl",
  },
  description:
    "Karl ist der KI-native Workspace für agile Teams. User Stories, Sprints und Projektmanagement — unterstützt durch KI.",
  keywords: ["KI", "Projektmanagement", "User Stories", "Agile", "Scrum", "Sprint", "AI Workspace"],
  authors: [{ name: "Karl" }],
  creator: "Karl",
  metadataBase: new URL("https://heykarl.app"),
  openGraph: {
    type: "website", locale: "de_DE", url: "https://heykarl.app", siteName: "Karl",
    title: "Karl — KI-Workspace für agile Teams",
    description: "User Stories, Sprints und Projektmanagement — unterstützt durch KI.",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Karl — KI-Workspace" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Karl — KI-Workspace für agile Teams",
    description: "User Stories, Sprints und Projektmanagement — unterstützt durch KI.",
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
        {/* Synchronous theme bootstrap — runs before first paint to prevent flash */}
        <script dangerouslySetInnerHTML={{ __html: `(function(){try{var t=localStorage.getItem('theme');document.documentElement.dataset.theme=(t==='paperwork'||t==='karl')?t:'agile';}catch(e){}})();` }} />

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
