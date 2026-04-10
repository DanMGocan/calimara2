import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { Heart, Eye, Calendar, ArrowLeft, Share2, MessageCircle } from "lucide-react";
import { fetchPostDetail, toggleLike, createComment, type CommentCreateData } from "@/api/posts";
import { useSubdomain } from "@/hooks/useSubdomain";
import { useAuth } from "@/hooks/useAuth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { getAvatarUrl, formatDate, getBlogUrl, stripHtml, truncate } from "@/lib/utils";
import DOMPurify from "dompurify";

export default function PostDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const { username } = useSubdomain();
  const { user, isAuthenticated } = useAuth();
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

  const { blog_owner, post, related_posts, other_authors_posts, other_authors } = data;

  return (
    <>
      <Helmet>
        <title>{post.title} - {blog_owner.username} | Calimara</title>
        <meta name="description" content={truncate(stripHtml(post.content), 160)} />
      </Helmet>

      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="grid gap-8 lg:grid-cols-3">
          {/* Main Content */}
          <article className="lg:col-span-2">
            {/* Back link */}
            <a href={getBlogUrl(blog_owner.username)} className="inline-flex items-center gap-1 text-sm text-muted hover:text-primary mb-6 no-underline">
              <ArrowLeft className="h-4 w-4" /> Inapoi la {blog_owner.username}
            </a>

            {/* Post Header */}
            <header>
              <div className="flex items-center gap-3 mb-4">
                <a href={getBlogUrl(blog_owner.username)}>
                  <img src={getAvatarUrl(blog_owner.avatar_seed, 48)} alt={blog_owner.username} className="h-12 w-12 rounded-full" />
                </a>
                <div>
                  <a href={getBlogUrl(blog_owner.username)} className="font-medium text-primary hover:text-accent no-underline">{blog_owner.username}</a>
                  <div className="flex items-center gap-2 text-xs text-muted">
                    <span className="flex items-center gap-1"><Calendar className="h-3 w-3" /> {formatDate(post.created_at)}</span>
                    <span className="flex items-center gap-1"><Eye className="h-3 w-3" /> {post.view_count}</span>
                  </div>
                </div>
              </div>
              <h1 className="font-display text-3xl font-medium text-primary md:text-4xl">{post.title}</h1>
              <div className="mt-3 flex items-center gap-2">
                <Badge>{post.category}</Badge>
                {post.genre && <Badge variant="secondary">{post.genre}</Badge>}
                {post.tags?.map((tag) => (
                  <Badge key={tag.id} variant="outline">{tag.tag_name}</Badge>
                ))}
              </div>
            </header>

            {/* Post Content */}
            <div
              className="prose-content mt-8 text-primary/90 leading-relaxed"
              dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(post.content) }}
            />

            {/* Actions */}
            <div className="mt-8 flex items-center gap-4 border-t border-border pt-6">
              <Button
                variant="outline"
                size="sm"
                onClick={() => likeMutation.mutate()}
                disabled={likeMutation.isPending}
              >
                <Heart className={`h-4 w-4 ${likeMutation.isSuccess ? "fill-danger text-danger" : ""}`} />
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
            <section className="mt-10">
              <h2 className="font-display text-xl font-medium text-primary flex items-center gap-2">
                <MessageCircle className="h-5 w-5" />
                Comentarii ({post.approved_comments?.length ?? 0})
              </h2>

              {/* Comment List */}
              <div className="mt-4 space-y-4">
                {post.approved_comments?.map((comment) => (
                  <div key={comment.id} className="rounded-lg border border-border bg-surface-raised p-4">
                    <div className="flex items-center gap-2 mb-2">
                      {comment.user ? (
                        <>
                          <img src={getAvatarUrl(comment.user.avatar_seed, 24)} alt="" className="h-6 w-6 rounded-full" />
                          <span className="text-sm font-medium text-primary">{comment.user.username}</span>
                        </>
                      ) : (
                        <span className="text-sm font-medium text-primary">{comment.author_name}</span>
                      )}
                      <span className="text-xs text-muted">{formatDate(comment.created_at)}</span>
                    </div>
                    <p className="text-sm text-primary/80">{comment.content}</p>
                  </div>
                ))}
              </div>

              {/* Comment Form */}
              <form
                className="mt-6 space-y-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  commentMutation.mutate();
                }}
              >
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
          <aside className="space-y-6">
            {/* Related Posts */}
            {related_posts.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Mai mult de la {blog_owner.username}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {related_posts.map((p) => (
                    <a key={p.id} href={`${getBlogUrl(blog_owner.username)}/${p.slug}`} className="block text-sm font-medium text-primary hover:text-accent no-underline line-clamp-2">
                      {p.title}
                    </a>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Other Authors */}
            {other_authors.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Descopera si alti scriitori</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {other_authors.map((author) => (
                    <a key={author.id} href={getBlogUrl(author.username)} className="flex items-center gap-3 no-underline group">
                      <img src={getAvatarUrl(author.avatar_seed, 32)} alt="" className="h-8 w-8 rounded-full" />
                      <div>
                        <span className="text-sm font-medium text-primary group-hover:text-accent">{author.username}</span>
                        {author.subtitle && <p className="text-xs text-muted">{author.subtitle}</p>}
                      </div>
                    </a>
                  ))}
                </CardContent>
              </Card>
            )}
          </aside>
        </div>
      </div>
    </>
  );
}
