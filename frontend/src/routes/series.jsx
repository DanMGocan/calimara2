import { Fragment } from "react";
import { fetchSeries, seriesPdfUrl } from "../api/series.js";
import { AuthorLink, PostTitleLink } from "../app/content.jsx";
import { categoryLabel } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { AdSlot, PageShell, StatusPanel } from "../app/layout.jsx";
import { blogUrl } from "../app/paths.js";

function SeriesView({ slug }) {
  const { data, error, loading } = useAsync(() => fetchSeries(slug), [slug]);
  const posts = data?.posts?.map((entry) => entry.post).filter(Boolean) ?? [];
  const pdfHref = data?.slug ? seriesPdfUrl(data.slug) : "#";

  return (
    <PageShell
      kicker="serie"
      title={data?.title ?? "Serie"}
      sub={data?.description || (data?.owner?.username ? <>Serie de <AuthorLink user={data.owner} />.</> : "Texte în ordine pe călimara.ro.")}
    >
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca seria">{error}</StatusPanel> : null}
      {data ? (
        <div className="detail-stack">
          <div className="piece-actions" aria-label="Acțiuni serie">
            <a className="react-btn react-link" href={pdfHref}>PDF</a>
            {data.owner?.username ? (
              <a className="react-btn react-link" href={blogUrl(data.owner.username)}>Autor</a>
            ) : null}
          </div>
          {posts.length ? (
            <div className="list-grid">
              {posts.map((post, index) => (
                <Fragment key={post.id}>
                  <article className={`piece-card ${post.super_likes_count > 0 ? "has-super-like" : ""}`}>
                    <div className="piece-card-kicker">{categoryLabel(post.category)}</div>
                    <h2 className="piece-card-title">
                      <PostTitleLink post={post}>{post.title}</PostTitleLink>
                    </h2>
                    <div className="piece-card-meta">
                      {post.owner?.username ? <AuthorLink user={post.owner} /> : null}
                    </div>
                  </article>
                  {index === 1 ? <AdSlot placement="inline" /> : null}
                </Fragment>
              ))}
            </div>
          ) : (
            <StatusPanel title="Seria nu are texte publice încă" />
          )}
        </div>
      ) : null}
    </PageShell>
  );
}

export default function SeriesRoute({ route }) {
  return <SeriesView slug={route.slug} />;
}
