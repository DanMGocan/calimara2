import { PageShell } from "../app/layout.jsx";

const ABOUT_SECTIONS = [
  {
    id: "pe-scurt",
    title: "Pe scurt",
    paragraphs: [
      "Călimara este un spațiu românesc pentru citit, publicat și lucrat texte literare. Platforma pornește de la poezie și proză scurtă, dar adaugă în jurul lor profiluri de autor, comentarii, prietenii, cluburi, teatru colaborativ, Ștafeta, audio, serii, recomandări și un sistem de recompense.",
      "Poți folosi Călimara ca cititor, ca autor sau ca membru al unei comunități de atelier. Unele pagini sunt publice, altele cer cont, iar unele funcții avansate depind de planul Premium activ."
    ],
    items: [
      "Cititorii pot descoperi texte aprobate, profiluri publice, serii, piese de teatru, cluburi și discuții.",
      "Autorii pot scrie, salva ciorne, publica, edita, organiza texte în serii și primi reacții de la comunitate.",
      "Comunitatea poate comenta, aprecia, super-aprecia, urmări autori, trimite cereri de prietenie, conversa prin mesaje și participa la spații de lucru comune.",
      "Conținutul care ajunge public trece prin moderare, iar utilizatorii pot raporta conținut ofensiv, plagiat sau probleme din platformă."
    ]
  },
  {
    id: "conturi",
    title: "Conturi, acces și autentificare",
    paragraphs: [
      "Un cont îți leagă textele, profilul public, prieteniile, mesajele, notificările, inventarul și beneficiile Premium. Autentificarea se poate face cu email și parolă, Google sau prin invitație primită de la echipă.",
      "După prima autentificare, îți configurezi numele public, descrierea și imaginea de profil. Numele ales devine identitatea ta de autor în cititor, în comentarii, în forum și pe profilul public."
    ],
    items: [
      "Platforma poate funcționa temporar pe bază de acces aprobat sau invitație, mai ales în perioade de testare sau lansare controlată.",
      "Conturile create prin invitație pot folosi parola temporară din email, apoi pot schimba parola din pagina Profil.",
      "Dacă intri printr-un link de recomandare, recomandarea este păstrată până la finalizarea contului.",
      "Sesiunea rămâne activă între domeniul principal și paginile publice de autor, ca să nu fie nevoie să te autentifici repetat."
    ]
  },
  {
    id: "citire",
    title: "Citire și descoperire",
    paragraphs: [
      "Prima pagină afișează texte aprobate din platformă într-un format de lectură curat. Poți trece la alt text, poți deschide pagina autorului, poți descărca PDF-ul unei postări aprobate și poți folosi acțiunile de lectură din subsolul cititorului.",
      "Textele publice apar în arhiva Toate operele, pe subdomeniul autorului, în serii și, când este cazul, în suprafețele de descoperire ale platformei. Pe profilul autorului apar textele și autorii promovați de acesta."
    ],
    items: [
      "Categoriile principale sunt Poezie și Proză scurtă.",
      "Profilurile publice arată descrierea autorului, linkurile sociale, distincțiile, promovările, inventarul echipat, statisticile vizibile și accesul către arhiva completă Toate operele.",
      "Pagina unei postări poate arăta contextul de serie, textul, autorul, comentariile, reacțiile, vizualizările, audio-ul disponibil și opțiunea de descărcare PDF.",
      "Paginile publice pot fi indexate de motoarele de căutare când sunt aprobate și potrivite pentru afișare publică."
    ]
  },
  {
    id: "publicare",
    title: "Scriere, ciorne și publicare",
    paragraphs: [
      "Pagina Scrie este locul în care autorii creează texte noi sau editează postări existente. Editorul este gândit pentru literatură, cu suport pentru poezie, proză scurtă, formatare de bază și pauze de rând potrivite pentru versuri.",
      "Poți publica direct sau poți păstra ciorne. Ciornele rămân private, apar în Panou și pot fi reluate mai târziu."
    ],
    items: [
      "Titlul poate avea până la 120 de caractere.",
      "Poezia poate avea până la 10.000 de caractere, iar proza scurtă până la 50.000 de caractere.",
      "Nota explicativă este opțională și poate ajuta cititorul să înțeleagă contextul textului.",
      "După publicare, textul intră la moderare. Până la aprobare, autorul îl poate vedea, dar publicul larg nu îl vede ca text aprobat.",
      "Din Panou poți edita, șterge, deschide, urmări starea moderării și porni funcții audio pentru textele eligibile."
    ]
  },
  {
    id: "diacritice",
    title: "Diacritice",
    paragraphs: [
      "Funcția Diacritice ajută la corectarea textelor fără diacritice. Este disponibilă în zonele în care scrii: postări, comentarii, discuții, mesaje private, teatru și descrierea profilului.",
      "Când alegi această funcție, platforma îți arată textul pregătit și îți permite să verifici înainte de salvare sau publicare."
    ],
    items: [
      "Contul gratuit include o cotă lunară de caractere pentru Diacritice.",
      "Planurile Premium măresc cota lunară, astfel încât autorii activi să poată corecta texte mai lungi.",
      "Cota este afișată în Panou și pe pagina Premium.",
      "Poți salva direct fără Diacritice dacă vrei să păstrezi textul exact așa cum l-ai scris."
    ]
  },
  {
    id: "moderare",
    title: "Moderare, siguranță și raportări",
    paragraphs: [
      "Călimara folosește moderare automată și revizie umană pentru a păstra un spațiu civilizat. Scopul nu este să schimbe stilul literar, ci să țină departe abuzul, spamul, conținutul ofensiv și problemele evidente de siguranță.",
      "Un text, comentariu, răspuns de forum, intrare de teatru sau fișier audio poate fi aprobat, trimis la revizie, respins sau eliminat de moderatori."
    ],
    items: [
      "Conținutul aflat în așteptare poate apărea pentru autor cu un mesaj de moderare, dar nu este tratat ca public aprobat.",
      "Conținutul respins nu mai apare în spațiile publice obișnuite.",
      "Utilizatorii autentificați pot raporta postări, forum, răspunsuri și mesaje private pentru conținut ofensiv sau plagiat.",
      "Raportările ajung la moderatori, care pot respinge, șterge, păstra sau marca drept rezolvat conținutul analizat.",
      "Butonul de sugestii din subsol trimite feedback despre platformă, separat de raportările de conținut."
    ]
  },
  {
    id: "reactii",
    title: "Comentarii, aprecieri și Super-apreciez",
    paragraphs: [
      "Fiecare postare aprobată are o zonă de acțiuni pentru reacții și dialog. Acolo vezi aprecieri, Super-aprecieri, vizualizări, comentarii, descărcarea PDF, raportarea și, când există, audio-ul textului.",
      "Comentariile sunt parte din conversația literară, dar trec prin aceeași grijă de moderare ca restul conținutului comunitar."
    ],
    items: [
      "Aprecierea simplă marchează faptul că ți-a plăcut un text.",
      "Super-apreciez este o reacție mai rară, cu limită lunară, folosită pentru textele pe care vrei să le susții mai puternic.",
      "Comentariile pot primi reacții de tip Util, Amuzant și Profund.",
      "Nu poți reacționa la propriul comentariu.",
      "Comentariile pot include mențiuni către alți utilizatori, iar mențiunile sunt trimise după aprobare.",
      "Vizualizările sunt numărate cu grijă, astfel încât aceeași lectură să nu mărească incorect statistica."
    ]
  },
  {
    id: "profiluri",
    title: "Profil public și Călimara mea",
    paragraphs: [
      "Profilul public este pagina ta de autor. Acolo cititorii găsesc textele aprobate, descrierea, imaginea, coperta, linkurile, distincțiile, promovările și inventarul echipat.",
      "Călimara mea este zona de administrare a profilului tău. De acolo îți schimbi prezentarea, imaginile, linkurile, preferințele de email, parola, participarea la Ștafeta și promovările."
    ],
    items: [
      "Poți seta descriere, locație, playlist YouTube, linkuri sociale și copertă generată.",
      "Utilizatorii Premium pot încărca fotografie de profil și copertă proprie.",
      "Linkurile de susținere, precum PayPal, Patreon și Cafea, sunt disponibile pentru planurile Premium.",
      "Poți promova pe profilul tău texte proprii, autori și texte ale altor autori.",
      "Profilul are acces către Toate operele, urmăritori, urmăriți și inventarul public.",
      "Distincțiile câștigate apar public pe profil."
    ]
  },
  {
    id: "serii",
    title: "Serii și arhiva autorului",
    paragraphs: [
      "Seriile grupează texte ale aceluiași autor într-o ordine aleasă. Sunt utile pentru proză în episoade, cicluri de poeme, proiecte tematice sau colecții în desfășurare.",
      "Panoul autorului include atât postările publicate, cât și ciornele, plus instrumentele pentru organizarea seriilor."
    ],
    items: [
      "Poți crea serii, le poți redenumi, le poți descrie și le poți șterge.",
      "Poți adăuga postări într-o serie, le poți scoate și le poți reordona.",
      "Pagina unei serii afișează textele aprobate, autorul și ordinea capitolelor.",
      "O serie poate fi descărcată ca PDF atunci când conținutul este public și aprobat.",
      "Pagina Toate operele permite răsfoirea arhivei publice a autorului și sortarea după cele mai noi texte, comentarii, aprecieri sau Super-aprecieri."
    ]
  },
  {
    id: "audio",
    title: "Audio, ascultare și playlisturi",
    paragraphs: [
      "Călimara include lectură audio pentru texte. Unele fișiere sunt generate din text, iar planul Rapsod permite autorilor să încarce propria lectură audio pentru postările aprobate.",
      "Audio-ul poate fi ascultat din playerul compact al postării, din playerul global, de pe profilul unui autor sau din playlisturile private."
    ],
    items: [
      "Generarea audio folosește o cotă de caractere afișată în Panou și pe pagina Premium.",
      "Playerul audio global oferă 20 de minute gratuite pe zi conturilor conectate; Trubadur, Cronicar și Rapsod ascultă nelimitat, iar Rapsod poate încărca înregistrări de autor.",
      "Înregistrările de autor sunt verificate înainte să devină publice.",
      "Playerul global poate reda texte aleatorii, texte ale unui autor sau texte dintr-un playlist.",
      "Playlisturile audio sunt private și disponibile pentru Rapsod.",
      "O postare poate fi adăugată într-un playlist numai dacă are audio disponibil."
    ]
  },
  {
    id: "premium",
    title: "Premium, cote și plăți",
    paragraphs: [
      "Planurile Premium extind funcțiile pentru autorii activi și pentru cititorii care vor o experiență mai bogată. Plățile sunt procesate prin Stripe, iar abonamentul poate fi gestionat din portalul de client.",
      "Planurile curente sunt Gratuit, Trubadur, Cronicar și Rapsod."
    ],
    items: [
      "Gratuit include publicare, comentarii, aprecieri, prieteni, recomandări, cote de bază pentru Diacritice, audio și o Super-apreciere pe lună.",
      "Trubadur adaugă mai multe Super-aprecieri, cotă mai mare pentru Diacritice și audio, experiență fără reclame când ești conectat și imagini premium de profil.",
      "Cronicar include funcțiile Trubadur, cote mai mari, conversie audio pentru textele proprii și emailuri de analiză.",
      "Rapsod include funcțiile Cronicar, cea mai mare cotă audio, încărcări de lecturi de autor și playlisturi audio private.",
      "Poți susține proiectul și fără abonament prin linkul de cafea, fără beneficii funcționale suplimentare."
    ]
  },
  {
    id: "recomandari",
    title: "Invitații și recomandări",
    paragraphs: [
      "Există două tipuri de invitații: invitațiile de acces trimise de echipă și linkurile de recomandare ale utilizatorilor. Prima categorie ajută la intrarea pe platformă când accesul este limitat. A doua categorie recompensează utilizatorii care aduc autori activi.",
      "Pagina Invitații arată linkul tău de recomandare și progresul autorilor invitați."
    ],
    items: [
      "Dacă un autor își creează cont prin linkul tău și ajunge la pragul de Gologani stabilit, primești zile de Trubadur.",
      "Progresul recomandării urmărește Gologanii câștigați, nu soldul rămas după cumpărături.",
      "În lista de invitați vezi textele publicate, Gologanii câștigați, progresul și recompensele acordate.",
      "Linkul poate fi copiat din pagina Premium sau din pagina Invitații."
    ]
  },
  {
    id: "comunitate",
    title: "Prieteni, urmăriri, mesaje și notificări",
    paragraphs: [
      "Călimara are mai multe feluri de relații sociale. Urmărirea este potrivită când vrei să fii la curent cu un autor, iar prietenia este o legătură explicită între două conturi.",
      "Mesajele private și notificările țin conversațiile într-un loc separat de spațiul public."
    ],
    items: [
      "Poți urmări și opri urmărirea unui autor din profilul public.",
      "Poți trimite, accepta, refuza sau anula cereri de prietenie.",
      "Directorul Utilizatori permite căutare, filtrare după relație și sortare după activitate.",
      "Mesajele private au conversații, căutare, mesaje necitite și raportare.",
      "Notificările apar în panoul contului și pot fi marcate ca citite, necitite sau șterse.",
      "Preferințele de email includ comentarii, mențiuni, analitice și anunțuri administrative."
    ]
  },
  {
    id: "forum",
    title: "Discuții",
    paragraphs: [
      "Zona Discuții este forumul platformei. Este locul pentru întrebări, conversații generale, schimburi despre poezie și proză scurtă, plus anunțuri.",
      "Poți citi discuții publice, iar pentru a deschide o discuție nouă sau a răspunde trebuie să ai cont."
    ],
    items: [
      "Secțiunile sunt Anunțuri, Discuții generale, Poezie și Proză scurtă.",
      "Discuțiile și răspunsurile pot folosi editorul bogat, mențiuni și Diacritice.",
      "Conținutul nou intră la moderare înainte să fie tratat ca public aprobat.",
      "Discuțiile și răspunsurile aprobate pot fi raportate.",
      "Moderatorii pot închide, elimina sau revizui conținutul problematic."
    ]
  },
  {
    id: "cluburi",
    title: "Cluburi literare",
    paragraphs: [
      "Cluburile sunt spații de atelier în jurul unei teme. Un club poate fi deschis, cu cerere de aderare sau doar pe invitație.",
      "Fiecare utilizator poate crea un club, iar creatorul îl administrează împreună cu rolurile permise."
    ],
    items: [
      "Clubul are nume, descriere, temă, motto, domeniu literar și mod de înscriere.",
      "Membrii pot folosi tabla clubului pentru fire de discuție și răspunsuri.",
      "Creatorul poate primi cereri, invita autori, aproba sau respinge accesul.",
      "Cluburile pot avea imagini de profil și copertă pentru creatorii eligibili.",
      "Un club poate evidenția Creația săptămânii.",
      "Activitatea de atelier poate debloca insigne ale clubului."
    ]
  },
  {
    id: "teatru",
    title: "Teatru colaborativ",
    paragraphs: [
      "Teatrul colaborativ permite scrierea unei piese împreună cu alți autori. O piesă are personaje, distribuție, scene, replici și indicații scenice.",
      "Creatorul piesei organizează distribuția și poate invita actori sau aproba cereri de participare."
    ],
    items: [
      "Poți crea o piesă, descrie personajele și lăsa roluri libere sau atribuite.",
      "Autorii pot cere un rol, propune un personaj sau accepta o invitație.",
      "Scenele se scriu pe rând, cu replici și indicații scenice.",
      "Creatorul poate gestiona rândul, încheia scene și administra personajele.",
      "Intrările de teatru sunt moderate.",
      "Piesele aprobate pot fi citite public și exportate ca PDF."
    ]
  },
  {
    id: "stafeta",
    title: "Ștafeta",
    paragraphs: [
      "Ștafeta este un mod de scriere în lanț. Un autor începe un text, apoi îl trimite mai departe către alt participant, ales direct sau automat.",
      "Participarea se poate porni sau opri din Profil, unde alegi și câte Ștafete vrei să ai active în același timp."
    ],
    items: [
      "Poți crea o Ștafetă nouă cu titlu, categorie și început de text.",
      "Poți trimite mai departe către un autor anume sau către potrivirea automată.",
      "Participanții pot accepta, refuza sau continua fragmentul primit.",
      "Creatorul poate publica sau anula Ștafeta.",
      "Textele rămân private între participanți până când sunt publicate.",
      "Planurile mai mari permit mai multe Ștafete active în paralel."
    ]
  },
  {
    id: "gologani",
    title: "Gologani, magazin și inventar",
    paragraphs: [
      "Gologanii sunt moneda internă a platformei. Ei recompensează activitatea literară și pot fi folosiți în magazin pentru obiecte cosmetice.",
      "Obiectele cumpărate pot fi echipate pe profil, iar inventarul poate fi văzut și public pe pagina autorului."
    ],
    items: [
      "Gologanii pot veni din contribuții aprobate, aprecieri și Super-aprecieri.",
      "Magazinul include obiecte pentru insignă profil, costum, ramă, fundal și titlu.",
      "Un obiect cumpărat rămâne în inventarul tău.",
      "Poți echipa sau dezechipa obiecte pe sloturile disponibile.",
      "Inventarul public arată obiectele și echipările vizibile ale autorului."
    ]
  },
  {
    id: "date",
    title: "Date, exporturi și confidențialitate",
    paragraphs: [
      "Călimara include instrumente pentru controlul datelor personale și pentru mutarea conținutului propriu. Acestea sunt disponibile din Profil.",
      "Politica de confidențialitate și Termenii rămân paginile oficiale pentru regulile juridice, dar aici găsești pe scurt funcțiile practice."
    ],
    items: [
      "Poți exporta un fișier JSON cu profilul și postările aprobate.",
      "Poți importa un fișier JSON compatibil în contul tău.",
      "Poți schimba parola dacă ai autentificare locală.",
      "Poți gestiona preferințele de email.",
      "Mesajele private, ciornele, playlisturile private și spațiile cu acces limitat nu sunt tratate ca pagini publice.",
      "Plățile sunt procesate de Stripe, iar Călimara nu stochează datele cardului."
    ]
  },
  {
    id: "statistici",
    title: "Statistici, reclame și vizibilitate",
    paragraphs: [
      "Platforma afișează statistici utile pentru cititori și autori: număr de texte, autori, vizualizări, aprecieri, comentarii, urmăritori și alte semnale de activitate.",
      "Unele statistici sunt publice, iar altele sunt disponibile doar autorului sau administratorilor."
    ],
    items: [
      "Footerul poate afișa totaluri de platformă, precum numărul de texte și autori.",
      "Postările aprobate au vizualizări, aprecieri, Super-aprecieri și comentarii.",
      "Autorii pot primi emailuri de analiză în funcție de preferințe și plan.",
      "Paginile publice gratuite pot afișa reclame.",
      "Utilizatorii Premium conectați au experiență fără reclame în interfața publică."
    ]
  },
  {
    id: "inceput",
    title: "De unde începi",
    paragraphs: [
      "Dacă ești nou pe Călimara, poți începe ca cititor, apoi îți poți face cont când vrei să comentezi, să publici sau să participi la comunitate."
    ],
    items: [
      "Pentru citit: începe de pe prima pagină, deschide profilurile autorilor și urmărește textele care îți plac.",
      "Pentru publicat: intră în cont, configurează profilul, apoi folosește Scrie pentru primul text.",
      "Pentru comunitate: caută utilizatori, urmărește autori, trimite cereri de prietenie, intră în Discuții sau caută un club.",
      "Pentru proiecte comune: încearcă Teatru colaborativ sau Ștafeta.",
      "Pentru funcții avansate: verifică pagina Premium, unde vezi planurile, cotele și beneficiile active."
    ]
  }
];

const LEGAL_UPDATED_AT = "Ultima actualizare: 27 noiembrie 2026.";
const OPERATOR_ADDRESS = "11 College Court, Portobello, Dublin, Irlanda";
const OPERATOR = `Daniel Mihai, persoană fizică, cu adresa ${OPERATOR_ADDRESS}`;

const PRIVACY_SECTIONS = [
  {
    id: "pe-scurt",
    title: "Pe scurt",
    paragraphs: [
      "Această politică explică ce date folosim pe Călimara, de ce avem nevoie de ele, când sunt publice, când rămân private și cum îți poți exercita drepturile. Este scrisă pentru utilizatori, nu pentru specialiști.",
      "Călimara este o platformă literară cu profiluri de autor, texte publice, ciorne, comentarii, mesaje, cluburi, teatru colaborativ, Ștafeta, audio, Premium, reclame, notificări și instrumente de administrare a contului."
    ],
    items: [
      `Călimara (calimara.ro) este administrată de ${OPERATOR}, care este și operatorul datelor tale.`,
      "Contactul pentru confidențialitate, conturi și întrebări juridice este contact@calimara.ro.",
      "Nu vindem datele tale personale.",
      "Nu stocăm datele cardului. Plățile Premium sunt procesate prin Stripe.",
      "Unele pagini sunt publice prin natura lor, cum ar fi profilul de autor și textele aprobate. Alte zone, cum ar fi ciornele, mesajele private și playlisturile private, nu sunt publice."
    ]
  },
  {
    id: "operator-contact",
    title: "Operator și contact",
    paragraphs: [
      `Operatorul datelor prelucrate de platformă este ${OPERATOR}. Călimara nu este o companie, ci un proiect administrat de această persoană. Folosim datele doar pentru a oferi serviciul, pentru a proteja comunitatea, pentru a gestiona abonamentele și pentru a respecta obligațiile legale aplicabile.`,
      <>Pentru orice cerere legată de datele tale, scrie la <a href="mailto:contact@calimara.ro">contact@calimara.ro</a>. Încearcă să folosești adresa de email a contului tău, ca să putem verifica mai ușor cererea.</>
    ],
    items: [
      "Poți cere informații despre datele tale.",
      "Poți cere corectarea unor date incorecte.",
      "Poți cere ștergerea contului sau a anumitor date, în limitele legii și ale obligațiilor de siguranță.",
      "Poți cere exportul datelor disponibile.",
      "Poți opri anumite emailuri din preferințele contului sau din linkurile de dezabonare, unde sunt disponibile."
    ]
  },
  {
    id: "date-cont",
    title: "Date de cont și autentificare",
    paragraphs: [
      "Pentru a crea și folosi un cont, prelucrăm datele necesare identificării contului și menținerii sesiunii. Autentificarea se poate face prin email și parolă, Google sau prin invitație, în funcție de opțiunile active pe platformă.",
      "Dacă intri prin Google, primim datele strict necesare autentificării, de regulă identificatorul furnizorului, emailul și informațiile de profil permise de Google. Setările și politicile Google se aplică separat folosirii contului tău la ei."
    ],
    items: [
      "Date de bază: email, nume public, nume de utilizator, parolă locală criptată, imagine de profil, copertă, descriere, locație și preferințe de profil.",
      "Date de conectare prin Google: identificatori ai furnizorului, email verificat și informații minime primite la autentificare.",
      "Date de sesiune: cookie-ul de sesiune, adresa IP, browserul, dispozitivul, momentul autentificării și informații tehnice folosite pentru securitate.",
      "Date de invitație sau recomandare: coduri, linkuri, progresul recomandărilor și recompensele acordate, unde funcția este disponibilă.",
      "Date de administrare: rolul contului, starea accesului, eventuale suspendări, istoricul unor acțiuni administrative și preferințele de email."
    ]
  },
  {
    id: "date-publice-private",
    title: "Ce este public și ce rămâne privat",
    paragraphs: [
      "Călimara combină pagini publice cu zone private. Înainte să publici, este important să înțelegi ce poate fi văzut de alți oameni și ce este destinat doar contului tău sau moderatorilor.",
      "Conținutul public poate fi citit de vizitatori neautentificați și poate fi indexat de motoarele de căutare atunci când pagina este aprobată și potrivită pentru afișare publică."
    ],
    items: [
      "Publice de regulă: profilul de autor, numele public, descrierea, linkurile afișate de tine, textele aprobate, seriile publice, comentariile aprobate, reacțiile agregate, distincțiile, inventarul echipat și anumite statistici.",
      "Cu acces limitat: cluburile cu cerere sau invitație, tabla clubului, firele interne, participarea la teatru înainte de publicare și unele zone de atelier.",
      "Private pentru contul tău: ciornele, playlisturile audio private, preferințele de email, parola, datele de plată păstrate doar ca identificatori, exporturile și setările personale.",
      "Private între participanți, cu posibilă vizibilitate pentru moderare: mesajele private, raportările, Ștafetele nepublicate și contribuțiile trimise spre revizie.",
      "Vizibile echipei tehnice sau moderatorilor când este necesar: conținut raportat, conținut în moderare, jurnale de siguranță, date de cont necesare suportului și istoricul unor acțiuni administrative."
    ]
  },
  {
    id: "continut-creat",
    title: "Texte, comentarii, forum, cluburi, teatru și Ștafeta",
    paragraphs: [
      "Când scrii pe Călimara, prelucrăm conținutul introdus de tine pentru salvare, publicare, moderare, afișare, export, căutare internă, notificări și funcții asociate. Conținutul poate include texte literare, note explicative, ciorne, comentarii, răspunsuri de forum, fire de club, scene de teatru, replici, indicații scenice și fragmente de Ștafetă.",
      "Conținutul aflat în așteptare poate fi analizat automat și de moderatori înainte să apară public. Scopul este protejarea comunității, nu modificarea stilului literar."
    ],
    items: [
      "Postările și seriile aprobate pot apărea pe prima pagină, pe profilul tău, în arhive, în subdomeniul de autor, în PDF-uri și în alte suprafețe de descoperire.",
      "Ciornele rămân private până când alegi să le publici.",
      "Comentariile, mențiunile și răspunsurile pot genera notificări pentru utilizatorii vizați, după aprobare.",
      "Discuțiile și cluburile pot păstra istoricul conversațiilor, rolurilor, cererilor de aderare, invitațiilor și deciziilor de administrare.",
      "Teatrul colaborativ și Ștafeta pot păstra distribuția, rolurile, ordinea contribuțiilor, starea moderării și istoricul necesar continuității proiectului.",
      "Raportările pot include motivul ales, explicații, conținutul reclamat și decizia moderatorului."
    ]
  },
  {
    id: "media-audio",
    title: "Imagini, audio și fișiere generate",
    paragraphs: [
      "Platforma poate prelucra imagini de profil, coperți, fișiere audio, fișiere generate și documente PDF asociate textelor. Unele funcții sunt disponibile doar pentru anumite planuri Premium.",
      "Audio-ul poate fi generat din text sau încărcat ca lectură de autor. Înregistrările de autor pot fi verificate înainte să devină publice."
    ],
    items: [
      "Imaginile încărcate sau generate sunt folosite pentru afișarea profilului, a cluburilor sau a paginilor publice relevante.",
      "Fișierele audio sunt folosite pentru redare în playerul postării, playerul global sau playlisturile disponibile.",
      "Playlisturile audio private sunt vizibile contului tău, nu publicului larg.",
      "PDF-urile sunt create pentru citire, descărcare sau export public al conținutului aprobat.",
      "Pentru generare audio, Diacritice și alte instrumente automate, textul introdus poate fi transmis serviciilor tehnice necesare funcționării, în limitele configurării platformei."
    ]
  },
  {
    id: "reactii-social",
    title: "Reacții, prietenii, urmăriri, mesaje și notificări",
    paragraphs: [
      "Funcțiile sociale au nevoie de date despre relațiile dintre conturi și despre interacțiunile tale cu alte persoane. Aceste date ajută la afișarea notificărilor, conversațiilor, statisticilor și recomandărilor de conținut.",
      "Mesajele private sunt destinate participanților conversației. Totuși, pot fi analizate de moderatori dacă sunt raportate sau dacă este necesar pentru siguranță, suport, prevenirea abuzului ori respectarea legii."
    ],
    items: [
      "Păstrăm aprecieri, Super-aprecieri, reacții la comentarii, vizualizări, urmăriri, prietenii și cereri de prietenie.",
      "Păstrăm conversații private, mesaje necitite, raportări ale mesajelor și metadate necesare livrării.",
      "Notificările pot include aprobări, respingeri, comentarii, mențiuni, mesaje, cereri, invitații, activitate de teatru, activitate de club, urmăriri și evenimente administrative.",
      "Preferințele de email controlează dacă primești anumite notificări prin email.",
      "Unele statistici agregate, cum ar fi aprecierile sau vizualizările unei postări, pot fi publice."
    ]
  },
  {
    id: "premium-plati",
    title: "Premium, plăți și Stripe",
    paragraphs: [
      "Planurile Premium sunt gestionate prin Stripe Checkout și Stripe Customer Portal. Stripe procesează plata și poate prelucra datele necesare tranzacției, prevenirii fraudei, facturării și conformității financiare, conform propriilor politici.",
      "Călimara nu stochează numărul cardului, codul CVV sau datele complete ale metodei de plată. Platforma păstrează doar informațiile necesare activării beneficiilor: identificatori Stripe, tierul Premium, perioada abonamentului și starea abonamentului."
    ],
    items: [
      "Date posibile: email, identificator client Stripe, identificator abonament, tier Premium, perioadă activă, starea plății și notificări tehnice de plată relevante.",
      "Beneficiile Premium sunt afișate și activate în cont pe baza stării primite de la Stripe.",
      "Portalul Stripe poate fi folosit pentru administrarea abonamentului, în funcție de opțiunile disponibile.",
      "Pentru probleme de plată, putem avea nevoie de identificatori de tranzacție sau abonament, dar nu îți vom cere date complete de card prin email."
    ]
  },
  {
    id: "reclame-cookie",
    title: "Reclame, cookie-uri și consimțământ",
    paragraphs: [
      "Folosim cookie-uri și tehnologii similare pentru autentificare, securitate, păstrarea sesiunii, preferințe și funcții tehnice ale platformei. Cookie-ul de sesiune este necesar pentru conectare și pentru păstrarea accesului între domeniul principal și paginile publice de autor.",
      "Paginile publice gratuite pot afișa reclame Google AdSense. Google și partenerii săi pot folosi cookie-uri, stocare locală, adrese IP, identificatori sau tehnologii similare pentru afișarea, măsurarea și personalizarea reclamelor, în funcție de consimțământul tău și de setările disponibile."
    ],
    items: [
      "În Spațiul Economic European, Regatul Unit și Elveția, consimțământul pentru reclame este colectat prin instrumentele Google disponibile pe pagină.",
      "Dacă refuzi personalizarea reclamelor, pot apărea în continuare reclame nepersonalizate, unde legea și configurarea permit acest lucru.",
      "Utilizatorii Premium conectați beneficiază de experiență fără reclame în interfața publică.",
      "Poți controla cookie-urile din browser, dar blocarea cookie-urilor necesare poate împiedica autentificarea sau funcțiile contului.",
      "Politicile Google se aplică separat pentru datele prelucrate de Google în cadrul produselor sale."
    ]
  },
  {
    id: "emailuri",
    title: "Emailuri, comunicări și Brevo",
    paragraphs: [
      "Călimara poate trimite emailuri pentru cont, invitații, parole temporare, notificări, mențiuni, comentarii, analize, anunțuri administrative și informații importante despre serviciu. Unele emailuri sunt necesare pentru funcționarea contului, iar altele pot fi controlate din preferințe.",
      "Trimiterea emailurilor poate fi realizată printr-un furnizor specializat, inclusiv Brevo, atunci când este configurat. Furnizorul primește datele necesare livrării: adresa de email, conținutul mesajului, momentul trimiterii și metadate de livrare."
    ],
    items: [
      "Poți dezactiva emailurile pentru comentarii și mențiuni din setările contului, unde funcția este disponibilă.",
      "Emailurile administrative importante pot fi trimise chiar dacă ai oprit emailurile opționale.",
      "Linkurile de dezabonare sau codurile de preferințe sunt folosite pentru a aplica opțiunile tale.",
      "Păstrăm un istoric tehnic al emailurilor trimise sau programate, pentru livrare, depanare și prevenirea abuzului."
    ]
  },
  {
    id: "moderare-siguranta",
    title: "Moderare, siguranță și protecția comunității",
    paragraphs: [
      "Pentru siguranța platformei, folosim moderare automată, revizie umană, raportări și jurnale administrative. Aceste mecanisme ajută la prevenirea spamului, hărțuirii, conținutului ilegal, plagiatului, abuzului și accesului neautorizat.",
      "Moderarea poate analiza conținutul publicat, comentariile, forumul, cluburile, teatrul, mesajele raportate, fișierele audio, imaginile și alte materiale trimise pe platformă."
    ],
    items: [
      "Putem păstra raportări, motive, decizii, note administrative și istoricul moderării.",
      "Putem limita, ascunde, respinge sau elimina conținut pentru siguranță, conform termenilor platformei.",
      "Putem suspenda sau restricționa conturi care pun în pericol platforma sau încalcă regulile.",
      "Jurnalele tehnice pot include adrese IP, informații despre browser, erori, evenimente de autentificare și acțiuni sensibile.",
      "Unele date pot fi păstrate mai mult dacă sunt necesare pentru investigarea abuzurilor, apărarea unor drepturi, prevenirea fraudei sau respectarea legii."
    ]
  },
  {
    id: "temeiuri",
    title: "De ce avem voie să prelucrăm datele",
    paragraphs: [
      "În funcție de situație, prelucrăm datele pe baza contractului cu tine, a consimțământului, a interesului legitim, a obligațiilor legale sau pentru protejarea drepturilor și siguranței platformei.",
      "Nu toate datele au același temei. De exemplu, sesiunea de autentificare este necesară pentru furnizarea contului, reclamele personalizate depind de consimțământ unde legea o cere, iar moderarea se bazează pe siguranța comunității și interesul legitim de a proteja serviciul."
    ],
    items: [
      "Contract: cont, autentificare, publicare, comentarii, mesaje, Premium, exporturi și funcții cerute de tine.",
      "Consimțământ: anumite reclame, comunicări opționale și setări pe care le activezi voluntar.",
      "Interes legitim: securitate, prevenirea abuzului, moderare, îmbunătățirea serviciului, statistici agregate și suport.",
      "Obligație legală: date fiscale sau de plată unde se aplică, răspunsuri la cereri legale și păstrarea unor evidențe necesare.",
      "Apărarea drepturilor: investigarea incidentelor, soluționarea disputelor, aplicarea termenilor și protejarea autorilor sau cititorilor."
    ]
  },
  {
    id: "destinatari-transferuri",
    title: "Furnizori și transferuri",
    paragraphs: [
      "Pentru ca platforma să funcționeze, folosim furnizori tehnici. Fiecare primește doar datele necesare serviciului pe care îl oferă și le prelucrează în numele nostru. Unii furnizori se află în afara Spațiului Economic European, de regulă în Statele Unite.",
      "Când datele ajung în afara Spațiului Economic European, transferul se face pe baza Cadrului UE-SUA privind protecția datelor, a clauzelor contractuale standard aprobate de Comisia Europeană sau a altor garanții permise de lege."
    ],
    items: [
      "Găzduire și copii de siguranță: Contabo (Germania), unde rulează serverul și unde păstrăm copiile de siguranță ale bazei de date și ale fișierelor, cel mult 30 de zile.",
      "Livrare și protecție a site-ului: Cloudflare, prin care trece traficul către calimara.ro (adrese IP și date tehnice ale cererilor).",
      "Plăți: Stripe (Irlanda), pentru plăți, abonamente și portalul de client.",
      "Emailuri: Brevo (Franța), pentru trimiterea emailurilor de cont și a notificărilor.",
      "Autentificare: Google, dacă alegi să intri cu contul Google.",
      "Procesare automată a textului: servicii externe care primesc textul trimis spre moderare, corectarea diacriticelor, formatare sau comentarii de atelier, doar pentru a returna rezultatul.",
      "Sinteză vocală și transcriere: Google Cloud, pentru generarea audio din text și verificarea lecturilor de autor.",
      <>Lista exactă a furnizorilor de procesare automată a textului este disponibilă la cerere, la <a href="mailto:contact@calimara.ro">contact@calimara.ro</a>.</>,
      "Autoritățile publice pot primi date doar când există o obligație legală sau o solicitare validă."
    ]
  },
  {
    id: "retentie",
    title: "Cât timp păstrăm datele",
    paragraphs: [
      "Păstrăm datele cât timp ai cont, cât timp conținutul este public sau cât timp sunt necesare pentru funcționarea platformei, siguranță, obligații legale, soluționarea disputelor sau apărarea drepturilor.",
      "Când ștergi conținut sau când contul este închis, încercăm să eliminăm datele care nu mai sunt necesare. Totuși, anumite date pot rămâne temporar în copii de siguranță, jurnale, evidențe de plată, raportări sau arhive administrative."
    ],
    items: [
      "Textele publice rămân disponibile până când sunt șterse, retrase, respinse sau contul este gestionat conform cererii tale.",
      "Ciornele rămân în cont până când le ștergi sau până la închiderea contului, în limitele sistemelor de backup.",
      "Mesajele private pot rămâne pentru participanții conversației, chiar dacă unul dintre conturi își schimbă starea, cu excepția cererilor aplicabile de ștergere.",
      "Datele de plată, facturare și abonament pot fi păstrate conform obligațiilor fiscale, antifraudă sau contractuale.",
      "Raportările, deciziile de moderare și jurnalele de securitate pot fi păstrate cât timp este necesar pentru protecția comunității și apărarea drepturilor."
    ]
  },
  {
    id: "drepturi",
    title: "Drepturile tale",
    paragraphs: [
      "Dacă locuiești în Uniunea Europeană, inclusiv în România, ai drepturi legate de datele tale personale. Unele drepturi se aplică în orice situație, iar altele depind de temeiul prelucrării și de context.",
      <>Pentru exercitarea drepturilor, scrie la <a href="mailto:contact@calimara.ro">contact@calimara.ro</a>. Putem cere informații suplimentare pentru confirmarea identității, mai ales când cererea privește accesul, exportul sau ștergerea contului.</>
    ],
    items: [
      "Dreptul de acces: poți întreba ce date avem despre tine.",
      "Dreptul la rectificare: poți cere corectarea datelor greșite sau incomplete.",
      "Dreptul la ștergere: poți cere ștergerea datelor, cu excepțiile permise de lege.",
      "Dreptul la restricționare: poți cere limitarea prelucrării în anumite situații.",
      "Dreptul la portabilitate: poți cere datele într-un format utilizabil, unde se aplică.",
      "Dreptul la opoziție: te poți opune anumitor prelucrări bazate pe interes legitim sau marketing direct.",
      "Dreptul de a retrage consimțământul: poți retrage consimțământul pentru prelucrările bazate pe consimțământ, fără a afecta ce s-a întâmplat înainte de retragere.",
      "Dreptul de a depune plângere: poți contacta Data Protection Commission din Irlanda (dataprotection.ie), autoritatea competentă pentru operator, sau autoritatea din țara în care locuiești, de exemplu ANSPDCP în România."
    ]
  },
  {
    id: "export-stergere",
    title: "Export, import și ștergere",
    paragraphs: [
      "Călimara include instrumente de portabilitate pentru profil și conținut. Poți exporta datele disponibile într-un fișier JSON și poți importa un fișier compatibil, unde funcția este activă.",
      "Pentru ștergerea contului sau pentru cereri care nu sunt acoperite de interfață, contactează-ne. Vom analiza cererea în funcție de datele implicate, de drepturile altor persoane, de conținutul publicat, de raportări și de obligațiile legale."
    ],
    items: [
      "Exportul poate include profilul și postările eligibile.",
      "Exportul nu garantează includerea tuturor datelor tehnice, jurnalelor, raportărilor, mesajelor altor persoane sau datelor care afectează drepturile altora.",
      "Importul nu transferă automat statutul Premium, plățile, moderarea, prieteniile, mesajele, statisticile sau raportările.",
      "Ștergerea unui cont poate afecta afișarea profilului, postărilor, comentariilor și relațiilor sociale asociate.",
      "Conținutul public citat, distribuit sau salvat de alte persoane poate rămâne în afara controlului direct al platformei."
    ]
  },
  {
    id: "minori-securitate",
    title: "Minori și securitate",
    paragraphs: [
      "Călimara este o platformă pentru public larg, dar conținutul literar și interacțiunile comunitare presupun responsabilitate. Dacă ești minor, folosește platforma cu acordul și supravegherea părintelui sau tutorelui, în măsura cerută de lege.",
      "Luăm măsuri rezonabile pentru protejarea datelor, cum ar fi parole criptate, sesiuni securizate, limitarea accesului administrativ, jurnale de securitate și verificări de moderare. Niciun serviciu online nu poate garanta securitate absolută."
    ],
    items: [
      "Nu trimite în texte, comentarii sau mesaje date personale sensibile care nu trebuie publicate.",
      "Nu trimite parole, date complete de card sau documente personale prin mesaje sau email.",
      "Dacă observi acces neautorizat, conținut abuziv sau o problemă de securitate, contactează-ne cât mai repede.",
      "Putem restricționa temporar conturi sau funcții dacă există risc pentru siguranța platformei."
    ]
  },
  {
    id: "modificari",
    title: "Modificări ale politicii",
    paragraphs: [
      "Putem actualiza această politică atunci când schimbăm funcții, furnizori, reguli sau obligații legale. Data ultimei actualizări apare la începutul paginii.",
      "Dacă modificările sunt importante, putem afișa un anunț în platformă sau putem trimite o notificare, în funcție de natura schimbării."
    ],
    items: [
      "Versiunea aplicabilă este cea publicată pe această pagină.",
      "Continuarea folosirii platformei după publicarea modificărilor înseamnă că ai luat la cunoștință noua versiune.",
      <>Pentru întrebări, scrie la <a href="mailto:contact@calimara.ro">contact@calimara.ro</a>.</>
    ]
  }
];

const TERMS_SECTIONS = [
  {
    id: "acceptare",
    title: "Acceptarea termenilor",
    paragraphs: [
      "Acești termeni explică regulile de folosire a platformei Călimara. Prin accesarea platformei, crearea unui cont, publicarea de conținut, folosirea funcțiilor comunitare sau achiziționarea unui abonament Premium, accepți acești termeni.",
      "Dacă nu ești de acord cu termenii, nu folosi platforma. Dacă ai întrebări înainte să creezi cont sau să cumperi Premium, ne poți contacta."
    ],
    items: [
      "Călimara este o platformă literară pentru citire, publicare, ateliere, comunitate și funcții asociate autorilor.",
      `Platforma este administrată de ${OPERATOR}. În acești termeni, „noi” înseamnă această persoană.`,
      "Unele funcții sunt publice, unele cer autentificare, iar unele sunt disponibile doar pentru anumite planuri Premium.",
      "Politica de confidențialitate explică separat ce date prelucrăm și de ce.",
      <>Contactul pentru întrebări despre termeni este <a href="mailto:contact@calimara.ro">contact@calimara.ro</a>.</>
    ]
  },
  {
    id: "conturi-acces",
    title: "Conturi, acces și responsabilitate",
    paragraphs: [
      "Ești responsabil pentru contul tău, pentru parola aleasă și pentru activitatea desfășurată din cont. Nu folosi contul altcuiva și nu oferi acces la contul tău unei persoane care nu are dreptul să îl folosească.",
      "Platforma poate funcționa cu acces deschis, acces prin invitație sau acces aprobat, în funcție de perioada de dezvoltare și de regulile active."
    ],
    items: [
      "Datele introduse la cont trebuie să fie rezonabil de corecte și să nu inducă în eroare.",
      "Numele public, imaginea, descrierea și linkurile tale nu trebuie să imite fraudulos altă persoană sau organizație.",
      "Dacă ești minor, folosește platforma cu acordul părintelui sau tutorelui, când legea cere acest lucru.",
      "Putem refuza, limita sau retrage accesul dacă un cont încalcă termenii, legea sau siguranța comunității.",
      "Dacă observi acces neautorizat la cont, anunță-ne cât mai repede."
    ]
  },
  {
    id: "continut-drepturi",
    title: "Conținutul tău și drepturile de autor",
    paragraphs: [
      "Tu rămâi titularul drepturilor asupra textelor, comentariilor, imaginilor, înregistrărilor și materialelor pe care le creezi, în măsura în care acestea îți aparțin. Publicarea pe Călimara nu transferă dreptul de autor către platformă.",
      "Pentru ca platforma să poată funcționa, ne acorzi o licență neexclusivă, gratuită, valabilă cât timp conținutul este păstrat pe platformă, pentru a găzdui, salva, afișa, modera, promova în interiorul platformei, indexa, converti tehnic, genera previzualizări, reda audio, crea PDF-uri și pune la dispoziție conținutul conform setărilor tale."
    ],
    items: [
      "Publică doar conținut creat de tine sau conținut pentru care ai drepturile necesare.",
      "Nu publica texte plagiate, copiate fără drept, atribuite fals sau încărcate fără acordul autorului.",
      "Dacă folosești citate, referințe sau materiale inspirate din alte opere, ești responsabil să respecți legea și bunele practici.",
      "Dacă ștergi conținutul, licența pentru afișarea lui se oprește pentru viitor, cu excepția copiilor tehnice, arhivelor, disputelor, raportărilor sau obligațiilor legale.",
      "Poți cere analizarea unei posibile încălcări a drepturilor prin contact sau raportare, unde funcția este disponibilă."
    ]
  },
  {
    id: "public-privat",
    title: "Suprafețe publice și private",
    paragraphs: [
      "Călimara are pagini publice și zone private. Trebuie să tratezi ca public orice conținut pe care îl publici pe profil, într-o postare aprobată, într-un comentariu aprobat, într-o serie publică, într-o discuție publică sau într-o piesă publicată.",
      "Ciornele, mesajele private, playlisturile private și proiectele aflate înainte de publicare nu sunt destinate publicului larg, dar pot fi prelucrate pentru funcționare, moderare, suport și siguranță."
    ],
    items: [
      "Textele aprobate pot apărea pe prima pagină, profil, subdomenii de autor, arhive, pagini de serie, PDF-uri și rezultate de căutare.",
      "Comentariile și răspunsurile aprobate pot fi vizibile public și asociate numelui tău public.",
      "Cluburile pot avea reguli de acces: deschise, cu cerere sau pe invitație.",
      "Ștafeta și teatrul colaborativ pot rămâne private sau cu acces limitat până la publicare.",
      "Mesajele private pot fi analizate de moderatori dacă sunt raportate sau dacă există motive serioase de siguranță."
    ]
  },
  {
    id: "reguli-conduita",
    title: "Reguli de conduită",
    paragraphs: [
      "Călimara trebuie folosită ca spațiu literar și comunitar civilizat. Critica literară este permisă, inclusiv critica fermă, dar abuzul personal, hărțuirea și conținutul ilegal nu sunt permise.",
      "Regulile se aplică postărilor, comentariilor, forumului, mesajelor, cluburilor, teatrului, Ștafetei, profilurilor, imaginilor, audio-ului, linkurilor și oricărei alte funcții a platformei."
    ],
    items: [
      "Nu hărțui, amenința, umili, doxxa sau intimida alte persoane.",
      "Nu publica spam, reclame abuzive, linkuri periculoase, escrocherii sau conținut creat pentru manipularea platformei.",
      "Nu publica materiale ilegale, instigări la violență, exploatare, conținut sexual abuziv, date personale ale altora sau conținut care pune persoane în pericol.",
      "Nu folosi platforma pentru impersonare, phishing, colectare neautorizată de date, automatizări abuzive sau acces neautorizat.",
      "Nu abuza de raportări, reacții, recomandări, Gologani, invitații, promovări sau alte mecanisme ale platformei.",
      "Nu încerca să eviți suspendări, limite tehnice sau reguli Premium prin conturi multiple sau metode artificiale."
    ]
  },
  {
    id: "moderare",
    title: "Moderare, raportări și măsuri",
    paragraphs: [
      "Putem folosi moderare automată și revizie umană pentru conținutul publicat sau raportat. Moderarea poate duce la aprobare, respingere, trimitere la revizie, ascundere, ștergere, suspendare, limitarea funcțiilor sau alte măsuri proporționale.",
      "Scopul moderării este protejarea comunității, respectarea legii și menținerea unui spațiu potrivit pentru literatură. Nu garantăm că orice conținut problematic va fi identificat imediat."
    ],
    items: [
      "Conținutul nou poate sta în așteptare înainte să apară public.",
      "Conținutul respins sau eliminat nu mai este tratat ca public aprobat.",
      "Moderatorii pot analiza postări, comentarii, forum, cluburi, teatru, audio, imagini, mesaje raportate și conturi.",
      "Utilizatorii pot raporta conținut ofensiv, plagiat, abuz sau probleme de siguranță, unde raportarea este disponibilă.",
      "Putem păstra istoricul raportărilor și deciziilor pentru siguranță, audit și prevenirea abuzului.",
      "Dacă o decizie ți se pare greșită, poți contacta platforma cu detalii clare."
    ]
  },
  {
    id: "functionalitati-literare",
    title: "Funcții literare și de lucru",
    paragraphs: [
      "Funcțiile de scriere și lucru sunt oferite pentru a ajuta autorii să creeze, organizeze și publice texte. Rezultatele depind de conținutul introdus, de limitele tehnice, de planul activ și de moderare.",
      "Unele instrumente folosesc procesare automată. Verifică întotdeauna rezultatul înainte să publici sau să salvezi definitiv."
    ],
    items: [
      "Editorul de texte permite poezie, proză scurtă, formatare de bază, note explicative, ciorne și publicare.",
      "Diacritice ajută la corectarea textelor fără diacritice, dar nu garantează perfecțiunea rezultatului.",
      "Seriile grupează texte într-o ordine aleasă de autor.",
      "PDF-urile sunt generate pentru citirea sau descărcarea conținutului eligibil.",
      "Audio-ul poate fi generat din text sau încărcat de autor, în funcție de plan și eligibilitate.",
      "Playlisturile audio private sunt disponibile conform planului activ și depind de existența audio-ului pentru postările alese.",
      "Statisticile de vizualizări, aprecieri și comentarii sunt orientative și pot fi ajustate pentru a preveni abuzul."
    ]
  },
  {
    id: "comunitate",
    title: "Comunitate, mesaje, cluburi, teatru și Ștafeta",
    paragraphs: [
      "Funcțiile comunitare sunt oferite pentru dialog literar, colaborare și descoperirea autorilor. Folosește-le cu respect față de ceilalți și față de spațiile în care intri.",
      "Când participi la proiecte comune, accepti că mai multe persoane pot contribui la aceeași lucrare sau conversație și că regulile proiectului pot influența publicarea finală."
    ],
    items: [
      "Poți urmări autori, trimite cereri de prietenie, primi notificări și conversa prin mesaje private.",
      "Forumurile și comentariile sunt pentru discuții publice sau semi-publice, în funcție de context.",
      "Cluburile pot avea creatori, membri, invitații, cereri de aderare, roluri și reguli de acces.",
      "Teatrul colaborativ poate include personaje, distribuție, invitații, cereri de rol, scene, replici și export PDF.",
      "Ștafeta permite scrierea în lanț și poate rămâne privată până când creatorul sau regulile fluxului permit publicarea.",
      "În proiectele comune, nu publica contribuțiile altora în afara platformei fără acordul necesar."
    ]
  },
  {
    id: "reactii-economie",
    title: "Reacții, Gologani, inventar și promovări",
    paragraphs: [
      "Călimara include mecanisme de reacție și recompensare, cum ar fi aprecieri, Super-apreciez, Gologani, inventar, obiecte cosmetice, distincții și promovări pe profil. Acestea sunt funcții interne ale platformei.",
      "Gologanii, obiectele, distincțiile și beneficiile similare nu sunt bani, nu reprezintă monedă electronică și nu pot fi convertite automat în bani reali."
    ],
    items: [
      "Putem schimba regulile de acordare, limitele, costurile sau disponibilitatea obiectelor, cu efect pentru viitor.",
      "Putem corecta solduri, reacții, recompense sau statistici dacă apar erori, fraudă sau abuz.",
      "Super-apreciez poate avea limite lunare sau reguli diferite în funcție de plan.",
      "Inventarul public poate afișa obiectele echipate pe profil.",
      "Promovările de autori sau texte trebuie folosite fără spam, manipulare sau conținut înșelător.",
      "Linkurile de susținere externă, cum ar fi PayPal, Patreon sau Cafea, sunt responsabilitatea autorului care le afișează și a serviciilor externe respective."
    ]
  },
  {
    id: "premium",
    title: "Premium, plăți și anulare",
    paragraphs: [
      `Planurile Premium sunt vândute de ${OPERATOR}. Beneficiile, prețurile și limitele active sunt cele afișate în pagina Premium și în fluxul de plată la momentul achiziției. Prețul afișat la plată este prețul final.`,
      "Plățile sunt procesate prin Stripe. Călimara nu stochează datele complete ale cardului. Abonamentul poate fi gestionat prin Stripe Customer Portal, când portalul este disponibil pentru contul tău."
    ],
    items: [
      "Abonamentele se plătesc lunar și se reînnoiesc automat până când le anulezi. Le poți anula oricând din portalul de client, iar anularea oprește plățile viitoare.",
      "Premium începe imediat după plată. Când accepți termenii la plată, ceri ca serviciul să înceapă imediat, în perioada de retragere.",
      "Rambursare în 14 zile: poți cere rambursarea integrală a primei plăți a unui abonament, sau a unei plăți de tip cafea, în 14 zile de la plată, fără să explici motivul. Scrie la contact@calimara.ro de pe adresa contului tău.",
      "Rambursarea se face prin Stripe, pe aceeași metodă de plată, în cel mult 14 zile de la cerere. După rambursare, beneficiile Premium plătite cu acea plată se opresc.",
      "Plățile de reînnoire lunară nu se rambursează automat, dar poți anula oricând ca să nu mai fie taxată luna următoare. Dacă o plată a fost făcută din greșeală, scrie-ne și analizăm cererea.",
      "Beneficiile Premium sunt active cât timp abonamentul este valid conform stării primite de la Stripe.",
      "Dacă anulezi abonamentul, beneficiile pot rămâne active până la finalul perioadei deja plătite, în funcție de regulile Stripe și de plan.",
      "Dacă plata eșuează, beneficiile Premium pot fi suspendate, reduse sau retrase.",
      "Planurile, cotele, prețurile și beneficiile se pot modifica pentru viitor. Modificările importante vor fi afișate în platformă sau în fluxul de plată.",
      "Drepturile legale ale consumatorilor rămân aplicabile. Pentru întrebări despre o plată, scrie cu detalii clare și, dacă există, identificatorul abonamentului.",
      "Donațiile sau susținerile externe, cum ar fi linkul de cafea, nu oferă automat beneficii funcționale Premium, dacă pagina nu spune explicit altceva."
    ]
  },
  {
    id: "reclame-linkuri",
    title: "Reclame și linkuri externe",
    paragraphs: [
      "Paginile publice gratuite pot afișa reclame Google AdSense. Reclamele sunt furnizate de terți și nu reprezintă recomandări editoriale ale Călimara.",
      "Platforma poate include linkuri către site-uri externe: profiluri sociale, linkuri de susținere, YouTube, PayPal, Patreon, Cafea, Stripe, Google, Facebook sau alte servicii. Aceste site-uri au propriile reguli și politici."
    ],
    items: [
      "Nu controlăm conținutul, prețurile, disponibilitatea sau politicile serviciilor externe.",
      "Verifică singur informațiile înainte să plătești, să donezi sau să introduci date pe un site extern.",
      "Conturile Premium conectate nu văd reclame în interfața publică, conform configurării active.",
      "Nu folosi linkurile externe pentru fraudă, spam, conținut periculos sau ocolirea regulilor platformei."
    ]
  },
  {
    id: "disponibilitate",
    title: "Disponibilitate, schimbări și limite",
    paragraphs: [
      "Încercăm să menținem platforma disponibilă și stabilă, dar nu garantăm funcționare fără întreruperi, erori sau pierderi temporare de acces. Pot apărea mentenanță, incidente tehnice, schimbări de furnizori sau limitări operaționale.",
      "Putem schimba, adăuga, limita sau retrage funcții pentru a îmbunătăți serviciul, pentru siguranță, pentru conformitate legală sau pentru a gestiona costurile."
    ],
    items: [
      "Recomandăm să păstrezi copii proprii ale textelor importante.",
      "Exportul de date este un instrument util, dar nu înlocuiește arhiva personală a autorului.",
      "Funcțiile experimentale sau noi pot fi ajustate, întrerupte sau limitate.",
      "Cotele pentru Diacritice, audio, Super-apreciez, Ștafeta sau alte funcții pot fi modificate pentru viitor.",
      "Nu garantăm rezultate literare, vizibilitate, audiență, venituri, reacții, comentarii sau promovare pentru conținutul publicat."
    ]
  },
  {
    id: "raspundere",
    title: "Răspundere",
    paragraphs: [
      "Folosirea platformei se face pe propria răspundere, în limitele legii. Călimara oferă infrastructura de publicare și comunitate, dar utilizatorii sunt responsabili pentru conținutul pe care îl publică și pentru modul în care interacționează.",
      "Nu putem verifica preventiv toate afirmațiile, drepturile de autor, identitățile, linkurile externe sau conținutul generat de utilizatori."
    ],
    items: [
      "Nu suntem responsabili pentru pierderi cauzate de folosirea greșită a contului, publicarea unor date sensibile sau nerespectarea termenilor.",
      "Nu suntem responsabili pentru serviciile externe, inclusiv procesatori de plăți, rețele sociale, reclame sau linkuri de susținere.",
      "Nimic din acești termeni nu limitează drepturile care nu pot fi limitate prin lege.",
      "Dacă o problemă este cauzată de o eroare a platformei, vom încerca să o remediem rezonabil și proporțional cu impactul."
    ]
  },
  {
    id: "incetare",
    title: "Suspendare, închidere și încetare",
    paragraphs: [
      "Poți înceta folosirea platformei oricând. Pentru cereri privind contul sau datele tale, contactează-ne sau folosește instrumentele disponibile în profil.",
      "Putem suspenda, limita sau închide conturi care încalcă termenii, legea, drepturile altora sau siguranța comunității. Măsurile pot fi temporare sau permanente, în funcție de gravitate."
    ],
    items: [
      "Închiderea contului poate afecta accesul la postări, mesaje, Premium, Gologani, inventar, distincții, cluburi și proiecte colaborative.",
      "Unele date pot fi păstrate după închidere pentru obligații legale, raportări, securitate, prevenirea abuzului sau apărarea drepturilor.",
      "Conținutul creat împreună cu alții poate necesita tratament separat, ca să nu afecteze disproporționat drepturile celorlalți participanți.",
      "Dacă ai un abonament activ, anularea contului nu înlocuiește automat anularea abonamentului în Stripe, dacă portalul de plată cere o acțiune separată."
    ]
  },
  {
    id: "lege-contact",
    title: "Legea aplicabilă și contact",
    paragraphs: [
      "Acești termeni sunt guvernați de legea din Irlanda. Dacă ești consumator în altă țară din Uniunea Europeană, păstrezi protecția oferită de legile obligatorii ale țării în care locuiești și poți apela la instanțele de acolo.",
      "Înainte de orice dispută, te rugăm să ne contactezi cu detalii clare. În multe situații, problemele de cont, plată, moderare sau conținut pot fi rezolvate mai rapid prin dialog."
    ],
    items: [
      <>Pentru întrebări despre termeni, scrie la <a href="mailto:contact@calimara.ro">contact@calimara.ro</a>.</>,
      `Adresa poștală: ${OPERATOR_ADDRESS}.`,
      "Pentru cereri de confidențialitate, folosește aceeași adresă și menționează contul vizat.",
      "Putem actualiza termenii atunci când schimbăm funcții, furnizori, reguli sau obligații legale.",
      "Data ultimei actualizări apare la începutul paginii."
    ]
  }
];

function SectionToc({ sections, label }) {
  return (
    <aside className="about-toc">
      <div className="side-kicker">cuprins</div>
      <nav className="about-toc-links" aria-label={label}>
        {sections.map((section, index) => (
          <a href={`#${section.id}`} key={section.id}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            {section.title}
          </a>
        ))}
      </nav>
    </aside>
  );
}

function AboutToc() {
  return <SectionToc sections={ABOUT_SECTIONS} label="Cuprins Ce este calimara.ro" />;
}

function LegalToc({ sections, label }) {
  return <SectionToc sections={sections} label={label} />;
}

function LegalSection({ section }) {
  return (
    <section className="legal-section" id={section.id}>
      <h2>{section.title}</h2>
      {section.paragraphs.map((paragraph, index) => <p key={`${section.id}-p-${index}`}>{paragraph}</p>)}
      {section.items?.length ? (
        <ul className="legal-list">
          {section.items.map((item, index) => <li key={`${section.id}-item-${index}`}>{item}</li>)}
        </ul>
      ) : null}
    </section>
  );
}

function PrivacyView() {
  return (
    <PageShell
      kicker="legal"
      title="Politica de confidențialitate"
      sub={LEGAL_UPDATED_AT}
      side={<LegalToc sections={PRIVACY_SECTIONS} label="Cuprins Politica de confidențialitate" />}
      className="about-page"
    >
      <div className="legal-copy">
        {PRIVACY_SECTIONS.map((section) => <LegalSection key={section.id} section={section} />)}
      </div>
    </PageShell>
  );
}
function TermsView() {
  return (
    <PageShell
      kicker="legal"
      title="Termeni și condiții"
      sub={LEGAL_UPDATED_AT}
      side={<LegalToc sections={TERMS_SECTIONS} label="Cuprins Termeni și condiții" />}
      className="about-page"
    >
      <div className="legal-copy">
        {TERMS_SECTIONS.map((section) => <LegalSection key={section.id} section={section} />)}
      </div>
    </PageShell>
  );
}

function AboutView() {
  return (
    <PageShell
      kicker="călimara.ro"
      title="Ce este calimara.ro?"
      sub="Ghid public pentru cititori, autori și comunitate: ce poți face pe platformă, unde găsești funcțiile și ce se întâmplă cu textele tale."
      side={<AboutToc />}
      className="about-page"
    >
      <div className="legal-copy">
        {ABOUT_SECTIONS.map((section) => <LegalSection key={section.id} section={section} />)}
      </div>
    </PageShell>
  );
}

export default function LegalRoute({ route }) {
  if (route.name === "about") return <AboutView />;
  if (route.name === "terms") return <TermsView />;
  return <PrivacyView />;
}
