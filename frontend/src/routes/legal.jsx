import { PageShell } from "../app/layout.jsx";

function PrivacyView() {
  return (
    <PageShell kicker="legal" title="Politica de confidențialitate" sub="Ultima actualizare: 28 aprilie 2026.">
      <div className="legal-copy">
        <section className="legal-section">
          <h2>Datele contului</h2>
          <p>Călimara folosește autentificare prin email și parolă, Google sau Facebook. Păstrăm datele necesare funcționării platformei: nume public, email, identificatori de autentificare, texte publicate, comentarii, reacții, mesaje, abonamente și preferințe de profil.</p>
        </section>
        <section className="legal-section">
          <h2>Cookie-uri și sesiuni</h2>
          <p>Folosim cookie-uri de sesiune pentru autentificare, securitate și funcțiile contului. Aceste cookie-uri sunt necesare pentru conectare și pentru păstrarea sesiunii între domeniul principal și blogurile de autor.</p>
        </section>
        <section className="legal-section">
          <h2>Publicitate</h2>
          <p>Paginile publice gratuite pot afișa reclame prin Google AdSense. Google și partenerii săi pot folosi cookie-uri sau stocare locală pentru afișarea, măsurarea și personalizarea reclamelor, în funcție de consimțământul tău și de setările disponibile în mesajul de confidențialitate Google.</p>
          <p>În Spațiul Economic European, Regatul Unit și Elveția, consimțământul pentru reclame este colectat prin Google Privacy & messaging. Utilizatorii Premium nu văd reclame în interfața publică atunci când sunt conectați.</p>
        </section>
        <section className="legal-section">
          <h2>Plăți</h2>
          <p>Plățile pentru Premium sunt procesate prin Stripe. Călimara nu stochează datele cardului. Păstrăm doar identificatori Stripe și starea abonamentului necesare activării beneficiilor Premium.</p>
        </section>
        <section className="legal-section">
          <h2>Contact</h2>
          <p>Pentru întrebări despre datele tale sau despre această politică, scrie la <a href="mailto:contact@calimara.ro">contact@calimara.ro</a>.</p>
        </section>
      </div>
    </PageShell>
  );
}
function TermsView() {
  return (
    <PageShell kicker="legal" title="Termeni și condiții" sub="Ultima actualizare: 28 aprilie 2026.">
      <div className="legal-copy">
        <section className="legal-section">
          <h2>Utilizarea platformei</h2>
          <p>Călimara este o platformă pentru publicarea și descoperirea textelor literare. Utilizatorii sunt responsabili pentru conținutul pe care îl publică și pentru respectarea drepturilor de autor.</p>
        </section>
        <section className="legal-section">
          <h2>Conținut și moderare</h2>
          <p>Putem modera, respinge sau elimina conținut care încalcă regulile platformei, legea aplicabilă sau siguranța comunității. Funcțiile de comentarii, forum și mesaje trebuie folosite fără hărțuire, spam sau abuz.</p>
        </section>
        <section className="legal-section">
          <h2>Reclame</h2>
          <p>Paginile publice gratuite pot include reclame Google AdSense. Reclamele nu trebuie confundate cu navigația, acțiunile platformei sau conținutul editorial. Conturile Premium conectate beneficiază de experiență fără reclame.</p>
        </section>
        <section className="legal-section">
          <h2>Premium</h2>
          <p>Abonamentele Premium sunt gestionate prin Stripe Checkout și Stripe Customer Portal. Beneficiile Premium sunt active cât timp abonamentul este valid conform stării primite de la Stripe.</p>
        </section>
        <section className="legal-section">
          <h2>Contact</h2>
          <p>Pentru întrebări despre acești termeni, scrie la <a href="mailto:contact@calimara.ro">contact@calimara.ro</a>.</p>
        </section>
      </div>
    </PageShell>
  );
}

export default function LegalRoute({ route }) {
  if (route.name === "terms") return <TermsView />;
  return <PrivacyView />;
}
