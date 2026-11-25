import { PageShell } from "../app/layout.jsx";
import { mainPath } from "../app/paths.js";

function NotFoundView() {
  return (
    <PageShell
      kicker="404"
      title="Pagina nu există"
      sub="Pagina pe care o cauți nu există, a fost ștearsă sau adresa conține o greșeală."
    >
      <div className="not-found-actions">
        <a className="cal-btn primary" href={mainPath("/")}>Înapoi la prima pagină</a>
        <a className="cal-btn" href={mainPath("/discutii")}>Discuții</a>
        <a className="cal-btn" href={mainPath("/ce-este-calimara")}>Ce este Călimara</a>
      </div>
    </PageShell>
  );
}

export default function NotFoundRoute() {
  return <NotFoundView />;
}
