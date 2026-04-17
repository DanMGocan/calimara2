import { cva, type VariantProps } from "class-variance-authority";

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
  {
    variants: {
      variant: {
        default: "bg-primary text-white hover:bg-primary-light shadow-sm",
        secondary: "bg-surface text-primary border border-border hover:bg-beige hover:border-border-strong",
        outline: "border border-border-strong bg-white text-primary hover:bg-surface hover:border-primary",
        ghost: "text-primary hover:bg-surface",
        danger: "bg-danger text-white hover:bg-red-700 shadow-sm",
        link: "text-primary underline-offset-4 hover:underline",
        iconRound:
          "rounded-full border border-border bg-white text-primary hover:border-border-strong hover:bg-surface",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-6 text-base",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "md",
    },
  },
);

export type ButtonVariantProps = VariantProps<typeof buttonVariants>;
