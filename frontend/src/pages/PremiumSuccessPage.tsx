import { useEffect, useRef, useState } from "react";
import { Helmet } from "react-helmet-async";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { fetchCurrentUser } from "@/api/auth";
import { Stage, PieceCol } from "@/components/ui/stage";
import { KindBadge } from "@/components/ui/kind-badge";

export default function PremiumSuccessPage() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [confirmed, setConfirmed] = useState(false);
  const [giveUp, setGiveUp] = useState(false);
  const triesRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await fetchCurrentUser();
        if (cancelled) return;
        if (res?.user?.is_premium) {
          qc.invalidateQueries({ queryKey: ["auth", "me"] });
          qc.invalidateQueries({ queryKey: ["super-like-quota"] });
          setConfirmed(true);
          setTimeout(() => nav("/dashboard", { replace: true }), 1200);
          return;
        }
      } catch {
        /* keep polling */
      }
      triesRef.current += 1;
      if (triesRef.current < 10) {
        setTimeout(poll, 1000);
      } else {
        setGiveUp(true);
      }
    };
    poll();
    return () => {
      cancelled = true;
    };
  }, [nav, qc]);

  return (
    <>
      <Helmet>
        <title>Mulțumim! | călimara.ro</title>
      </Helmet>
      <Stage variant="centered">
        <PieceCol>
          <KindBadge label="Premium" />
          <h1 className="piece-title">Mulțumim!</h1>
          {confirmed ? (
            <p>Contul tău este acum Premium. Te redirecționăm…</p>
          ) : giveUp ? (
            <p>
              Plata a fost înregistrată. Actualizarea poate dura câteva momente —
              reîncarcă dashboardul sau revino în scurt timp.
            </p>
          ) : (
            <p>Confirmăm plata cu Stripe…</p>
          )}
        </PieceCol>
      </Stage>
    </>
  );
}
