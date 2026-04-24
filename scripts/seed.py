#!/usr/bin/env python3
"""
Populate the database with sample Romanian content for local development.

Runs after `scripts/initdb.py` / `run.py`'s `init_database()` has produced an
empty schema. Creates a handful of authors with short poetry and prose,
comments, likes, best-friend links, featured posts, and one award each — just
enough to make every page of the app feel alive when the user clicks around.

Invocation:
    python scripts/seed.py

Or called automatically at the end of `run.py`'s init step.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
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

AUTHORS = [
    {
        "username": "mireasufletului",
        "email": "mireasufletului@example.com",
        "google_id": "seed-google-1",
        "subtitle": "versuri scrise la ceas târziu, când oraşul adoarme",
        "avatar_seed": "mirea-01",
    },
    {
        "username": "vanatordecuvinte",
        "email": "vanatordecuvinte@example.com",
        "google_id": "seed-google-2",
        "subtitle": "caut cuvintele care nu s-au rostit încă",
        "avatar_seed": "vanator-42",
    },
    {
        "username": "filedintramvai",
        "email": "filedintramvai@example.com",
        "google_id": "seed-google-3",
        "subtitle": "proză scurtă, scrisă între staţii",
        "avatar_seed": "file-07",
    },
    {
        "username": "noaptedetarziu",
        "email": "noaptedetarziu@example.com",
        "google_id": "seed-google-4",
        "subtitle": "melancolii urbane şi alte forme de insomnie",
        "avatar_seed": "noapte-99",
    },
]


POSTS = [
    # ── mireasufletului — poezie ────────────────────────────
    {
        "author": "mireasufletului",
        "title": "Fereastra stinsă",
        "slug": "fereastra-stinsa",
        "category": "poezie",
        "days_ago": 2,
        "content": (
            "Lumina stinsă în fereastră\n"
            "nu ne mai cheamă acasă.\n"
            "\n"
            "Rămâne doar conturul\n"
            "unui gest care n-a fost făcut,\n"
            "un cuvânt pe care l-am păstrat\n"
            "pentru altă iarnă.\n"
            "\n"
            "Şi totuşi ceva\n"
            "mai bate încet în geam —\n"
            "poate-o frunză, poate-o amintire\n"
            "care nu ştie că s-a dus."
        ),
    },
    {
        "author": "mireasufletului",
        "title": "Dimineaţa ta",
        "slug": "dimineata-ta",
        "category": "poezie",
        "days_ago": 6,
        "content": (
            "Mi-ai spus odată\n"
            "că dimineţile tale\n"
            "miros a cafea şi a pagini nescrise.\n"
            "\n"
            "Eu ţi-am răspuns\n"
            "că dimineţile mele\n"
            "miros a tine\n"
            "şi atât."
        ),
    },
    {
        "author": "mireasufletului",
        "title": "Scrisoare pentru luni",
        "slug": "scrisoare-pentru-luni",
        "category": "poezie",
        "days_ago": 14,
        "content": (
            "Dragă luni,\n"
            "nu-ţi port pică.\n"
            "\n"
            "Ştiu că şi tu\n"
            "ai vrea câteodată\n"
            "să fii duminică seara —\n"
            "să te amâni pe tine însăţi\n"
            "până când cineva\n"
            "ţi-ar spune în sfârşit\n"
            "că e bine aşa."
        ),
    },
    # ── vanatordecuvinte — poezie ───────────────────────────
    {
        "author": "vanatordecuvinte",
        "title": "Oraşul dimineaţa",
        "slug": "orasul-dimineata",
        "category": "poezie",
        "days_ago": 1,
        "content": (
            "Oraşul dimineaţa\n"
            "e un animal blând\n"
            "care se întinde în soare\n"
            "şi uită că are gheare.\n"
            "\n"
            "Trecem pe lângă el\n"
            "fără să-l atingem,\n"
            "cu grija copiilor\n"
            "care trec pe lângă câinii străzii."
        ),
    },
    {
        "author": "vanatordecuvinte",
        "title": "Cuvinte fără adresă",
        "slug": "cuvinte-fara-adresa",
        "category": "poezie",
        "days_ago": 9,
        "content": (
            "Sunt cuvinte\n"
            "pe care le-am rostit\n"
            "doar pentru ca ele să existe.\n"
            "\n"
            "Le-am pus pe masă,\n"
            "le-am privit o vreme,\n"
            "apoi le-am trimis\n"
            "la o adresă\n"
            "pe care n-am scris-o\n"
            "niciodată."
        ),
    },
    {
        "author": "vanatordecuvinte",
        "title": "Manual",
        "slug": "manual",
        "category": "poezie",
        "days_ago": 20,
        "content": (
            "Se scrie aşa:\n"
            "o frază\n"
            "care să pară că ştie ceva.\n"
            "\n"
            "Apoi, imediat dedesubt,\n"
            "încă una\n"
            "care să recunoască\n"
            "că nu ştie nimic.\n"
            "\n"
            "Restul —\n"
            "tăcere dactilografiată."
        ),
    },
    # ── filedintramvai — proză ──────────────────────────────
    {
        "author": "filedintramvai",
        "title": "Tramvaiul 21",
        "slug": "tramvaiul-21",
        "category": "proza_scurta",
        "days_ago": 3,
        "content": (
            "Tramvaiul opreşte în ceaţă şi nimeni nu coboară. E aceea dintre "
            "staţii care există numai pe hartă, un nume pus de cineva acum "
            "şaptezeci de ani, care a rămas cum rămâne un semn de carte într-o "
            "carte pe care n-o mai deschide nimeni.\n"
            "\n"
            "Şoferul deschide uşa mai mult din obişnuinţă. Aerul de-afară e "
            "umed, miroase a iarnă veche şi a pâine proaspătă dintr-o brutărie "
            "care nu se vede. Aştept trei secunde, ca o formalitate, apoi "
            "uşile se închid şi mergem mai departe.\n"
            "\n"
            "În geam, pentru o clipă, cineva îmi face semn cu mâna. Nu ştiu "
            "dacă sunt eu — sau cine altcineva."
        ),
    },
    {
        "author": "filedintramvai",
        "title": "Geamantan",
        "slug": "geamantan",
        "category": "proza_scurta",
        "days_ago": 8,
        "content": (
            "Avea un geamantan maro cu colţurile tocite şi îl ducea cu mâna "
            "stângă, deşi se vedea că e mai uşor decât pretindea. Când a "
            "trecut pe lângă mine, mirosea a colonie ieftină şi a cafea "
            "băută în grabă la un bar de gară.\n"
            "\n"
            "M-am gândit că poate se întoarce acasă. M-am gândit că poate "
            "pleacă. M-am gândit că poate, de fapt, nu se duce nicăieri — că "
            "pur şi simplu îşi poartă geamantanul prin oraş, ca alţii îşi "
            "poartă câinele, ca să nu rămână singuri cu ei înşişi."
        ),
    },
    {
        "author": "filedintramvai",
        "title": "Doamna cu pâine",
        "slug": "doamna-cu-paine",
        "category": "proza_scurta",
        "days_ago": 17,
        "content": (
            "O doamnă de vreo şaptezeci de ani s-a aşezat lângă mine, a pus "
            "plasa cu pâine pe genunchi şi a scos din ea o carte. Era un "
            "roman pe care îl citisem în liceu.\n"
            "\n"
            "Am stat aşa, şase staţii. Ea citea; eu mă uitam pe geam. La un "
            "moment dat, fără să ridice ochii, mi-a spus: „am ajuns la partea "
            "în care se despart.\"\n"
            "\n"
            "I-am răspuns că îmi pare rău. A dat din cap — şi şi-a văzut, "
            "liniştită, de pagină."
        ),
    },
    # ── noaptedetarziu — amestec ────────────────────────────
    {
        "author": "noaptedetarziu",
        "title": "Trei dimineaţa",
        "slug": "trei-dimineata",
        "category": "poezie",
        "days_ago": 0,
        "content": (
            "La trei dimineaţa\n"
            "oraşul are vocea\n"
            "unui prieten vechi\n"
            "care şi-a uitat ultima replică.\n"
            "\n"
            "Îi ţin locul în linişte\n"
            "până la lumină —\n"
            "apoi plecăm amândoi\n"
            "fără să ne mai datorăm nimic."
        ),
    },
    {
        "author": "noaptedetarziu",
        "title": "Liftul",
        "slug": "liftul",
        "category": "proza_scurta",
        "days_ago": 4,
        "content": (
            "Liftul s-a oprit între etaje şi am râs, aşa cum râde omul "
            "cuminte când i se întâmplă ceva mic şi previzibil. Apoi am stat. "
            "Am stat ceva mai mult decât mi-aş fi dorit.\n"
            "\n"
            "Într-un colţ, o oglindă care nu mă mai arăta decât pe jumătate. "
            "Pe celălalt perete, un afiş cu instrucţiuni pe care le citisem "
            "fără să le citesc, ani la rând.\n"
            "\n"
            "Când s-au deschis uşile, nu eram la etajul meu. Nu era etajul "
            "nimănui. Am ieşit oricum — pentru că liftul, ca multe altele în "
            "oraşul ăsta, nu te aşteaptă să fii pregătit."
        ),
    },
    {
        "author": "noaptedetarziu",
        "title": "Exerciţiu",
        "slug": "exercitiu",
        "category": "poezie",
        "days_ago": 12,
        "content": (
            "Scrie ceva care să nu fie nici trist, nici vesel.\n"
            "Un lucru mic, ca un cui într-un perete vechi.\n"
            "\n"
            "Să ţină un tablou —\n"
            "sau o haină —\n"
            "sau nimic,\n"
            "dacă nimic are nevoie, la rândul lui, de un cui."
        ),
    },
]


COMMENTS = [
    {
        "post_slug": "fereastra-stinsa",
        "author_name": None,  # authenticated
        "author_username": "vanatordecuvinte",
        "content": "Versul despre cuvântul păstrat pentru altă iarnă mi-a rămas în minte.",
        "days_ago": 1,
    },
    {
        "post_slug": "fereastra-stinsa",
        "author_name": "cititor anonim",
        "author_email": "cititor@example.com",
        "content": "Mulţumesc. Exact aşa se simte acum, la mine.",
        "days_ago": 1,
    },
    {
        "post_slug": "tramvaiul-21",
        "author_username": "mireasufletului",
        "content": "Finalul, cu mâna din geam, e o lovitură mică şi curată.",
        "days_ago": 2,
    },
    {
        "post_slug": "orasul-dimineata",
        "author_username": "filedintramvai",
        "content": "Imaginea cu animalul blând e pe gustul meu.",
        "days_ago": 0,
    },
    {
        "post_slug": "doamna-cu-paine",
        "author_name": "maria",
        "content": "Am recitit de două ori. E atât de liniştit.",
        "days_ago": 10,
    },
    {
        "post_slug": "trei-dimineata",
        "author_username": "mireasufletului",
        "content": "„Îi ţin locul în linişte\" — versul ăsta mă urmăreşte.",
        "days_ago": 0,
    },
    {
        "post_slug": "liftul",
        "author_username": "vanatordecuvinte",
        "content": "Ieşitul la un etaj care nu e al tău — foarte adevărat.",
        "days_ago": 3,
    },
    {
        "post_slug": "manual",
        "author_name": "un trecător",
        "content": "„Tăcere dactilografiată.\" Gata, am plecat cu ea.",
        "days_ago": 18,
    },
]


# Likes: mostly user-authored (some anonymous IPs sprinkled in)
LIKES = [
    ("fereastra-stinsa", "vanatordecuvinte"),
    ("fereastra-stinsa", "filedintramvai"),
    ("fereastra-stinsa", "noaptedetarziu"),
    ("dimineata-ta", "noaptedetarziu"),
    ("dimineata-ta", "filedintramvai"),
    ("scrisoare-pentru-luni", "vanatordecuvinte"),
    ("orasul-dimineata", "filedintramvai"),
    ("orasul-dimineata", "mireasufletului"),
    ("orasul-dimineata", "noaptedetarziu"),
    ("cuvinte-fara-adresa", "mireasufletului"),
    ("manual", "mireasufletului"),
    ("manual", "noaptedetarziu"),
    ("tramvaiul-21", "mireasufletului"),
    ("tramvaiul-21", "noaptedetarziu"),
    ("geamantan", "vanatordecuvinte"),
    ("doamna-cu-paine", "mireasufletului"),
    ("doamna-cu-paine", "vanatordecuvinte"),
    ("trei-dimineata", "mireasufletului"),
    ("trei-dimineata", "filedintramvai"),
    ("liftul", "vanatordecuvinte"),
    ("exercitiu", "mireasufletului"),
]

# IP-based anonymous likes for realism
ANON_LIKES = [
    ("fereastra-stinsa", "192.0.2.10"),
    ("fereastra-stinsa", "192.0.2.11"),
    ("dimineata-ta", "192.0.2.12"),
    ("orasul-dimineata", "192.0.2.13"),
    ("tramvaiul-21", "192.0.2.14"),
    ("doamna-cu-paine", "192.0.2.15"),
    ("trei-dimineata", "192.0.2.16"),
    ("manual", "192.0.2.17"),
]


BEST_FRIENDS = [
    # (user, friend, position)
    ("mireasufletului", "vanatordecuvinte", 1),
    ("mireasufletului", "filedintramvai", 2),
    ("mireasufletului", "noaptedetarziu", 3),
    ("vanatordecuvinte", "mireasufletului", 1),
    ("vanatordecuvinte", "noaptedetarziu", 2),
    ("filedintramvai", "noaptedetarziu", 1),
    ("filedintramvai", "mireasufletului", 2),
    ("noaptedetarziu", "filedintramvai", 1),
    ("noaptedetarziu", "mireasufletului", 2),
]


FEATURED = [
    # (user, post_slug, position)
    ("mireasufletului", "fereastra-stinsa", 1),
    ("mireasufletului", "dimineata-ta", 2),
    ("vanatordecuvinte", "manual", 1),
    ("vanatordecuvinte", "orasul-dimineata", 2),
    ("filedintramvai", "tramvaiul-21", 1),
    ("filedintramvai", "doamna-cu-paine", 2),
    ("noaptedetarziu", "trei-dimineata", 1),
]


CLUBS = [
    {
        "owner": "mireasufletului",
        "title": "Poeți la ceas târziu",
        "slug": "poeti-la-ceas-tarziu",
        "speciality": "poezie",
        "theme": "Poezie melancolică",
        "motto": "scriem când oraşul tace",
        "description": (
            "Un cerc de poeți care scriu între miezul nopții și primii zori, "
            "împărtășind versuri despre orașe adormite, ferestre stinse și "
            "absențe blânde."
        ),
        "avatar_seed": "club-poeti-melancolici",
        "members": [
            ("vanatordecuvinte", "admin"),
            ("noaptedetarziu", "member"),
        ],
        "featured_post_slug": "fereastra-stinsa",
    },
    {
        "owner": "mireasufletului",
        "title": "Tramvaie și povești",
        "slug": "tramvaie-si-povesti",
        "speciality": "proza_scurta",
        "theme": "Proză urbană scurtă",
        "motto": "fragmente de oraș, șase staţii deodată",
        "description": (
            "Proză scurtă despre oameni întâlniți în tramvaie, lifturi blocate "
            "și brutării din ceaţă. Pentru cei care colecționează detalii."
        ),
        "avatar_seed": "club-tramvaie-povesti",
        "members": [
            ("filedintramvai", "admin"),
        ],
        "featured_post_slug": None,
    },
]


CLUB_BOARD_MESSAGES = [
    # (club_slug, author_username, content, parent_index_in_this_list_or_None, days_ago)
    ("poeti-la-ceas-tarziu", "mireasufletului",
     "Bun venit în club! Aici discutăm liber despre versurile noastre nocturne.", None, 5),
    ("poeti-la-ceas-tarziu", "vanatordecuvinte",
     "Mulțumesc pentru invitație. Am o întrebare despre ritmul versului scurt — cum decideți unde se rupe?", None, 3),
    ("poeti-la-ceas-tarziu", "mireasufletului",
     "De obicei las urechea să decidă: dacă pauza ar fi prea lungă rostită cu voce tare, e semn că versul s-a terminat.", 1, 2),
    ("poeti-la-ceas-tarziu", "noaptedetarziu",
     "La trei dimineața toate versurile par mai scurte decât sunt.", None, 0),
    ("tramvaie-si-povesti", "mireasufletului",
     "Bun venit! Postați aici fragmente, observații, dialoguri scurte auzite în tramvai.", None, 4),
    ("tramvaie-si-povesti", "filedintramvai",
     "Aseară am auzit un copil întrebând unde merg trenurile când nu sunt la lucru. Răspunsul mamei: „acasă, ca toți”. Mă bântuie.", None, 1),
]


AWARDS = [
    {
        "username": "mireasufletului",
        "title": "Poetul lunii",
        "description": "Martie 2026 — votat de cititori",
        "award_date": date(2026, 3, 31),
        "award_type": "community",
    },
    {
        "username": "filedintramvai",
        "title": "Proză scurtă a săptămânii",
        "description": "Pentru „Doamna cu pâine\"",
        "award_date": date(2026, 4, 5),
        "award_type": "writing",
    },
    {
        "username": "vanatordecuvinte",
        "title": "100 de texte publicate",
        "description": "O etapă rotundă — felicitări!",
        "award_date": date(2026, 2, 18),
        "award_type": "milestone",
    },
]


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
        raise SystemExit("DB_USER / DB_PASSWORD missing from env — cannot seed.")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


def _ts(days_ago: int) -> datetime:
    return datetime.now() - timedelta(days=days_ago, hours=days_ago % 4)


def seed(session: Session, *, quiet: bool = False) -> None:
    log = (lambda *_a, **_k: None) if quiet else print

    # ── Users ──────────────────────────────────────────────
    # `mireasufletului` is seeded with active premium so club ownership
    # demos work locally without going through Stripe.
    premium_until = datetime.now(tz=timezone.utc).replace(tzinfo=None) + timedelta(days=365)
    users_by_username: dict[str, models.User] = {}
    for row in AUTHORS:
        u = models.User(
            username=row["username"],
            email=row["email"],
            google_id=row["google_id"],
            subtitle=row["subtitle"],
            avatar_seed=row["avatar_seed"],
            premium_until=premium_until if row["username"] == "mireasufletului" else None,
        )
        session.add(u)
        users_by_username[row["username"]] = u
    session.flush()
    log(f"  Seed: {len(users_by_username)} authors")

    # ── Posts ──────────────────────────────────────────────
    posts_by_slug: dict[str, models.Post] = {}
    for row in POSTS:
        author = users_by_username[row["author"]]
        created = _ts(row["days_ago"])
        p = models.Post(
            user_id=author.id,
            title=row["title"],
            slug=row["slug"],
            content=row["content"],
            category=row["category"],
            view_count=10 + (row["days_ago"] * 7) % 137,
            moderation_status="approved",
            theme_analysis_status="completed",
            created_at=created,
            updated_at=created,
        )
        session.add(p)
        posts_by_slug[row["slug"]] = p
    session.flush()

    log(f"  Seed: {len(posts_by_slug)} posts")

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
