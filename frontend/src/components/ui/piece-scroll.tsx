import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

type PieceScrollProps = {
  children: ReactNode;
  resetKey?: string | number;
  hint?: string;
};

export function PieceScroll({ children, resetKey, hint = "derulează" }: PieceScrollProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [atTop, setAtTop] = useState(true);
  const [atBottom, setAtBottom] = useState(false);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = 0;
    const noOverflow = el.scrollHeight <= el.clientHeight + 1;
    setAtTop(true);
    setAtBottom(noOverflow);
  }, [resetKey]);

  const onScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    setAtTop(el.scrollTop < 4);
    setAtBottom(el.scrollTop + el.clientHeight >= el.scrollHeight - 4);
  };

  return (
    <div className="piece-scroll-wrap">
      <div
        ref={scrollRef}
        className={cn("piece-scroll", atTop && "at-top", atBottom && "at-bottom")}
        onScroll={onScroll}
      >
        <div className="piece-body-inner">{children}</div>
      </div>
      <div className={cn("scroll-hint-wrap", atBottom && "hidden")} aria-hidden>
        <div className="scroll-hint">
          <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
            <path
              d="M3 5l4 4 4-4"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span>{hint}</span>
        </div>
      </div>
    </div>
  );
}
