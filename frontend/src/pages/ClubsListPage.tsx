import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { fetchClubs, type ClubSpeciality } from "@/api/clubs";
import { useAuth } from "@/hooks/useAuth";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { Stage, LeftCol, PieceCol } from "@/components/ui/stage";
import { KindBadge } from "@/components/ui/kind-badge";
import { ActionsGroup, ActionRow, SideKicker, SideHint } from "@/components/ui/action-row";
import { ClubCard } from "@/components/clubs/ClubCard";

type Filter = "toate" | ClubSpeciality;

export default function ClubsListPage() {
  const { user } = useAuth();
  const [filter, setFilter] = useState<Filter>("toate");
  const [themeQuery, setThemeQuery] = useState("");
  const [appliedTheme, setAppliedTheme] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["clubs", "list", filter, appliedTheme],
    queryFn: () =>
      fetchClubs({
        speciality: filter === "toate" ? undefined : filter,
        theme: appliedTheme || undefined,
      }),
  });

  if (isLoading) return <PageLoader />;
  const clubs = data?.clubs ?? [];

  return (
    <>
      <Helmet>
        <title>Cluburi — călimara.ro</title>
        <meta
          name="description"
          content="Descoperă cluburi de poezie și proză scurtă pe călimara.ro."
        />
      </Helmet>

      <Stage>
        <LeftCol>
          <aside className="side-col">
            <SideKicker>filtre</SideKicker>
            <ActionsGroup>
              <ActionRow
                num={1}
                label="Toate cluburile"
                active={filter === "toate"}
                onClick={() => setFilter("toate")}
              />
              <ActionRow
                num={2}
                label="Poezie"
                active={filter === "poezie"}
                onClick={() => setFilter("poezie")}
              />
              <ActionRow
                num={3}
                label="Proză scurtă"
                active={filter === "proza_scurta"}
                onClick={() => setFilter("proza_scurta")}
              />
            </ActionsGroup>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setAppliedTheme(themeQuery.trim());
              }}
              style={{ marginTop: 12 }}
            >
              <input
                type="text"
                value={themeQuery}
                onChange={(e) => setThemeQuery(e.target.value)}
                placeholder="caută după temă..."
                className="cal-input"
                style={{ width: "100%" }}
              />
            </form>
            {user?.is_premium ? (
              <div style={{ marginTop: 14 }}>
                <Link to="/cluburi/nou" className="cal-btn" style={{ display: "inline-block" }}>
                  + Creează un club
                </Link>
              </div>
            ) : (
              <SideHint>
                <span>Doar membrii Premium pot crea cluburi.</span>
              </SideHint>
            )}
          </aside>
        </LeftCol>
        <PieceCol>
          <KindBadge label="Cluburi" meta={`${clubs.length} cluburi`} />
          <h1 className="piece-title">Cluburi de scriitori</h1>
          <p
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: 16,
              color: "var(--color-ink-soft)",
              marginTop: 8,
              marginBottom: 24,
              lineHeight: 1.5,
            }}
          >
            Comunități focalizate pe o temă, conduse de scriitori. Aplică pentru
            a te alătura sau primește o invitație.
          </p>
          {clubs.length === 0 ? (
            <p style={{ color: "var(--color-ink-faint)", fontFamily: "var(--font-sans)", fontSize: 14 }}>
              Nu am găsit cluburi care să corespundă filtrelor.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {clubs.map((c) => (
                <ClubCard key={c.id} club={c} />
              ))}
            </div>
          )}
        </PieceCol>
      </Stage>
    </>
  );
}
