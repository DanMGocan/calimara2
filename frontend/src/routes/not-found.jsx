import { PageShell } from "../app/layout.jsx";
import { mainPath } from "../app/paths.js";

function NotFoundView() {
  return (
    <PageShell kicker="404" title="Pagina nu există" sub="Ruta nu este disponibilă în noul frontend.">
      <a className="cal-btn primary" href={mainPath("/")}>Înapoi acasă</a>
    </PageShell>
  );
}

export default function NotFoundRoute() {
  return <NotFoundView />;
}
