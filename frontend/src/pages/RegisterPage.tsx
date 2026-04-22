import { Helmet } from "react-helmet-async";
import { Button } from "@/components/ui/button";
import { Stage } from "@/components/ui/stage";

export default function RegisterPage() {
  return (
    <>
      <Helmet>
        <title>Intră în călimara | călimara.ro</title>
      </Helmet>
      <Stage variant="centered">
        <div className="auth-card">
          <div className="auth-kicker">începe</div>
          <h1 className="auth-title">Intră în călimara</h1>
          <p className="auth-sub">
            Conectează-te cu Google pentru a crea un cont și a începe să publici poezie și proză.
          </p>
          <Button asChild size="lg" className="w-full">
            <a href="/auth/google">continuă cu Google</a>
          </Button>
          <p
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--color-ink-faint)",
              textAlign: "center",
              marginTop: 20,
            }}
          >
            contul e liber · fără reclame
          </p>
        </div>
      </Stage>
    </>
  );
}
