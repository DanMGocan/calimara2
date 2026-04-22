import type { ReactNode, MouseEvent } from "react";
import { cn } from "@/lib/utils";
import { SmartLink } from "@/components/ui/smart-link";

type ActionRowProps = {
  num: number;
  label: string;
  sub?: string;
  active?: boolean;
  disabled?: boolean;
  href?: string;
  onClick?: (e: MouseEvent) => void;
  trailing?: ReactNode;
};

const Arrow = () => (
  <span className="action-arrow" aria-hidden>
    <svg width="14" height="10" viewBox="0 0 14 10" fill="none">
      <path
        d="M1 5h11m0 0L9 1m3 4l-3 4"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  </span>
);

export function ActionRow({
  num,
  label,
  sub,
  active,
  disabled,
  href,
  onClick,
  trailing,
}: ActionRowProps) {
  const padded = num.toString().padStart(2, "0");
  const content = (
    <>
      <span className="action-num">{padded}</span>
      <span className="action-body">
        <span className="action-label">{label}</span>
        {sub ? <span className="action-sub">{sub}</span> : null}
      </span>
      {trailing ?? <Arrow />}
    </>
  );

  const className = cn("action-row", active && "active");

  if (href) {
    return (
      <SmartLink href={href} className={className} aria-disabled={disabled || undefined}>
        {content}
      </SmartLink>
    );
  }
  return (
    <button type="button" className={className} disabled={disabled} onClick={onClick}>
      {content}
    </button>
  );
}

export function ActionsGroup({ children }: { children: ReactNode }) {
  return <div className="actions-group">{children}</div>;
}

export function SideKicker({ children }: { children: ReactNode }) {
  return <div className="side-kicker">{children}</div>;
}

export function SideHint({ children }: { children: ReactNode }) {
  return <div className="side-hint">{children}</div>;
}
