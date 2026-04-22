import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type StageProps = {
  children: ReactNode;
  variant?: "default" | "single" | "centered";
  className?: string;
};

export function Stage({ children, variant = "default", className }: StageProps) {
  const variantClass =
    variant === "single" ? "stage-single" : variant === "centered" ? "stage-center" : "";
  return <main className={cn("stage", variantClass, className)}>{children}</main>;
}

export function LeftCol({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("left-col", className)}>{children}</div>;
}

export function PieceCol({
  children,
  transitioning,
  className,
}: {
  children: ReactNode;
  transitioning?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("piece-col", className)}>
      <div className={cn("piece-wrap", transitioning && "transitioning")}>{children}</div>
    </div>
  );
}
