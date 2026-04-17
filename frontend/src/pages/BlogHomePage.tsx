import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { Heart, MessageCircle, Eye, Award, Users } from "lucide-react";
import { fetchBlog } from "@/api/posts";
import { useSubdomain } from "@/hooks/useSubdomain";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { getAvatarUrl, formatDate, stripHtml, truncate, getBlogUrl } from "@/lib/utils";

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

  if (isLoading) return <PageLoader />;
  if (error || !data) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center px-4">
        <p className="text-muted">Nu am putut încărca blogul.</p>
      </div>
    );
  }

  const { blog_owner, featured_posts, latest_posts, all_posts, available_months, best_friends, user_awards, total_likes, total_comments } = data;

  return (
    <>
      <Helmet>
        <title>{blog_owner.username} | Calimara</title>
        <meta name="description" content={blog_owner.subtitle || `Blogul lui ${blog_owner.username} pe Calimara`} />
      </Helmet>

      {/* Blog Header */}
      <section className="border-b border-border bg-white py-14">
        <div className="mx-auto max-w-4xl px-4 text-center">
          <img
            src={getAvatarUrl(blog_owner.avatar_seed, 96)}
            alt={blog_owner.username}
            className="mx-auto h-24 w-24 rounded-full border border-border"
          />
          <h1 className="mt-5 font-display text-3xl font-semibold text-primary md:text-4xl">{blog_owner.username}</h1>
          {blog_owner.subtitle && (
            <p className="mt-3 text-muted">{blog_owner.subtitle}</p>
          )}
          <div className="mt-6 flex items-center justify-center gap-6 text-sm text-secondary">
            <span className="flex items-center gap-1.5"><Heart className="h-4 w-4" /> {total_likes} aprecieri</span>
            <span className="flex items-center gap-1.5"><MessageCircle className="h-4 w-4" /> {total_comments} comentarii</span>
            <span className="flex items-center gap-1.5"><Eye className="h-4 w-4" /> {all_posts.length} postări</span>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="grid gap-8 lg:grid-cols-3">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-8">
            {/* Featured Posts */}
            {featured_posts.length > 0 && (
              <div>
                <h2 className="mb-5 text-xs font-semibold uppercase tracking-[0.12em] text-muted">Postări alese</h2>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {featured_posts.map((post) => (
                    <a
                      key={post.id}
                      href={`${getBlogUrl(blog_owner.username)}/${post.slug}`}
                      className="group rounded-lg border border-border bg-white p-4 transition-colors hover:border-border-strong no-underline"
                    >
                      <h3 className="text-sm font-semibold tracking-tight text-primary line-clamp-2">{post.title}</h3>
                      <p className="mt-1.5 text-xs text-muted line-clamp-2">{truncate(stripHtml(post.content), 80)}</p>
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Latest Posts — editorial feed with hairline separators */}
            {latest_posts.length > 0 && (
              <div>
                <h2 className="mb-5 text-xs font-semibold uppercase tracking-[0.12em] text-muted">Cele mai recente</h2>
                <div className="divide-y divide-border">
                  {latest_posts.map((post) => (
                    <a
                      key={post.id}
                      href={`${getBlogUrl(blog_owner.username)}/${post.slug}`}
                      className="group block py-6 no-underline"
                    >
                      <h3 className="text-xl font-semibold tracking-tight text-primary transition-colors group-hover:text-primary-light md:text-2xl">{post.title}</h3>
                      <p className="mt-2 text-sm leading-relaxed text-secondary line-clamp-3">{truncate(stripHtml(post.content), 200)}</p>
                      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
                        <Badge variant="default">{post.category}</Badge>
                        <span>{formatDate(post.created_at)}</span>
                        <span className="flex items-center gap-1"><Heart className="h-3 w-3" /> {post.likes_count}</span>
                        <span className="flex items-center gap-1"><Eye className="h-3 w-3" /> {post.view_count}</span>
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Archive Table */}
            <div>
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">Arhivă</h2>
                {/* Month Filter */}
                {available_months.length > 0 && (
                  <select
                    className="rounded-md border border-border bg-white px-3 py-1.5 text-sm text-primary transition-colors hover:border-border-strong focus:outline-2 focus:outline-primary focus:outline-offset-0"
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
                    <option value="">Toate</option>
                    {available_months.map((m) => (
                      <option key={`${m.month}-${m.year}`} value={`${m.month}-${m.year}`}>
                        {new Date(m.year, m.month - 1).toLocaleDateString("ro-RO", { month: "long", year: "numeric" })} ({m.count})
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div className="rounded-lg border border-border overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-surface text-left">
                    <tr>
                      <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted">Titlu</th>
                      <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted hidden sm:table-cell">Categorie</th>
                      <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted hidden md:table-cell">Data</th>
                      <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted text-right">Vizualizări</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border bg-white">
                    {all_posts.map((post) => (
                      <tr key={post.id} className="transition-colors hover:bg-surface">
                        <td className="px-4 py-3">
                          <a href={`${getBlogUrl(blog_owner.username)}/${post.slug}`} className="font-medium text-primary hover:underline underline-offset-4 no-underline">
                            {post.title}
                          </a>
                        </td>
                        <td className="px-4 py-3 hidden sm:table-cell">
                          <Badge variant="default">{post.category}</Badge>
                        </td>
                        <td className="px-4 py-3 text-muted hidden md:table-cell">{formatDate(post.created_at)}</td>
                        <td className="px-4 py-3 text-right text-muted">{post.view_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {all_posts.length === 0 && (
                  <div className="px-4 py-10 text-center text-muted bg-white">Nicio postare încă.</div>
                )}
              </div>
            </div>
          </div>

          {/* Sidebar — sticky on lg+ */}
          <aside className="space-y-6 lg:sticky lg:top-20 lg:self-start">
            {/* Best Friends */}
            {best_friends.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-secondary" /> Prieteni apropiați
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {best_friends.map(({ user }) => (
                    <a key={user.id} href={getBlogUrl(user.username)} className="flex items-center gap-3 no-underline group">
                      <img src={getAvatarUrl(user.avatar_seed, 32)} alt={user.username} className="h-8 w-8 rounded-full border border-border" />
                      <span className="text-sm font-medium text-primary transition-colors group-hover:text-secondary">{user.username}</span>
                    </a>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Awards */}
            {user_awards.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2">
                    <Award className="h-4 w-4 text-secondary" /> Premii
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {user_awards.map((award) => (
                    <div key={award.id}>
                      <p className="text-sm font-medium text-primary">{award.award_title}</p>
                      <p className="text-xs text-muted">{award.award_description}</p>
                    </div>
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
