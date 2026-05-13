#!/usr/bin/env python3
"""
Populate the database with sample Romanian content for local development.

Runs after `run.py`'s `init_database()` has produced an empty schema. Creates
two accounts and ten posts: five Ion Creangă prose entries on the tier-3
premium gocandan account and five Mihai Eminescu poems on the dangocan account.

Invocation:
    python scripts/seed.py

Or called automatically at the end of `run.py`'s init step.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
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
        "username": "dangocan",
        "email": "dangocan@outlook.com",
        "google_id": "seed-google-dangocan",
        "subtitle": "Mihai Eminescu",
        "avatar_seed": "dangocan-eminescu",
    },
]


POSTS = [
    # ── gocandan — Ion Creangă ──────────────────────────────
    {
        "author": "gocandan",
        "title": "Punguța cu doi bani",
        "slug": "punguta-cu-doi-bani",
        "category": "proza_scurta",
        "days_ago": 2,
        "content": (
            "Ion Creangă\n\n"
            "Titlu: Punguța cu doi bani\n\n"
            "Era odată o babă și un moșneag. Baba avea o găină, iar moșneagul "
            "avea un cocoș. Găina babei făcea ouă în fiecare zi, pe când "
            "cocoșul moșneagului nu aducea nimic în casă, lucru pentru care "
            "baba îl tot ocăra pe bietul moșneag.\n\n"
            "Alungat de acasă, cocoșul pleacă în lume și găsește o punguță cu "
            "doi bani. De aici începe drumul lui plin de încăpățânare și noroc."
        ),
    },
    {
        "author": "gocandan",
        "title": "Ursul păcălit de vulpe",
        "slug": "ursul-pacalit-de-vulpe",
        "category": "proza_scurta",
        "days_ago": 6,
        "content": (
            "Ion Creangă\n\n"
            "Titlu: Ursul păcălit de vulpe\n\n"
            "Vulpea, șireată cum o știe toată lumea, se preface moartă în drum "
            "și ajunge în carul unui țăran încărcat cu pește. Când omul nu se "
            "uită, ea aruncă peștii jos unul câte unul, apoi sare din car și "
            "își strânge prada.\n\n"
            "Ursul o găsește ospătându-se și cere și el pește. Vulpea îl învață "
            "să-și bage coada în baltă, iar ursul, lacom și credul, plătește "
            "scump ascultarea."
        ),
    },
    {
        "author": "gocandan",
        "title": "Capra cu trei iezi",
        "slug": "capra-cu-trei-iezi",
        "category": "proza_scurta",
        "days_ago": 14,
        "content": (
            "Ion Creangă\n\n"
            "Titlu: Capra cu trei iezi\n\n"
            "Capra pleacă după hrană și își lasă iezii singuri acasă, poruncindu-le "
            "să nu deschidă ușa nimănui până nu vor auzi cântecul ei. Lupul "
            "pândește vorbele, își subțiază glasul și încearcă să-i păcălească.\n\n"
            "Doi dintre iezi uită sfatul mamei și cad în cursă. Cel mic se ascunde "
            "bine, iar întoarcerea caprei schimbă frica în judecată aspră."
        ),
    },
    {
        "author": "gocandan",
        "title": "Povestea unui om leneș",
        "slug": "povestea-unui-om-lenes",
        "category": "proza_scurta",
        "days_ago": 20,
        "content": (
            "Ion Creangă\n\n"
            "Titlu: Povestea unui om leneș\n\n"
            "Se spune că era într-un sat un om atât de leneș, încât nici mâncarea "
            "nu și-ar fi dus-o singur la gură dacă ar fi găsit pe altcineva s-o "
            "facă pentru el. Sătenii, sătui de neputința lui, hotărăsc să-l ducă "
            "departe de sat.\n\n"
            "Pe drum, o femeie miloasă vrea să-i dea posmagi. Leneșul întreabă "
            "dacă sunt muiați, iar răspunsul lui îi lămurește pe toți."
        ),
    },
    {
        "author": "gocandan",
        "title": "Dănilă Prepeleac",
        "slug": "danila-prepeleac",
        "category": "proza_scurta",
        "days_ago": 28,
        "content": (
            "Ion Creangă\n\n"
            "Titlu: Dănilă Prepeleac\n\n"
            "Dănilă pornește la târg cu doi boi zdraveni și se întoarce, după "
            "schimburi tot mai păguboase, aproape cu nimic. Fratele său îl "
            "mustră, dar Dănilă nu se leapădă de felul lui năuc și încăpățânat.\n\n"
            "Când ajunge însă față în față cu dracii, nepriceputul de până atunci "
            "găsește destulă istețime cât să-i încurce pe toți."
        ),
    },
    # ── dangocan — Mihai Eminescu ───────────────────────────
    {
        "author": "dangocan",
        "title": "Somnoroase păsărele",
        "slug": "somnoroase-pasarele",
        "category": "poezie",
        "days_ago": 1,
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
        raise SystemExit("DB_USER / DB_PASSWORD missing from env — cannot seed.")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


def _ts(days_ago: int) -> datetime:
    return datetime.now() - timedelta(days=days_ago, hours=days_ago % 4)


def seed(session: Session, *, quiet: bool = False) -> None:
    log = (lambda *_a, **_k: None) if quiet else print

    # ── Users ──────────────────────────────────────────────
    users_by_username: dict[str, models.User] = {}
    for row in AUTHORS:
        premium_until = None
        if row.get("premium_until_days"):
            premium_until = (
                datetime.now(tz=timezone.utc).replace(tzinfo=None)
                + timedelta(days=row["premium_until_days"])
            )
        u = models.User(
            username=row["username"],
            email=row["email"],
            google_id=row["google_id"],
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
