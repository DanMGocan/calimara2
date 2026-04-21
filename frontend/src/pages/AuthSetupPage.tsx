import { useState } from "react";
import { Helmet } from "react-helmet-async";
import { completeSetup } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast-context";
import { DebugLabel } from "@/components/ui/debug-label";
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
      setError("Numele de utilizator trebuie sa aiba intre 3 si 20 de caractere.");
      return;
    }
    if (!/^[a-z0-9]+$/.test(username)) {
      setError("Doar litere mici si cifre.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await completeSetup({
        username,
        subtitle: subtitle || undefined,
        avatar_seed: selectedSeed,
      });
      showToast("Cont creat cu succes!", "success");
      window.location.href = getBlogUrl(res.username);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Eroare la crearea contului.";
      setError(message);
      setSubmitting(false);
    }
  };

  return (
    <>
      <Helmet>
        <title>Configureaza-ti contul | Calimara</title>
      </Helmet>
      <div className="relative flex min-h-[60vh] items-center justify-center px-4 py-12">
        <DebugLabel name="AuthSetupPage" />
        <Card className="relative w-full max-w-lg">
          <DebugLabel name="AuthSetupCard" />
          <CardHeader className="text-center">
            <CardTitle className="font-display text-2xl">Configureaza-ti profilul</CardTitle>
            <p className="text-sm text-muted mt-1">Alege un nume de utilizator si un avatar</p>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Avatar Selection */}
              <div>
                <label className="block text-sm font-medium text-primary mb-3">Avatar</label>
                <div className="grid grid-cols-6 gap-3">
                  {seeds.map((seed) => (
                    <button
                      key={seed}
                      type="button"
                      aria-label={`Alege avatarul ${seed}`}
                      aria-pressed={selectedSeed === seed}
                      onClick={() => setSelectedSeed(seed)}
                      className={`rounded-full p-0.5 transition-all cursor-pointer ${
                        selectedSeed === seed
                          ? "ring-2 ring-accent ring-offset-2"
                          : "hover:ring-2 hover:ring-border"
                      }`}
                    >
                      <img src={getAvatarUrl(seed, 64)} alt="" className="h-12 w-12 rounded-full" />
                    </button>
                  ))}
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="mt-2"
                  onClick={() => {
                    const newSeeds = generateAvatarSeeds(6);
                    setSeeds(newSeeds);
                    setSelectedSeed(newSeeds[0]);
                  }}
                >
                  Genereaza altele
                </Button>
              </div>

              {/* Username */}
              <div>
                <label htmlFor="username" className="block text-sm font-medium text-primary mb-1">
                  Nume de utilizator
                </label>
                <Input
                  id="username"
                  value={username}
                  onChange={(e) => {
                    setUsername(e.target.value.toLowerCase());
                    setError("");
                  }}
                  placeholder="numeleTau"
                  maxLength={20}
                  required
                />
                <p className="mt-1 text-xs text-muted">3-20 caractere, doar litere mici si cifre</p>
              </div>

              {/* Subtitle */}
              <div>
                <label htmlFor="subtitle" className="block text-sm font-medium text-primary mb-1">
                  Subtitlu (optional)
                </label>
                <Input
                  id="subtitle"
                  value={subtitle}
                  onChange={(e) => setSubtitle(e.target.value)}
                  placeholder="Poet, scriitor, visator..."
                  maxLength={100}
                />
              </div>

              {error && <p className="text-sm text-danger">{error}</p>}

              <Button type="submit" disabled={submitting} className="w-full">
                {submitting ? "Se creeaza..." : "Creeaza contul"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
