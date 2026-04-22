import { Helmet } from "react-helmet-async";
import { Link } from "react-router-dom";
import { Stage, PieceCol } from "@/components/ui/stage";
import { KindBadge } from "@/components/ui/kind-badge";

export default function PremiumCancelPage() {
  return (
    <>
      <Helmet>
        <title>Plată anulată | călimara.ro</title>
      </Helmet>
      <Stage variant="centered">
        <PieceCol>
          <KindBadge label="Premium" />
          <h1 className="piece-title">Plata a fost anulată</h1>
          <p>Nicio problemă, poate altă dată.</p>
          <p>
            <Link to="/premium">Încearcă din nou</Link>
          </p>
        </PieceCol>
      </Stage>
    </>
  );
}
