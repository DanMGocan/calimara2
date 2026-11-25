import { AuthRequired, PageShell, StatusPanel } from "../app/layout.jsx";

const DOC_SECTIONS = [
  {
    id: "harta",
    title: "Harta aplicației",
    summary: "Călimara este o aplicație FastAPI + React pentru publicare literară, comunitate și operațiuni editoriale. Frontendul este un SPA Vite, backendul expune API-uri românești sub /api, iar PostgreSQL este definit din schema.sql.",
    bullets: [
      "run.py pornește aplicația, reconstruiește schema doar când CALIMARA_RESET_DATABASE este activ, iar serviciul systemd păstrează datele existente la restart.",
      "Serviciul systemd setează workerii Uvicorn, pool-ul PostgreSQL, cache-ul public de 60s și pragul de slow request folosite de panoul Performanță.",
      "React decide ruta în frontend/src/app/router.jsx; backendul servește index.html pentru rutele SPA și păstrează /api pentru JSON.",
      "Shell-ul global afișează bannerul galben de testare deasupra navigației, cu link către pagina Facebook Călimara.",
      "Frontendul încarcă Finlandica Headline din Google Fonts și o folosește prin variabilele globale --serif, --sans și --mono din frontend/src/index.css.",
      "Autentificarea folosește sesiunea calimara_sess, epoch-ul DB invalidează sesiunile vechi după reset, iar subdomeniile de autor sunt rutate prin host.",
      "schema.sql este sursa de adevăr pentru structura DB; proiectul nu folosește migrații SQL versionate în fluxul curent."
    ]
  },
  {
    id: "auth",
    title: "Conturi, acces și sesiuni",
    summary: "Utilizatorii intră prin Google, autentificare locală cu coduri email sau invitații admin. Platforma pornește închisă și acceptă doar emailuri din lista de acces sau invitații active până când un admin o deschide manual.",
    bullets: [
      "Fluxurile OAuth păstrează return_to doar pentru domeniul principal sau subdomenii valide și trimit utilizatorii noi în configurarea profilului.",
      "Configurarea profilului/blogului cere acceptarea explicită a Termenilor și condițiilor și a Politicii de confidențialitate; backendul respinge finalizarea fără accept_terms_and_privacy.",
      "După configurarea unui cont din invitație, return_to către pagina invitației sau către rutele de autentificare este ignorat, iar utilizatorul este trimis către propriul blog.",
      "În configurarea inițială, descrierea profilului poate fi verificată cu Diacritice prin /api/autentificare/configurare/diacritice înainte ca blogul să fie creat; dacă serviciul AI cade, utilizatorul poate finaliza fără Diacritice.",
      "Fereastra de autentificare permite intrare locală, creare cont cu email și parolă, plus Google.",
      "Autentificarea locală trimite coduri pentru activarea contului și resetarea parolei prin EmailOutbox.",
      "Linkurile de recomandare folosesc parametrul ref și permit configurarea unui cont nou cu referrer păstrat până la finalizarea profilului.",
      "Invitațiile admin includ un email simplu cu buton compatibil cu Gmail, link complet de rezervă, opțiune Google și parolă temporară; utilizatorul poate schimba parola ulterior din profil, dar nu este obligat.",
      "Panoul admin controlează deschiderea platformei, lista de emailuri permise și invitațiile; starea implicită este închisă.",
      "Rolurile principale sunt utilizator, moderator și admin; adminul include drepturi de moderare."
    ]
  },
  {
    id: "seo",
    title: "SEO și indexare",
    summary: "Suprafața publică are metadate dinamice, sitemap și robots.txt pentru descoperire în Google, în timp ce paginile private rămân marcate noindex.",
    bullets: [
      "Backendul servește /robots.txt și /sitemap.xml din app/seo.py; sitemapul listează homepage, pagini legale/publice, profiluri cu texte aprobate, toate-operele, postări aprobate, serii cu texte aprobate, piese de teatru și discuții aprobate.",
      "Catch-all-ul React injectează title, description, canonical, Open Graph, Twitter card, robots și JSON-LD înainte să livreze index.html pentru rutele publice.",
      "Subdomeniile de autor folosesc wildcard DNS, dar backendul verifică username-ul înainte să livreze shell-ul React; subdomeniile fără autor existent primesc 404.",
      "Paginile de postare folosesc CreativeWork JSON-LD, profilurile folosesc ProfilePage, seriile CreativeWorkSeries, iar discuțiile DiscussionForumPosting.",
      "Rutele protejate sau operaționale precum /panou, /profil, /scrie, /mesaje, /prieteni, /cluburi, /stafeta, /moderare, /docs, autentificare și invitații primesc noindex, nofollow și X-Robots-Tag.",
      "Frontendul actualizează metadatele la navigare prin frontend/src/app/seo.js, iar paginile dinamice le rescriu după încărcarea datelor reale.",
      "Pentru lansare SEO: verifică domeniul în Google Search Console, trimite https://calimara.ro/sitemap.xml, inspectează homepage, un profil public, o postare aprobată și o serie, apoi urmărește erorile de acoperire."
    ]
  },
  {
    id: "texte",
    title: "Publicare, editor și lectură",
    summary: "Autorii publică poezie și proză scurtă, pot salva ciorne, edita texte și gestiona arhiva proprie din /panou.",
    bullets: [
      "Editorul folosește RichTextEditor pe Tiptap și limitele din constants.js: titlu 120 caractere, poezie 10.000, proză scurtă 50.000.",
      "Lipirea în editor este unificată: formatările externe sunt curățate, poezia păstrează rândurile ca versuri, iar proza transformă rândurile lipite în paragrafe curate; butonul Curăță formatarea cu AI trimite textul la Mistral Small pentru refacerea paragrafelor, versurilor și strofelor.",
      "Diacriticele sunt disponibile pentru utilizatorii autentificați cu limită lunară de caractere: Gratuit 15.000, Trubadur 60.000, Cronicar 120.000, Rapsod 180.000; la erori Mistral, cererile intră temporar în cooldown și compozitoarele oferă trimitere fără Diacritice.",
      "O postare nouă pornește cu moderation_status pending, intră în coada AI post_publish, nu apare public până la aprobare și rămâne vizibilă autorului în cititor/carduri cu overlay translucid peste text.",
      "După aprobare, postarea devine vizibilă pe landing, profil public, arhivă și subdomeniul autorului.",
      "Pagina de lectură comună folosește PieceCol, post actions, progres de derulare și export PDF.",
      "Portabilitatea datelor exportă doar postările aprobate și le poate importa direct ca aprobate în contul autentificat."
    ]
  },
  {
    id: "moderare",
    title: "Moderare AI și revizie umană",
    summary: "Moderarea este asincronă. Cererile creează AIJob, workerul procesează conținutul, scrie moderation_logs și modifică statusul conținutului.",
    bullets: [
      "Tipuri procesate: post, comment, forum_thread, forum_reply, theatre_entry, audio, plus joburi de follow-up pentru critic AI.",
      "Conținutul curat este aprobat automat; conținutul ambiguu devine flagged și intră în revizie umană.",
      "Decizia umană rejected scoate conținutul din suprafețele utilizatorilor chiar dacă rândul de conținut a rămas temporar pending sau flagged.",
      "Apelurile Mistral Small trec printr-un guard comun de context: se estimează intrarea, se adaugă rezerva de output și se blochează cererile peste fereastra configurată.",
      "Eșecurile serviciilor AI trimit alerte deduplicate către SYSTEM_ALERT_EMAIL, implicit contact@calimara.ro, prin EmailOutbox.",
      "Jurnalul arată decizia AI, scoruri, motive, decizia umană și moderatorul.",
      "Rapoartele de la utilizatori sunt separate de AI: plagiat/ofensiv, review admin, respingere, ștergere sau dismiss.",
      "Workerul scripts/process_ai_jobs.py --loop trebuie să rămână pornit; joburile blocate apar în tabul Joburi."
    ]
  },
  {
    id: "comentarii-reactii",
    title: "Comentarii, aprecieri și Super-apreciez",
    summary: "Comentariile apar în firul normal cu overlay translucid cât timp sunt pending/flagged, iar reacțiile alimentează clasamentele și economia internă după aprobare.",
    bullets: [
      "Comentariile pending/flagged sunt returnate în firul postării cu overlay de moderare; cele respinse nu mai apar în firul public.",
      "Comentariile aprobate pot declanșa notificări pentru mențiuni și emailuri către autor.",
      "Comentariile aprobate au reacții separate: Util, Amuzant și Profund; un utilizator autentificat poate păstra o singură reacție activă pe comentariu, dar nu pe propriul comentariu.",
      "Aprecierile simple și Super-aprecierile sunt separate; niciuna nu poate fi oferită propriilor postări. Super-apreciez are cotă lunară: Gratuit 1, Trubadur 3, Cronicar 4, Rapsod 5, și acordă recompense.",
      "PostActionTools este suprafața comună pentru acțiuni pe landing și pe pagina postării; reacțiile deja oferite rămân apăsate și inactive.",
      "Aprecierile vizitatorilor folosesc IP-ul real din proxy headers plus sesiunea browserului, ca landing și subdomeniile autorilor să nu dubleze reacția.",
      "Contoarele publice folosesc valorile canonice din backend, inclusiv view_count și deduplicarea vizualizărilor."
    ]
  },
  {
    id: "profiluri",
    title: "Profil public și Călimara mea",
    summary: "Profilul public este hubul autorului: bio, linkuri, media, inventar echipat, promovări și acces către arhiva completă.",
    bullets: [
      "Setările profilului includ descriere cu opțiune Diacritice, de maximum 400 de caractere, avatar, copertă, locație, playlist YouTube și linkuri sociale; avatarul și coperta alese la configurare folosesc opțiuni stabile și pot fi schimbate ulterior aici.",
      "Profilul include backup JSON pentru profil și postări aprobate prin /api/portabilitate/export și /api/portabilitate/import; reimportarea propriului export sare peste textele deja existente, fără duplicate.",
      "Linkurile de donații PayPal, Patreon și Cafea sunt vizibile și editabile doar pentru tierurile premium Bronz, Argint și Aur.",
      "Profilul public separă linkurile sociale/donațiile de acțiunile de relație: urmărire, prietenie, promovarea autorului pe profilul tău și mesaj privat.",
      "Profilul public afișează buton Play cu FiPlay când autorul are audio ready; butonul pornește playerul comun în mod autor și este dezactivat pentru vizitatori neautentificați, sub Cronicar sau fără audio.",
      "Călimara mea nu afișează automat toate textele autorului; suprafața principală are trei zone promovate: opere proprii, autori promovați și opere de la alți autori.",
      "Autorul își selectează textele proprii promovate din /panou, direct de pe fiecare text aprobat; pe propria pagină Călimara mea poate căuta autori sau texte ale altor autori pentru promovare.",
      "Structura curentă de promovare folosește limitele 2 / 3 / 3 și câmpurile promoted_own_posts, promoted_authors, promoted_external_posts; autorii promovați trebuie să aibă texte publice aprobate.",
      "Profilul păstrează acces către ruta Toate operele, unde sunt afișate toate textele publice aprobate ale autorului, plus urmăritori, urmăriți și inventarul public."
    ]
  },
  {
    id: "social",
    title: "Prieteni, urmăriri și director",
    summary: "Aplicația are două relații sociale: follow pentru abonare publică și prietenie pentru legături explicite.",
    bullets: [
      "Prieteni gestionează cereri primite/trimise, prieteni confirmați și link către Toți utilizatorii.",
      "Directorul complet /utilizatori este autentificat și oferă căutare, sortare după activitate și metrici de descoperire.",
      "Follow/unfollow alimentează urmăritorii publici, funcționează independent de prietenie și notifică urmăritorii când autorul publică o postare aprobată.",
      "Autorii promovați sunt o structură de profil, separată de sistemul de prietenii."
    ]
  },
  {
    id: "mesaje-notificari",
    title: "Mesaje și notificări",
    summary: "Mesajele private sunt conversații între doi utilizatori, iar notificările țin la zi autorii, actorii și moderatorii.",
    bullets: [
      "Mesajele sunt în /mesaje și folosesc Conversation + Message, cu istoric de conversații, Mesaj nou și fire cu avataruri și bule de conversație.",
      "Un utilizator autentificat poate porni o conversație din /mesaje sau din butonul de mesaj privat de pe profilul public al altui autor; toate compozitoarele de mesaje private pot folosi Diacritice.",
      "Răspunsurile admin la feedback sau buguri se transformă la primul răspuns în conversații de suport cu Călimara, iar utilizatorul poate continua firul din /mesaje; răspunsurile noi ale utilizatorului sunt necitite până când un admin deschide firul din Sesizări și apar pe rândul sesizării cu număr și previzualizare.",
      "Mesajele primite pot fi raportate cu steagul roșu din colțul din dreapta jos; raportarea intră în aceeași coadă de moderare ca raportările de postări.",
      "Notificările apar în panoul legat de iconul profilului, afișează count necitit și pot fi marcate citit/necitit sau șterse individual; mesajele au badge separat pe iconul Mesaje.",
      "Evenimentele care notifică includ mesaje private, aprobare/respingere moderare, postări noi de la autori urmăriți, comentarii aprobate, mențiuni, teatru, cluburi și feedback operațional.",
      "Mențiunile se trimit după aprobare, nu înainte."
    ]
  },
  {
    id: "audio",
    title: "Audio, TTS și player",
    summary: "Audio-ul are două surse: generare TTS pentru texte și înregistrări de autor, cu acces condiționat de tier premium.",
    bullets: [
      "Cronicar și Rapsod au acces la player audio; Rapsod poate încărca înregistrări de autor.",
      "TTS calculează cote pe număr de caractere și pornește joburi asincrone: Gratuit 1.000, Trubadur 50.000, Cronicar 100.000, Rapsod 200.000 pe lună/ciclu.",
      "Generarea TTS pentru texte lungi împarte textul în bucăți sub limita Google și păstrează jobul în coadă dacă furnizorul returnează o eroare temporară; la eșec final se trimite alertă operațională.",
      "Înregistrările de autor sunt transcrise și comparate cu textul postării înainte de a deveni ready.",
      "Rapsod încarcă sau înlocuiește lecturile de autor din cardurile postărilor aprobate din Panou.",
      "Secundele ascultate se înregistrează atât din playerul global, cât și din playerul compact al postării, pentru audio public aprobat.",
      "Playerul global este în navbar, afișează textul curent cu linkuri către postare și autor, are controale Redă/Pauză, Anterior și Următor și include acțiuni rapide de urmărire/prietenie pentru autor.",
      "Playerul comun poate porni global, pe profil de autor prin /api/audio/autori/{username}/aleatoriu sau pe playlist prin /api/audio/playlisturi/{playlist_id}/lista-redare.",
      "Rapsod are playlisturi private în /playlisturi; tabelele audio_playlists și audio_playlist_items sunt owner-scoped, fără slug public, cu ștergere cascade și poziții păstrate în ordine de inserare.",
      "API-urile de playlist sunt /api/audio/playlisturi, /api/audio/playlisturi/{playlist_id}, /api/audio/playlisturi/{playlist_id}/postari și /api/audio/playlisturi/{playlist_id}/lista-redare; toate cer Rapsod și owner-only.",
      "PostActionTools afișează Adaugă în playlist doar pentru Rapsod când postarea aprobată are best-audio ready; postările fără audio ready nu pot fi adăugate.",
      "Acțiunile audio compacte rămân în PostActionTools."
    ]
  },
  {
    id: "premium",
    title: "Premium și plăți",
    summary: "Tierurile sunt Gratuit, Trubadur, Cronicar și Rapsod. Planurile sunt servite de backend și checkoutul merge prin Stripe/portal.",
    bullets: [
      "Premium controlează accesul la facilități precum Super-apreciez, audio și funcții de autor; cota lunară Super-apreciez este Gratuit 1, Trubadur 3, Cronicar 4, Rapsod 5, iar generarea audio este Gratuit 1.000, Trubadur 50.000, Cronicar 100.000, Rapsod 200.000.",
      "Cronicar și Rapsod pot asculta profiluri cu audio ready; playlisturile private și încărcările de lecturi de autor sunt exclusive Rapsod.",
      "Cotele pentru Diacritice sunt contorizate pe caractere după normalizarea textului; utilizatorii Premium folosesc ciclul de facturare, iar utilizatorii gratuiți folosesc luna ancorată de data creării contului.",
      "Adminul poate ajusta manual tierul, perioada și identificatorii Stripe ai unui utilizator sau poate trimite invitații cu premium activat după configurarea contului.",
      "Evenimentele Stripe sunt deduplicate, iar abonamentele setează premium_tier, premium_period_start și premium_until.",
      "Pagina premium afișează cele patru planuri din /api/premium/planuri, inclusiv Gratuit, nu valori hardcodate în UI.",
      "Programul de recomandări are pagina /invitatii, expune /api/recomandari/eu și acordă 7 zile de Trubadur referrerului când utilizatorul recomandat ajunge la 600 Gologani câștigați.",
      "/invitatii afișează linkul de recomandare, recompensa, textele publicate de fiecare utilizator invitat, balanța curentă de Gologani și progresul până la prag."
    ]
  },
  {
    id: "economie",
    title: "Gologani, magazin și inventar",
    summary: "Gologanii recompensează contribuții aprobate și se cheltuiesc pe cosmetice de profil.",
    bullets: [
      "Recompensele vin din conținut aprobat, aprecieri și Super-aprecieri, prin GologaniTransaction.",
      "Totalul pozitiv din GologaniTransaction este pragul folosit de recomandări; cheltuielile din magazin nu scad progresul către pragul de 600.",
      "Magazinul are obiecte pe sloturi: insignă profil, costum, ramă, fundal și titlu.",
      "Inventarul utilizatorului permite echipare/dezechipare pe slot, iar profilul public serializează obiectele echipate.",
      "Adminul poate crea/dezactiva obiecte, ajusta manual balanța unui utilizator și seta câți Gologani acordă fiecare interacțiune recompensată."
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
      "Pagina /teatru afișează invitațiile proprii în așteptare, cu acțiuni directe de acceptare sau refuz.",
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
      "Threadurile și răspunsurile pending/flagged apar în firul normal cu overlay translucid până la decizia de aprobare sau respingere; după respingere nu mai apar în forum.",
      "Moderatorii pot șterge sau schimba starea discuțiilor, iar adminii pot administra conținutul din panoul central.",
      "Threadurile și răspunsurile aprobate au steag roșu de raportare în colțul din dreapta jos și trimit sesizările către tabul Raportări din panoul admin.",
      "Răspunsurile aprobate notifică participanții relevanți și actualizează activitatea threadului.",
      "Butonul Discuție nouă păstrează secțiunea activă și preselectează câmpul Secțiune în formular.",
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
      "Landing, profilele publice și toate-operele folosesc payloaduri publice cu statistici și acțiuni permise; profilele și toate-operele au cache public anonim de maximum 60s, iar footerul comun citește totalurile din /api/statistici/platforma.",
      "Exporturile refuză conținutul neaprobat pentru a evita publicarea accidentală."
    ]
  },
  {
    id: "email",
    title: "Emailuri",
    summary: "EmailOutbox este coada comună pentru coduri de autentificare, invitații, comentarii aprobate, mențiuni, digesturi, campanii admin și alerte operaționale.",
    bullets: [
      "Brevo trimite emailurile când EMAILS_ENABLED este activ, iar run.py pornește automat workerul scripts/process_email_outbox.py --loop pentru rândurile due.",
      "Preferințele utilizatorului acoperă comentarii, mențiuni, digesturi de analytics și anunțuri admin.",
      "Invitațiile admin folosesc aceeași coadă și includ parola temporară doar în conținutul emailului trimis.",
      "Campaniile admin folosesc HTML brut, filtre de audiență și aceeași coadă de trimitere.",
      "Butonul Trimite notificare test din tabul Email apelează /api/admin/email/test-notification și trimite către contact@calimara.ro aceeași structură de email de mențiune pe care ar primi-o un utilizator cu emailurile active.",
      "Alertele operaționale folosesc email_type system_alert, dedupe pe serviciu/eroare/fereastră și nu au link de dezabonare.",
      "Linkurile de dezabonare folosesc tokenuri semnate."
    ]
  },
  {
    id: "admin",
    title: "Panoul admin",
    summary: "Panoul /moderare centralizează operațiunile: overview, acces și invitații, utilizatori, conținut, sesizări, email, moderare, rapoarte, jurnal, economie, premium, stocare, joburi, audit și referințe interne.",
    bullets: [
      "Moderatorii văd coada AI, marcate, raportări și jurnal; adminii văd toate taburile operaționale.",
      "Overview agregă utilizatori, conținut, trafic, premium, joburi și metrici zilnice.",
      "Tabul Acces permite deschiderea platformei, allowlist manual și trimiterea/retrimiterea/revocarea invitațiilor.",
      "Titlurile, autorii, comentariile, raportările, țintele din joburi/audit și referințele de stocare duc direct către elementul inspectat când acesta încă există.",
      "Adminii pot răspunde la feedback sau buguri direct din Sesizări; primul răspuns creează firul privat de suport cu Călimara, nu închide automat sesizarea, iar tabul Sesizări afișează un badge roșu cu numărul răspunsurilor noi de la utilizatori. Rândurile cu răspunsuri noi sunt marcate separat și rămân vizibile în filtrul Deschise + răspunsuri noi chiar dacă sesizarea fusese închisă.",
      "Ștergerea unui utilizator din admin elimină conținutul deținut de acesta, inclusiv postări, ciorne, comentarii, reacții și contribuții în forum/cluburi/teatru/Ștafeta, apoi înregistrează rezumatul în audit.",
      "Grupul Referință include Raport QA, alimentat de /api/admin/referinta/raport-qa; intrările de raport sunt excluse din Sesizări ca să rămână separate de feedbackul utilizatorilor.",
      "Tabul Stocare listează bucketul de obiecte, marchează fișierele referențiate, permite ștergerea sigură a obiectelor Călimara nereferențiate și are Curăță pentru ștergerea obiectului împreună cu referințele cunoscute.",
      "Auditul înregistrează acțiuni administrative cu actor, țintă, motiv și metadata.",
      "Joburi arată AIJob, retry/cancel și erori pentru investigarea workerelor.",
      "Performanță este read-only, se actualizează la 10 secunde și citește /api/admin/performance/live pentru CPU/load/RAM/swap/disk, utilizatori activi în ultimele 15 minute, utilizatori activi 24h, workere, servicii nginx/Postgres, conexiuni DB, cache hit, cozi AI/email și configurare runtime.",
      "Endpointul " + "/api/admin/performance/history" + " păstrează snapshoturi ușoare în admin_performance_snapshots pentru ultimele 24h; dacă tabela lipsește într-o bază veche, endpointul live rămâne disponibil și marchează istoricul ca indisponibil."
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
      "Procese importante: calimara.service/run.py --serve, scripts/process_ai_jobs.py --loop, scripts/process_email_outbox.py --loop, Vite dev server pe 5173 când este folosit.",
      "Alertele pentru Diacritice, formatare AI, moderare AI, critic AI și audio se trimit către SYSTEM_ALERT_EMAIL sau contact@calimara.ro, cu cooldown implicit de 30 de minute pe eroare.",
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
      "Panoul admin include Raport QA și link direct către documentație în grupul Referință.",
      "Documentația curentă include moderarea theatre_entry, coada AI, schema.sql ca sursă de adevăr și fluxurile noi de teatru, email, economie, realizări, playlisturi audio și acces platformă.",
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
