import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { fetchBlog } from "@/api/posts";
import { fetchUserCollections } from "@/api/collections";
import { useSubdomain } from "@/hooks/useSubdomain";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { Stage, LeftCol } from "@/components/ui/stage";
import { SideKicker } from "@/components/ui/action-row";
import {
  cn,
  formatDate,
  getAvatarUrl,
  getBlogUrl,
  stripHtml,
  truncate,
} from "@/lib/utils";

export default function BlogHomePage() {
  const { username } = useSubdomain();
  const [searchParams, setSearchParams] = useSearchParams();
  const month = searchParams.get("month") ? Number(searchParams.get("month")) : undefined;
  const year = searchParams.get("year") ? Number(searchParams.get("year")) : undefined;

  const { data, isLoading, error } = useQuery({
    queryKey: ["blog", username, month, year],
    queryFn: () => fetchBlog(username!, month, year),
    enabled: !!username,
  });

  const collectionsQuery = useQuery({
    queryKey: ["user", username ?? "", "collections"],
    queryFn: () => fetchUserCollections(username!),
    enabled: !!username,
  });

  if (isLoading) return <PageLoader />;
  if (error || !data) {
    return (
      <Stage variant="centered">
        <div className="auth-card text-center">
          <div className="auth-kicker">eroare</div>
          <h1 className="auth-title">Blogul nu a putut fi încărcat.</h1>
        </div>
      </Stage>
    );
  }

  const {
    blog_owner,
    featured_posts,
    latest_posts,
    all_posts,
    available_months,
    best_friends,
    user_awards,
    total_likes,
    total_comments,
    category_counts,
  } = data;

  const activeCategories = (category_counts ?? []).filter((c) => c.count > 0);

  return (
    <>
      <Helmet>
        <title>{blog_owner.username} — călimara.ro</title>
        <meta
          name="description"
          content={blog_owner.subtitle || `Blogul lui ${blog_owner.username} pe călimara.ro`}
        />
      </Helmet>

      <Stage>
        <LeftCol>
          <aside className="side-col">
            <SideKicker>autor</SideKicker>

            <div className="flex items-center gap-4">
              <img
                src={getAvatarUrl(blog_owner.avatar_seed, 72)}
                alt={blog_owner.username}
                style={{
                  width: 72,
                  height: 72,
                  borderRadius: "50%",
                  border: "1px solid var(--color-hairline)",
                }}
              />
              <div>
                <div
                  style={{
                    fontFamily: "var(--font-serif)",
                    fontSize: 24,
                    fontWeight: 500,
                    letterSpacing: "-0.02em",
                    color: "var(--color-ink)",
                    lineHeight: 1.05,
                  }}
                >
                  {blog_owner.username}
                </div>
                {blog_owner.subtitle ? (
                  <div
                    style={{
                      fontFamily: "var(--font-serif)",
                      fontSize: 15,
                      fontStyle: "italic",
                      color: "var(--color-ink-mute)",
                      marginTop: 6,
                      lineHeight: 1.4,
                    }}
                  >
                    {blog_owner.subtitle}
                  </div>
                ) : null}
              </div>
            </div>

            <div className="rail" style={{ marginTop: 8 }}>
              <div className="rail-stat">
                <span className="rail-label">Texte</span>
                <span className="rail-count">{all_posts.length}</span>
              </div>
              {activeCategories.map((c) => (
                <div key={c.category} className="rail-stat">
                  <span className="rail-label">{c.category_name}</span>
                  <span className="rail-count">{c.count}</span>
                </div>
              ))}
              <div className="rail-stat">
                <span className="rail-label">Aprecieri</span>
                <span className="rail-count">{total_likes}</span>
              </div>
              <div className="rail-stat">
                <span className="rail-label">Comentarii</span>
                <span className="rail-count">{total_comments}</span>
              </div>
            </div>

            {best_friends.length > 0 ? (
              <>
                <SideKicker>prieteni apropiați</SideKicker>
                <div className="flex flex-col gap-3">
                  {best_friends.map(({ user }) => (
                    <a
                      key={user.id}
                      href={getBlogUrl(user.username)}
                      className="flex items-center gap-3"
                      style={{ textDecoration: "none" }}
                    >
                      <img
                        src={getAvatarUrl(user.avatar_seed, 32)}
                        alt={user.username}
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: "50%",
                          border: "1px solid var(--color-hairline)",
                        }}
                      />
                      <span
                        style={{
                          fontFamily: "var(--font-sans)",
                          fontSize: 13,
                          color: "var(--color-ink-soft)",
                        }}
                      >
                        {user.username}
                      </span>
                    </a>
                  ))}
                </div>
              </>
            ) : null}

            {(collectionsQuery.data?.collections ?? []).length > 0 ? (
              <>
                <SideKicker>colecții</SideKicker>
                <div className="flex flex-col gap-2">
                  {(collectionsQuery.data?.collections ?? []).map((c) => (
                    <Link
                      key={c.id}
                      to={`/colectii/${c.slug}`}
                      style={{
                        textDecoration: "none",
                        color: "inherit",
                        padding: "8px 0",
                        borderBottom: "1px solid var(--color-hairline)",
                      }}
                    >
                      <div
                        style={{
                          fontFamily: "var(--font-serif)",
                          fontSize: 15,
                          color: "var(--color-ink)",
                        }}
                      >
                        {c.title}
                      </div>
                      <div
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 10,
                          letterSpacing: "0.18em",
                          textTransform: "uppercase",
                          color: "var(--color-ink-faint)",
                          marginTop: 2,
                        }}
                      >
                        {c.post_count} {c.post_count === 1 ? "piesă" : "piese"}
                      </div>
                    </Link>
                  ))}
                </div>
              </>
            ) : null}

            {user_awards.length > 0 ? (
              <>
                <SideKicker>distincții</SideKicker>
                <div className="flex flex-col gap-3">
                  {user_awards.map((award) => (
                    <div key={award.id}>
                      <div
                        style={{
                          fontFamily: "var(--font-serif)",
                          fontSize: 15,
                          fontWeight: 500,
                          color: "var(--color-ink)",
                          letterSpacing: "-0.01em",
                        }}
                      >
                        {award.award_title}
                      </div>
                      <div
                        style={{
                          fontFamily: "var(--font-sans)",
                          fontSize: 12,
                          color: "var(--color-ink-faint)",
                          marginTop: 2,
                        }}
                      >
                        {award.award_description}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : null}
          </aside>
        </LeftCol>

        <div className="piece-col">
          <div className="piece-wrap">
            <div className="piece-kind-row">
              <span className="piece-kind-badge">Blog</span>
              <span className="piece-kind-sep" />
              <span className="piece-kind-meta">{all_posts.length} texte</span>
            </div>

            {featured_posts.length > 0 ? (
              <section style={{ marginBottom: 48 }}>
                <SideKicker>texte alese</SideKicker>
                <div className="mt-4 grid gap-3">
                  {featured_posts.slice(0, 3).map((post) => (
                    <Link
                      key={post.id}
                      to={`/${post.slug}`}
                      className={cn("piece-card", post.super_likes_count > 0 && "has-super-like")}
                    >
                      <div className="piece-card-kicker">
                        {post.category_name ?? post.category}
                      </div>
                      <h3 className="piece-card-title">{post.title}</h3>
                      <p className="piece-card-excerpt">
                        {truncate(stripHtml(post.content), 180)}
                      </p>
                      <div className="piece-card-meta">
                        <span>{formatDate(post.created_at)}</span>
                        <span className="piece-meta-dot" />
                        <span>{post.likes_count} aprecieri</span>
                        <span className="piece-meta-dot" />
                        <span>{post.view_count} vizualizări</span>
                      </div>
                    </Link>
                  ))}
                </div>
              </section>
            ) : null}

            {latest_posts.length > 0 ? (
              <section style={{ marginBottom: 48 }}>
                <SideKicker>cele mai recente</SideKicker>
                <div className="mt-4 grid gap-3">
                  {latest_posts.map((post) => (
                    <Link
                      key={post.id}
                      to={`/${post.slug}`}
                      className={cn("piece-card", post.super_likes_count > 0 && "has-super-like")}
                    >
                      <div className="piece-card-kicker">
                        {post.category_name ?? post.category}
                      </div>
                      <h3 className="piece-card-title">{post.title}</h3>
                      <p className="piece-card-excerpt">
                        {truncate(stripHtml(post.content), 200)}
                      </p>
                      <div className="piece-card-meta">
                        <span>{formatDate(post.created_at)}</span>
                        <span className="piece-meta-dot" />
                        <span>{post.likes_count} aprecieri</span>
                      </div>
                    </Link>
                  ))}
                </div>
              </section>
            ) : null}

            <section>
              <div className="flex items-center justify-between" style={{ marginBottom: 16 }}>
                <SideKicker>arhivă</SideKicker>
                {available_months.length > 0 ? (
                  <select
                    className="cal-input"
                    style={{ width: 220, height: 34 }}
                    value={month && year ? `${month}-${year}` : ""}
                    onChange={(e) => {
                      if (!e.target.value) {
                        setSearchParams({});
                      } else {
                        const [m, y] = e.target.value.split("-");
                        setSearchParams({ month: m, year: y });
                      }
                    }}
                  >
                    <option value="">toate lunile</option>
                    {available_months.map((m) => (
                      <option key={`${m.month}-${m.year}`} value={`${m.month}-${m.year}`}>
                        {new Date(m.year, m.month - 1).toLocaleDateString("ro-RO", {
                          month: "long",
                          year: "numeric",
                        })}{" "}
                        ({m.count})
                      </option>
                    ))}
                  </select>
                ) : null}
              </div>

              {all_posts.length > 0 ? (
                <div
                  style={{
                    border: "1px solid var(--color-hairline)",
                    borderRadius: 10,
                    background: "rgba(255,255,255,0.6)",
                  }}
                >
                  {all_posts.map((post, i) => (
                    <Link
                      key={post.id}
                      to={`/${post.slug}`}
                      className="grid grid-cols-[1fr_auto] items-baseline gap-4 px-4 py-3"
                      style={{
                        borderBottom:
                          i < all_posts.length - 1
                            ? "1px solid var(--color-hairline)"
                            : "none",
                        textDecoration: "none",
                      }}
                    >
                      <div>
                        <div
                          style={{
                            fontFamily: "var(--font-serif)",
                            fontSize: 16,
                            fontWeight: 500,
                            color: "var(--color-ink)",
                            letterSpacing: "-0.01em",
                          }}
                        >
                          {post.title}
                        </div>
                        <div
                          style={{
                            fontFamily: "var(--font-sans)",
                            fontSize: 12,
                            color: "var(--color-ink-faint)",
                            marginTop: 2,
                          }}
                        >
                          {post.category_name ?? post.category} · {formatDate(post.created_at)}
                        </div>
                      </div>
                      <div
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 11,
                          color: "var(--color-ink-faint)",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {post.view_count} vizualizări
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <p
                  style={{
                    fontFamily: "var(--font-sans)",
                    fontSize: 13,
                    color: "var(--color-ink-faint)",
                  }}
                >
                  Nicio postare încă.
                </p>
              )}
            </section>
          </div>
        </div>
      </Stage>
    </>
  );
}
