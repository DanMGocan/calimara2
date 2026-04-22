import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import DOMPurify from "dompurify";
import {
  createComment,
  fetchPostDetail,
  toggleLike,
  type CommentCreateData,
} from "@/api/posts";
import { fetchPostCollections } from "@/api/collections";
import { AddToCollectionDialog } from "@/components/collections/AddToCollectionDialog";
import { useSubdomain } from "@/hooks/useSubdomain";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/components/ui/toast-context";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { Stage, LeftCol, PieceCol } from "@/components/ui/stage";
import {
  ActionRow,
  ActionsGroup,
  SideHint,
  SideKicker,
} from "@/components/ui/action-row";
import { KindBadge } from "@/components/ui/kind-badge";
import { RevealText } from "@/components/ui/reveal-text";
import { PieceScroll } from "@/components/ui/piece-scroll";
import { ReactionButton } from "@/components/ui/reaction-button";
import { SuperLikeButton } from "@/components/ui/super-like-button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  cn,
  formatDateTime,
  formatRelativeTime,
  getBlogUrl,
  stripHtml,
  truncate,
} from "@/lib/utils";

const heartSvg = (filled: boolean) => (
  <svg width="14" height="14" viewBox="0 0 16 16" fill={filled ? "currentColor" : "none"} aria-hidden>
    <path
      d="M8 13.5s-4.8-2.9-6.2-5.7C.6 5.7 1.7 3 4.2 3c1.6 0 2.7.9 3.3 2.1h1c.6-1.2 1.7-2.1 3.3-2.1 2.5 0 3.6 2.7 2.4 4.8C12.8 10.6 8 13.5 8 13.5Z"
      stroke="currentColor"
      strokeWidth="1.2"
      strokeLinejoin="round"
    />
  </svg>
);

const shareSvg = (
  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
    <circle cx="4" cy="8" r="1.8" stroke="currentColor" strokeWidth="1.2" />
    <circle cx="12" cy="4" r="1.8" stroke="currentColor" strokeWidth="1.2" />
    <circle cx="12" cy="12" r="1.8" stroke="currentColor" strokeWidth="1.2" />
    <path d="M5.6 7.2l4.8-2.4M5.6 8.8l4.8 2.4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
  </svg>
);

const commentSvg = (
  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
    <path
      d="M2.5 3.5h11a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H6l-3 2.5v-2.5h-.5a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1Z"
      stroke="currentColor"
      strokeWidth="1.2"
      strokeLinejoin="round"
    />
  </svg>
);

export default function PostDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const { username } = useSubdomain();
  const { isAuthenticated, user } = useAuth();
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["post", username, slug],
    queryFn: () => fetchPostDetail(username!, slug!),
    enabled: !!username && !!slug,
  });

  const postId = data?.post.id;
  const collectionsQuery = useQuery({
    queryKey: ["post", postId ?? 0, "collections"],
    queryFn: () => fetchPostCollections(postId!),
    enabled: !!postId,
  });

  const [commentsOpen, setCommentsOpen] = useState(false);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [commentForm, setCommentForm] = useState<CommentCreateData>({
    content: "",
    author_name: "",
    author_email: "",
  });

  const likeMutation = useMutation({
    mutationFn: () => toggleLike(data!.post.id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["post", username, slug] }),
  });

  const commentMutation = useMutation({
    mutationFn: () => createComment(data!.post.id, commentForm),
    onSuccess: () => {
      setCommentForm({ content: "", author_name: "", author_email: "" });
      queryClient.invalidateQueries({ queryKey: ["post", username, slug] });
      showToast("Comentariu trimis.", "success");
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  if (isLoading) return <PageLoader />;
  if (error || !data) {
    return (
      <Stage variant="centered">
        <PieceCol>
          <KindBadge label="404" />
          <h1 className="piece-title">Postarea nu a fost găsită.</h1>
        </PieceCol>
      </Stage>
    );
  }

  const { blog_owner, post, related_posts } = data;
  const plainBody = stripHtml(DOMPurify.sanitize(post.content));
  const when = formatDateTime(post.created_at);
  const blogUrl = getBlogUrl(blog_owner.username);
  const kindLabel = post.category_name ?? "Text";
  const approvedComments = post.approved_comments ?? [];

  return (
    <>
      <Helmet>
        <title>
          {post.title} — {blog_owner.username} | călimara.ro
        </title>
        <meta name="description" content={truncate(plainBody, 160)} />
      </Helmet>

      <Stage>
        <LeftCol>
          <aside className="side-col">
            <SideKicker>autor</SideKicker>
            <ActionsGroup>
              <ActionRow num={1} label={`Blogul lui ${blog_owner.username}`} sub="înapoi la pagina autorului" href={blogUrl} />
            </ActionsGroup>
            {related_posts.length > 0 ? (
              <>
                <SideKicker>alte texte</SideKicker>
                <div className="flex flex-col gap-3">
                  {related_posts.slice(0, 4).map((p) => (
                    <Link
                      key={p.id}
                      to={`/${p.slug}`}
                      className="text-sm leading-snug"
                      style={{
                        fontFamily: "var(--font-serif)",
                        color: "var(--color-ink-soft)",
                        textDecoration: "none",
                        borderBottom: "1px solid var(--color-hairline)",
                        paddingBottom: 10,
                      }}
                    >
                      {p.title}
                    </Link>
                  ))}
                </div>
              </>
            ) : null}
            <SideHint>
              <span className="kbd">Esc</span>
              <span>înapoi</span>
            </SideHint>
          </aside>
        </LeftCol>

        <PieceCol>
          <KindBadge label={kindLabel} />
          <h1 className={cn("piece-title", post.super_likes_count > 0 && "has-super-like")}>
            {post.title}
          </h1>
          <div className="piece-meta">
            <Link to="/" className="piece-author" style={{ textDecoration: "none" }}>
              {blog_owner.username}
            </Link>
            <span className="piece-meta-dot" />
            <span className="piece-year">{when}</span>
            <span className="piece-meta-dot" />
            <span className="piece-year">{post.view_count} vizualizări</span>
          </div>

          <PieceScroll resetKey={post.id}>
            <RevealText text={plainBody} keySeed={post.id} />
            <div className="piece-end">
              <span>fin</span>
              <span className="piece-end-mark">· · ·</span>
            </div>
          </PieceScroll>

          <div className="piece-reactions">
            <ReactionButton
              icon={heartSvg(likeMutation.isSuccess)}
              label="Apreciază"
              count={post.likes_count}
              variant="like"
              active={likeMutation.isSuccess}
              disabled={likeMutation.isPending}
              onClick={() => likeMutation.mutate()}
            />
            <SuperLikeButton
              postId={post.id}
              postOwnerId={post.user_id}
              viewerId={user?.id ?? null}
              superLikesCount={post.super_likes_count}
              viewerSuperLiked={post.viewer_super_liked}
              onChange={(nextCount, nextLiked) => {
                queryClient.setQueryData<typeof data>(
                  ["post", username, slug],
                  (old) =>
                    old && {
                      ...old,
                      post: {
                        ...old.post,
                        super_likes_count: nextCount,
                        viewer_super_liked: nextLiked,
                      },
                    },
                );
              }}
              onError={(msg) => showToast(msg, "danger")}
            />
            <ReactionButton
              icon={shareSvg}
              label="Distribuie"
              onClick={() => {
                try {
                  if (navigator.share) {
                    navigator.share({
                      title: post.title,
                      text: `${post.title} — ${blog_owner.username}`,
                      url: window.location.href,
                    });
                  } else {
                    navigator.clipboard?.writeText(window.location.href);
                    showToast("Link copiat.", "success");
                  }
                } catch {
                  /* noop */
                }
              }}
            />
            <ReactionButton
              icon={commentSvg}
              label="Comentarii"
              count={approvedComments.length}
              active={commentsOpen}
              onClick={() => setCommentsOpen((v) => !v)}
            />
          </div>

          <div className="piece-actions">
            <button
              type="button"
              className="piece-pdf"
              onClick={() => window.print()}
              aria-label="Descarcă PDF"
              title="Descarcă PDF"
            >
              <svg width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden>
                <path
                  d="M7 1v8m0 0L4 6.5M7 9l3-2.5"
                  stroke="currentColor"
                  strokeWidth="1.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M2 11.5v1a.5.5 0 0 0 .5.5h9a.5.5 0 0 0 .5-.5v-1"
                  stroke="currentColor"
                  strokeWidth="1.2"
                  strokeLinecap="round"
                />
              </svg>
              <span>PDF</span>
            </button>
            <PieceCollections
              collections={collectionsQuery.data?.collections ?? []}
              loading={collectionsQuery.isLoading}
            />
            {isAuthenticated && user ? (
              <button
                type="button"
                className="piece-collection"
                onClick={() => setAddDialogOpen(true)}
                style={{
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  color: "var(--color-ink-soft)",
                  padding: 0,
                }}
              >
                {user.id === post.user_id
                  ? "+ Sugerează într-o colecție"
                  : "+ Adaugă la colecția mea"}
              </button>
            ) : null}
          </div>

          <AddToCollectionDialog
            open={addDialogOpen}
            onOpenChange={setAddDialogOpen}
            post={{ id: post.id, title: post.title, user_id: post.user_id }}
            currentUserId={user?.id ?? null}
            excludeCollectionIds={(collectionsQuery.data?.collections ?? [])
              .filter((c) => user && c.owner.id === user.id)
              .map((c) => c.id)}
          />

          <div
            className={`piece-comments ${commentsOpen ? "open" : ""}`}
            aria-hidden={!commentsOpen}
          >
            <div className="piece-comments-inner">
              {approvedComments.length > 0 ? (
                <ul className="comment-list">
                  {approvedComments.map((c) => (
                    <li key={c.id} className="comment">
                      <div className="comment-head">
                        <span className="comment-author">
                          {c.user?.username ?? c.author_name ?? "anonim"}
                        </span>
                        <span className="comment-time">{formatRelativeTime(c.created_at)}</span>
                      </div>
                      <p className="comment-body">{c.content}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p
                  style={{
                    color: "var(--color-ink-faint)",
                    fontFamily: "var(--font-sans)",
                    fontSize: 13,
                  }}
                >
                  Niciun comentariu încă.
                </p>
              )}

              <form
                className="mt-6 flex flex-col gap-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  commentMutation.mutate();
                }}
              >
                {!isAuthenticated ? (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Input
                      placeholder="Numele tău"
                      value={commentForm.author_name}
                      onChange={(e) =>
                        setCommentForm({ ...commentForm, author_name: e.target.value })
                      }
                      required
                      tabIndex={commentsOpen ? 0 : -1}
                    />
                    <Input
                      type="email"
                      placeholder="Email (opțional)"
                      value={commentForm.author_email}
                      onChange={(e) =>
                        setCommentForm({ ...commentForm, author_email: e.target.value })
                      }
                      tabIndex={commentsOpen ? 0 : -1}
                    />
                  </div>
                ) : null}
                <Textarea
                  placeholder="Scrie un comentariu…"
                  value={commentForm.content}
                  onChange={(e) => setCommentForm({ ...commentForm, content: e.target.value })}
                  required
                  rows={3}
                  tabIndex={commentsOpen ? 0 : -1}
                />
                <div className="flex items-center justify-between">
                  <span
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      letterSpacing: "0.18em",
                      textTransform: "uppercase",
                      color: "var(--color-ink-faint)",
                    }}
                  >
                    comentariile sunt moderate
                  </span>
                  <Button
                    type="submit"
                    size="sm"
                    disabled={commentMutation.isPending}
                    tabIndex={commentsOpen ? 0 : -1}
                  >
                    {commentMutation.isPending ? "se trimite…" : "trimite"}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </PieceCol>
      </Stage>
    </>
  );
}

function PieceCollections({
  collections,
  loading,
}: {
  collections: { id: number; title: string; slug: string; owner: { username: string } }[];
  loading: boolean;
}) {
  const icon = (
    <svg width="12" height="12" viewBox="0 0 14 14" fill="none" aria-hidden>
      <path
        d="M3 2.5h6.5L11 4v7.5H3v-9Z"
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinejoin="round"
        opacity="0.6"
      />
    </svg>
  );
  if (loading) {
    return (
      <span className="piece-collection piece-collection-empty">
        {icon}
        <span>se încarcă colecțiile…</span>
      </span>
    );
  }
  if (collections.length === 0) {
    return (
      <span className="piece-collection piece-collection-empty">
        {icon}
        <span>Nu face parte dintr-o colecție</span>
      </span>
    );
  }
  if (collections.length === 1) {
    const c = collections[0];
    const href = `${getBlogUrl(c.owner.username)}/colectii/${c.slug}`;
    return (
      <a href={href} className="piece-collection" style={{ textDecoration: "none", color: "inherit" }}>
        {icon}
        <span>
          Face parte din colecția <strong>{c.title}</strong>
        </span>
      </a>
    );
  }
  // 2+
  const first = collections[0];
  const firstHref = `${getBlogUrl(first.owner.username)}/colectii/${first.slug}`;
  return (
    <a href={firstHref} className="piece-collection" style={{ textDecoration: "none", color: "inherit" }}>
      {icon}
      <span>Face parte din mai multe colecții</span>
    </a>
  );
}
