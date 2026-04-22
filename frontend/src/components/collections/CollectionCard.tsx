import { Link } from "react-router-dom";
import type { CollectionSummary } from "@/api/collections";
import { getBlogUrl } from "@/lib/utils";

interface Props {
  collection: CollectionSummary;
  /** When true, render a link pointing to the owner's subdomain /colectii/{slug}; otherwise same-origin. */
  sameOrigin?: boolean;
  /** Optional action(s) rendered on the right side (owner controls). */
  actions?: React.ReactNode;
}

export function CollectionCard({ collection, sameOrigin = true, actions }: Props) {
  const href = sameOrigin
    ? `/colectii/${collection.slug}`
    : `${collection.owner ? getBlogUrl(collection.owner.username) : ""}/colectii/${collection.slug}`;

  const content = (
    <>
      <div
        style={{
          fontFamily: "var(--font-serif)",
          fontSize: 18,
          color: "var(--color-ink)",
          lineHeight: 1.2,
        }}
      >
        {collection.title}
      </div>
      {collection.description ? (
        <p
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: 13,
            color: "var(--color-ink-mute)",
            marginTop: 6,
            lineHeight: 1.4,
          }}
        >
          {collection.description}
        </p>
      ) : null}
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 10,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          color: "var(--color-ink-faint)",
          marginTop: 8,
        }}
      >
        {collection.post_count} {collection.post_count === 1 ? "piesă" : "piese"}
        {collection.pending_count > 0 ? ` · ${collection.pending_count} în așteptare` : ""}
      </div>
    </>
  );

  return (
    <div
      className="rounded-[10px] border border-[color:var(--color-hairline)] p-4 hover:border-[color:var(--color-ink-mute)] transition-colors"
      style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        {sameOrigin ? (
          <Link to={href} style={{ textDecoration: "none", color: "inherit", display: "block" }}>
            {content}
          </Link>
        ) : (
          <a href={href} style={{ textDecoration: "none", color: "inherit", display: "block" }}>
            {content}
          </a>
        )}
      </div>
      {actions ? <div style={{ flexShrink: 0 }}>{actions}</div> : null}
    </div>
  );
}
