import { useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { fetchClubBySlug, applyToClub, deleteClub } from "@/api/clubs";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/components/ui/toast-context";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { Stage, LeftCol, PieceCol } from "@/components/ui/stage";
import { KindBadge } from "@/components/ui/kind-badge";
import { ActionsGroup, ActionRow, SideKicker, SideHint } from "@/components/ui/action-row";
import { ClubBoard } from "@/components/clubs/ClubBoard";
import { ClubMemberList } from "@/components/clubs/ClubMemberList";
import { ClubFeaturedSection } from "@/components/clubs/ClubFeaturedSection";
import { ManageClubRequestsSection } from "@/components/clubs/ManageClubRequestsSection";
import { InviteUserDialog } from "@/components/clubs/InviteUserDialog";
import { formatDate, getAvatarUrl, getBlogUrl } from "@/lib/utils";

const SPECIALITY_LABELS: Record<string, string> = {
  poezie: "Poezie",
  proza_scurta: "Proză scurtă",
};

export default function ClubDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const { user, isAuthenticated } = useAuth();
  const { showToast } = useToast();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [inviteOpen, setInviteOpen] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["clubs", "bySlug", slug],
    queryFn: () => fetchClubBySlug(slug!),
    enabled: !!slug,
  });

  const apply = useMutation({
    mutationFn: () => applyToClub(data!.id),
    onSuccess: () => {
      showToast("Cererea a fost trimisă", "success");
      qc.invalidateQueries({ queryKey: ["clubs", "bySlug", slug] });
    },
    onError: (e: Error) => showToast(e.message || "Acțiune eșuată", "danger"),
  });

  const remove = useMutation({
    mutationFn: () => deleteClub(data!.id),
    onSuccess: () => {
      showToast("Clubul a fost șters", "success");
      navigate("/cluburi");
    },
    onError: (e: Error) => showToast(e.message || "Acțiune eșuată", "danger"),
  });

  if (isLoading) return <PageLoader />;
  if (error || !data) {
    return (
      <Stage variant="centered">
        <PieceCol>
          <KindBadge label="404" />
          <h1 className="piece-title">Clubul nu a fost găsit.</h1>
          <Link
            to="/cluburi"
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              letterSpacing: "0.22em",
              textTransform: "uppercase",
              color: "var(--color-ink-faint)",
              textDecoration: "none",
              marginTop: 16,
              display: "inline-block",
            }}
          >
            ← înapoi la cluburi
          </Link>
        </PieceCol>
      </Stage>
    );
  }

  const isOwner = data.my_role === "owner";
  const isAdmin = data.my_role === "admin";
  const isMember = !!data.my_role;
  const canApply =
    isAuthenticated && !isMember && data.my_pending_request_status === null;
  const ownerUrl = data.owner ? getBlogUrl(data.owner.username) : "/";

  return (
    <>
      <Helmet>
        <title>{data.title} — club | călimara.ro</title>
        {data.description ? <meta name="description" content={data.description} /> : null}
      </Helmet>

      <Stage>
        <LeftCol>
          <aside className="side-col">
            <SideKicker>club</SideKicker>
            <div
              style={{
                display: "flex",
                gap: 12,
                alignItems: "center",
                marginBottom: 12,
              }}
            >
              <img
                src={getAvatarUrl(data.avatar_seed || `${data.slug}-club`, 56)}
                width={56}
                height={56}
                alt=""
                style={{ borderRadius: 6, background: "var(--color-paper-2)" }}
              />
              <div>
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    letterSpacing: "0.18em",
                    textTransform: "uppercase",
                    color: "var(--color-ink-faint)",
                  }}
                >
                  {SPECIALITY_LABELS[data.speciality] ?? data.speciality}
                </div>
                {data.theme ? (
                  <div
                    style={{
                      fontFamily: "var(--font-serif)",
                      fontSize: 14,
                      color: "var(--color-ink-soft)",
                      marginTop: 2,
                    }}
                  >
                    {data.theme}
                  </div>
                ) : null}
              </div>
            </div>

            <ActionsGroup>
              {!isAuthenticated ? (
                <ActionRow
                  num={1}
                  label="Autentifică-te ca să te alături"
                  href="/auth/google"
                />
              ) : canApply ? (
                <ActionRow
                  num={1}
                  label="Aplică să te alături"
                  sub="cerere către administratori"
                  disabled={apply.isPending}
                  onClick={() => apply.mutate()}
                />
              ) : data.my_pending_request_status ? (
                <ActionRow
                  num={1}
                  label="Cerere în așteptare"
                  sub={
                    data.my_pending_request_status === "invitation"
                      ? "ai fost invitat — răspunde din notificări"
                      : "ai aplicat — așteaptă răspuns"
                  }
                  disabled
                />
              ) : null}
              {(isOwner || isAdmin) ? (
                <ActionRow
                  num={2}
                  label="Invită un utilizator"
                  sub="trimite invitație personală"
                  onClick={() => setInviteOpen(true)}
                />
              ) : null}
              {data.owner ? (
                <ActionRow
                  num={3}
                  label={`Blogul lui ${data.owner.username}`}
                  sub="autorul clubului"
                  href={ownerUrl}
                />
              ) : null}
              {isOwner ? (
                <ActionRow
                  num={4}
                  label="Șterge clubul"
                  sub="acțiune ireversibilă"
                  onClick={() => {
                    if (confirm("Ești sigur că vrei să ștergi clubul? Această acțiune este ireversibilă."))
                      remove.mutate();
                  }}
                  disabled={remove.isPending}
                />
              ) : null}
            </ActionsGroup>

            {data.motto ? (
              <SideHint>
                <span style={{ fontStyle: "italic" }}>„{data.motto}"</span>
              </SideHint>
            ) : null}
          </aside>
        </LeftCol>

        <PieceCol>
          <KindBadge
            label="Club"
            meta={`înființat ${formatDate(data.created_at)} · ${data.member_count} ${
              data.member_count === 1 ? "membru" : "membri"
            }`}
          />
          <h1 className="piece-title">{data.title}</h1>

          {data.description ? (
            <p
              style={{
                fontFamily: "var(--font-serif)",
                fontSize: 17,
                lineHeight: 1.5,
                color: "var(--color-ink-soft)",
                marginTop: 12,
                marginBottom: 16,
              }}
            >
              {data.description}
            </p>
          ) : null}

          <ClubFeaturedSection
            clubId={data.id}
            clubSlug={data.slug}
            speciality={data.speciality}
            featured={data.featured}
            myRole={data.my_role}
            members={data.members}
          />

          {(isOwner || isAdmin) ? (
            <ManageClubRequestsSection clubId={data.id} clubSlug={data.slug} />
          ) : null}

          <ClubBoard
            clubId={data.id}
            clubSlug={data.slug}
            messages={data.recent_messages}
            myRole={data.my_role}
          />

          <ClubMemberList
            clubId={data.id}
            clubSlug={data.slug}
            ownerId={data.owner_id}
            members={data.members}
            myRole={data.my_role}
          />

          <div style={{ marginTop: 24 }}>
            <Link
              to="/cluburi"
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                letterSpacing: "0.22em",
                textTransform: "uppercase",
                color: "var(--color-ink-faint)",
                textDecoration: "none",
              }}
            >
              ← înapoi la cluburi
            </Link>
          </div>
        </PieceCol>
      </Stage>

      {(isOwner || isAdmin) ? (
        <InviteUserDialog
          clubId={data.id}
          clubSlug={data.slug}
          open={inviteOpen}
          onOpenChange={setInviteOpen}
        />
      ) : null}
    </>
  );
}
