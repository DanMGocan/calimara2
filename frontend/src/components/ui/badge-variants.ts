import { cva, type VariantProps } from "class-variance-authority";

export const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "bg-surface border border-border text-secondary",
        solid: "bg-primary text-white",
        secondary: "bg-surface text-secondary border border-border",
        success: "bg-success/10 text-success",
        warning: "bg-warning/10 text-warning",
        danger: "bg-danger/10 text-danger",
        outline: "border border-border text-muted",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export type BadgeVariantProps = VariantProps<typeof badgeVariants>;
