import { Link } from "react-router-dom";
import type { ClubSummary } from "@/api/clubs";
import { getAvatarUrl } from "@/lib/utils";

interface Props {
  club: ClubSummary;
  actions?: React.ReactNode;
}

const SPECIALITY_LABELS: Record<string, string> = {
  poezie: "Poezie",
  proza_scurta: "Proză scurtă",
};

export function ClubCard({ club, actions }: Props) {
  const avatarSeed = club.avatar_seed || `${club.slug}-club`;
  return (
    <div
      className="rounded-[10px] border border-[color:var(--color-hairline)] p-4 hover:border-[color:var(--color-ink-mute)] transition-colors"
      style={{ display: "flex", alignItems: "flex-start", gap: 12 }}
    >
      <Link
        to={`/cluburi/${club.slug}`}
        style={{ flexShrink: 0, textDecoration: "none" }}
        aria-label={club.title}
      >
        <img
          src={getAvatarUrl(avatarSeed, 56)}
          width={56}
          height={56}
          alt=""
          style={{ display: "block", borderRadius: 6, background: "var(--color-paper-2)" }}
        />
      </Link>
      <div style={{ flex: 1, minWidth: 0 }}>
        <Link
          to={`/cluburi/${club.slug}`}
          style={{ textDecoration: "none", color: "inherit", display: "block" }}
        >
          <div
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: 18,
              color: "var(--color-ink)",
              lineHeight: 1.2,
            }}
          >
            {club.title}
          </div>
          {club.theme ? (
            <div
              style={{
                fontFamily: "var(--font-sans)",
                fontSize: 12,
                color: "var(--color-ink-mute)",
                marginTop: 4,
              }}
            >
              {club.theme}
            </div>
          ) : null}
          {club.motto ? (
            <p
              style={{
                fontFamily: "var(--font-serif)",
                fontStyle: "italic",
                fontSize: 13,
                color: "var(--color-ink-soft)",
                marginTop: 6,
                lineHeight: 1.4,
              }}
            >
              „{club.motto}"
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
              display: "flex",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <span>{SPECIALITY_LABELS[club.speciality] ?? club.speciality}</span>
            <span>
              {club.member_count} {club.member_count === 1 ? "membru" : "membri"}
            </span>
          </div>
        </Link>
      </div>
      {actions ? <div style={{ flexShrink: 0 }}>{actions}</div> : null}
    </div>
  );
}
