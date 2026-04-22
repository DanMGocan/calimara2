import { cva, type VariantProps } from "class-variance-authority";

export const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium tracking-[0.04em] transition-colors",
  {
    variants: {
      variant: {
        default:
          "border-[color:var(--color-hairline)] bg-white/60 text-[color:var(--color-ink-mute)]",
        solid:
          "border-[color:var(--color-ink)] bg-[color:var(--color-ink)] text-[color:var(--color-paper)]",
        secondary:
          "border-[color:var(--color-hairline)] bg-[color:var(--color-paper-2)] text-[color:var(--color-ink-soft)]",
        success:
          "border-[color:var(--color-hairline)] bg-white/60 text-[color:var(--color-success)]",
        warning:
          "border-[color:var(--color-hairline)] bg-white/60 text-[color:var(--color-warning)]",
        danger:
          "border-[color:var(--color-like)]/40 bg-white/60 text-[color:var(--color-like)]",
        outline:
          "border-[color:var(--color-hairline)] bg-transparent font-[family-name:var(--font-mono)] text-[10px] uppercase tracking-[0.14em] text-[color:var(--color-ink-faint)]",
        accent:
          "border-[color:var(--color-accent-line)] bg-[color:var(--color-accent-soft)] text-[color:var(--color-accent)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export type BadgeVariantProps = VariantProps<typeof badgeVariants>;
