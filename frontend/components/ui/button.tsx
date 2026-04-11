import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva("neo-btn", {
  variants: {
    variant: {
      default:     "neo-btn--default",
      outline:     "neo-btn--outline",
      orange:      "neo-btn--orange",
      yellow:      "neo-btn--yellow",
      teal:        "neo-btn--teal",
      ghost:       "neo-btn--ghost",
      destructive: "neo-btn--orange",
    },
    size: {
      sm:        "neo-btn--sm",
      default:   "",
      lg:        "neo-btn--lg",
      icon:      "neo-btn--icon",
      "icon-sm": "neo-btn--icon-sm",
    },
  },
  defaultVariants: { variant: "default", size: "default" },
});

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
