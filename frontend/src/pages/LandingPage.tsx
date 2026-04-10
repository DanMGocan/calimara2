import { useState, useCallback, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { fetchLanding } from "@/api/posts";
import type { Post } from "@/api/posts";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { getBlogUrl } from "@/lib/utils";

type ContentType = "poezie" | "proza" | "piese";

const TABS: { key: ContentType; label: string }[] = [
  { key: "poezie", label: "Poezie" },
  { key: "proza", label: "Proză" },
  { key: "piese", label: "Teatru" },
];

export default function LandingPage() {
  const [contentType, setContentType] = useState<ContentType>("poezie");
  const [refreshKey, setRefreshKey] = useState(0);
  const [visible, setVisible] = useState(true);
  const [displayedPost, setDisplayedPost] = useState<Post | null>(null);
  const pendingSwap = useRef(false);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["landing", contentType, refreshKey],
    queryFn: () => fetchLanding(contentType),
  });

  const post = data?.random_posts?.[0] ?? null;

  const refresh = useCallback((type: ContentType) => {
    setVisible(false);
    pendingSwap.current = true;
    if (type === contentType) {
      setTimeout(() => setRefreshKey((k) => k + 1), 350);
    } else {
      setTimeout(() => setContentType(type), 350);
    }
  }, [contentType]);

  useEffect(() => {
    if (!isFetching && post) {
      setDisplayedPost(post);
      requestAnimationFrame(() => setVisible(true));
    }
  }, [post, isFetching]);

  useEffect(() => {
    if (data?.random_posts?.[0] && !displayedPost) {
      setDisplayedPost(data.random_posts[0]);
      setVisible(true);
    }
  }, [data, displayedPost]);

  if (isLoading && !data && !displayedPost) return <PageLoader />;

  return (
    <>
      <Helmet>
        <title>Calimara - Platformă de microblogging pentru scriitori</title>
        <meta name="description" content="Calimara este o platformă de microblogging pentru scriitori și poeți români." />
      </Helmet>

      <div>
        {/* Inline tabs */}
        <nav className="mb-10 flex flex-wrap items-center gap-y-2" role="tablist" aria-label="Tip conținut">
          {TABS.map(({ key, label }, i) => (
            <span key={key} className="flex items-center">
              <Tab
                label={label}
                active={contentType === key}
                onClick={() => refresh(key)}
              />
              {i < TABS.length - 1 && (
                <span className="mx-5 text-primary/20 select-none" aria-hidden="true">|</span>
              )}
            </span>
          ))}
        </nav>

        {/* Content */}
        <div
          className="transition-all duration-500 ease-in-out"
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
                <h2 className="font-display text-3xl font-medium text-primary leading-tight md:text-4xl">
                  {displayedPost.title}
                </h2>
              </a>

              {displayedPost.owner && (
                <p className="mt-3 text-sm text-muted">
                  de{" "}
                  <a
                    href={getBlogUrl(displayedPost.owner.username)}
                    className="font-medium text-primary/70 hover:text-primary no-underline"
                  >
                    {displayedPost.owner.username}
                  </a>
                </p>
              )}

              <div
                className="prose-content mt-8 text-lg leading-relaxed text-primary/80"
                dangerouslySetInnerHTML={{ __html: displayedPost.content }}
              />
            </article>
          ) : (
            <div className="py-16 text-center">
              <p className="text-muted">Nu există conținut în această categorie.</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function Tab({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`cursor-pointer bg-transparent text-sm tracking-wide transition-all focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent ${
        active
          ? "font-bold text-primary"
          : "font-normal text-muted hover:text-primary/70"
      }`}
    >
      {label}
    </button>
  );
}
