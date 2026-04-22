import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  setClubFeatured,
  clearClubFeatured,
  type ClubFeatured,
  type ClubMember,
  type ClubMemberRole,
  type ClubSpeciality,
} from "@/api/clubs";
import { fetchBlog } from "@/api/posts";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast-context";
import { formatDate, getBlogUrl } from "@/lib/utils";

interface Props {
  clubId: number;
  clubSlug: string;
  speciality: ClubSpeciality;
  featured: ClubFeatured | null;
  myRole: ClubMemberRole | null;
  members: ClubMember[];
}

function daysRemaining(until: string): string {
  const ms = new Date(until).getTime() - Date.now();
  if (ms <= 0) return "expirat";
  const days = Math.ceil(ms / 86400000);
  return days === 1 ? "1 zi" : `${days} zile`;
}

export function ClubFeaturedSection({
  clubId,
  clubSlug,
  speciality,
  featured,
  myRole,
  members,
}: Props) {
  const isOwner = myRole === "owner";
  const { showToast } = useToast();
  const qc = useQueryClient();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [selectedMember, setSelectedMember] = useState<string | null>(null);
  const [memberPosts, setMemberPosts] = useState<{ id: number; title: string; slug: string; category: string }[]>([]);
  const [loadingMember, setLoadingMember] = useState(false);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["clubs", "bySlug", clubSlug] });

  const setFeaturedMutation = useMutation({
    mutationFn: (postId: number) => setClubFeatured(clubId, postId),
    onSuccess: () => {
      setPickerOpen(false);
      setSelectedMember(null);
      setMemberPosts([]);
      invalidate();
      showToast("Creația săptămânii a fost setată", "success");
    },
    onError: (e: Error) => showToast(e.message || "Acțiune eșuată", "danger"),
  });

  const clearFeaturedMutation = useMutation({
    mutationFn: () => clearClubFeatured(clubId),
    onSuccess: () => {
      invalidate();
      showToast("Creația săptămânii a fost retrasă", "success");
    },
    onError: (e: Error) => showToast(e.message || "Acțiune eșuată", "danger"),
  });

  const loadMemberPosts = async (username: string) => {
    setSelectedMember(username);
    setLoadingMember(true);
    try {
      const blog = await fetchBlog(username);
      const eligible = blog.all_posts
        .filter((p) => p.category === speciality && p.moderation_status === "approved")
        .map((p) => ({ id: p.id, title: p.title, slug: p.slug, category: p.category }));
      setMemberPosts(eligible);
    } catch (e) {
      showToast((e as Error).message || "Nu am putut încărca textele", "danger");
      setMemberPosts([]);
    } finally {
      setLoadingMember(false);
    }
  };

  return (
    <div
      style={{
        border: "1px solid var(--color-hairline)",
        borderRadius: 8,
        padding: 16,
        margin: "16px 0",
        background: "var(--color-paper-2)",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 10,
          letterSpacing: "0.22em",
          textTransform: "uppercase",
          color: "var(--color-ink-mute)",
          marginBottom: 8,
        }}
      >
        Creația săptămânii
      </div>
      {featured ? (
        <>
          <a
            href={
              featured.post_author
                ? `${getBlogUrl(featured.post_author.username)}/${featured.post_slug}`
                : "#"
            }
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: 20,
              color: "var(--color-ink)",
              textDecoration: "none",
              display: "block",
            }}
          >
            {featured.post_title}
          </a>
          <div
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: 12,
              color: "var(--color-ink-mute)",
              marginTop: 4,
            }}
          >
            de {featured.post_author?.username ?? "necunoscut"} · expiră în{" "}
            {daysRemaining(featured.featured_until)} ({formatDate(featured.featured_until)})
          </div>
          {isOwner ? (
            <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
              <button
                type="button"
                className="cal-btn"
                onClick={() => setPickerOpen(true)}
              >
                Schimbă
              </button>
              <button
                type="button"
                className="cal-btn"
                disabled={clearFeaturedMutation.isPending}
                onClick={() => {
                  if (confirm("Retragi creația săptămânii?")) clearFeaturedMutation.mutate();
                }}
              >
                Elimină
              </button>
            </div>
          ) : null}
        </>
      ) : (
        <>
          <p
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: 13,
              color: "var(--color-ink-faint)",
              margin: 0,
            }}
          >
            Nicio creație featured săptămâna asta.
          </p>
          {isOwner ? (
            <button
              type="button"
              className="cal-btn"
              style={{ marginTop: 8 }}
              onClick={() => setPickerOpen(true)}
            >
              Alege creația săptămânii
            </button>
          ) : null}
        </>
      )}

      {isOwner ? (
        <Dialog open={pickerOpen} onOpenChange={setPickerOpen}>
          <DialogTrigger asChild>
            <span style={{ display: "none" }} />
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Alege creația săptămânii</DialogTitle>
              <DialogDescription>
                Selectează un membru, apoi alege un text din textele lui care se potrivește
                cu specialitatea clubului.
              </DialogDescription>
            </DialogHeader>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  color: "var(--color-ink-faint)",
                }}
              >
                Membru
              </div>
              <div
                style={{
                  display: "flex",
                  gap: 6,
                  flexWrap: "wrap",
                  maxHeight: 120,
                  overflowY: "auto",
                }}
              >
                {members.map((m) => (
                  <button
                    key={m.user_id}
                    type="button"
                    className="cal-btn"
                    onClick={() => loadMemberPosts(m.username)}
                    style={{
                      borderColor:
                        selectedMember === m.username ? "var(--color-ink)" : undefined,
                    }}
                  >
                    {m.username}
                  </button>
                ))}
              </div>
              {selectedMember ? (
                <>
                  <div
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      letterSpacing: "0.18em",
                      textTransform: "uppercase",
                      color: "var(--color-ink-faint)",
                      marginTop: 8,
                    }}
                  >
                    Texte ({speciality === "poezie" ? "Poezie" : "Proză scurtă"})
                  </div>
                  {loadingMember ? (
                    <p style={{ fontSize: 13, color: "var(--color-ink-mute)" }}>Se încarcă...</p>
                  ) : memberPosts.length === 0 ? (
                    <p style={{ fontSize: 13, color: "var(--color-ink-mute)" }}>
                      {selectedMember} nu are texte care să se potrivească cu specialitatea
                      clubului.
                    </p>
                  ) : (
                    <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                      {memberPosts.map((p) => (
                        <li key={p.id}>
                          <button
                            type="button"
                            onClick={() => setFeaturedMutation.mutate(p.id)}
                            disabled={setFeaturedMutation.isPending}
                            style={{
                              display: "block",
                              width: "100%",
                              textAlign: "left",
                              padding: "8px 0",
                              border: "none",
                              borderBottom: "1px solid var(--color-hairline)",
                              background: "none",
                              cursor: "pointer",
                              fontFamily: "var(--font-serif)",
                              fontSize: 15,
                              color: "var(--color-ink)",
                            }}
                          >
                            {p.title}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              ) : null}
            </div>
          </DialogContent>
        </Dialog>
      ) : null}
    </div>
  );
}
