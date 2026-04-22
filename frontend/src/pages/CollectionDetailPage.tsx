import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { fetchCollectionBySlug } from "@/api/collections";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { Stage, LeftCol, PieceCol } from "@/components/ui/stage";
import { KindBadge } from "@/components/ui/kind-badge";
import { ActionsGroup, ActionRow, SideHint, SideKicker } from "@/components/ui/action-row";
import { formatDate, getBlogUrl } from "@/lib/utils";

export default function CollectionDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["collections", "bySlug", slug],
    queryFn: () => fetchCollectionBySlug(slug!),
    enabled: !!slug,
  });

  if (isLoading) return <PageLoader />;
  if (error || !data) {
    return (
      <Stage variant="centered">
        <PieceCol>
          <KindBadge label="404" />
          <h1 className="piece-title">Colecția nu a fost găsită.</h1>
        </PieceCol>
      </Stage>
    );
  }

  const ownerUrl = data.owner ? getBlogUrl(data.owner.username) : "/";

  return (
    <>
      <Helmet>
        <title>{data.title} — colecție | călimara.ro</title>
        {data.description ? <meta name="description" content={data.description} /> : null}
      </Helmet>

      <Stage>
        <LeftCol>
          <aside className="side-col">
            <SideKicker>colecție</SideKicker>
            <ActionsGroup>
              <ActionRow
                num={1}
                label={`Blogul lui ${data.owner?.username ?? ""}`}
                sub="înapoi la pagina autorului"
                href={ownerUrl}
              />
              <ActionRow num={2} label="Alte colecții" sub="ale acestui autor" href={`${ownerUrl}`} />
            </ActionsGroup>
            <SideHint>
              <span>curatoriat de</span>
              <span style={{ fontFamily: "var(--font-serif)", color: "var(--color-ink)" }}>
                {data.owner?.username}
              </span>
            </SideHint>
          </aside>
        </LeftCol>

        <PieceCol>
          <KindBadge label="Colecție" meta={formatDate(data.updated_at)} />
          <h1 className="piece-title">{data.title}</h1>
          <div className="piece-meta">
            <span className="piece-author">{data.owner?.username}</span>
            <span className="piece-meta-dot" />
            <span className="piece-year">
              {data.post_count} {data.post_count === 1 ? "piesă" : "piese"}
            </span>
          </div>

          {data.description ? (
            <p
              style={{
                fontFamily: "var(--font-serif)",
                fontSize: 17,
                lineHeight: 1.5,
                color: "var(--color-ink-soft)",
                marginTop: 12,
                marginBottom: 24,
              }}
            >
              {data.description}
            </p>
          ) : null}

          {data.posts.length === 0 ? (
            <p
              style={{
                color: "var(--color-ink-faint)",
                fontFamily: "var(--font-sans)",
                fontSize: 14,
              }}
            >
              Colecția nu conține încă niciun text.
            </p>
          ) : (
            <ul className="flex flex-col gap-3">
              {data.posts.map((entry, idx) => {
                if (!entry.post) return null;
                const p = entry.post;
                const postUrl = p.owner ? `${getBlogUrl(p.owner.username)}/${p.slug}` : `/${p.slug}`;
                return (
                  <li key={entry.id}>
                    <a
                      href={postUrl}
                      style={{
                        display: "flex",
                        alignItems: "baseline",
                        gap: 14,
                        padding: "12px 0",
                        borderBottom: "1px solid var(--color-hairline)",
                        textDecoration: "none",
                        color: "inherit",
                      }}
                    >
                      <span
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 10,
                          letterSpacing: "0.22em",
                          color: "var(--color-ink-faint)",
                          width: 32,
                          flexShrink: 0,
                        }}
                      >
                        {(idx + 1).toString().padStart(2, "0")}
                      </span>
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span
                          className={(p.super_likes_count ?? 0) > 0 ? "has-super-like" : undefined}
                          style={{
                            fontFamily: "var(--font-serif)",
                            fontSize: 18,
                            color: "var(--color-ink)",
                            display: "block",
                            position: (p.super_likes_count ?? 0) > 0 ? "relative" : undefined,
                          }}
                        >
                          <span className={(p.super_likes_count ?? 0) > 0 ? "piece-card-title has-super-like" : undefined}>
                            {p.title}
                          </span>
                        </span>
                        <span
                          style={{
                            fontFamily: "var(--font-sans)",
                            fontSize: 12,
                            color: "var(--color-ink-mute)",
                          }}
                        >
                          {p.owner?.username ?? ""}
                          {p.category ? ` · ${p.category}` : ""}
                        </span>
                      </span>
                    </a>
                  </li>
                );
              })}
            </ul>
          )}
          <div style={{ marginTop: 24 }}>
            <Link
              to="/"
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                letterSpacing: "0.22em",
                textTransform: "uppercase",
                color: "var(--color-ink-faint)",
                textDecoration: "none",
              }}
            >
              ← înapoi
            </Link>
          </div>
        </PieceCol>
      </Stage>
    </>
  );
}
