import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { Link } from "react-router-dom";
import { Heart, Eye, ArrowRight } from "lucide-react";
import { fetchLanding } from "@/api/posts";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { getAvatarUrl, formatRelativeTime, stripHtml, truncate, getBlogUrl } from "@/lib/utils";
import { CATEGORY_LABELS } from "@/lib/constants";

export default function LandingPage() {
  const [category, setCategory] = useState("toate");

  const { data, isLoading } = useQuery({
    queryKey: ["landing", category],
    queryFn: () => fetchLanding(category),
  });

  if (isLoading && !data) return <PageLoader />;

  return (
    <>
      <Helmet>
        <title>Calimara - Platforma de microblogging pentru scriitori</title>
        <meta name="description" content="Calimara este o platforma de microblogging pentru scriitori si poeti romani." />
      </Helmet>

      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-primary via-secondary to-accent py-20 text-white">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_50%,rgba(255,255,255,0.05),transparent)]" />
        <div className="relative mx-auto max-w-4xl px-4 text-center">
          <h1 className="font-display text-5xl font-bold tracking-tight md:text-6xl">
            Calimara
          </h1>
          <p className="mt-4 text-lg text-white/80 md:text-xl">
            Un loc pentru scriitori si poeti. Scrie, citeste, descopera.
          </p>
          <div className="mt-8 flex items-center justify-center gap-4">
            <Button size="lg" className="bg-white text-primary hover:bg-white/90" asChild>
              <a href="/auth/google" className="no-underline">Incepe sa scrii</a>
            </Button>
            <Button variant="outline" size="lg" className="border-white/30 text-white hover:bg-white/10" asChild>
              <a href="#descopera" className="no-underline">Descopera</a>
            </Button>
          </div>
        </div>
      </section>

      {/* Random Users */}
      {data?.random_users && data.random_users.length > 0 && (
        <section className="mx-auto max-w-6xl px-4 py-12">
          <h2 className="font-display text-2xl font-bold text-primary">Scriitori</h2>
          <p className="mt-1 text-sm text-muted">Descopera bloguri noi</p>
          <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-5">
            {data.random_users.map((user) => (
              <a
                key={user.id}
                href={getBlogUrl(user.username)}
                className="group flex flex-col items-center gap-2 rounded-xl border border-border bg-surface-raised p-4 transition-all hover:shadow-md hover:-translate-y-0.5 no-underline"
              >
                <img
                  src={getAvatarUrl(user.avatar_seed, 64)}
                  alt={user.username}
                  className="h-16 w-16 rounded-full"
                />
                <span className="text-sm font-medium text-primary group-hover:text-accent">
                  {user.username}
                </span>
                {user.subtitle && (
                  <span className="text-xs text-muted text-center line-clamp-1">
                    {user.subtitle}
                  </span>
                )}
              </a>
            ))}
          </div>
        </section>
      )}

      {/* Category Filter + Posts */}
      <section id="descopera" className="mx-auto max-w-6xl px-4 pb-16">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-display text-2xl font-bold text-primary">Postari recente</h2>
            <p className="mt-1 text-sm text-muted">Filtreaza dupa categorie</p>
          </div>
        </div>

        {/* Category Filter Buttons */}
        <div className="mt-6 flex flex-wrap gap-2">
          {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setCategory(key)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors cursor-pointer ${
                category === key
                  ? "bg-accent text-white"
                  : "bg-surface-raised border border-border text-muted hover:border-accent/30 hover:text-primary"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Posts Grid */}
        <div className="mt-8 grid gap-6 md:grid-cols-2">
          {data?.random_posts?.map((post) => (
            <Card key={post.id} className="group transition-all hover:shadow-md hover:-translate-y-0.5">
              <CardContent className="p-5">
                <div className="flex items-start gap-3">
                  {post.owner && (
                    <a href={getBlogUrl(post.owner.username)} className="shrink-0">
                      <img
                        src={getAvatarUrl(post.owner.avatar_seed, 40)}
                        alt={post.owner.username}
                        className="h-10 w-10 rounded-full"
                      />
                    </a>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      {post.owner && (
                        <a href={getBlogUrl(post.owner.username)} className="text-sm font-medium text-primary hover:text-accent no-underline">
                          {post.owner.username}
                        </a>
                      )}
                      <span className="text-xs text-muted">{formatRelativeTime(post.created_at)}</span>
                    </div>
                    <a
                      href={post.owner ? `${getBlogUrl(post.owner.username)}/${post.slug}` : "#"}
                      className="mt-1 block no-underline"
                    >
                      <h3 className="text-base font-semibold text-primary group-hover:text-accent transition-colors line-clamp-1">
                        {post.title}
                      </h3>
                    </a>
                    <p className="mt-1 text-sm text-muted line-clamp-2">
                      {truncate(stripHtml(post.content), 150)}
                    </p>
                    <div className="mt-3 flex items-center gap-3">
                      <Badge variant="default">{post.category}</Badge>
                      <span className="flex items-center gap-1 text-xs text-muted">
                        <Heart className="h-3 w-3" /> {post.likes_count}
                      </span>
                      <span className="flex items-center gap-1 text-xs text-muted">
                        <Eye className="h-3 w-3" /> {post.view_count}
                      </span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {data?.random_posts?.length === 0 && (
          <div className="mt-8 rounded-xl border border-border bg-surface-raised p-12 text-center">
            <p className="text-muted">Nu exista postari in aceasta categorie.</p>
          </div>
        )}
      </section>
    </>
  );
}
