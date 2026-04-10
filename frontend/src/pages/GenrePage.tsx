import { useParams, useSearchParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { Heart, Eye, ArrowLeft } from "lucide-react";
import { fetchGenrePage } from "@/api/posts";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { getAvatarUrl, formatDate, stripHtml, truncate, getBlogUrl } from "@/lib/utils";

export default function GenrePage() {
  const { categoryKey, genreKey } = useParams<{ categoryKey: string; genreKey: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const sortBy = searchParams.get("sort_by") || "newest";

  const { data, isLoading } = useQuery({
    queryKey: ["genre", categoryKey, genreKey, sortBy],
    queryFn: () => fetchGenrePage(categoryKey!, genreKey!, sortBy),
    enabled: !!categoryKey && !!genreKey,
  });

  if (isLoading || !data) return <PageLoader />;

  return (
    <>
      <Helmet>
        <title>{data.genre_name} - {data.category_name} | Calimara</title>
      </Helmet>

      <div className="mx-auto max-w-6xl px-4 py-8">
        <Link to={`/category/${categoryKey}`} className="inline-flex items-center gap-1 text-sm text-muted hover:text-primary mb-4 no-underline">
          <ArrowLeft className="h-4 w-4" /> {data.category_name}
        </Link>

        <h1 className="font-display text-3xl font-medium text-primary mb-4">{data.genre_name}</h1>

        <div className="mb-6 flex items-center gap-2">
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

        <div className="grid gap-6 md:grid-cols-2">
          {data.posts.map((post) => (
            <Card key={post.id} className="group transition-all hover:shadow-md hover:-translate-y-0.5">
              <CardContent className="p-5">
                {post.owner && (
                  <div className="flex items-center gap-2 mb-3">
                    <img src={getAvatarUrl(post.owner.avatar_seed, 32)} alt="" className="h-8 w-8 rounded-full" />
                    <a href={getBlogUrl(post.owner.username)} className="text-sm font-medium text-primary hover:text-accent no-underline">{post.owner.username}</a>
                  </div>
                )}
                <a href={post.owner ? `${getBlogUrl(post.owner.username)}/${post.slug}` : "#"} className="no-underline">
                  <h3 className="text-lg font-semibold text-primary group-hover:text-accent">{post.title}</h3>
                </a>
                <p className="mt-2 text-sm text-muted line-clamp-3">{truncate(stripHtml(post.content), 200)}</p>
                <div className="mt-3 flex items-center gap-3 text-xs text-muted">
                  <span>{formatDate(post.created_at)}</span>
                  <span className="flex items-center gap-1"><Heart className="h-3 w-3" /> {post.likes_count}</span>
                  <span className="flex items-center gap-1"><Eye className="h-3 w-3" /> {post.view_count}</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {data.posts.length === 0 && (
          <div className="rounded-xl border border-border bg-surface-raised p-12 text-center">
            <p className="text-muted">Nicio postare in acest gen.</p>
          </div>
        )}
      </div>
    </>
  );
}
