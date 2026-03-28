import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * Neobrutalist button — hard black border, offset shadow, presses on click.
 *
 * Variants:
 *   default  — black bg, white text
 *   outline  — white bg, black border
 *   orange   — orange bg, black text
 *   ghost    — no border, no shadow
 *   yellow   — yellow bg, black text
 *   teal     — teal bg, black text
 *
 * Sizes: sm | default | lg
 */
const buttonVariants = cva(
  // Base classes
  [
    "inline-flex items-center justify-center gap-2",
    "font-heading font-600 whitespace-nowrap",
    "border-2 border-[#0A0A0A]",
    "cursor-pointer select-none",
    "transition-[transform,box-shadow] duration-[80ms] ease-out",
    // Press animation
    "active:translate-x-[2px] active:translate-y-[2px] active:shadow-[1px_1px_0px_#0A0A0A]",
    // Disabled
    "disabled:pointer-events-none disabled:opacity-40",
    // Focus
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#FF5C00] focus-visible:ring-offset-2",
  ],
  {
    variants: {
      variant: {
        default: [
          "bg-[#0A0A0A] text-white",
          "shadow-[4px_4px_0px_#0A0A0A]",
          "hover:bg-[#1a1a1a]",
          // Reset shadow on hover to keep visual precision
          "hover:shadow-[4px_4px_0px_#0A0A0A]",
        ],
        outline: [
          "bg-white text-[#0A0A0A]",
          "shadow-[4px_4px_0px_#0A0A0A]",
          "hover:bg-[#F5F0E8]",
        ],
        orange: [
          "bg-[#FF5C00] text-[#0A0A0A]",
          "shadow-[4px_4px_0px_#0A0A0A]",
          "hover:bg-[#e65200]",
        ],
        yellow: [
          "bg-[#FFD700] text-[#0A0A0A]",
          "shadow-[4px_4px_0px_#0A0A0A]",
          "hover:bg-[#e6c000]",
        ],
        teal: [
          "bg-[#00D4AA] text-[#0A0A0A]",
          "shadow-[4px_4px_0px_#0A0A0A]",
          "hover:bg-[#00b894]",
        ],
        ghost: [
          "bg-transparent text-[#0A0A0A]",
          "border-transparent shadow-none",
          "hover:bg-[rgba(10,10,10,0.06)]",
          // Ghost never presses with shadow since it has none
          "active:shadow-none",
        ],
        destructive: [
          "bg-[#EF4444] text-white",
          "shadow-[4px_4px_0px_#0A0A0A]",
          "hover:bg-[#dc2626]",
        ],
      },
      size: {
        sm: "text-[0.8125rem] px-3.5 py-[0.375rem]",
        default: "text-[0.9375rem] px-5 py-[0.625rem]",
        lg: "text-[1.0625rem] px-7 py-[0.875rem]",
        icon: "h-10 w-10 p-0",
        "icon-sm": "h-8 w-8 p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /**
   * When true, renders the button as a child component via Radix Slot.
   * Useful for wrapping Next.js <Link> or other polymorphic components.
   */
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);

Button.displayName = "Button";

export { Button, buttonVariants };
