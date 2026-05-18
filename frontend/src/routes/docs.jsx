import { AuthRequired, PageShell, StatusPanel } from "../app/layout.jsx";

const DOC_SECTIONS = [
  {
    id: "harta",
    title: "Harta aplicației",
    summary: "Călimara este o aplicație FastAPI + React pentru publicare literară, comunitate și operațiuni editoriale. Frontendul este un SPA Vite, backendul expune API-uri românești sub /api, iar PostgreSQL este definit din schema.sql.",
    bullets: [
      "run.py pornește aplicația, reconstruiește schema în mediul de dezvoltare când CALIMARA_RESET_DATABASE este activ, construiește frontendul și lansează workerul AI.",
      "React decide ruta în frontend/src/app/router.jsx; backendul servește index.html pentru rutele SPA și păstrează /api pentru JSON.",
      "Frontendul încarcă Finlandica Headline din Google Fonts și o folosește prin variabilele globale --serif, --sans și --mono din frontend/src/index.css.",
      "Autentificarea folosește sesiunea calimara_sess, epoch-ul DB invalidează sesiunile vechi după reset, iar subdomeniile de autor sunt rutate prin host.",
      "schema.sql este sursa de adevăr pentru structura DB; proiectul nu folosește migrații SQL versionate în fluxul curent."
    ]
  },
  {
    id: "auth",
    title: "Conturi, acces și sesiuni",
    summary: "Utilizatorii intră prin Google, Facebook sau autentificare locală cu coduri email. Platforma pornește închisă și acceptă doar emailuri din lista de acces până când un admin o deschide manual.",
    bullets: [
      "Fluxurile OAuth păstrează return_to doar pentru domeniul principal sau subdomenii valide și trimit utilizatorii noi în configurarea profilului.",
      "Fereastra de autentificare permite intrare locală, creare cont cu email și parolă, plus Google și Facebook.",
      "Autentificarea locală trimite coduri pentru activarea contului și resetarea parolei prin EmailOutbox.",
      "Panoul admin controlează deschiderea platformei și lista de emailuri permise; starea implicită este închisă.",
      "Rolurile principale sunt utilizator, moderator și admin; adminul include drepturi de moderare."
    ]
  },
  {
    id: "texte",
    title: "Publicare, editor și lectură",
    summary: "Autorii publică poezie și proză scurtă, pot salva ciorne, edita texte și gestiona arhiva proprie din /panou.",
    bullets: [
      "Editorul folosește RichTextEditor și limitele din constants.js: titlu 120 caractere, poezie 10.000, proză scurtă 50.000.",
      "O postare nouă pornește cu moderation_status pending și intră în coada AI post_publish.",
      "După aprobare, postarea devine vizibilă pe landing, profil public, arhivă și subdomeniul autorului.",
      "Pagina de lectură comună folosește PieceCol, post actions, progres de derulare și export PDF."
    ]
  },
  {
    id: "moderare",
    title: "Moderare AI și revizie umană",
    summary: "Moderarea este asincronă. Cererile creează AIJob, workerul procesează conținutul, scrie moderation_logs și modifică statusul conținutului.",
    bullets: [
      "Tipuri procesate: post, comment, forum_thread, forum_reply, theatre_entry, audio, plus joburi de follow-up pentru teme și critic AI.",
      "Conținutul curat este aprobat automat; conținutul ambiguu devine flagged și intră în revizie umană.",
      "Jurnalul arată decizia AI, scoruri, motive, decizia umană și moderatorul.",
      "Rapoartele de la utilizatori sunt separate de AI: plagiat/ofensiv, review admin, respingere, ștergere sau dismiss.",
      "Workerul scripts/process_ai_jobs.py --loop trebuie să rămână pornit; joburile blocate apar în tabul Joburi."
    ]
  },
  {
    id: "comentarii-reactii",
    title: "Comentarii, aprecieri și Super-apreciez",
    summary: "Comentariile sunt moderate înainte de afișare, iar reacțiile alimentează clasamentele și economia internă.",
    bullets: [
      "Comentariile aprobate pot declanșa notificări pentru mențiuni și emailuri către autor.",
      "Aprecierile simple și Super-aprecierile sunt separate; Super-apreciez consumă resurse premium și acordă recompense.",
      "PostActionTools este suprafața comună pentru acțiuni pe landing și pe pagina postării.",
      "Contoarele publice folosesc valorile canonice din backend, inclusiv view_count și deduplicarea vizualizărilor."
    ]
  },
  {
    id: "profiluri",
    title: "Profil public și Călimara mea",
    summary: "Profilul public este hubul autorului: opere, bio, linkuri, media, inventar echipat și promovări.",
    bullets: [
      "Setările profilului includ subtitlu, descriere, avatar, copertă, locație, playlist YouTube și linkuri sociale.",
      "Linkurile de donații PayPal, Patreon și Cafea sunt vizibile și editabile doar pentru tierurile premium Bronz, Argint și Aur.",
      "Călimara mea are trei zone promovate: opere proprii, autori promovați și opere de la alți autori.",
      "Structura curentă de promovare folosește limitele 2 / 3 / 3 și câmpurile promoted_own_posts, promoted_authors, promoted_external_posts.",
      "Profilul păstrează acces către toate operele, urmăritori, urmăriți și inventarul public."
    ]
  },
  {
    id: "social",
    title: "Prieteni, urmăriri și director",
    summary: "Aplicația are două relații sociale: follow pentru abonare publică și prietenie pentru legături explicite.",
    bullets: [
      "Prieteni gestionează cereri primite/trimise, prieteni confirmați și link către Toti utilizatorii.",
      "Directorul complet /utilizatori este autentificat și oferă căutare, sortare după activitate și metrici de descoperire.",
      "Follow/unfollow alimentează urmăritorii publici și poate fi folosit independent de prietenie.",
      "Best friends rămâne o structură de profil, separată de sistemul de prietenii."
    ]
  },
  {
    id: "mesaje-notificari",
    title: "Mesaje și notificări",
    summary: "Mesajele private sunt conversații între doi utilizatori, iar notificările țin la zi autorii, actorii și moderatorii.",
    bullets: [
      "Mesajele sunt în /mesaje și folosesc Conversation + Message.",
      "Notificările apar în panoul legat de iconul profilului și afișează count necitit.",
      "Evenimentele care notifică includ aprobare/respingere moderare, comentarii aprobate, mențiuni, teatru, cluburi și feedback operațional.",
      "Mențiunile se trimit după aprobare, nu înainte."
    ]
  },
  {
    id: "audio",
    title: "Audio, TTS și player",
    summary: "Audio-ul are două surse: generare TTS pentru texte și înregistrări de autor, cu acces condiționat de tier premium.",
    bullets: [
      "Cronicar și Rapsod au acces la player audio; Rapsod poate încărca înregistrări de autor.",
      "TTS calculează cote pe număr de caractere și pornește joburi asincrone.",
      "Înregistrările de autor sunt transcrise și comparate cu textul postării înainte de a deveni ready.",
      "Playerul global este în navbar, iar acțiunile audio compacte sunt în PostActionTools."
    ]
  },
  {
    id: "premium",
    title: "Premium și plăți",
    summary: "Tierurile sunt Gratuit, Trubadur, Cronicar și Rapsod. Planurile sunt servite de backend și checkoutul merge prin Stripe/portal.",
    bullets: [
      "Premium controlează accesul la facilități precum Super-apreciez, audio și funcții de autor.",
      "Adminul poate ajusta manual tierul, perioada și identificatorii Stripe ai unui utilizator.",
      "Evenimentele Stripe sunt deduplicate, iar abonamentele setează premium_tier, premium_period_start și premium_until.",
      "Pagina premium afișează planurile din /api/premium/planuri, nu valori hardcodate în UI."
    ]
  },
  {
    id: "economie",
    title: "Gologani, magazin și inventar",
    summary: "Gologanii recompensează contribuții aprobate și se cheltuiesc pe cosmetice de profil.",
    bullets: [
      "Recompensele vin din conținut aprobat, aprecieri și Super-aprecieri, prin GologaniTransaction.",
      "Magazinul are obiecte pe sloturi: insignă profil, costum, ramă, fundal și titlu.",
      "Inventarul utilizatorului permite echipare/dezechipare pe slot, iar profilul public serializează obiectele echipate.",
      "Adminul poate crea/dezactiva obiecte și ajusta manual balanța unui utilizator."
    ]
  },
  {
    id: "realizari",
    title: "Realizări și distincții",
    summary: "Realizările sunt reguli codate care acordă distincții publice pe profil și notificări când apar evenimente eligibile.",
    bullets: [
      "Definițiile sunt seeduite în cod în app/achievements, nu create din UI-ul admin.",
      "user_awards este registrul idempotent pentru distincții: achievement_key, dedupe_key, sursă, metadata și data acordării.",
      "Regulile rulează doar pentru evenimente noi; nu există backfill istoric automat sau manual în versiunea curentă.",
      "Ferestrele de timp pentru postări folosesc publicarea prin aprobare: Post.moderated_at este ancora pentru reguli precum Piciorul lui Hermes."
    ]
  },
  {
    id: "cluburi",
    title: "Cluburi",
    summary: "Cluburile sunt spații comunitare cu proprietar, membri, cereri/invitații, roluri și panou intern.",
    bullets: [
      "Un owner creează clubul, aprobă cereri, invită membri, schimbă roluri sau elimină membri.",
      "Club board messages pot fi fire de discuție sau răspunsuri și se pot șterge de către rolurile permise.",
      "Un club poate avea o postare recomandată, controlată de owner/admin.",
      "Notificările anunță cereri, invitații și rezultate."
    ]
  },
  {
    id: "teatru",
    title: "Teatru colaborativ",
    summary: "Teatrul permite piese scrise pe rând, cu personaje, actori, scene, replici, indicații scenice și export PDF.",
    bullets: [
      "Creatorul deschide o piesă, aprobă personaje, invită actori sau răspunde cererilor de participare.",
      "Scenele au o ordine, un actor curent și un personaj curent; replicile pot muta rândul către următorul personaj.",
      "Intrările de teatru sunt moderate ca theatre_entry și apar în jurnalul de moderare.",
      "PDF-ul exportă doar intrările aprobate, astfel încât ciornele/moderarea să nu ajungă în documentul public."
    ]
  },
  {
    id: "stafeta",
    title: "Ștafeta",
    summary: "Ștafeta creează texte private pornite de un autor și continuate pe rând de participanți, cu potrivire automată dintr-un pool.",
    bullets: [
      "O Ștafetă se poate crea chiar dacă nu există destinatar disponibil; rămâne activă fără rând curent până intră în potrivirea automată.",
      "Participarea are un număr dorit de Ștafete active: Gratuit și Trubadur până la 3, Cronicar până la 6, Rapsod până la 10.",
      "Potrivirea folosește doar invitații/rânduri pending sau active pentru limită și alocă întâi utilizatorii cu cele mai puține Ștafete deschise.",
      "Când un rând nu poate merge mai departe aleatoriu, Ștafeta revine în pool în loc să eșueze cererea."
    ]
  },
  {
    id: "forum",
    title: "Discuții",
    summary: "Forumul are secțiuni pentru anunțuri, discuții generale, poezie și proză scurtă.",
    bullets: [
      "Threadurile și răspunsurile intră în moderare AI înainte să fie publice.",
      "Moderatorii pot șterge sau schimba starea discuțiilor, iar adminii pot administra conținutul din panoul central.",
      "Răspunsurile aprobate notifică participanții relevanți și actualizează activitatea threadului.",
      "Secțiunea anunțuri este separată în UI și poate fi folosită pentru comunicare oficială."
    ]
  },
  {
    id: "serii-exporturi",
    title: "Serii, exporturi și pagini publice",
    summary: "Seriile grupează postări ale aceluiași autor, iar exporturile PDF servesc postări sau piese de teatru aprobate.",
    bullets: [
      "Un text poate fi într-o singură serie a autorului; ordinea capitolelor se poate schimba.",
      "Paginile publice ascund postările neaprobate, dar panoul autorului le poate afișa pentru editare.",
      "Landing, profilele publice și toate-operele folosesc payloaduri publice cu statistici și acțiuni permise.",
      "Exporturile refuză conținutul neaprobat pentru a evita publicarea accidentală."
    ]
  },
  {
    id: "email",
    title: "Emailuri",
    summary: "EmailOutbox este coada comună pentru coduri de autentificare, comentarii aprobate, mențiuni, digesturi și campanii admin.",
    bullets: [
      "Brevo trimite emailurile când EMAILS_ENABLED este activ, iar workerul process_email_outbox revendică rânduri due.",
      "Preferințele utilizatorului acoperă comentarii, mențiuni, digesturi de analytics și anunțuri admin.",
      "Campaniile admin folosesc HTML brut, filtre de audiență și aceeași coadă de trimitere.",
      "Linkurile de dezabonare folosesc tokenuri semnate."
    ]
  },
  {
    id: "admin",
    title: "Panoul admin",
    summary: "Panoul /moderare centralizează operațiunile: overview, acces, utilizatori, conținut, sesizări, email, moderare, rapoarte, jurnal, economie, premium, joburi și audit.",
    bullets: [
      "Moderatorii văd coada AI, marcate, raportări și jurnal; adminii văd toate taburile operaționale.",
      "Overview agregă utilizatori, conținut, trafic, premium, joburi și metrici zilnice.",
      "Auditul înregistrează acțiuni administrative cu actor, țintă, motiv și metadata.",
      "Joburi arată AIJob, retry/cancel și erori pentru investigarea workerelor."
    ]
  },
  {
    id: "analytics",
    title: "Statistici, ads și trafic",
    summary: "Statisticile separă vizualizările reale de boți și alimentează dashboardul, digesturile și rapoartele admin.",
    bullets: [
      "PageView și DailyStat stochează trafic pe content_type/content_id sau content_key.",
      "Vizualizările postărilor sunt deduplicate și actualizează view_count canonic.",
      "AdSense este activ doar pe rutele din AD_SUPPORTED_ROUTES și numai când env-ul o permite.",
      "Digesturile de analytics folosesc vizualizări, ascultări, comentarii și aprecieri aprobate."
    ]
  },
  {
    id: "operare",
    title: "Operare și depanare",
    summary: "Pentru probleme live se verifică întâi serviciul, workerul, frontendul, DB-ul și endpointul concret.",
    bullets: [
      "Procese importante: calimara.service/run.py --serve, scripts/process_ai_jobs.py --loop, Vite dev server pe 5173 când este folosit.",
      "Pentru DB, sursa este schema.sql; fără migrații, schimbările se aplică prin reset/rebuild sau operații live punctuale în dezvoltare.",
      "Pentru 502 sau failed to fetch se probează 127.0.0.1:8000, nginx/proxy și endpointul JSON înainte de refactor.",
      "Testele backend focalizate se rulează cu python -m pytest, iar frontendul se verifică prin npm run build."
    ]
  },
  {
    id: "schimbari",
    title: "Schimbări documentate",
    summary: "Această pagină este ea însăși parte din suprafața admin și trebuie actualizată când apar funcții noi.",
    bullets: [
      "/docs este servit de backend doar pentru admini și este rutat în React ca pagină protejată.",
      "Panoul admin include link direct către documentație în grupul Referință.",
      "Documentația curentă include moderarea theatre_entry, coada AI, schema.sql ca sursă de adevăr și fluxurile noi de teatru, email, economie, realizări și acces platformă.",
      "Când se schimbă o funcție majoră, actualizează întâi codul și testele, apoi această pagină, apoi memoria agentului."
    ]
  }
];

function slugLabel(index) {
  return String(index + 1).padStart(2, "0");
}

function DocsSection({ section, index }) {
  return (
    <section className="docs-section" id={section.id}>
      <div className="docs-section-head">
        <span>{slugLabel(index)}</span>
        <h2>{section.title}</h2>
      </div>
      <p className="docs-summary">{section.summary}</p>
      <ul className="docs-list">
        {section.bullets.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </section>
  );
}

export default function DocsRoute({ user }) {
  if (!user) return <AuthRequired />;
  if (!user.is_admin) {
    return (
      <PageShell kicker="docs" title="Acces admin necesar" sub="Documentația internă este disponibilă doar administratorilor.">
        <StatusPanel title="Acces restricționat">Contul curent nu are rol de administrator.</StatusPanel>
      </PageShell>
    );
  }

  return (
    <PageShell
      kicker="docs"
      title="Documentație aplicație"
      sub="Ghid intern pentru arhitectură, fluxuri de produs, moderare, operațiuni și suprafețe admin."
    >
      <div className="docs-layout">
        <aside className="docs-toc" aria-label="Cuprins documentație">
          <h2>Cuprins</h2>
          <nav>
            {DOC_SECTIONS.map((section, index) => (
              <a href={`#${section.id}`} key={section.id}>
                <span>{slugLabel(index)}</span>
                {section.title}
              </a>
            ))}
          </nav>
        </aside>
        <div className="docs-content">
          {DOC_SECTIONS.map((section, index) => <DocsSection key={section.id} section={section} index={index} />)}
        </div>
      </div>
    </PageShell>
  );
}
