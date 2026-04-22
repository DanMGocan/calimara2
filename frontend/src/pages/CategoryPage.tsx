import { useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { fetchCategoryPage } from "@/api/posts";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { Stage, LeftCol } from "@/components/ui/stage";
import {
  ActionRow,
  ActionsGroup,
  SideKicker,
} from "@/components/ui/action-row";
import { cn, formatDate, getBlogUrl, stripHtml, truncate } from "@/lib/utils";

const SORTS = [
  { key: "newest", label: "Cele mai recente", sub: "după dată" },
  { key: "popular", label: "Populare", sub: "după vizualizări" },
  { key: "most_liked", label: "Apreciate", sub: "după aprecieri" },
] as const;

export default function CategoryPage() {
  const { categoryKey } = useParams<{ categoryKey: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const sortBy = searchParams.get("sort_by") || "newest";

  const { data, isLoading } = useQuery({
    queryKey: ["category", categoryKey, sortBy],
    queryFn: () => fetchCategoryPage(categoryKey!, sortBy),
    enabled: !!categoryKey,
  });

  if (isLoading || !data) return <PageLoader />;

  return (
    <>
      <Helmet>
        <title>{data.category_name} — călimara.ro</title>
      </Helmet>

      <Stage>
        <LeftCol>
          <aside className="side-col">
            <SideKicker>sortează</SideKicker>
            <ActionsGroup>
              {SORTS.map((s, i) => (
                <ActionRow
                  key={s.key}
                  num={i + 1}
                  label={s.label}
                  sub={s.sub}
                  active={sortBy === s.key}
                  onClick={() => setSearchParams({ sort_by: s.key })}
                />
              ))}
            </ActionsGroup>
            <SideKicker>alte categorii</SideKicker>
            <div className="flex flex-col gap-2">
              {[
                { k: "poezie", n: "Poezie" },
                { k: "proza_scurta", n: "Proză scurtă" },
                { k: "toate", n: "Toate textele" },
              ].map((c) => (
                <a
                  key={c.k}
                  href={`/category/${c.k}`}
                  style={{
                    fontFamily: "var(--font-sans)",
                    fontSize: 13,
                    color:
                      c.k === categoryKey
                        ? "var(--color-accent)"
                        : "var(--color-ink-mute)",
                    textDecoration: "none",
                    padding: "6px 0",
                    borderBottom: "1px solid var(--color-hairline)",
                  }}
                >
                  {c.n}
                </a>
              ))}
            </div>
          </aside>
        </LeftCol>

        <div className="piece-col">
          <div className="piece-wrap">
            <div className="piece-kind-row">
              <span className="piece-kind-badge">{data.category_name}</span>
              <span className="piece-kind-sep" />
              <span className="piece-kind-meta">{data.posts.length} texte</span>
            </div>

            <h1
              className="piece-title"
              style={{ fontSize: "clamp(32px, 4vw, 52px)", marginBottom: 32 }}
            >
              {data.category_name}
            </h1>

            {data.posts.length > 0 ? (
              <div className="grid gap-3">
                {data.posts.map((post) => (
                  <a
                    key={post.id}
                    href={
                      post.owner
                        ? `${getBlogUrl(post.owner.username)}/${post.slug}`
                        : "#"
                    }
                    className={cn("piece-card", post.super_likes_count > 0 && "has-super-like")}
                  >
                    <div className="piece-card-kicker">
                      {post.owner ? `de ${post.owner.username}` : "anonim"}
                    </div>
                    <h3 className="piece-card-title">{post.title}</h3>
                    <p className="piece-card-excerpt">
                      {truncate(stripHtml(post.content), 220)}
                    </p>
                    <div className="piece-card-meta">
                      <span>{formatDate(post.created_at)}</span>
                      <span className="piece-meta-dot" />
                      <span>{post.likes_count} aprecieri</span>
                      <span className="piece-meta-dot" />
                      <span>{post.view_count} vizualizări</span>
                    </div>
                  </a>
                ))}
              </div>
            ) : (
              <div
                style={{
                  padding: "60px 20px",
                  border: "1px dashed var(--color-hairline-strong)",
                  borderRadius: 10,
                  textAlign: "center",
                  color: "var(--color-ink-faint)",
                  fontFamily: "var(--font-serif)",
                  fontStyle: "italic",
                  fontSize: 17,
                }}
              >
                Nicio postare în această categorie.
              </div>
            )}
          </div>
        </div>
      </Stage>
    </>
  );
}
