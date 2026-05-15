import { useEffect, useState } from "react";
import { FiBookOpen } from "react-icons/fi";
import { fetchPostDetail, postPdfUrl } from "../api/public.js";
import { TEXT_MODERATION_MESSAGE } from "../app/constants.js";
import { PieceCol, postHref, postToPiece } from "../app/content.jsx";
import { formatNumber } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { AdSlot, StatusPanel } from "../app/layout.jsx";
import { mainPath } from "../app/paths.js";
import { PostPromotionMenu } from "../app/post-actions.jsx";

const DESKTOP_READER_QUERY = "(min-width: 821px)";

function useDesktopReaderSurface() {
  const [matches, setMatches] = useState(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
    return window.matchMedia(DESKTOP_READER_QUERY).matches;
  });

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return undefined;
    const query = window.matchMedia(DESKTOP_READER_QUERY);
    const update = () => setMatches(query.matches);
    update();
    if (typeof query.addEventListener === "function") {
      query.addEventListener("change", update);
      return () => query.removeEventListener("change", update);
    }
    query.addListener(update);
    return () => query.removeListener(update);
  }, []);

  return matches;
}

function SeriesContextPanel({ context }) {
  if (!context?.series) return null;
  const { series, previous_post: previousPost, next_post: nextPost } = context;
  return (
    <section className="piece-series" aria-label="Context serie">
      <div className="piece-series-head">
        <div>
          <div className="piece-series-kicker">serie · {formatNumber(context.position)} din {formatNumber(context.total_posts)}</div>
          <a className="piece-series-name" href={mainPath(`/serii/${series.slug}`)}>{series.title}</a>
        </div>
        <FiBookOpen aria-hidden="true" />
      </div>
      <div className="piece-series-links">
        {previousPost ? (
          <a className="piece-series-link" href={postHref(previousPost)}>Anterior: {previousPost.title}</a>
        ) : <span className="piece-series-empty">Primul text din serie</span>}
        {nextPost ? (
          <a className="piece-series-link" href={postHref(nextPost)}>Următor: {nextPost.title}</a>
        ) : <span className="piece-series-empty">Ultimul text din serie</span>}
      </div>
    </section>
  );
}
function PostDetailView({ username, slug, user, onAuthPostIdChange, onFooterPostActionsChange }) {
  const { data, error, loading } = useAsync(() => fetchPostDetail(username, slug), [username, slug, user?.id]);
  const desktopReaderSurface = useDesktopReaderSurface();
  const piece = data ? postToPiece({ ...data.post, owner: data.blog_owner }) : null;
  const actionPost = data ? { ...data.post, owner: data.blog_owner } : null;
  const pdfHref = data?.blog_owner?.username && data?.post?.slug
    ? postPdfUrl(data.blog_owner.username, data.post.slug)
    : "#";

  useEffect(() => {
    const visiblePostId = data?.post?.moderation_status === "approved" ? data.post.id : null;
    onAuthPostIdChange?.(visiblePostId ?? null);
    return () => onAuthPostIdChange?.(null);
  }, [data?.post?.id, data?.post?.moderation_status, onAuthPostIdChange]);

  useEffect(() => {
    if (!data || data.post.moderation_status !== "approved") {
      onFooterPostActionsChange?.(null);
      return undefined;
    }
    onFooterPostActionsChange?.({
      key: `post:${data.post.id}`,
      post: { ...data.post, owner: data.blog_owner },
      pdfHref
    });
    return () => onFooterPostActionsChange?.(null);
  }, [data, pdfHref, onFooterPostActionsChange]);

  const detailExtras = data ? (
    <>
      <SeriesContextPanel context={data.series_context} />
      <AdSlot placement="postFooter" />
    </>
  ) : null;

  return (
    <main className="stage stage-single">
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca textul">{error}</StatusPanel> : null}
      {piece ? (
        <div className={`piece-wrap ${data.post.super_likes_count > 0 ? "has-super-like" : ""}`}>
          <div className="detail-stack">
            {data.post.moderation_status !== "approved" ? (
              <StatusPanel title="Text în curs de moderare">{TEXT_MODERATION_MESSAGE}</StatusPanel>
            ) : null}
            <PieceCol
              piece={piece}
              animKey={slug}
              titleAction={data.post.moderation_status === "approved" ? (
                <PostPromotionMenu post={actionPost} author={data.blog_owner} user={user} />
              ) : null}
              readerFooter={desktopReaderSurface ? detailExtras : null}
            />
            {desktopReaderSurface ? null : detailExtras}
          </div>
        </div>
      ) : null}
    </main>
  );
}

export default function PostRoute({ route, user, onAuthPostIdChange, onFooterPostActionsChange }) {
  return (
    <PostDetailView
      username={route.username}
      slug={route.slug}
      user={user}
      onAuthPostIdChange={onAuthPostIdChange}
      onFooterPostActionsChange={onFooterPostActionsChange}
    />
  );
}
