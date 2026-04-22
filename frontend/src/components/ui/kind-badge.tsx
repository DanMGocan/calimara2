import type { ReactNode } from "react";

export function KindBadge({ label, meta }: { label: string; meta?: ReactNode }) {
  return (
    <div className="piece-kind-row">
      <span className="piece-kind-badge">{label}</span>
      {meta ? (
        <>
          <span className="piece-kind-sep" />
          <span className="piece-kind-meta">{meta}</span>
        </>
      ) : null}
    </div>
  );
}
