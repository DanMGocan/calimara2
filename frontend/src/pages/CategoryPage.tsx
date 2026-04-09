import { useParams, useSearchParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { Heart, Eye } from "lucide-react";
import { fetchCategoryPage } from "@/api/posts";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { getCategoryName } from "@/lib/categories";
import { getAvatarUrl, formatDate, stripHtml, truncate, getBlogUrl } from "@/lib/utils";

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
        <title>{data.category_name} | Calimara</title>
      </Helmet>

      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="mb-8">
          <h1 className="font-display text-3xl font-bold text-primary">{data.category_name}</h1>
          {/* Genre links */}
          {data.genres.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-2">
              {data.genres.map(([key, name]) => (
                <Link
                  key={key}
                  to={`/category/${categoryKey}/${key}`}
                  className="rounded-full border border-border px-3 py-1 text-sm text-muted transition-colors hover:border-accent hover:text-accent no-underline"
                >
                  {name}
                </Link>
              ))}
            </div>
          )}

          {/* Sort */}
          <div className="mt-4 flex items-center gap-2">
            <span className="text-sm text-muted">Sorteaza:</span>
            {(["newest", "popular", "most_liked"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSearchParams({ sort_by: s })}
                className={`rounded-full px-3 py-1 text-sm cursor-pointer ${sortBy === s ? "bg-accent text-white" : "text-muted hover:text-primary"}`}
              >
                {s === "newest" ? "Recente" : s === "popular" ? "Populare" : "Apreciate"}
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          {data.posts.map((post) => (
            <Card key={post.id} className="group transition-all hover:shadow-md hover:-translate-y-0.5">
              <CardContent className="p-5">
                {post.owner && (
                  <div className="flex items-center gap-2 mb-3">
                    <img src={getAvatarUrl(post.owner.avatar_seed, 32)} alt="" className="h-8 w-8 rounded-full" />
                    <a href={getBlogUrl(post.owner.username)} className="text-sm font-medium text-primary hover:text-accent no-underline">{post.owner.username}</a>
                    <span className="text-xs text-muted">{formatDate(post.created_at)}</span>
                  </div>
                )}
                <a href={post.owner ? `${getBlogUrl(post.owner.username)}/${post.slug}` : "#"} className="no-underline">
                  <h3 className="text-lg font-semibold text-primary group-hover:text-accent">{post.title}</h3>
                </a>
                <p className="mt-2 text-sm text-muted line-clamp-3">{truncate(stripHtml(post.content), 200)}</p>
                <div className="mt-3 flex items-center gap-3 text-xs text-muted">
                  {post.genre && <Badge variant="secondary">{post.genre}</Badge>}
                  <span className="flex items-center gap-1"><Heart className="h-3 w-3" /> {post.likes_count}</span>
                  <span className="flex items-center gap-1"><Eye className="h-3 w-3" /> {post.view_count}</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {data.posts.length === 0 && (
          <div className="rounded-xl border border-border bg-surface-raised p-12 text-center">
            <p className="text-muted">Nicio postare in aceasta categorie.</p>
          </div>
        )}
      </div>
    </>
  );
}
