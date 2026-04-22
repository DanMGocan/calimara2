import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import DOMPurify from "dompurify";
import { useNavigate } from "react-router-dom";
import { fetchLanding, type Post } from "@/api/posts";
import { fetchRandomUser } from "@/api/users";
import { fetchRandomClub } from "@/api/clubs";
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
import { cn, formatDateTime, getBlogUrl, stripHtml } from "@/lib/utils";

type Kind = "poezie" | "proza_scurta";

export default function LandingPage() {
  const [kind, setKind] = useState<Kind>("poezie");
  const [refreshKey, setRefreshKey] = useState(0);
  const [transitioning, setTransitioning] = useState(false);
  const [displayedPost, setDisplayedPost] = useState<Post | null>(null);
  const seedRef = useRef(0);

  const { showToast } = useToast();
  const navigate = useNavigate();

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["landing", kind, refreshKey],
    queryFn: () => fetchLanding(kind),
  });

  const post = data?.random_posts?.[0] ?? null;

  const swap = useCallback(
    (next: Kind) => {
      if (transitioning) return;
      setTransitioning(true);
      setTimeout(() => {
        if (next !== kind) setKind(next);
        setRefreshKey((k) => k + 1);
      }, 340);
    },
    [kind, transitioning],
  );

  useEffect(() => {
    if (isFetching) return;
    if (!post) return;
    seedRef.current += 1;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDisplayedPost(post);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTransitioning(false);
  }, [post, isFetching]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
      if (e.key === "p" || e.key === "P") {
        e.preventDefault();
        swap("poezie");
      }
      if (e.key === "s" || e.key === "S") {
        e.preventDefault();
        swap("proza_scurta");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [swap]);

  const randomAuthor = useMutation({
    mutationFn: fetchRandomUser,
    onSuccess: (u) => {
      window.location.href = getBlogUrl(u.username);
    },
    onError: () => showToast("Nu am putut deschide un autor nou.", "danger"),
  });

  const randomClub = useMutation({
    mutationFn: fetchRandomClub,
    onSuccess: (c) => {
      navigate(`/cluburi/${c.slug}`);
    },
    onError: () => showToast("Nu am găsit niciun club disponibil.", "danger"),
  });

  if (isLoading && !displayedPost) return <PageLoader />;

  const kindLabel = kind === "poezie" ? "Poezie" : "Proză scurtă";
  const plainBody = displayedPost ? stripHtml(DOMPurify.sanitize(displayedPost.content)) : "";
  const when = displayedPost ? formatDateTime(displayedPost.created_at) : null;

  return (
    <>
      <Helmet>
        <title>călimara.ro — poezie și proză</title>
        <meta
          name="description"
          content="călimara.ro — platformă de microblogging pentru scriitori și poeți români."
        />
      </Helmet>

      <Stage>
        <LeftCol>
          <aside className="side-col">
            <SideKicker>alege un text</SideKicker>
            <ActionsGroup>
              <ActionRow
                num={1}
                label="Poezie la întâmplare"
                active={kind === "poezie"}
                disabled={transitioning}
                onClick={() => swap("poezie")}
              />
              <ActionRow
                num={2}
                label="Proză scurtă la întâmplare"
                active={kind === "proza_scurta"}
                disabled={transitioning}
                onClick={() => swap("proza_scurta")}
              />
              <ActionRow
                num={3}
                label="Un autor la întâmplare"
                sub="deschide blogul unui scriitor"
                disabled={randomAuthor.isPending}
                onClick={() => randomAuthor.mutate()}
              />
              <ActionRow
                num={4}
                label="Club la întâmplare"
                sub="o comunitate aleatorie"
                disabled={randomClub.isPending}
                onClick={() => randomClub.mutate()}
              />
            </ActionsGroup>
            <SideHint>
              <span className="kbd">P</span>
              <span>poezie</span>
              <span style={{ width: 8 }} />
              <span className="kbd">S</span>
              <span>proză</span>
            </SideHint>

            {data?.stats ? (
              <div className="rail">
                <div className="rail-stat">
                  <span className="rail-label">Texte</span>
                  <span className="rail-count">
                    {data.stats.total_posts.toLocaleString("ro-RO")}
                  </span>
                  <span className="rail-sub">poezie și proză</span>
                </div>
                <div className="rail-stat">
                  <span className="rail-label">Autori</span>
                  <span className="rail-count">
                    {data.stats.total_authors.toLocaleString("ro-RO")}
                  </span>
                  <span className="rail-sub">autori activi</span>
                </div>
              </div>
            ) : null}
          </aside>
        </LeftCol>

        <PieceCol transitioning={transitioning}>
          {displayedPost ? (
            <>
              <KindBadge
                label={kindLabel}
                meta={
                  <a
                    href={
                      displayedPost.owner
                        ? `${getBlogUrl(displayedPost.owner.username)}/${displayedPost.slug}`
                        : "#"
                    }
                    style={{ color: "inherit" }}
                  >
                    citește pe blog
                  </a>
                }
              />
              <h1 className={cn("piece-title", displayedPost.super_likes_count > 0 && "has-super-like")}>
                {displayedPost.title}
              </h1>
              <div className="piece-meta">
                {displayedPost.owner ? (
                  <a
                    href={getBlogUrl(displayedPost.owner.username)}
                    className="piece-author"
                    style={{ textDecoration: "none" }}
                  >
                    {displayedPost.owner.username}
                  </a>
                ) : (
                  <span className="piece-author">anonim</span>
                )}
                {when ? (
                  <>
                    <span className="piece-meta-dot" />
                    <span className="piece-year">{when}</span>
                  </>
                ) : null}
              </div>
              <PieceScroll resetKey={seedRef.current}>
                <RevealText text={plainBody} keySeed={seedRef.current} />
                <div className="piece-end">
                  <span>fin</span>
                  <span className="piece-end-mark">· · ·</span>
                </div>
              </PieceScroll>
            </>
          ) : (
            <div className="py-16 text-center">
              <p style={{ color: "var(--color-ink-mute)" }}>
                Nu există conținut în această categorie.
              </p>
            </div>
          )}
        </PieceCol>
      </Stage>
    </>
  );
}
