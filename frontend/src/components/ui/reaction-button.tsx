import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

type ReactionButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  icon?: ReactNode;
  label: string;
  count?: number | string;
  variant?: "default" | "like";
  active?: boolean;
};

export function ReactionButton({
  icon,
  label,
  count,
  variant = "default",
  active,
  className,
  ...rest
}: ReactionButtonProps) {
  return (
    <button
      type="button"
      className={cn(
        "react-btn",
        variant === "like" && "react-like",
        active && "on",
        className,
      )}
      aria-pressed={active}
      {...rest}
    >
      {icon}
      <span>{label}</span>
      {count !== undefined && count !== null && <span className="react-count">{count}</span>}
    </button>
  );
}

type PieceActionButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  icon?: ReactNode;
  children: ReactNode;
};

export function PieceActionButton({ icon, children, className, ...rest }: PieceActionButtonProps) {
  return (
    <button type="button" className={cn("piece-pdf", className)} {...rest}>
      {icon}
      <span>{children}</span>
    </button>
  );
}
