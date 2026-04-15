import Link from "next/link";

const FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif";

export function MarketingTopbar({ activePage }: { activePage?: "demo" }) {
  return (
    <header style={{
      position: "fixed", top: 0, left: 0, right: 0, zIndex: 200,
      background: "rgba(255,255,255,.88)",
      backdropFilter: "blur(12px)",
      WebkitBackdropFilter: "blur(12px)",
      borderBottom: "1px solid rgba(13,13,13,.1)",
      padding: "0 max(24px, 5vw)",
      fontFamily: FONT,
    }}>
      <div style={{ maxWidth: 1100, margin: "0 auto", display: "flex", alignItems: "center", height: 64, gap: 32 }}>
        {/* Logo */}
        <Link href="/" style={{ fontSize: 22, fontWeight: 900, letterSpacing: "-0.5px", display: "flex", alignItems: "center", gap: 2, color: "#0D0D0D", textDecoration: "none" }}>
          Hey<span style={{ color: "#FF5C00" }}>Karl</span>
        </Link>

        {/* Nav links */}
        <div style={{ display: "flex", gap: 28, marginLeft: "auto" }}>
          {[
            { label: "Home",    href: "/" },
            { label: "Details", href: "/#funktionen" },
            { label: "Demo",    href: "/demo" },
          ].map(({ label, href }) => (
            <Link key={label} href={href}
              style={{ fontSize: 14, fontWeight: 500, color: activePage === "demo" && label === "Demo" ? "#FF5C00" : "rgba(13,13,13,.7)", textDecoration: "none" }}>
              {label}
            </Link>
          ))}
        </div>

        {/* Login CTA */}
        <div style={{ marginLeft: 8 }}>
          <Link href="/login"
            style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "9px 20px", fontSize: 14, fontWeight: 700, borderRadius: 14, background: "#FF5C00", color: "#FFFFFF", border: "2px solid #FF5C00", boxShadow: "0 2px 8px rgba(255,92,0,.3)", textDecoration: "none" }}>
            Login
          </Link>
        </div>
      </div>
    </header>
  );
}
