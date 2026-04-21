import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { Heart, Eye, Calendar, ArrowLeft, Share2, MessageCircle } from "lucide-react";
import { fetchPostDetail, toggleLike, createComment, type CommentCreateData } from "@/api/posts";
import { useSubdomain } from "@/hooks/useSubdomain";
import { useAuth } from "@/hooks/useAuth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast-context";
import { DebugLabel } from "@/components/ui/debug-label";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { getAvatarUrl, formatDate, getBlogUrl, stripHtml, truncate } from "@/lib/utils";
import DOMPurify from "dompurify";

export default function PostDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const { username } = useSubdomain();
  const { isAuthenticated } = useAuth();
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["post", username, slug],
    queryFn: () => fetchPostDetail(username!, slug!),
    enabled: !!username && !!slug,
  });

  // Like mutation
  const likeMutation = useMutation({
    mutationFn: () => toggleLike(data!.post.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["post", username, slug] });
    },
  });

  // Comment form
  const [commentForm, setCommentForm] = useState<CommentCreateData>({ content: "", author_name: "", author_email: "" });
  const commentMutation = useMutation({
    mutationFn: () => createComment(data!.post.id, commentForm),
    onSuccess: () => {
      setCommentForm({ content: "", author_name: "", author_email: "" });
      queryClient.invalidateQueries({ queryKey: ["post", username, slug] });
      showToast("Comentariu trimis!", "success");
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  if (isLoading) return <PageLoader />;
  if (error || !data) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <p className="text-muted">Postarea nu a fost gasita.</p>
      </div>
    );
  }

  const { blog_owner, post, related_posts, other_authors } = data;

  return (
    <>
      <Helmet>
        <title>{post.title} - {blog_owner.username} | Calimara</title>
        <meta name="description" content={truncate(stripHtml(post.content), 160)} />
      </Helmet>

      <div className="relative py-10">
        <DebugLabel name="PostDetailPage" />
        <div className="relative mx-auto grid gap-12 lg:max-w-5xl lg:grid-cols-[minmax(0,680px)_260px]">
          <DebugLabel name="PostDetailGrid" />
          {/* Main Content — narrow reading column */}
          <article className="relative min-w-0">
            <DebugLabel name="PostArticle" />
            {/* Back link */}
            <a href={getBlogUrl(blog_owner.username)} className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-primary mb-8 no-underline transition-colors">
              <ArrowLeft className="h-4 w-4" /> Înapoi la {blog_owner.username}
            </a>

            {/* Post Header */}
            <header className="relative">
              <DebugLabel name="PostHeader" />
              <h1 className="font-display text-3xl font-semibold leading-[1.1] text-primary md:text-4xl">{post.title}</h1>

              <div className="mt-6 flex items-center gap-3">
                <a href={getBlogUrl(blog_owner.username)}>
                  <img src={getAvatarUrl(blog_owner.avatar_seed, 44)} alt={blog_owner.username} className="h-11 w-11 rounded-full border border-border" />
                </a>
                <div>
                  <a href={getBlogUrl(blog_owner.username)} className="text-sm font-medium text-primary hover:underline underline-offset-4 no-underline">{blog_owner.username}</a>
                  <div className="mt-0.5 flex items-center gap-3 text-xs text-muted">
                    <span className="flex items-center gap-1"><Calendar className="h-3 w-3" /> {formatDate(post.created_at)}</span>
                    <span className="flex items-center gap-1"><Eye className="h-3 w-3" /> {post.view_count}</span>
                  </div>
                </div>
              </div>

              {(post.category_name || (post.tags && post.tags.length > 0)) && (
                <div className="mt-5 flex flex-wrap items-center gap-2">
                  {post.category_name && <Badge>{post.category_name}</Badge>}
                  {post.tags?.map((tag) => (
                    <Badge key={tag.id} variant="outline">{tag.tag_name}</Badge>
                  ))}
                </div>
              )}
            </header>

            {/* Post Content */}
            <div
              className="prose-content mt-10 text-primary"
              dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(post.content) }}
            />

            {/* Actions */}
            <div className="relative mt-10 flex items-center gap-3 border-t border-border pt-6">
              <DebugLabel name="PostActions" />
              <Button
                variant="outline"
                size="sm"
                onClick={() => likeMutation.mutate()}
                disabled={likeMutation.isPending}
              >
                <Heart className={`h-4 w-4 ${likeMutation.isSuccess ? "fill-primary text-primary" : ""}`} />
                {post.likes_count} aprecieri
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  navigator.clipboard.writeText(window.location.href);
                  showToast("Link copiat!", "success");
                }}
              >
                <Share2 className="h-4 w-4" /> Distribuie
              </Button>
            </div>

            {/* Comments */}
            <section className="relative mt-14 border-t border-border pt-10">
              <DebugLabel name="CommentsSection" />
              <h2 className="flex items-center gap-2 text-lg font-semibold tracking-tight text-primary">
                <MessageCircle className="h-5 w-5" />
                Comentarii ({post.approved_comments?.length ?? 0})
              </h2>

              {/* Comment List */}
              <div className="relative mt-6 space-y-3">
                <DebugLabel name="CommentList" />
                {post.approved_comments?.map((comment) => (
                  <div key={comment.id} className="rounded-lg bg-surface p-4">
                    <div className="flex items-center gap-2 mb-2">
                      {comment.user ? (
                        <>
                          <img src={getAvatarUrl(comment.user.avatar_seed, 24)} alt={`Avatar ${comment.user.username}`} className="h-6 w-6 rounded-full border border-border" />
                          <span className="text-sm font-medium text-primary">{comment.user.username}</span>
                        </>
                      ) : (
                        <span className="text-sm font-medium text-primary">{comment.author_name}</span>
                      )}
                      <span className="text-xs text-muted">{formatDate(comment.created_at)}</span>
                    </div>
                    <p className="text-sm leading-relaxed text-secondary">{comment.content}</p>
                  </div>
                ))}
              </div>

              {/* Comment Form */}
              <form
                className="relative mt-6 space-y-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  commentMutation.mutate();
                }}
              >
                <DebugLabel name="CommentForm" />
                {!isAuthenticated && (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Input
                      placeholder="Numele tau"
                      value={commentForm.author_name}
                      onChange={(e) => setCommentForm({ ...commentForm, author_name: e.target.value })}
                      required
                    />
                    <Input
                      type="email"
                      placeholder="Email (optional)"
                      value={commentForm.author_email}
                      onChange={(e) => setCommentForm({ ...commentForm, author_email: e.target.value })}
                    />
                  </div>
                )}
                <Textarea
                  placeholder="Scrie un comentariu..."
                  value={commentForm.content}
                  onChange={(e) => setCommentForm({ ...commentForm, content: e.target.value })}
                  required
                  rows={3}
                />
                <div className="flex items-center justify-between">
                  <p className="text-xs text-muted">Comentariile sunt moderate automat.</p>
                  <Button type="submit" size="sm" disabled={commentMutation.isPending}>
                    {commentMutation.isPending ? "Se trimite..." : "Trimite"}
                  </Button>
                </div>
              </form>
            </section>
          </article>

          {/* Sidebar */}
          <aside className="relative space-y-6 lg:sticky lg:top-20 lg:self-start">
            <DebugLabel name="PostSidebar" />
            {/* Related Posts */}
            {related_posts.length > 0 && (
              <div className="relative">
                <DebugLabel name="RelatedPosts" />
                <h3 className="mb-4 text-xs font-semibold uppercase tracking-[0.12em] text-muted">Mai mult de la {blog_owner.username}</h3>
                <div className="space-y-3 border-t border-border pt-4">
                  {related_posts.map((p) => (
                    <a key={p.id} href={`${getBlogUrl(blog_owner.username)}/${p.slug}`} className="block text-sm font-medium leading-snug text-primary hover:underline underline-offset-4 no-underline line-clamp-2">
                      {p.title}
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Other Authors */}
            {other_authors.length > 0 && (
              <div className="relative">
                <DebugLabel name="OtherAuthors" />
                <h3 className="mb-4 text-xs font-semibold uppercase tracking-[0.12em] text-muted">Descoperă și alți scriitori</h3>
                <div className="space-y-4 border-t border-border pt-4">
                  {other_authors.map((author) => (
                    <a key={author.id} href={getBlogUrl(author.username)} className="flex items-center gap-3 no-underline group">
                      <img src={getAvatarUrl(author.avatar_seed, 32)} alt={`Avatar ${author.username}`} className="h-8 w-8 rounded-full border border-border" />
                      <div>
                        <span className="text-sm font-medium text-primary transition-colors group-hover:text-secondary">{author.username}</span>
                        {author.subtitle && <p className="text-xs text-muted">{author.subtitle}</p>}
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </aside>
        </div>
      </div>
    </>
  );
}
