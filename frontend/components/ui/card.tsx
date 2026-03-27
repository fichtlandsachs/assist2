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
  orange: "border-l-[4px] border-l-[#FF5C00]",
  yellow: "border-l-[4px] border-l-[#FFD700]",
  teal: "border-l-[4px] border-l-[#00D4AA]",
  none: "",
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
        "bg-white border-2 border-[#0A0A0A]",
        // Shadow
        flat ? "shadow-none" : "shadow-neo",
        // Hover
        hover && !flat
          ? "transition-[transform,box-shadow] duration-150 ease-out hover:-translate-x-px hover:-translate-y-px hover:shadow-neo-lg"
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
      "font-heading font-700 text-xl leading-tight text-[#0A0A0A]",
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
    className={cn("text-sm text-[#6B6B6B] leading-relaxed", className)}
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
      "flex items-center gap-3 px-6 py-4 border-t-2 border-[#0A0A0A]",
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
    className={cn("border-0 border-t-2 border-[#0A0A0A] mx-6", className)}
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
        <span className="text-xs font-heading font-600 text-[#6B6B6B] uppercase tracking-widest">
          {label}
        </span>
        {icon && (
          <div className="w-8 h-8 border-2 border-[#0A0A0A] flex items-center justify-center bg-[#F5F0E8]">
            {icon}
          </div>
        )}
      </div>
      <div className="font-heading font-800 text-4xl text-[#0A0A0A] leading-none mb-1">
        {value}
      </div>
      {subtext && (
        <div className="text-sm text-[#6B6B6B] mt-1">{subtext}</div>
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
