import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2",
    "cursor-pointer select-none whitespace-nowrap",
    "transition-all duration-[120ms]",
    "disabled:pointer-events-none disabled:opacity-35",
    "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#8b5e52] focus-visible:ring-offset-1",
  ],
  {
    variants: {
      variant: {
        default: [
          "rounded-sm border-[0.5px] border-[#1c1810]",
          "bg-[#1c1810] text-[#faf9f6]",
          "hover:bg-[#5a5040]",
          "[font-family:var(--font-mono)] text-[9px] tracking-[.05em] uppercase",
        ],
        outline: [
          "rounded-sm border-[0.5px] border-[#cec8bc]",
          "bg-transparent text-[#5a5040]",
          "hover:bg-[#ece8e0] hover:border-[#a09080] hover:text-[#1c1810]",
          "[font-family:var(--font-mono)] text-[9px] tracking-[.05em] uppercase",
        ],
        orange: [
          "rounded-sm border-[0.5px] border-[#8b5e52]",
          "bg-[#8b5e52] text-[#faf9f6]",
          "hover:bg-[#7a5248]",
          "[font-family:var(--font-mono)] text-[9px] tracking-[.05em] uppercase",
        ],
        yellow: [
          "rounded-sm border-[0.5px] border-[#7a6450]",
          "bg-[rgba(122,100,80,.1)] text-[#7a6450]",
          "hover:bg-[rgba(122,100,80,.18)]",
          "[font-family:var(--font-mono)] text-[9px] tracking-[.05em] uppercase",
        ],
        teal: [
          "rounded-sm border-[0.5px] border-[#526b5e]",
          "bg-[rgba(82,107,94,.1)] text-[#526b5e]",
          "hover:bg-[rgba(82,107,94,.18)]",
          "[font-family:var(--font-mono)] text-[9px] tracking-[.05em] uppercase",
        ],
        ghost: [
          "bg-transparent border-transparent",
          "text-[#5a5040] hover:bg-[rgba(28,24,16,.06)] hover:text-[#1c1810]",
          "[font-family:var(--font-mono)] text-[9px] tracking-[.05em] uppercase",
        ],
        destructive: [
          "rounded-sm border-[0.5px] border-[#8b5e52]",
          "bg-[#8b5e52] text-[#faf9f6]",
          "hover:bg-[#7a5248]",
          "[font-family:var(--font-mono)] text-[9px] tracking-[.05em] uppercase",
        ],
      },
      size: {
        sm:        "text-[8px] px-2.5 py-[3px]",
        default:   "text-[9px] px-3 py-[5px]",
        lg:        "text-[10px] px-4 py-[7px]",
        icon:      "h-8 w-8 p-0 text-xs",
        "icon-sm": "h-6 w-6 p-0 text-xs",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
