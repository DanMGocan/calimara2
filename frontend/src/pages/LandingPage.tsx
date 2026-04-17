import { useState, useCallback, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import DOMPurify from "dompurify";
import { Feather, BookOpen, UserRound } from "lucide-react";
import { fetchLanding } from "@/api/posts";
import type { Post } from "@/api/posts";
import { fetchRandomUser } from "@/api/users";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { useToast } from "@/components/ui/toast-context";
import { getBlogUrl } from "@/lib/utils";

type ContentType = "poezie" | "proza_scurta";

export default function LandingPage() {
  const [contentType, setContentType] = useState<ContentType>("poezie");
  const [refreshKey, setRefreshKey] = useState(0);
  const [visible, setVisible] = useState(true);
  const [displayedPost, setDisplayedPost] = useState<Post | null>(null);
  const { showToast } = useToast();

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["landing", contentType, refreshKey],
    queryFn: () => fetchLanding(contentType),
  });

  const post = data?.random_posts?.[0] ?? null;

  const refresh = useCallback((type: ContentType) => {
    setVisible(false);
    if (type === contentType) {
      setTimeout(() => setRefreshKey((k) => k + 1), 350);
    } else {
      setTimeout(() => {
        setContentType(type);
        setRefreshKey((k) => k + 1);
      }, 350);
    }
  }, [contentType]);

  const randomUserMutation = useMutation({
    mutationFn: fetchRandomUser,
    onSuccess: (user) => {
      window.location.href = getBlogUrl(user.username);
    },
    onError: () => {
      showToast("Nu am putut încărca un autor. Încearcă mai târziu.", "danger");
    },
  });

  // Sync the freshly-fetched post into local display state and fade it in.
  // react-hooks/set-state-in-effect flags this pattern, but animation
  // choreography (fade-out before refetch, fade-in after) needs state sync.
  useEffect(() => {
    if (isFetching || !post) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDisplayedPost(post);
    requestAnimationFrame(() => setVisible(true));
  }, [post, isFetching]);

  if (isLoading && !displayedPost) return <PageLoader />;

  return (
    <>
      <Helmet>
        <title>Calimara - Platformă de microblogging pentru scriitori</title>
        <meta name="description" content="Calimara este o platformă de microblogging pentru scriitori și poeți români." />
      </Helmet>

      <div className="mx-auto max-w-5xl">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_280px]">
          {/* Main content */}
          <div
            className="min-w-0 transition-all duration-500 ease-in-out"
            style={{
              opacity: visible ? 1 : 0,
              transform: visible ? "translateY(0)" : "translateY(12px)",
            }}
          >
            {displayedPost ? (
              <article>
                <a
                  href={displayedPost.owner ? `${getBlogUrl(displayedPost.owner.username)}/${displayedPost.slug}` : "#"}
                  className="no-underline"
                >
                  <h2 className="font-display text-3xl font-semibold text-primary leading-[1.15] md:text-4xl">
                    {displayedPost.title}
                  </h2>
                </a>

                {displayedPost.owner && (
                  <p className="mt-4 text-sm text-muted">
                    de{" "}
                    <a
                      href={getBlogUrl(displayedPost.owner.username)}
                      className="font-medium text-primary hover:underline underline-offset-4 no-underline"
                    >
                      {displayedPost.owner.username}
                    </a>
                  </p>
                )}

                <div
                  className="prose-content mt-8 text-primary"
                  dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(displayedPost.content) }}
                />
              </article>
            ) : (
              <div className="py-16 text-center">
                <p className="text-muted">Nu există conținut în această categorie.</p>
              </div>
            )}
          </div>

          {/* Right-side discovery cards */}
          <aside className="space-y-3 lg:sticky lg:top-20 lg:self-start">
            <DiscoverCard
              icon={<Feather className="h-5 w-5 text-primary" />}
              title="Descoperă o poezie la întâmplare"
              description="Încarcă o poezie nouă din platformă"
              onClick={() => refresh("poezie")}
              disabled={isFetching}
            />
            <DiscoverCard
              icon={<BookOpen className="h-5 w-5 text-primary" />}
              title="Descoperă proză la întâmplare"
              description="Încarcă un text de proză scurtă"
              onClick={() => refresh("proza_scurta")}
              disabled={isFetching}
            />
            <DiscoverCard
              icon={<UserRound className="h-5 w-5 text-primary" />}
              title="Descoperă un autor la întâmplare"
              description="Vizitează blogul unui scriitor aleatoriu"
              onClick={() => randomUserMutation.mutate()}
              disabled={randomUserMutation.isPending}
            />
          </aside>
        </div>
      </div>
    </>
  );
}

function DiscoverCard({
  icon,
  title,
  description,
  onClick,
  disabled,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="group block w-full cursor-pointer rounded-lg border border-border bg-surface-raised p-4 text-left transition-colors hover:border-border-strong hover:bg-surface disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:border-border disabled:hover:bg-surface-raised"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 shrink-0">{icon}</span>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-primary">{title}</h3>
          <p className="mt-0.5 text-xs text-muted">{description}</p>
        </div>
      </div>
    </button>
  );
}
