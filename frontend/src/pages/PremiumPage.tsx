import { Helmet } from "react-helmet-async";
import { Link } from "react-router-dom";
import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/components/ui/toast-context";
import { Button } from "@/components/ui/button";
import { Stage, PieceCol } from "@/components/ui/stage";
import { KindBadge } from "@/components/ui/kind-badge";
import { startPremiumCheckout, openCustomerPortal } from "@/api/premium";
import { ApiError } from "@/api/client";
import { formatDate } from "@/lib/utils";

export default function PremiumPage() {
  const { isAuthenticated, user } = useAuth();
  const { showToast } = useToast();
  const [busy, setBusy] = useState(false);

  const handleCheckout = async () => {
    setBusy(true);
    try {
      await startPremiumCheckout();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Nu am putut porni plata.";
      showToast(msg, "danger");
      setBusy(false);
    }
  };

  const handlePortal = async () => {
    setBusy(true);
    try {
      await openCustomerPortal();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Nu am putut deschide portalul.";
      showToast(msg, "danger");
      setBusy(false);
    }
  };

  return (
    <>
      <Helmet>
        <title>Premium | călimara.ro</title>
      </Helmet>
      <Stage variant="centered">
        <PieceCol>
          <KindBadge label="Premium" />
          <h1 className="piece-title">Super-aprecieri, mai multe</h1>

          {!isAuthenticated ? (
            <>
              <p>Autentifică-te pentru a accesa abonamentul Premium.</p>
              <p>
                <Link to="/register">Autentifică-te</Link>
              </p>
            </>
          ) : user?.is_premium ? (
            <>
              <p>
                Abonamentul tău Premium este activ până la{" "}
                <strong>
                  {user.premium_until ? formatDate(user.premium_until) : "—"}
                </strong>
                .
              </p>
              <p>Primești 3 super-aprecieri în fiecare săptămână, în loc de una.</p>
              <Button onClick={handlePortal} disabled={busy}>
                {busy ? "se deschide…" : "Gestionează abonamentul"}
              </Button>
            </>
          ) : (
            <>
              <ul style={{ fontFamily: "var(--font-serif)", fontSize: 18, lineHeight: 1.8 }}>
                <li>3 super-aprecieri pe săptămână (în loc de 1)</li>
                <li>Accent auriu pe postările pe care le super-apreciezi</li>
                <li>Susții dezvoltarea platformei</li>
              </ul>
              <p style={{ fontSize: 20, margin: "20px 0" }}>
                <strong>3.99 € / lună</strong> · facturat lunar prin Stripe
              </p>
              <Button onClick={handleCheckout} disabled={busy}>
                {busy ? "se redirectează…" : "Devino Premium"}
              </Button>
              <p style={{ fontSize: 12, color: "var(--color-ink-faint)", marginTop: 16 }}>
                Plata este procesată de Stripe. Poți anula oricând din portalul de facturare.
              </p>
            </>
          )}
        </PieceCol>
      </Stage>
    </>
  );
}
