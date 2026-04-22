import { useState } from "react";
import { Helmet } from "react-helmet-async";
import { completeSetup } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast-context";
import { Stage } from "@/components/ui/stage";
import { generateAvatarSeeds } from "@/hooks/useDiceBearAvatar";
import { getAvatarUrl, getBlogUrl } from "@/lib/utils";

export default function AuthSetupPage() {
  const { showToast } = useToast();
  const [username, setUsername] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [seeds, setSeeds] = useState(() => generateAvatarSeeds(6));
  const [selectedSeed, setSelectedSeed] = useState(seeds[0]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (username.length < 3 || username.length > 20) {
      setError("Numele de utilizator trebuie să aibă între 3 și 20 de caractere.");
      return;
    }
    if (!/^[a-z0-9]+$/.test(username)) {
      setError("Doar litere mici și cifre.");
      return;
    }
    setSubmitting(true);
    try {
      const res = await completeSetup({
        username,
        subtitle: subtitle || undefined,
        avatar_seed: selectedSeed,
      });
      showToast("Cont creat.", "success");
      window.location.href = getBlogUrl(res.username);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Eroare la crearea contului.";
      setError(message);
      setSubmitting(false);
    }
  };

  return (
    <>
      <Helmet>
        <title>Configurează profilul | călimara.ro</title>
      </Helmet>

      <Stage variant="centered">
        <div className="auth-card" style={{ maxWidth: 540 }}>
          <div className="auth-kicker">pas final</div>
          <h1 className="auth-title">Configurează-ți profilul</h1>
          <p className="auth-sub">
            Alege un nume de utilizator și un avatar. Poți schimba ulterior oricând.
          </p>

          <form onSubmit={handleSubmit}>
            <label className="auth-field">Avatar</label>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(6, 1fr)",
                gap: 12,
                marginBottom: 12,
              }}
            >
              {seeds.map((seed) => (
                <button
                  key={seed}
                  type="button"
                  onClick={() => setSelectedSeed(seed)}
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
                    background: "transparent",
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
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                const newSeeds = generateAvatarSeeds(6);
                setSeeds(newSeeds);
                setSelectedSeed(newSeeds[0]);
              }}
            >
              generează alte opțiuni
            </Button>

            <label className="auth-field" htmlFor="username">
              Nume de utilizator
            </label>
            <Input
              id="username"
              value={username}
              onChange={(e) => {
                setUsername(e.target.value.toLowerCase());
                setError("");
              }}
              placeholder="numele_tau"
              maxLength={20}
              required
            />
            <p
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                letterSpacing: "0.14em",
                color: "var(--color-ink-faint)",
                marginTop: 4,
              }}
            >
              3–20 caractere · litere mici și cifre
            </p>

            <label className="auth-field" htmlFor="subtitle">
              Subtitlu (opțional)
            </label>
            <Input
              id="subtitle"
              value={subtitle}
              onChange={(e) => setSubtitle(e.target.value)}
              placeholder="poet, visător, călător…"
              maxLength={100}
            />

            {error ? <p className="auth-error">{error}</p> : null}

            <Button
              type="submit"
              disabled={submitting}
              className="w-full"
              style={{ marginTop: 24 }}
            >
              {submitting ? "se creează…" : "creează contul"}
            </Button>
          </form>
        </div>
      </Stage>
    </>
  );
}
