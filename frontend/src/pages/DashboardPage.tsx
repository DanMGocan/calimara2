import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { fetchArchive, deletePost } from "@/api/posts";
import { updateUser, updateSocialLinks, type SocialLinksData } from "@/api/users";
import { useAuth } from "@/hooks/useAuth";
import type { CurrentUser } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast-context";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { generateAvatarSeeds } from "@/hooks/useDiceBearAvatar";
import { Stage, LeftCol } from "@/components/ui/stage";
import {
  ActionRow,
  ActionsGroup,
  SideKicker,
} from "@/components/ui/action-row";
import { formatDate, getAvatarUrl, getBlogUrl } from "@/lib/utils";
import { CollectionsSection } from "@/components/collections/CollectionsSection";

type Section = "posts" | "collections" | "profile" | "social" | "new";

export default function DashboardPage() {
  const { user, refetch: refetchAuth } = useAuth();
  if (!user) return <PageLoader />;
  return <DashboardContent key={user.id} user={user} refetchAuth={refetchAuth} />;
}

function DashboardContent({
  user,
  refetchAuth,
}: {
  user: CurrentUser;
  refetchAuth: () => void;
}) {
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialSection = (searchParams.get("tab") as Section) || "posts";
  const [section, setSection] = useState<Section>(initialSection);

  useEffect(() => {
    const current = searchParams.get("tab");
    if (section !== "posts" && current !== section) {
      setSearchParams({ tab: section });
    } else if (section === "posts" && current) {
      setSearchParams({});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section]);

  const { data: archiveData, isLoading } = useQuery({
    queryKey: ["posts", "archive"],
    queryFn: fetchArchive,
  });

  const [avatarSeeds, setAvatarSeeds] = useState(() => generateAvatarSeeds(6));
  const [selectedSeed, setSelectedSeed] = useState(user.avatar_seed);
  const avatarMutation = useMutation({
    mutationFn: (seed: string) => updateUser({ avatar_seed: seed }),
    onSuccess: () => {
      refetchAuth();
      showToast("Avatar actualizat.", "success");
    },
  });

  const [subtitle, setSubtitle] = useState(user.subtitle ?? "");
  const subtitleMutation = useMutation({
    mutationFn: (sub: string) => updateUser({ subtitle: sub }),
    onSuccess: () => {
      refetchAuth();
      showToast("Subtitlu actualizat.", "success");
    },
  });

  const [socialLinks, setSocialLinks] = useState<SocialLinksData>({});
  const socialMutation = useMutation({
    mutationFn: (data: SocialLinksData) => updateSocialLinks(data),
    onSuccess: () => showToast("Legăturile au fost salvate.", "success"),
  });

  const [deleteId, setDeleteId] = useState<number | null>(null);
  const deleteMutation = useMutation({
    mutationFn: (id: number) => deletePost(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["posts", "archive"] });
      setDeleteId(null);
      showToast("Postare ștearsă.", "success");
    },
  });

  if (isLoading) return <PageLoader />;
  const posts = archiveData?.posts ?? [];
  const blogUrl = getBlogUrl(user.username);

  return (
    <>
      <Helmet>
        <title>Panou — {user.username} | călimara.ro</title>
      </Helmet>

      <Stage>
        <LeftCol>
          <aside className="side-col">
            <SideKicker>panou</SideKicker>
            <ActionsGroup>
              <ActionRow
                num={1}
                label="Textele mele"
                sub={`${posts.length} postări`}
                active={section === "posts"}
                onClick={() => setSection("posts")}
              />
              <ActionRow
                num={2}
                label="Colecții"
                sub="grupurile tale curate"
                active={section === "collections"}
                onClick={() => setSection("collections")}
              />
              <ActionRow
                num={3}
                label="Profil"
                sub="avatar și subtitlu"
                active={section === "profile"}
                onClick={() => setSection("profile")}
              />
              <ActionRow
                num={4}
                label="Legături sociale"
                sub="facebook, instagram…"
                active={section === "social"}
                onClick={() => setSection("social")}
              />
              <ActionRow
                num={5}
                label="Postare nouă"
                sub="scrie un text"
                href={`${blogUrl}/create-post`}
              />
            </ActionsGroup>
          </aside>
        </LeftCol>

        <div className="piece-col">
          <div className="piece-wrap">
            {!user.is_premium ? (
              <div className="premium-banner">
                <span>Vrei 3 super-aprecieri pe săptămână? </span>
                <Link to="/premium">Devino Premium</Link>
              </div>
            ) : null}
            {section === "posts" ? (
              <>
                <div className="piece-kind-row">
                  <span className="piece-kind-badge">textele tale</span>
                  <span className="piece-kind-sep" />
                  <span className="piece-kind-meta">{posts.length}</span>
                </div>
                <h1
                  className="piece-title"
                  style={{ fontSize: "clamp(32px, 4vw, 52px)", marginBottom: 24 }}
                >
                  Textele mele
                </h1>
                {posts.length === 0 ? (
                  <div
                    style={{
                      padding: "60px 20px",
                      border: "1px dashed var(--color-hairline-strong)",
                      borderRadius: 10,
                      textAlign: "center",
                      color: "var(--color-ink-faint)",
                      fontFamily: "var(--font-serif)",
                      fontStyle: "italic",
                      fontSize: 17,
                    }}
                  >
                    Nu ai nicio postare încă.
                  </div>
                ) : (
                  <div
                    style={{
                      border: "1px solid var(--color-hairline)",
                      borderRadius: 10,
                      background: "rgba(255,255,255,0.6)",
                    }}
                  >
                    {posts.map((post, i) => (
                      <div
                        key={post.id}
                        className="grid grid-cols-[1fr_auto] items-start gap-4 px-4 py-4"
                        style={{
                          borderBottom:
                            i < posts.length - 1
                              ? "1px solid var(--color-hairline)"
                              : "none",
                        }}
                      >
                        <div style={{ minWidth: 0 }}>
                          <Link
                            to={`/${post.slug}`}
                            style={{
                              fontFamily: "var(--font-serif)",
                              fontSize: 18,
                              fontWeight: 500,
                              color: "var(--color-ink)",
                              letterSpacing: "-0.01em",
                              textDecoration: "none",
                            }}
                          >
                            {post.title}
                          </Link>
                          <div
                            style={{
                              fontFamily: "var(--font-sans)",
                              fontSize: 12,
                              color: "var(--color-ink-faint)",
                              marginTop: 4,
                              display: "flex",
                              gap: 10,
                              flexWrap: "wrap",
                            }}
                          >
                            <span>{post.category_name ?? post.category}</span>
                            <span className="piece-meta-dot" />
                            <span>{formatDate(post.created_at)}</span>
                            <span className="piece-meta-dot" />
                            <span>{post.view_count} vizualizări</span>
                            <span className="piece-meta-dot" />
                            <span>{post.likes_count} aprecieri</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button asChild size="sm" variant="outline">
                            <Link to={`/edit-post/${post.id}`}>editează</Link>
                          </Button>
                          <Button
                            size="sm"
                            variant="danger"
                            onClick={() => setDeleteId(post.id)}
                          >
                            șterge
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : null}

            {section === "collections" ? <CollectionsSection /> : null}

            {section === "profile" ? (
              <>
                <div className="piece-kind-row">
                  <span className="piece-kind-badge">profil</span>
                  <span className="piece-kind-sep" />
                  <span className="piece-kind-meta">avatar și subtitlu</span>
                </div>
                <h1
                  className="piece-title"
                  style={{ fontSize: "clamp(32px, 4vw, 52px)", marginBottom: 32 }}
                >
                  Profil
                </h1>

                <section style={{ marginBottom: 32 }}>
                  <label className="auth-field">Avatar</label>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(6, 1fr)",
                      gap: 12,
                    }}
                  >
                    {avatarSeeds.map((seed) => (
                      <button
                        key={seed}
                        type="button"
                        onClick={() => {
                          setSelectedSeed(seed);
                          avatarMutation.mutate(seed);
                        }}
                        aria-label={`avatar ${seed}`}
                        style={{
                          width: 56,
                          height: 56,
                          borderRadius: "50%",
                          padding: 3,
                          border:
                            selectedSeed === seed
                              ? "2px solid var(--color-accent)"
                              : "1px solid var(--color-hairline)",
                          transition: "all 160ms ease",
                          cursor: "pointer",
                        }}
                      >
                        <img
                          src={getAvatarUrl(seed, 48)}
                          alt=""
                          style={{
                            width: "100%",
                            height: "100%",
                            borderRadius: "50%",
                          }}
                        />
                      </button>
                    ))}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-3"
                    onClick={() => setAvatarSeeds(generateAvatarSeeds(6))}
                  >
                    generează alte opțiuni
                  </Button>
                </section>

                <section>
                  <label className="auth-field">Subtitlu</label>
                  <div className="flex gap-2">
                    <Input
                      value={subtitle}
                      onChange={(e) => setSubtitle(e.target.value)}
                      placeholder="Descriere scurtă…"
                      maxLength={100}
                    />
                    <Button
                      size="md"
                      onClick={() => subtitleMutation.mutate(subtitle)}
                      disabled={subtitleMutation.isPending}
                    >
                      salvează
                    </Button>
                  </div>
                </section>
              </>
            ) : null}

            {section === "social" ? (
              <>
                <div className="piece-kind-row">
                  <span className="piece-kind-badge">legături</span>
                  <span className="piece-kind-sep" />
                  <span className="piece-kind-meta">rețele sociale</span>
                </div>
                <h1
                  className="piece-title"
                  style={{ fontSize: "clamp(32px, 4vw, 52px)", marginBottom: 32 }}
                >
                  Legături sociale
                </h1>

                <div className="flex flex-col gap-3">
                  {(
                    [
                      { k: "facebook_url", l: "Facebook" },
                      { k: "instagram_url", l: "Instagram" },
                      { k: "tiktok_url", l: "TikTok" },
                      { k: "x_url", l: "X" },
                      { k: "bluesky_url", l: "Bluesky" },
                    ] as const
                  ).map((f) => (
                    <div key={f.k}>
                      <label className="auth-field" style={{ marginTop: 8 }}>
                        {f.l}
                      </label>
                      <Input
                        placeholder={`https://…`}
                        value={(socialLinks as Record<string, string>)[f.k] ?? ""}
                        onChange={(e) =>
                          setSocialLinks({ ...socialLinks, [f.k]: e.target.value })
                        }
                      />
                    </div>
                  ))}
                  <Button
                    className="mt-4 self-start"
                    onClick={() => socialMutation.mutate(socialLinks)}
                    disabled={socialMutation.isPending}
                  >
                    salvează legăturile
                  </Button>
                </div>
              </>
            ) : null}
          </div>
        </div>
      </Stage>

      <Dialog open={deleteId !== null} onOpenChange={() => setDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <div className="auth-kicker">confirmare</div>
            <DialogTitle>Șterge postarea</DialogTitle>
          </DialogHeader>
          <p
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: 14,
              color: "var(--color-ink-mute)",
            }}
          >
            Această acțiune este permanentă și nu poate fi anulată.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)}>
              anulează
            </Button>
            <Button
              variant="danger"
              onClick={() => deleteId && deleteMutation.mutate(deleteId)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "se șterge…" : "șterge"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
