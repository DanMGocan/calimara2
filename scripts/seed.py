#!/usr/bin/env python3
"""
Populate the database with sample Romanian content for local development.

Runs after `run.py`'s `init_database()` has produced an empty schema. Creates
three accounts, sixteen public-domain seed posts, and the saved audio links for
those posts: eight Ion Creangă prose entries on the tier-3 premium gocandan
account, eight Mihai Eminescu poetry entries on the dangocan account, and one
local admin account.

Invocation:
    python scripts/seed.py

Or called automatically at the end of `run.py`'s init step.
"""
from __future__ import annotations

import base64
import hashlib
import html
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from textwrap import dedent
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from app import models  # noqa: E402


# ──────────────────────────────────────────────────────────────────────
# Content
# ──────────────────────────────────────────────────────────────────────

def _clean_text(content: str) -> str:
    return dedent(content).strip()


def _plain_text_to_html(content: str) -> str:
    paragraphs = []
    for block in str(content or "").strip().split("\n\n"):
        lines = [html.escape(line) for line in block.splitlines()]
        paragraphs.append(f"<p>{'<br>'.join(lines)}</p>")
    return "".join(paragraphs)


def _seed_password_hash(password: str) -> str:
    # Seed-only helper: keeps deliberately short fixture passwords out of normal signup validation.
    iterations = 260_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "$".join(
        [
            "pbkdf2_sha256",
            str(iterations),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        ]
    )


def _seed_content_html(row: dict[str, str]) -> str:
    return _plain_text_to_html(row["content"])


def _seed_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)


AUTHORS = [
    {
        "username": "gocandan",
        "email": "gocandan@gmail.com",
        "google_id": "seed-google-gocandan",
        "subtitle": "Ion Creangă",
        "avatar_seed": "gocandan-premium",
        "is_admin": True,
        "is_moderator": True,
        "premium_tier": "rapsod",
        "premium_until_days": 3650,
    },
    {
        "username": "sad",
        "email": "sad@sad.com",
        "subtitle": "cont admin local",
        "avatar_seed": "sad-admin",
        "password": "123",
        "is_admin": True,
        "is_moderator": True,
    },
    {
        "username": "dangocan",
        "email": "dangocan@outlook.com",
        "google_id": "seed-google-dangocan",
        "subtitle": "Mihai Eminescu",
        "avatar_seed": "dangocan-eminescu",
    },
]


POSTS = [
    # ── gocandan: Ion Creangă ──────────────────────────────
    {
        "author": "gocandan",
        "title": "Punguța cu doi bani",
        "slug": "punguta-cu-doi-bani",
        "category": "proza_scurta",
        "days_ago": 2,
        "source_author": "Ion Creangă",
        "source_name": "Wikisource - Punguța cu doi bani",
        "source_url": "https://ro.wikisource.org/wiki/Pungu%C8%9Ba_cu_doi_bani",
        "content": _clean_text(
            """
            În ograda unei case sărace trăiau un moșneag liniștit și o babă aprigă la vorbă. Baba își lăuda găina pentru ouăle ei și îl certa pe moș pentru cocoșul care nu aducea nici un câștig. Când vorbele se înmulțiră, moșneagul își alungă pasărea, iar cocoșul porni pe drum cu gâtul sus, ca și cum sărăcia casei nu-l privea.

            Nu merse mult și găsi o punguță cu doi bani. Bucuros, o luă în cioc și se întoarse spre gospodărie. Dar un om puternic, văzând comoara, i-o smulse. Cocoșul nu se sperie. Se ținu după el, cerându-și punguța cu glas ascuțit, până când răbdarea stăpânului se prefăcu în mânie.

            Ca să scape de el, omul îl aruncă în fântână. Cocoșul bău apa și ieși. Îl aruncă în cuptor. Cocoșul vărsă apa și stinse focul. Îl aruncă în cireadă, apoi în vistierie, dar pasărea ieși de fiecare dată mai încărcată, strângând în sine vite, galbeni și tot ce-i fusese pus înainte. Încăpățânarea lui, care păruse ridicolă, se dovedi mai tare decât puterea celor mari.

            Când cocoșul ajunse acasă, ograda moșneagului se umplu de bogății. Baba, orbită de pizmă, își trimise găina să facă la fel. Găina însă nu găsi punguță, nu avu curaj și nu aduse decât rușine. Povestea rămâne o lecție veselă despre noroc, dreptate și felul în care cel mic poate să-și ceară partea fără să-și plece capul.
            """
        ),
    },
    {
        "author": "gocandan",
        "title": "Ursul păcălit de vulpe",
        "slug": "ursul-pacalit-de-vulpe",
        "category": "proza_scurta",
        "days_ago": 6,
        "source_author": "Ion Creangă",
        "source_name": "Wikisource - Ursul păcălit de vulpe",
        "source_url": "https://ro.wikisource.org/wiki/Ursul_p%C4%83c%C4%83lit_de_vulpe",
        "content": _clean_text(
            """
            Într-o iarnă cu drumuri scârțâind sub sănii, vulpea simți miros de pește și își făcu îndată planul. Se lungi în mijlocul cărării, nemișcată, cu ochii închiși și coada întinsă, prefăcându-se moartă. Țăranul care trecea cu carul încărcat o văzu și se bucură de blana ei. O aruncă peste pești, fără să bănuiască jocul.

            Vulpea așteptă până când roțile se afundară în liniștea drumului. Atunci începu să arunce peștii unul câte unul, încet și sigur, iar la urmă sări jos și își strânse prada în zăpadă. Se așeză la ospăț, mulțumită că istețimea poate umple burta mai repede decât munca.

            Pe acolo trecu ursul, flămând și mirat. Văzând atâta pește, o întrebă cum l-a prins. Vulpea îi povesti cu glas dulce că baltă are destul pește pentru cine știe să aștepte: trebuie numai să-și bage coada în copcă și să nu se miște până dimineață. Ursul, lacom și încrezător, făcu întocmai.

            Gerul își văzu de treabă, apa prinse coada ursului, iar spre zori pescarul de nevoie rămase legat de gheață. Când încercă să scape, trase cât putu și rămase fără podoaba dinapoi. Vulpea râse din ascunzătoare, iar povestea păstrează, sub haz, o judecată limpede: cine crede orice sfat doar pentru că-i promite câștig repede ajunge să plătească scump.
            """
        ),
    },
    {
        "author": "gocandan",
        "title": "Capra cu trei iezi",
        "slug": "capra-cu-trei-iezi",
        "category": "proza_scurta",
        "days_ago": 14,
        "source_author": "Ion Creangă",
        "source_name": "Wikisource - Capra cu trei iezi",
        "source_url": "https://ro.wikisource.org/wiki/Capra_cu_trei_iezi",
        "content": _clean_text(
            """
            Capra își creștea cei trei iezi cu grijă și cu frică de primejdiile pădurii. Într-o dimineață, trebuind să plece după hrană, îi strânse lângă vatră și le spuse să nu deschidă ușa decât atunci când vor auzi cântecul ei. Iezii promiseră, dar promisiunile copiilor se clatină ușor când primejdia bate cu glas schimbat.

            Lupul, ascuns aproape, prinse vorbele caprei și veni la ușă. Își îngroșă și își subție glasul, încercă vorbe dulci, apoi merse să-și netezească limba și să-și schimbe glasul până când păru cu adevărat mama întoarsă acasă. Iedul cel mare și cel mijlociu se lăsară convinși. Iedul cel mic, mai atent, simți minciuna și se ascunse.

            Când capra se întoarse, casa îi răspunse cu tăcere și cu urme grele. Din ascunzătoare, iedul cel mic îi povesti totul. Durerea caprei nu rămase fără rost; ea pregăti o masă mare și îl pofti pe lup ca și cum nimic nu s-ar fi întâmplat. Sub scaun însă îl aștepta judecata, iar focul punea capăt cruzimii.

            Povestea are asprimea basmelor vechi: dragostea mamei nu este numai mângâiere, ci și hotărâre. În lumea ei, neascultarea deschide ușa răului, iar răul nu pleacă până când nu este numit, prins și pedepsit.
            """
        ),
    },
    {
        "author": "gocandan",
        "title": "Povestea unui om leneș",
        "slug": "povestea-unui-om-lenes",
        "category": "proza_scurta",
        "days_ago": 20,
        "source_author": "Ion Creangă",
        "source_name": "Wikisource - Povestea unui om leneș",
        "source_url": "https://ro.wikisource.org/wiki/Povestea_unui_om_lene%C8%99",
        "content": _clean_text(
            """
            Într-un sat se afla un om despre care se spunea că nu se ridică nici când foamea îi bătea în coaste. Stătea pe prispă, privea la lume ca la o treabă a altora și aștepta ca mâncarea, apa și umbra să vină singure la el. La început oamenii au râs; apoi s-au supărat, căci lenea lui ajunsese povară pentru toți.

            Sătenii se sfătuiră și hotărâră să-l scoată din sat, nu din cruzime, ci din oboseala celor care nu mai puteau duce un om întreg pe spinarea lor. Îl puseră într-un car și porniră cu el pe drum. Leneșul nu întrebă unde merge, nu se împotrivi și nici nu mulțumi, ca și cum și plecarea era o treabă care nu-l privea.

            Pe drum îi întâlni o femeie miloasă. Auzind ce se întâmplă, i se făcu milă și zise că are posmagi acasă, numai să fie omul lăsat în grija ei. Toți se opriră, bucuroși că poate s-a găsit o scăpare. Atunci leneșul deschise gura și întrebă dacă posmagii sunt muiați. Când femeia spuse că nu, omul oftă că nu are rost să se mai ostenească.

            Întrebarea aceea îi lumină pe toți mai bine decât o judecată lungă. Nu sărăcia îl ținea jos, nici boala, nici nenorocul, ci refuzul de a face chiar și cel mai mic pas pentru propria viață. Hazul poveștii e scurt, dar mușcătura lui rămâne: mila nu poate înlocui voința celui care nu vrea să se miște.
            """
        ),
    },
    {
        "author": "gocandan",
        "title": "Dănilă Prepeleac",
        "slug": "danila-prepeleac",
        "category": "proza_scurta",
        "days_ago": 28,
        "source_author": "Ion Creangă",
        "source_name": "Wikisource - Dănilă Prepeleac",
        "source_url": "https://ro.wikisource.org/wiki/D%C4%83nil%C4%83_Prepeleac",
        "content": _clean_text(
            """
            Dănilă era omul care pornea cu avere și se întorcea cu pagubă, convins totuși că lucrurile s-au așezat cumva bine. Plecă la târg cu doi boi buni și, din schimb în schimb, coborî treaptă cu treaptă până ajunse aproape fără nimic. Fiecare tocmeală i se părea potrivită în clipa aceea, iar fiecare pas îl ducea mai departe de folos.

            Fratele lui, gospodar cu mintea întreagă, se crucea văzând cum s-au risipit boii. Îl mustră, îl trimise la treabă, îl puse să aducă lemne, dar Dănilă găsea mereu altă cale de a încurca lucrurile. Părea făcut să piardă și când drumul era drept.

            Numai că povestea schimbă pe nesimțite măsura omului. Ajuns lângă un iaz și intrat în vorbă cu dracii, Dănilă nu mai este doar năucul satului. În fața lor, slăbiciunile lui se prefac în viclenie. Îi pune la întreceri nepotrivite, le schimbă înțelesul probelor și îi face să creadă că puterea lui e mai mare decât este.

            Așa ajunge cel luat în râs să iasă biruitor tocmai acolo unde cei tari se credeau stăpâni. Povestea nu-l face pe Dănilă model de chibzuință, dar îi dă o dreptate de basm: uneori, mintea care rătăcește prin târg nimerește în fața răului o potecă neașteptat de bună.
            """
        ),
    },
    # ── dangocan: Mihai Eminescu ───────────────────────────
    {
        "author": "dangocan",
        "title": "Somnoroase păsărele",
        "slug": "somnoroase-pasarele",
        "category": "poezie",
        "days_ago": 1,
        "source_author": "Mihai Eminescu",
        "source_name": "Wikisource - Somnoroase păsărele",
        "source_url": "https://ro.wikisource.org/wiki/Somnoroase_p%C4%83s%C4%83rele...",
        "content": (
            "Somnoroase păsărele\n"
            "Pe la cuiburi se adună,\n"
            "Se ascund în rămurele -\n"
            "Noapte bună!\n"
            "\n"
            "Doar izvoarele suspină,\n"
            "Pe când codrul negru tace;\n"
            "Dorm și florile-n grădină -\n"
            "Dormi în pace!\n"
            "\n"
            "Trece lebăda pe ape\n"
            "Între trestii să se culce -\n"
            "Fie-ți îngerii aproape,\n"
            "Somnul dulce!\n"
            "\n"
            "Peste-a nopții feerie\n"
            "Se ridică mândra lună,\n"
            "Totu-i vis și armonie -\n"
            "Noapte bună!"
        ),
    },
    {
        "author": "dangocan",
        "title": "La steaua",
        "slug": "la-steaua",
        "category": "poezie",
        "days_ago": 4,
        "source_author": "Mihai Eminescu",
        "source_name": "Wikisource - La steaua",
        "source_url": "https://ro.wikisource.org/wiki/La_steaua",
        "content": (
            "La steaua care-a răsărit\n"
            "E-o cale-atât de lungă,\n"
            "Că mii de ani i-au trebuit\n"
            "Luminii să ne-ajungă.\n"
            "\n"
            "Poate de mult s-a stins în drum\n"
            "În depărtări albastre,\n"
            "Iar raza ei abia acum\n"
            "Luci vederii noastre.\n"
            "\n"
            "Icoana stelei ce-a murit\n"
            "Încet pe cer se suie;\n"
            "Era pe când nu s-a zărit,\n"
            "Azi o vedem, și nu e.\n"
            "\n"
            "Tot astfel când al nostru dor\n"
            "Pieri în noapte-adâncă,\n"
            "Lumina stinsului amor\n"
            "Ne urmărește încă."
        ),
    },
    {
        "author": "dangocan",
        "title": "Lacul",
        "slug": "lacul",
        "category": "poezie",
        "days_ago": 8,
        "source_author": "Mihai Eminescu",
        "source_name": "Wikisource - Lacul",
        "source_url": "https://ro.wikisource.org/wiki/Lacul_%28Eminescu%29",
        "content": (
            "Lacul codrilor albastru\n"
            "Nuferi galbeni îl încarcă;\n"
            "Tresărind în cercuri albe\n"
            "El cutremură o barcă.\n"
            "\n"
            "Și eu trec de-a lung de maluri,\n"
            "Parc-ascult și parc-aștept\n"
            "Ea din trestii să răsară\n"
            "Și să-mi cadă lin pe piept;\n"
            "\n"
            "Să sărim în luntrea mică,\n"
            "Îngânați de glas de ape,\n"
            "Și să scap din mână cârma,\n"
            "Și lopețile să-mi scape;\n"
            "\n"
            "Să plutim cuprinși de farmec\n"
            "Sub lumina blândei lune -\n"
            "Vântu-n trestii lin foșnească,\n"
            "Unduioasa apă sune!\n"
            "\n"
            "Dar nu vine... Singuratic\n"
            "În zadar suspin și sufăr\n"
            "Lângă lacul cel albastru\n"
            "Încărcat cu flori de nufăr."
        ),
    },
    {
        "author": "dangocan",
        "title": "Dorința",
        "slug": "dorinta",
        "category": "poezie",
        "days_ago": 12,
        "source_author": "Mihai Eminescu",
        "source_name": "Wikisource - Dorința",
        "source_url": "https://ro.wikisource.org/wiki/Dorin%C8%9Ba",
        "content": (
            "Vino-n codru la izvorul\n"
            "Care tremură pe prund,\n"
            "Unde prispa cea de brazde\n"
            "Crengi plecate o ascund.\n"
            "\n"
            "Și în brațele-mi întinse\n"
            "Să alergi, pe piept să-mi cazi,\n"
            "Să-ți desprind din creștet vălul,\n"
            "Să-l ridic de pe obraz.\n"
            "\n"
            "Pe genunchii mei ședea-vei,\n"
            "Vom fi singuri-singurei,\n"
            "Iar în păr înfiorate\n"
            "Or să-ți cadă flori de tei.\n"
            "\n"
            "Fruntea albă-n părul galben\n"
            "Pe-al meu braț încet s-o culci,\n"
            "Lăsând pradă gurii mele\n"
            "Ale tale buze dulci...\n"
            "\n"
            "Vom visa un vis ferice,\n"
            "Îngâna-ne-vor c-un cânt\n"
            "Singuratece izvoare,\n"
            "Blânda batere de vânt;\n"
            "\n"
            "Adormind de armonia\n"
            "Codrului bătut de gânduri,\n"
            "Flori de tei deasupra noastră\n"
            "Or să cadă rânduri-rânduri."
        ),
    },
    {
        "author": "dangocan",
        "title": "Ce te legeni...",
        "slug": "ce-te-legeni",
        "category": "poezie",
        "days_ago": 16,
        "source_author": "Mihai Eminescu",
        "source_name": "Wikisource - Ce te legeni...",
        "source_url": "https://ro.wikisource.org/wiki/Ce_te_legeni...",
        "content": (
            "Ce te legeni, codrule,\n"
            "Fără ploaie, fără vânt,\n"
            "Cu crengile la pământ?\n"
            "- De ce nu m-aș legăna,\n"
            "Dacă trece vremea mea!\n"
            "Ziua scade, noaptea crește\n"
            "Și frunzișul mi-l rărește.\n"
            "Bate vântul frunza-n dungă -\n"
            "Cântăreții mi-i alungă;\n"
            "Bate vântul dintr-o parte -\n"
            "Iarna-i ici, vara-i departe.\n"
            "Și de ce să nu mă plec,\n"
            "Dacă păsările trec!\n"
            "Peste vârf de rămurele\n"
            "Trec în stoluri rândunele,\n"
            "Ducând gândurile mele\n"
            "Și norocul meu cu ele.\n"
            "Și se duc pe rând, pe rând,\n"
            "Zarea lumii-ntunecând,\n"
            "Și se duc ca clipele,\n"
            "Scuturând aripele,\n"
            "Și mă lasă pustiit,\n"
            "Vestejit și amorțit\n"
            "Și cu doru-mi singurel,\n"
            "De mă-ngân numai cu el!"
        ),
    },
    {
        "author": "gocandan",
        "title": "Fata babei și fata moșneagului",
        "slug": "fata-babei-si-fata-mosneagului",
        "category": "proza_scurta",
        "days_ago": 32,
        "source_author": "Ion Creangă",
        "source_name": "Wikisource - Fata babei și fata moșneagului",
        "source_url": "https://ro.wikisource.org/wiki/Fata_babei_%C8%99i_fata_mo%C8%99neagului",
        "content": _clean_text(
            """
            Într-o casă trăiau un moșneag și o babă, fiecare cu fata lui. Fata moșneagului era harnică, blândă și răbdătoare, iar fata babei era răsfățată, leneșă și gata să arunce vina pe alții. Cum se întâmplă adesea în poveștile vechi, cea bună ducea greul casei, iar cea iubită fără măsură primea laude pentru nimic.

            Într-o zi, fata moșneagului fu trimisă de acasă, cu sufletul strâns și cu nădejdea în Dumnezeu. Pe drum întâlni un cățel bolnav, un păr năpădit de omizi, o fântână stricată și un cuptor părăsit. Fiecare îi ceru ajutorul. Fata nu se grăbi să-și plângă soarta; se opri, curăță, îngriji și puse lucrurile în rânduială. Bunătatea ei nu era vorbă, ci muncă făcută la timp.

            Ajunse la casa unei bătrâne cu înfățișare neobișnuită și sluji acolo cu răbdare. Când veni vremea răsplății, i se spuse să aleagă o ladă. Fata nu se repezi la cea mai mare, ci o luă pe cea smerită. La întoarcere, cuptorul îi dădu plăcinte, fântâna apă limpede, părul roade, iar cățelul bucurie. Acasă, lada se umplu de daruri.

            Fata babei porni apoi pe același drum, dar cu altă inimă. Batjocori cățelul, fântâna, părul și cuptorul, slujind fără chef și alegând la urmă lada cea mai mare. Drumul de întoarcere nu-i mai dădu nimic, iar lada aduse spaimă în loc de avere. Povestea rămâne limpede: lumea răspunde fiecăruia după felul în care el însuși răspunde lumii.
            """
        ),
    },
    {
        "author": "gocandan",
        "title": "Soacra cu trei nurori",
        "slug": "soacra-cu-trei-nurori",
        "category": "proza_scurta",
        "days_ago": 36,
        "source_author": "Ion Creangă",
        "source_name": "Wikisource - Soacra cu trei nurori",
        "source_url": "https://ro.wikisource.org/wiki/Soacra_cu_trei_nurori",
        "content": _clean_text(
            """
            O femeie cu trei feciori își ținea casa cu mână tare și limba ascuțită. Când băieții se însurară, soacra nu primi nurori, ci slujnice peste care voia să domnească din zori până în noapte. Le împărțea treburi fără sfârșit, le căuta greșeli în orice mișcare și le amintea mereu că în casa ei nimeni nu respiră fără încuviințare.

            Nurorile cele mari înghițiră multă vreme necazul, dar cea mică văzu mai limpede că frica nu face casă bună. Soacra se prefăcea că doarme, ascultând tot, iar femeile lucrau pe ascuns, șoptind și temându-se de ochiul ei mereu treaz. În loc să fie sprijin pentru familia care creștea, bătrâna se făcuse paznic de temniță.

            Tensiunea se strânse ca funia răsucită. Nurorile începură să răspundă vicleniei cu viclenie, iar casa se umplu de prefăcătorii. Fiecare gest avea două înțelesuri: unul pentru ochii soacrei și altul pentru dreptatea pe care tinerele o simțeau furată. Hazul poveștii ascunde o lume în care puterea fără milă ajunge să fie judecată de cei pe care i-a apăsat.

            La sfârșit, satul vorbește mult despre soacră și despre bocetele nurorelor. Dar dincolo de râsul amar rămâne întrebarea: ce fel de familie se zidește când dragostea este înlocuită cu porunca? Povestea nu îndulcește nimic; arată cum abuzul domestic se întoarce împotriva celui care l-a făcut lege.
            """
        ),
    },
    {
        "author": "gocandan",
        "title": "Ivan Turbincă",
        "slug": "ivan-turbinca",
        "category": "proza_scurta",
        "days_ago": 42,
        "source_author": "Ion Creangă",
        "source_name": "Wikisource - Ivan Turbincă",
        "source_url": "https://ro.wikisource.org/wiki/Ivan_Turbinc%C4%83",
        "content": _clean_text(
            """
            Ivan era soldat vechi, obișnuit cu drumul, cu foamea și cu gluma spusă la vreme potrivită. Când își termină slujba, porni prin lume cu puțin în traistă și cu mult curaj în suflet. Pe drum întâlni oameni sărmani și nu ținu strâns ce avea. Dădu din puținul lui, iar bunătatea aceea fără socoteală îi aduse un dar neașteptat.

            Darul era o turbincă fermecată, în care putea intra orice primea poruncă. Ivan înțelese repede că un asemenea lucru nu e doar pentru câștig, ci pentru a răsturna ordinea celor care se cred de neatins. Cu turbinca la îndemână, soldatul intră în case boierești, în încurcături drăcești și în întâmplări unde îndrăzneala face cât o armată.

            Dracii se speriară de el, căci Ivan nu se purta ca omul care tremură în fața întunericului. Îi păcăli, îi înghesui, îi scoase și îi puse la tocmeală. Mai târziu, când Moartea însăși veni să-și facă datoria, Ivan găsi chip să o amâne, să o prindă și să o țină departe. Pentru o vreme, lumea rămase fără sfârșit, iar oamenii aflară că și nemurirea poate deveni povară.

            În această poveste, hazul umblă lângă fior. Ivan nu este sfânt, nici înțelept de carte, dar are o libertate pe care nimeni nu i-o poate lua: râde de frică și nu se pleacă înaintea ei. De aceea, turbinca lui nu este doar un obiect fermecat, ci semnul unei minți care nu acceptă hotarele fără să le întrebe de ce stau acolo.
            """
        ),
    },
    {
        "author": "dangocan",
        "title": "Scrisoarea I (fragment de seed)",
        "slug": "scrisoarea-i-fragment-de-seed",
        "category": "poezie",
        "days_ago": 46,
        "source_author": "Mihai Eminescu",
        "source_name": "Wikisource - Scrisoarea I",
        "source_url": "https://ro.wikisource.org/wiki/Scrisoarea_I",
        "content": _clean_text(
            """
            Când lampa scade peste masă
            Și noaptea intră în odaie,
            Un gând se rupe de la casă
            Și trece dincolo de ploaie.

            Se face mică lumea toată,
            Un punct de pulbere în zare,
            Iar mintea, singură, se-mbată
            De drumuri fără de hotare.

            Bătrânul stă cu fruntea rece,
            Cu file vechi sub mâna lui;
            Prin semne timpul i se trece,
            Dar el tot caută ce nu-i.

            Își vede veacul ca pe-o clipă,
            Iar clipa ca pe-un cer rotund;
            Din orice număr se-nfiripă
            Un început fără răspuns.

            Și dacă mâine peste nume
            Se-așterne colbul nepăsării,
            Rămâne totuși, peste lume,
            O întrebare dată mării.

            Așa, sub luna care trece,
            Nu slava-i ține loc de scut;
            Ci liniștea, adâncă, rece,
            Că a gândit cât a putut.
            """
        ),
    },
    {
        "author": "dangocan",
        "title": "Luceafărul (fragment de seed)",
        "slug": "luceafarul-fragment-de-seed",
        "category": "poezie",
        "days_ago": 50,
        "source_author": "Mihai Eminescu",
        "source_name": "Wikisource - Luceafărul",
        "source_url": "https://ro.wikisource.org/wiki/Luceaf%C4%83rul_(Eminescu)",
        "content": _clean_text(
            """
            La geamul înalt al serii
            Stă gândul prins de stea,
            Și peste somnul tăcerii
            O rază cade grea.

            Departe, rece lumină,
            Își poartă drumul lin,
            Iar inima se înclină
            Spre cerul ei străin.

            Ea cheamă fără cuvinte,
            El vine fără trup;
            Între dorinți și morminte
            Hotare vechi se rup.

            Dar lumea cere măsură,
            Iar cerul cere uitări;
            Ce-i foc în clipa cea pură
            Se stinge între chemări.

            Rămâne fata cu visul,
            Rămâne astrul cu ger,
            Și între ei, necuprinsul
            Se face punte de cer.

            Iubirea vrea apropiere,
            Lumina vrea numai drum;
            De-aceea orice cădere
            Lasă în urmă un scrum.

            Când zorii spală fereastra,
            Chemarea nu s-a sfârșit;
            În om rămâne albastra
            Distanță de neatins.

            Iar steaua, fără mustrare,
            Își ține vechiul hotar:
            Ea dă pământului zare,
            Dar nu coboară-n zadar.
            """
        ),
    },
    {
        "author": "dangocan",
        "title": "Glossă (adaptare de seed)",
        "slug": "glossa-adaptare-de-seed",
        "category": "poezie",
        "days_ago": 54,
        "source_author": "Mihai Eminescu",
        "source_name": "Wikisource - Glossă",
        "source_url": "https://ro.wikisource.org/wiki/Gloss%C4%83",
        "content": _clean_text(
            """
            Vremea vine, vremea pleacă,
            Omul stă la răscruci,
            Unii strigă, alții pleacă,
            Tu în tine să te duci.

            Nu te pierde în mulțime,
            Nu te vinde pe-un cuvânt;
            Cine caută mărime
            Uită pasul pe pământ.

            Privește drept, dar fără ură,
            Judecă, dar nu te frânge;
            Gura lumii e măsură
            Care astăzi râde, mâine plânge.

            Ce e zgomot trece-n seară,
            Ce e limpede rămâne;
            Frunza cade, iarăși iară,
            Rădăcina tot se ține.

            De te cheamă la mărire,
            Cercetează prețul ei;
            Multe drumuri par iubire,
            Dar te duc departe de-ai tăi.

            Lasă clipa să vorbească,
            Lasă valul să se ducă;
            Mintea bună se păzească
            De podoaba care-ncurcă.

            Când te laudă furtuna,
            Nu te face turn de fum;
            Când te ceartă toți întruna,
            Nu-ți uita al tău drum.

            Toate vin cu față nouă,
            Toate pleacă mai apoi;
            Peste lacrimi cade rouă,
            Peste zgomot, pași de noi.
            """
        ),
    },
]


POST_AUDIO = [
    {
        "post_slug": "punguta-cu-doi-bani",
        "requester": "gocandan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/1/audio/tts-9ce9a71779cb4aa2849e3e8822520ef5.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 159168,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-13 12:15:59.875000",
        "updated_at": "2026-05-13 12:15:59.875000",
    },
    {
        "post_slug": "punguta-cu-doi-bani",
        "requester": "gocandan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/1/audio/tts-e9d3d3a3714c4b1aa8e40a3e439198fb.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 398400,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-18 15:30:30.705000",
        "updated_at": "2026-05-18 15:30:30.705000",
    },
    {
        "post_slug": "ce-te-legeni",
        "requester": "dangocan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/10/audio/tts-af1d75d21ded47f29ab773a4bd2e8344.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 271488,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-18 15:32:28.462000",
        "updated_at": "2026-05-18 15:32:28.462000",
    },
    {
        "post_slug": "fata-babei-si-fata-mosneagului",
        "requester": "gocandan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/11/audio/tts-08154fbd02db4a3d88106707a708d6d6.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 432288,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-18 15:27:12.824000",
        "updated_at": "2026-05-18 15:27:12.824000",
    },
    {
        "post_slug": "soacra-cu-trei-nurori",
        "requester": "gocandan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/12/audio/tts-51710fb8f3344c93b414ea6489355532.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 413280,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-18 15:26:39.373000",
        "updated_at": "2026-05-18 15:26:39.373000",
    },
    {
        "post_slug": "ivan-turbinca",
        "requester": "gocandan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/13/audio/tts-9beab5d0b7ad42eca94c4ce605fdcaa4.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 433536,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-18 15:25:52.874000",
        "updated_at": "2026-05-18 15:25:52.874000",
    },
    {
        "post_slug": "scrisoarea-i-fragment-de-seed",
        "requester": "dangocan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/14/audio/tts-7d25ee6cb1c247919ed3badc76dc4d61.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 270720,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-06 09:14:05.784000",
        "updated_at": "2026-05-06 09:14:05.784000",
    },
    {
        "post_slug": "scrisoarea-i-fragment-de-seed",
        "requester": "dangocan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/14/audio/tts-bb21e88a80f4485998dc1720171490f0.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 276960,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-18 15:33:23.453000",
        "updated_at": "2026-05-18 15:33:23.453000",
    },
    {
        "post_slug": "luceafarul-fragment-de-seed",
        "requester": "dangocan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/15/audio/tts-2ac645b4259e4619aac229df9b9b7e94.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 302496,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-18 15:32:56.418000",
        "updated_at": "2026-05-18 15:32:56.418000",
    },
    {
        "post_slug": "glossa-adaptare-de-seed",
        "requester": "dangocan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/16/audio/tts-1788a3afe53e4f61ab04680d0e8bf526.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 408096,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-01 13:46:32.920000",
        "updated_at": "2026-05-01 13:46:32.920000",
    },
    {
        "post_slug": "glossa-adaptare-de-seed",
        "requester": "dangocan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/16/audio/tts-b8403647ea4647c0a0dc0c1e3a4398c7.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 315840,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-18 15:33:57.491000",
        "updated_at": "2026-05-18 15:33:57.491000",
    },
    {
        "post_slug": "ursul-pacalit-de-vulpe",
        "requester": "gocandan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/2/audio/tts-64caedd63da545d7bbda217cc3a20c0c.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 371808,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-18 15:29:50.209000",
        "updated_at": "2026-05-18 15:29:50.209000",
    },
    {
        "post_slug": "ursul-pacalit-de-vulpe",
        "requester": "gocandan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/2/audio/tts-f44cc3a52db444c0ba30b100c1df397a.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 169536,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-13 12:16:15.118000",
        "updated_at": "2026-05-13 12:16:15.118000",
    },
    {
        "post_slug": "capra-cu-trei-iezi",
        "requester": "gocandan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/3/audio/tts-1940548a1eb140f497c9eab305a488fd.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 169920,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-13 12:16:36.235000",
        "updated_at": "2026-05-13 12:16:36.235000",
    },
    {
        "post_slug": "capra-cu-trei-iezi",
        "requester": "gocandan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/3/audio/tts-7c6def34245d4a4a9f255230e66f6eed.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 358368,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-18 15:29:13.184000",
        "updated_at": "2026-05-18 15:29:13.184000",
    },
    {
        "post_slug": "povestea-unui-om-lenes",
        "requester": "gocandan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/4/audio/tts-b274a1e944534724b001582196ae4a06.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 168288,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-13 12:16:54.166000",
        "updated_at": "2026-05-13 12:16:54.166000",
    },
    {
        "post_slug": "povestea-unui-om-lenes",
        "requester": "gocandan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/4/audio/tts-b78f42ce9fc6464fae2909ada130ff5a.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 423648,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-18 15:28:40.505000",
        "updated_at": "2026-05-18 15:28:40.505000",
    },
    {
        "post_slug": "danila-prepeleac",
        "requester": "gocandan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/5/audio/tts-695c2691daae416aa0a5da3bb579dd86.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 140448,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-13 12:17:10.485000",
        "updated_at": "2026-05-13 12:17:10.485000",
    },
    {
        "post_slug": "danila-prepeleac",
        "requester": "gocandan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/5/audio/tts-72be8cafed1b47e1a61a157f14a035d9.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 368736,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-18 15:27:48.890000",
        "updated_at": "2026-05-18 15:27:48.890000",
    },
    {
        "post_slug": "somnoroase-pasarele",
        "requester": "dangocan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/6/audio/tts-8eb0b0cf172749369d553c8b78e91f02.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 182880,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-18 15:30:51.301000",
        "updated_at": "2026-05-18 15:30:51.301000",
    },
    {
        "post_slug": "la-steaua",
        "requester": "dangocan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/7/audio/tts-9ddd34bfce8f481cac4422a30cafb5ca.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 176928,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-18 15:31:11.752000",
        "updated_at": "2026-05-18 15:31:11.752000",
    },
    {
        "post_slug": "lacul",
        "requester": "dangocan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/8/audio/tts-385526d7a37648fa910729bf6e0474f8.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 201696,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-18 15:31:35.862000",
        "updated_at": "2026-05-18 15:31:35.862000",
    },
    {
        "post_slug": "dorinta",
        "requester": "dangocan",
        "source": "tts",
        "status": "ready",
        "storage_backend": "s3",
        "storage_key": "posts/9/audio/tts-4677a5f42d08484b8e65a96640c3ec55.mp3",
        "content_type": "audio/mpeg",
        "byte_size": 249408,
        "language_code": "ro-RO",
        "moderation_status": "approved",
        "created_at": "2026-05-18 15:32:02.101000",
        "updated_at": "2026-05-18 15:32:02.101000",
    },
]


COMMENTS = []


LIKES = []

ANON_LIKES = []


BEST_FRIENDS = []


FEATURED = []


CLUBS = []


CLUB_BOARD_MESSAGES = []


AWARDS = []


# ──────────────────────────────────────────────────────────────────────
# Seed
# ──────────────────────────────────────────────────────────────────────

def _build_db_url() -> str:
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "calimara_db")
    if not user or not password:
        raise SystemExit("DB_USER / DB_PASSWORD missing from env; cannot seed.")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


def _ts(days_ago: int) -> datetime:
    return datetime.now() - timedelta(days=days_ago, hours=days_ago % 4)


def seed(session: Session, *, quiet: bool = False) -> None:
    log = (lambda *_a, **_k: None) if quiet else print

    # ── Users ──────────────────────────────────────────────
    users_by_username: dict[str, models.User] = {}
    for row in AUTHORS:
        now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        premium_until = None
        if row.get("premium_until_days"):
            premium_until = now + timedelta(days=row["premium_until_days"])
        password = row.get("password")
        u = models.User(
            username=row["username"],
            email=row["email"],
            google_id=row.get("google_id"),
            password_hash=_seed_password_hash(password) if password else None,
            email_verified_at=now if password else None,
            password_updated_at=now if password else None,
            subtitle=row["subtitle"],
            avatar_seed=row["avatar_seed"],
            is_admin=row.get("is_admin", False),
            is_moderator=row.get("is_moderator", False),
            premium_tier=row.get("premium_tier", "free"),
            premium_until=premium_until,
        )
        session.add(u)
        users_by_username[row["username"]] = u
    session.flush()
    log(f"  Seed: {len(users_by_username)} users")

    for row in AUTHORS:
        session.add(
            models.PlatformAllowedEmail(
                email=row["email"].lower(),
                note="seed",
            )
        )
    log(f"  Seed: {len(AUTHORS)} allowed platform emails")

    # ── Posts ──────────────────────────────────────────────
    posts_by_slug: dict[str, models.Post] = {}
    for row in POSTS:
        author = users_by_username[row["author"]]
        created = _ts(row["days_ago"])
        p = models.Post(
            user_id=author.id,
            title=row["title"],
            slug=row["slug"],
            content=_seed_content_html(row),
            category=row["category"],
            view_count=10 + (row["days_ago"] * 7) % 137,
            moderation_status="approved",
            created_at=created,
            updated_at=created,
        )
        session.add(p)
        posts_by_slug[row["slug"]] = p
    session.flush()

    log(f"  Seed: {len(posts_by_slug)} posts")

    # ── Post audio links ───────────────────────────────────
    for row in POST_AUDIO:
        post = posts_by_slug[row["post_slug"]]
        requester = users_by_username.get(row["requester"]) if row.get("requester") else None
        session.add(
            models.PostAudio(
                post_id=post.id,
                requester_user_id=requester.id if requester else None,
                source=row.get("source", "tts"),
                status=row.get("status", "ready"),
                tts_character_count=row.get("tts_character_count", 0),
                storage_backend=row["storage_backend"],
                storage_key=row["storage_key"],
                content_type=row.get("content_type"),
                byte_size=row.get("byte_size"),
                language_code=row.get("language_code"),
                moderation_status=row.get("moderation_status"),
                created_at=_seed_datetime(row.get("created_at")),
                updated_at=_seed_datetime(row.get("updated_at")),
            )
        )
    log(f"  Seed: {len(POST_AUDIO)} post audio links")

    # ── Comments ───────────────────────────────────────────
    for row in COMMENTS:
        post = posts_by_slug[row["post_slug"]]
        user_id: Optional[int] = None
        author_name: Optional[str] = row.get("author_name")
        author_email: Optional[str] = row.get("author_email")
        if "author_username" in row:
            user_id = users_by_username[row["author_username"]].id
        c = models.Comment(
            post_id=post.id,
            user_id=user_id,
            author_name=author_name,
            author_email=author_email,
            content=row["content"],
            approved=True,
            moderation_status="approved",
            created_at=_ts(row["days_ago"]),
        )
        session.add(c)
    log(f"  Seed: {len(COMMENTS)} comments")

    # ── Likes ──────────────────────────────────────────────
    for slug, username in LIKES:
        post = posts_by_slug[slug]
        user = users_by_username[username]
        session.add(models.Like(post_id=post.id, user_id=user.id))
    for slug, ip in ANON_LIKES:
        post = posts_by_slug[slug]
        session.add(models.Like(post_id=post.id, ip_address=ip))
    log(f"  Seed: {len(LIKES) + len(ANON_LIKES)} likes")

    # ── Best friends ───────────────────────────────────────
    for user_name, friend_name, position in BEST_FRIENDS:
        u = users_by_username[user_name]
        f = users_by_username[friend_name]
        session.add(
            models.BestFriend(user_id=u.id, friend_user_id=f.id, position=position)
        )
    log(f"  Seed: {len(BEST_FRIENDS)} best-friend links")

    # ── Featured posts ─────────────────────────────────────
    for user_name, slug, position in FEATURED:
        u = users_by_username[user_name]
        p = posts_by_slug[slug]
        session.add(
            models.FeaturedPost(user_id=u.id, post_id=p.id, position=position)
        )
    log(f"  Seed: {len(FEATURED)} featured posts")

    # ── Clubs ──────────────────────────────────────────────
    # Featured creations expire after a week, mirroring the live flow.
    featured_until = datetime.now(tz=timezone.utc).replace(tzinfo=None) + timedelta(days=7)
    clubs_by_slug: dict[str, models.Club] = {}
    for row in CLUBS:
        owner = users_by_username[row["owner"]]
        featured_post = None
        if row.get("featured_post_slug"):
            featured_post = posts_by_slug[row["featured_post_slug"]]
        club = models.Club(
            owner_id=owner.id,
            title=row["title"],
            slug=row["slug"],
            description=row["description"],
            motto=row["motto"],
            avatar_seed=row["avatar_seed"],
            theme=row["theme"],
            speciality=row["speciality"],
            featured_post_id=featured_post.id if featured_post else None,
            featured_until=(featured_until if featured_post else None),
        )
        session.add(club)
        clubs_by_slug[row["slug"]] = club
    session.flush()

    # Owner membership row for each club + extra members
    for row in CLUBS:
        club = clubs_by_slug[row["slug"]]
        owner = users_by_username[row["owner"]]
        session.add(models.ClubMember(club_id=club.id, user_id=owner.id, role="owner"))
        for member_username, role in row.get("members", []):
            user = users_by_username[member_username]
            session.add(models.ClubMember(club_id=club.id, user_id=user.id, role=role))
    session.flush()
    log(f"  Seed: {len(clubs_by_slug)} clubs")

    # Board messages (with simple parent linkage by index in the list)
    created_messages: list[models.ClubBoardMessage] = []
    for idx, (club_slug, author_username, content, parent_idx, days_ago) in enumerate(CLUB_BOARD_MESSAGES):
        club = clubs_by_slug[club_slug]
        author = users_by_username[author_username]
        parent_id = None
        if parent_idx is not None:
            parent_id = created_messages[parent_idx].id
        msg = models.ClubBoardMessage(
            club_id=club.id,
            author_id=author.id,
            parent_id=parent_id,
            content=content,
            created_at=_ts(days_ago),
            updated_at=_ts(days_ago),
        )
        session.add(msg)
        session.flush()
        created_messages.append(msg)
    log(f"  Seed: {len(CLUB_BOARD_MESSAGES)} club board messages")

    # ── Awards ─────────────────────────────────────────────
    for row in AWARDS:
        u = users_by_username[row["username"]]
        session.add(
            models.UserAward(
                user_id=u.id,
                award_title=row["title"],
                award_description=row["description"],
                award_date=row["award_date"],
                award_type=row["award_type"],
            )
        )
    log(f"  Seed: {len(AWARDS)} awards")

    session.commit()


def main(quiet: bool = False) -> None:
    engine = create_engine(_build_db_url())
    try:
        with Session(engine) as session:
            seed(session, quiet=quiet)
        if not quiet:
            print("  Seed data inserted.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
