import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Neobrutalist card system.
 *
 * Design rules:
 *   - White background, 2px solid black border, 4px offset shadow
 *   - No border radius (hard corners only)
 *   - Optional left-border accent: orange | yellow | teal
 *   - Optional flat variant: no shadow
 *   - Hover state: shadow grows, card nudges up-left
 */

/* ── Accent variant types ───────────────────────────────────────── */
type CardAccent = "orange" | "yellow" | "teal" | "none";

const accentClasses: Record<CardAccent, string> = {
  orange: "border-l-[3px] border-l-[#c0392b]",
  yellow: "border-l-[3px] border-l-[#8b4513]",
  teal:   "border-l-[3px] border-l-[#2d6a4f]",
  none:   "",
};

/* ── Card ────────────────────────────────────────────────────────── */
interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  accent?: CardAccent;
  flat?: boolean;
  hover?: boolean;
}

const Card = React.forwardRef<HTMLDivElement, CardProps>(
  (
    { className, accent = "none", flat = false, hover = true, ...props },
    ref
  ) => (
    <div
      ref={ref}
      className={cn(
        // Base
        "border border-[#e2ddd4] rounded-sm bg-[#faf9f6]",
        // Hover
        hover && !flat
          ? "transition-[border-color] duration-150 hover:border-[#cec8bc]"
          : "",
        // Accent
        accentClasses[accent],
        className
      )}
      {...props}
    />
  )
);
Card.displayName = "Card";

/* ── CardHeader ──────────────────────────────────────────────────── */
const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col gap-1.5 p-6", className)}
    {...props}
  />
));
CardHeader.displayName = "CardHeader";

/* ── CardTitle ───────────────────────────────────────────────────── */
const CardTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn(
      "[font-family:var(--font-serif)] italic font-normal text-xl leading-tight text-[#1c1810]",
      className
    )}
    {...props}
  />
));
CardTitle.displayName = "CardTitle";

/* ── CardDescription ─────────────────────────────────────────────── */
const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-[#a09080] leading-relaxed [font-family:var(--font-body)]", className)}
    {...props}
  />
));
CardDescription.displayName = "CardDescription";

/* ── CardContent ─────────────────────────────────────────────────── */
const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
));
CardContent.displayName = "CardContent";

/* ── CardFooter ──────────────────────────────────────────────────── */
const CardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "flex items-center gap-3 px-6 py-4 border-t border-[#e2ddd4]",
      className
    )}
    {...props}
  />
));
CardFooter.displayName = "CardFooter";

/* ── CardDivider ─────────────────────────────────────────────────── */
const CardDivider = React.forwardRef<
  HTMLHRElement,
  React.HTMLAttributes<HTMLHRElement>
>(({ className, ...props }, ref) => (
  <hr
    ref={ref}
    className={cn("border-0 border-t border-[#e2ddd4] mx-6", className)}
    {...props}
  />
));
CardDivider.displayName = "CardDivider";

/* ── Stat Card (convenience composition) ────────────────────────── */
interface StatCardProps {
  label: string;
  value: React.ReactNode;
  subtext?: string;
  accent?: CardAccent;
  icon?: React.ReactNode;
  className?: string;
}

function StatCard({
  label,
  value,
  subtext,
  accent = "none",
  icon,
  className,
}: StatCardProps) {
  return (
    <Card accent={accent} className={cn("p-6", className)}>
      <div className="flex items-start justify-between mb-3">
        <span className="[font-family:var(--font-mono)] text-[8px] text-[#a09080] uppercase tracking-widest">
          {label}
        </span>
        {icon && (
          <div className="w-8 h-8 border border-[#e2ddd4] rounded-sm flex items-center justify-center bg-[#f7f4ee]">
            {icon}
          </div>
        )}
      </div>
      <div className="[font-family:var(--font-serif)] italic font-normal text-4xl text-[#1c1810] leading-none mb-1">
        {value}
      </div>
      {subtext && (
        <div className="text-sm text-[#a09080] mt-1 [font-family:var(--font-body)]">{subtext}</div>
      )}
    </Card>
  );
}

export {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  CardDivider,
  StatCard,
};
export type { CardAccent, CardProps };
