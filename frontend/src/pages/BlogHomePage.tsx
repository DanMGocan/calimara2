import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { Heart, MessageCircle, Eye, Award, Users, Calendar } from "lucide-react";
import { fetchBlog } from "@/api/posts";
import { useSubdomain } from "@/hooks/useSubdomain";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { getAvatarUrl, formatDate, stripHtml, truncate, getBlogUrl } from "@/lib/utils";

export default function BlogHomePage() {
  const { username } = useSubdomain();
  const [searchParams, setSearchParams] = useSearchParams();
  const month = searchParams.get("month") ? Number(searchParams.get("month")) : undefined;
  const year = searchParams.get("year") ? Number(searchParams.get("year")) : undefined;

  const { data, isLoading } = useQuery({
    queryKey: ["blog", username, month, year],
    queryFn: () => fetchBlog(username!, month, year),
    enabled: !!username,
  });

  if (isLoading || !data) return <PageLoader />;

  const { blog_owner, featured_posts, latest_posts, all_posts, available_months, best_friends, user_awards, total_likes, total_comments } = data;

  return (
    <>
      <Helmet>
        <title>{blog_owner.username} | Calimara</title>
        <meta name="description" content={blog_owner.subtitle || `Blogul lui ${blog_owner.username} pe Calimara`} />
      </Helmet>

      {/* Blog Header */}
      <section className="border-b border-border bg-surface-raised py-12">
        <div className="mx-auto max-w-4xl px-4 text-center">
          <img
            src={getAvatarUrl(blog_owner.avatar_seed, 96)}
            alt={blog_owner.username}
            className="mx-auto h-24 w-24 rounded-full shadow-md"
          />
          <h1 className="mt-4 font-display text-3xl font-bold text-primary">{blog_owner.username}</h1>
          {blog_owner.subtitle && (
            <p className="mt-2 text-muted">{blog_owner.subtitle}</p>
          )}
          <div className="mt-4 flex items-center justify-center gap-6 text-sm text-muted">
            <span className="flex items-center gap-1"><Heart className="h-4 w-4" /> {total_likes} aprecieri</span>
            <span className="flex items-center gap-1"><MessageCircle className="h-4 w-4" /> {total_comments} comentarii</span>
            <span className="flex items-center gap-1"><Eye className="h-4 w-4" /> {all_posts.length} postari</span>
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
                <h2 className="font-display text-xl font-bold text-primary mb-4">Postari alese</h2>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {featured_posts.map((post) => (
                    <a
                      key={post.id}
                      href={`${getBlogUrl(blog_owner.username)}/${post.slug}`}
                      className="group rounded-xl border border-border bg-surface-raised p-4 transition-all hover:shadow-md hover:-translate-y-0.5 no-underline"
                    >
                      <h3 className="text-sm font-semibold text-primary group-hover:text-accent line-clamp-2">{post.title}</h3>
                      <p className="mt-1 text-xs text-muted line-clamp-2">{truncate(stripHtml(post.content), 80)}</p>
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Latest Posts */}
            {latest_posts.length > 0 && (
              <div>
                <h2 className="font-display text-xl font-bold text-primary mb-4">Cele mai recente</h2>
                <div className="space-y-4">
                  {latest_posts.map((post) => (
                    <Card key={post.id} className="group transition-all hover:shadow-md">
                      <CardContent className="p-5">
                        <a href={`${getBlogUrl(blog_owner.username)}/${post.slug}`} className="no-underline">
                          <h3 className="text-lg font-semibold text-primary group-hover:text-accent">{post.title}</h3>
                        </a>
                        <p className="mt-2 text-sm text-muted line-clamp-3">{truncate(stripHtml(post.content), 200)}</p>
                        <div className="mt-3 flex items-center gap-3 text-xs text-muted">
                          <Badge variant="default">{post.category}</Badge>
                          <span>{formatDate(post.created_at)}</span>
                          <span className="flex items-center gap-1"><Heart className="h-3 w-3" /> {post.likes_count}</span>
                          <span className="flex items-center gap-1"><Eye className="h-3 w-3" /> {post.view_count}</span>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            )}

            {/* Archive Table */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-display text-xl font-bold text-primary">Arhiva</h2>
                {/* Month Filter */}
                {available_months.length > 0 && (
                  <select
                    className="rounded-lg border border-border bg-surface-raised px-3 py-1.5 text-sm text-primary"
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

              <div className="rounded-xl border border-border overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-surface text-left">
                    <tr>
                      <th className="px-4 py-3 font-medium text-muted">Titlu</th>
                      <th className="px-4 py-3 font-medium text-muted hidden sm:table-cell">Categorie</th>
                      <th className="px-4 py-3 font-medium text-muted hidden md:table-cell">Data</th>
                      <th className="px-4 py-3 font-medium text-muted text-right">Vizualizari</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border bg-surface-raised">
                    {all_posts.map((post) => (
                      <tr key={post.id} className="hover:bg-surface transition-colors">
                        <td className="px-4 py-3">
                          <a href={`${getBlogUrl(blog_owner.username)}/${post.slug}`} className="font-medium text-primary hover:text-accent no-underline">
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
                  <div className="px-4 py-8 text-center text-muted bg-surface-raised">Nicio postare inca.</div>
                )}
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Best Friends */}
            {best_friends.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Users className="h-4 w-4 text-accent" /> Prieteni apropiati
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {best_friends.map(({ user }) => (
                    <a key={user.id} href={getBlogUrl(user.username)} className="flex items-center gap-3 no-underline group">
                      <img src={getAvatarUrl(user.avatar_seed, 32)} alt={user.username} className="h-8 w-8 rounded-full" />
                      <span className="text-sm font-medium text-primary group-hover:text-accent">{user.username}</span>
                    </a>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Awards */}
            {user_awards.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Award className="h-4 w-4 text-highlight" /> Premii
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
          </div>
        </div>
      </div>
    </>
  );
}
