import { cva, type VariantProps } from "class-variance-authority";

// Unified low-chrome button — matches .react-btn from design/lib/landing.css.
// Every variant is transparent with a 1px hairline border; hover deepens the
// border + adds a 4%-ink background; active nudges 1px down.
const base =
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-sans font-medium tracking-[0.02em] transition-colors duration-150 ease-out cursor-pointer select-none disabled:pointer-events-none disabled:opacity-50 active:translate-y-px";

export const buttonVariants = cva(base, {
  variants: {
    variant: {
      default:
        "border border-[color:var(--color-ink-faint)] bg-transparent text-[color:var(--color-ink-soft)] hover:text-[color:var(--color-ink)] hover:border-[color:var(--color-ink)] hover:bg-black/[0.04]",
      outline:
        "border border-[color:var(--color-ink-faint)] bg-transparent text-[color:var(--color-ink-soft)] hover:text-[color:var(--color-ink)] hover:border-[color:var(--color-ink)] hover:bg-black/[0.04]",
      secondary:
        "border border-[color:var(--color-hairline-strong)] bg-[color:var(--color-paper-2)] text-[color:var(--color-ink-soft)] hover:text-[color:var(--color-ink)] hover:border-[color:var(--color-ink-mute)]",
      ghost:
        "border border-transparent bg-transparent text-[color:var(--color-ink-soft)] hover:text-[color:var(--color-ink)] hover:bg-black/[0.04]",
      danger:
        "border border-[color:var(--color-like)] bg-transparent text-[color:var(--color-like)] hover:bg-[rgba(217,56,56,0.08)]",
      link:
        "border-0 bg-transparent p-0 h-auto text-[color:var(--color-ink)] underline-offset-4 hover:underline",
      iconRound:
        "w-11 h-11 p-0 rounded-none border-0 bg-transparent text-[color:var(--color-ink)] hover:-translate-y-px active:translate-y-0",
    },
    size: {
      sm: "h-8 px-3 text-xs",
      md: "h-[34px] px-[14px] text-xs tracking-[0.02em]",
      lg: "h-11 px-5 text-sm",
      icon: "h-11 w-11 p-0",
    },
  },
  defaultVariants: {
    variant: "default",
    size: "md",
  },
});

export type ButtonVariantProps = VariantProps<typeof buttonVariants>;
