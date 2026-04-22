import { Helmet } from "react-helmet-async";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Stage } from "@/components/ui/stage";

export default function NotFoundPage() {
  return (
    <>
      <Helmet>
        <title>404 · pagina nu există | călimara.ro</title>
      </Helmet>
      <Stage variant="centered">
        <div style={{ textAlign: "center", maxWidth: 520 }}>
          <div className="auth-kicker">404</div>
          <h1
            className="piece-title"
            style={{ fontSize: "clamp(44px, 6vw, 72px)" }}
          >
            Pagina nu există.
          </h1>
          <p
            style={{
              fontFamily: "var(--font-serif)",
              fontStyle: "italic",
              color: "var(--color-ink-mute)",
              fontSize: 17,
              margin: "16px 0 32px",
            }}
          >
            Poate textul a fost retras sau adresa e scrisă greșit.
          </p>
          <Button asChild>
            <Link to="/">înapoi acasă</Link>
          </Button>
        </div>
      </Stage>
    </>
  );
}
