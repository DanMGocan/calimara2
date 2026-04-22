import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { createClub, type ClubSpeciality } from "@/api/clubs";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/components/ui/toast-context";
import { Stage, PieceCol } from "@/components/ui/stage";
import { KindBadge } from "@/components/ui/kind-badge";

export default function ClubCreatePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [title, setTitle] = useState("");
  const [speciality, setSpeciality] = useState<ClubSpeciality>("poezie");
  const [theme, setTheme] = useState("");
  const [motto, setMotto] = useState("");
  const [description, setDescription] = useState("");

  const create = useMutation({
    mutationFn: () =>
      createClub({
        title: title.trim(),
        speciality,
        theme: theme.trim() || null,
        motto: motto.trim() || null,
        description: description.trim() || null,
      }),
    onSuccess: (club) => {
      showToast("Clubul a fost creat", "success");
      navigate(`/cluburi/${club.slug}`);
    },
    onError: (e: Error) => showToast(e.message || "Nu am putut crea clubul", "danger"),
  });

  if (!user?.is_premium) {
    return (
      <Stage variant="centered">
        <PieceCol>
          <KindBadge label="Premium" />
          <h1 className="piece-title">Creează un club</h1>
          <p
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: 16,
              color: "var(--color-ink-soft)",
              marginTop: 8,
              lineHeight: 1.5,
            }}
          >
            Crearea cluburilor este o funcție Premium. Devino Premium pentru a putea
            organiza propria comunitate de scriitori.
          </p>
          <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
            <Link to="/premium" className="cal-btn">
              Devino Premium
            </Link>
            <Link to="/cluburi" className="cal-btn">
              Înapoi la cluburi
            </Link>
          </div>
        </PieceCol>
      </Stage>
    );
  }

  return (
    <>
      <Helmet>
        <title>Creează un club — călimara.ro</title>
      </Helmet>
      <Stage variant="centered">
        <PieceCol>
          <KindBadge label="Cluburi" meta="creează un club" />
          <h1 className="piece-title">Creează un club nou</h1>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!title.trim()) return;
              create.mutate();
            }}
            style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 14 }}
          >
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  color: "var(--color-ink-faint)",
                }}
              >
                Titlu
              </span>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={120}
                required
                className="cal-input"
                placeholder="Poeții melancolici"
              />
            </label>

            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  color: "var(--color-ink-faint)",
                }}
              >
                Specialitate
              </span>
              <select
                value={speciality}
                onChange={(e) => setSpeciality(e.target.value as ClubSpeciality)}
                className="cal-input"
              >
                <option value="poezie">Poezie</option>
                <option value="proza_scurta">Proză scurtă</option>
              </select>
            </label>

            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  color: "var(--color-ink-faint)",
                }}
              >
                Tema (opțional)
              </span>
              <input
                type="text"
                value={theme}
                onChange={(e) => setTheme(e.target.value)}
                maxLength={200}
                className="cal-input"
                placeholder="ex. Poezie tristă, Poezie de dragoste"
              />
            </label>

            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  color: "var(--color-ink-faint)",
                }}
              >
                Motto (opțional)
              </span>
              <input
                type="text"
                value={motto}
                onChange={(e) => setMotto(e.target.value)}
                maxLength={200}
                className="cal-input"
                placeholder="o linie scurtă"
              />
            </label>

            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  color: "var(--color-ink-faint)",
                }}
              >
                Descriere (opțional)
              </span>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                maxLength={2000}
                rows={5}
                className="cal-textarea"
                placeholder="Câteva rânduri despre ce face acest club..."
              />
            </label>

            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <button
                type="submit"
                className="cal-btn"
                disabled={create.isPending || !title.trim()}
              >
                {create.isPending ? "Se creează..." : "Creează clubul"}
              </button>
              <Link to="/cluburi" className="cal-btn">
                Anulează
              </Link>
            </div>
          </form>
        </PieceCol>
      </Stage>
    </>
  );
}
