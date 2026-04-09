#!/usr/bin/env python3
"""
Calimara2 — comprehensive test suite.
Run:  python test.py                (all tests)
      python test.py db             (database only)
      python test.py api            (API endpoints only)
      python test.py auth           (auth flow only)
      python test.py security       (security checks only)
      python test.py moderation     (moderation pipeline only)
      python test.py themes         (theme analysis only)
"""
import os
import sys
import asyncio
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
PASS = "\033[92m\u2713\033[0m"
FAIL = "\033[91m\u2717\033[0m"
SKIP = "\033[93m\u2298\033[0m"
BOLD = "\033[1m"
RESET = "\033[0m"

results = {"passed": 0, "failed": 0, "skipped": 0}


def report(ok: bool, label: str, detail: str = ""):
    if ok:
        results["passed"] += 1
        print(f"  {PASS} {label}")
    else:
        results["failed"] += 1
        msg = f"  {FAIL} {label}"
        if detail:
            msg += f"\n      {detail}"
        print(msg)


def skip(label: str, reason: str = ""):
    results["skipped"] += 1
    msg = f"  {SKIP} {label}"
    if reason:
        msg += f"  — {reason}"
    print(msg)


def section(title: str):
    print(f"\n{BOLD}── {title} ──{RESET}")


def server_is_up() -> bool:
    try:
        r = requests.get(f"{BASE_URL}/docs", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


# ═══════════════════════════════════════════
# DATABASE TESTS
# ═══════════════════════════════════════════
def test_database():
    section("Database")
    try:
        from sqlalchemy import create_engine, text
        DB_USER = os.getenv("DB_USER")
        DB_PASSWORD = os.getenv("DB_PASSWORD")
        DB_HOST = os.getenv("DB_HOST", "localhost")
        DB_PORT = os.getenv("DB_PORT", "5432")
        DB_NAME = os.getenv("DB_NAME", "calimara_db")

        url = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        engine = create_engine(url)

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        report(True, "PostgreSQL connection")

        with engine.connect() as conn:
            tables_result = conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            ))
            tables = [r[0] for r in tables_result]

        expected = [
            "best_friends", "comments", "conversations", "featured_posts",
            "likes", "messages", "moderation_logs", "posts", "tags",
            "user_awards", "users"
        ]
        missing = [t for t in expected if t not in tables]
        report(len(missing) == 0, f"All {len(expected)} tables exist",
               f"missing: {missing}" if missing else "")

        with engine.connect() as conn:
            user_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
            post_count = conn.execute(text("SELECT COUNT(*) FROM posts")).scalar()
        report(user_count > 0, f"Sample users loaded ({user_count})")
        report(post_count > 0, f"Sample posts loaded ({post_count})")

        with engine.connect() as conn:
            conn.execute(text("SELECT genre FROM posts LIMIT 1"))
        report(True, "Genre column exists in posts")

        engine.dispose()

    except Exception as e:
        report(False, "Database connection", str(e))


# ═══════════════════════════════════════════
# APP IMPORT TESTS
# ═══════════════════════════════════════════
def test_imports():
    section("App Imports")
    try:
        from app.main import app
        report(True, "app.main imports cleanly")
        report(len(app.routes) > 40, f"Routes registered ({len(app.routes)})")
    except Exception as e:
        report(False, "app.main import", str(e))

    try:
        from app import moderation
        report(moderation.client is not None, "Mistral client initialized")
        report(moderation.MODERATION_ENABLED, "Moderation enabled")
        report(moderation.MODERATION_CLASSIFIER_MODEL != "",
               f"Classifier model: {moderation.MODERATION_CLASSIFIER_MODEL}")
        report(moderation.MODERATION_REVIEW_MODEL != "",
               f"Review model: {moderation.MODERATION_REVIEW_MODEL}")
    except Exception as e:
        report(False, "Moderation module import", str(e))

    try:
        from app import models, crud, schemas, auth, admin, categories
        report(True, "All core modules import")
    except Exception as e:
        report(False, "Core module imports", str(e))


# ═══════════════════════════════════════════
# API ENDPOINT TESTS
# ═══════════════════════════════════════════
def test_api():
    section("API Endpoints")
    if not server_is_up():
        skip("All API tests", "server not running at " + BASE_URL)
        return

    # Public endpoints
    r = requests.get(f"{BASE_URL}/")
    report(r.status_code == 200, f"GET / → {r.status_code}")

    r = requests.get(f"{BASE_URL}/register")
    report(r.status_code == 200, f"GET /register → {r.status_code}")

    r = requests.get(f"{BASE_URL}/api/user/me")
    report(r.status_code == 200, f"GET /api/user/me (unauthenticated) → {r.status_code}")
    data = r.json()
    report(data.get("authenticated") is False, "Unauthenticated user returns authenticated=false")

    r = requests.get(f"{BASE_URL}/api/posts/random")
    report(r.status_code == 200, f"GET /api/posts/random → {r.status_code}")

    r = requests.get(f"{BASE_URL}/api/genres/poezie")
    report(r.status_code == 200, f"GET /api/genres/poezie → {r.status_code}")

    r = requests.get(f"{BASE_URL}/api/tags/suggestions?q=poe")
    report(r.status_code == 200, f"GET /api/tags/suggestions → {r.status_code}")

    r = requests.get(f"{BASE_URL}/api/posts/1/likes/count")
    report(r.status_code == 200, f"GET /api/posts/1/likes/count → {r.status_code}")

    # Auth-required endpoints (should return 401)
    r = requests.get(f"{BASE_URL}/api/posts/archive")
    report(r.status_code == 401, f"GET /api/posts/archive (no auth) → {r.status_code}")

    r = requests.get(f"{BASE_URL}/api/messages/conversations")
    report(r.status_code == 401, f"GET /api/messages/conversations (no auth) → {r.status_code}")

    r = requests.get(f"{BASE_URL}/api/messages/unread-count")
    report(r.status_code == 401, f"GET /api/messages/unread-count (no auth) → {r.status_code}")

    r = requests.post(f"{BASE_URL}/api/posts/", json={"title": "test", "content": "test"})
    report(r.status_code == 401, f"POST /api/posts/ (no auth) → {r.status_code}")

    # Moderator-only endpoints (should return 401)
    r = requests.get(f"{BASE_URL}/api/moderation/stats")
    report(r.status_code == 401, f"GET /api/moderation/stats (no auth) → {r.status_code}")

    # 404 on removed debug routes
    r = requests.get(f"{BASE_URL}/api/debug")
    report(r.status_code in (404, 422), f"GET /api/debug (removed) → {r.status_code}")

    r = requests.get(f"{BASE_URL}/api/debug/session")
    report(r.status_code in (404, 422), f"GET /api/debug/session (removed) → {r.status_code}")

    # CORS headers
    r = requests.options(f"{BASE_URL}/api/user/me", headers={
        "Origin": "https://test.calimara.ro",
        "Access-Control-Request-Method": "GET"
    })
    has_cors = "access-control-allow-origin" in r.headers
    report(has_cors, "CORS headers present for *.calimara.ro")


# ═══════════════════════════════════════════
# AUTH FLOW TESTS
# ═══════════════════════════════════════════
def test_auth():
    section("Auth Flow")
    if not server_is_up():
        skip("All auth tests", "server not running at " + BASE_URL)
        return

    r = requests.get(f"{BASE_URL}/auth/google", allow_redirects=False)
    report(r.status_code in (302, 307, 500),
           f"GET /auth/google → {r.status_code} (redirect or config error)")

    r = requests.get(f"{BASE_URL}/api/logout", allow_redirects=False)
    report(r.status_code in (302, 307), f"GET /api/logout → {r.status_code} (redirect)")

    r = requests.get(f"{BASE_URL}/auth/setup", allow_redirects=False)
    report(r.status_code in (302, 307), f"GET /auth/setup (no session) → {r.status_code} (redirect)")


# ═══════════════════════════════════════════
# SECURITY TESTS
# ═══════════════════════════════════════════
def test_security():
    section("Security")
    if not server_is_up():
        skip("All security tests", "server not running at " + BASE_URL)
        return

    for path in ["/debug/login-form", "/api/debug", "/api/debug/session",
                 "/api/debug/session/set", "/api/debug/user/test",
                 "/api/moderation/test-simple", "/api/moderation/test-create-content"]:
        r = requests.get(f"{BASE_URL}{path}")
        report(r.status_code in (404, 405, 422),
               f"Debug endpoint removed: {path} → {r.status_code}")

    r = requests.get(f"{BASE_URL}/")
    session_cookie = r.cookies.get("session")
    if session_cookie:
        report(True, "Session cookie set on response")
    else:
        skip("Session cookie flags", "no session cookie in response")

    statuses = []
    for _ in range(7):
        try:
            r = requests.get(f"{BASE_URL}/auth/google", allow_redirects=False, timeout=5)
            statuses.append(r.status_code)
        except Exception:
            statuses.append(0)
    has_rate_limit = 429 in statuses
    report(has_rate_limit, f"Rate limiting on /auth/google (got 429: {has_rate_limit})",
           f"statuses: {statuses[-3:]}")


# ═══════════════════════════════════════════
# MODERATION — CONFIGURATION
# ═══════════════════════════════════════════
def test_moderation_config():
    section("Moderation — Configuration")
    from app import moderation

    report(moderation.MISTRAL_API_KEY != "", "MISTRAL_API_KEY is set")
    report(moderation.MODERATION_ENABLED, "MODERATION_ENABLED is True")
    report(moderation.client is not None, "Mistral client initialized")
    report(moderation.MODERATION_CLASSIFIER_MODEL != "",
           f"Classifier model: {moderation.MODERATION_CLASSIFIER_MODEL}")
    report(moderation.MODERATION_REVIEW_MODEL != "",
           f"Review model: {moderation.MODERATION_REVIEW_MODEL}")
    report(0 < moderation.MODERATION_THRESHOLD < 1,
           f"Threshold: {moderation.MODERATION_THRESHOLD}")


# ═══════════════════════════════════════════
# MODERATION — ROMANIAN PATTERN MATCHING
# ═══════════════════════════════════════════
def test_moderation_patterns():
    section("Moderation — Romanian Pattern Matching")
    from app.moderation import contains_romanian_profanity, contains_romanian_hate_speech

    has, score = contains_romanian_profanity("Esti un idiot si un prost!")
    report(has is True, f"Detects Romanian profanity (score={score:.2f})")

    has, score = contains_romanian_profanity("Aceasta este o poezie frumoasa.")
    report(has is False, "Clean text → no profanity detected")

    has, score = contains_romanian_hate_speech("Toti tiganii sunt hoti.")
    report(has is True, f"Detects Romanian hate speech (score={score:.2f})")

    has, score = contains_romanian_hate_speech("Iubesc literatura romana.")
    report(has is False, "Clean text → no hate speech detected")


# ═══════════════════════════════════════════
# MODERATION — PASS 1 CLASSIFIER
# ═══════════════════════════════════════════
def test_moderation_pass1():
    section("Moderation — Pass 1 (Mistral Classifier)")
    from app.moderation import classify_content, client

    if not client:
        skip("All classifier tests", "Mistral client not configured")
        return

    safe_text = "Aceasta este o poezie frumoasa despre natura din Romania."
    t0 = time.time()
    result = classify_content(safe_text)
    elapsed = time.time() - t0
    report("category_scores" in result, f"Returns category_scores (latency: {elapsed:.2f}s)")
    report("categories" in result, "Returns categories (boolean flags)")
    report("is_clean" in result, f"Returns is_clean flag: {result.get('is_clean')}")
    report(result.get("is_clean") is True, "Safe Romanian text → is_clean=True")

    expected_cats = [
        "sexual", "hate_and_discrimination", "violence_and_threats",
        "dangerous_and_criminal_content", "selfharm", "health",
        "financial", "law", "pii", "jailbreaking"
    ]
    scores = result.get("category_scores", {})
    present = [c for c in expected_cats if c in scores]
    report(len(present) == len(expected_cats),
           f"All {len(expected_cats)} categories returned ({len(present)} found)")

    toxic_text = "Du-te dracului, esti un idiot si iti doresc sa mori!"
    result_toxic = classify_content(toxic_text)
    report(result_toxic.get("is_clean") is False, "Toxic Romanian text → is_clean=False")
    flagged = result_toxic.get("flagged_categories", {})
    report(len(flagged) > 0, f"Flagged categories: {list(flagged.keys())}")

    hate_text = "Toti tiganii ar trebui deportati, sunt subumani."
    result_hate = classify_content(hate_text)
    report(result_hate.get("is_clean") is False, "Hate speech → is_clean=False")
    hate_flagged = result_hate.get("flagged_categories", {})
    report("hate_and_discrimination" in hate_flagged,
           f"hate_and_discrimination flagged: {'hate_and_discrimination' in hate_flagged}")


# ═══════════════════════════════════════════
# MODERATION — PASS 2 LLM REVIEW
# ═══════════════════════════════════════════
def test_moderation_pass2():
    section("Moderation — Pass 2 (Mistral Small LLM Review)")
    from app.moderation import review_content_with_llm, client

    if not client:
        skip("All LLM review tests", "Mistral client not configured")
        return

    literary_text = (
        "Moartea vine linistita, ca o umbra peste campie.\n"
        "Imi strange sufletul in gheare si ma poarta spre tacere.\n"
        "Dar eu nu ma tem de ea, caci in versuri voi trai mereu."
    )
    flagged = {"violence_and_threats": 0.6}
    ro_signals = {"profanity_detected": False, "profanity_score": 0.0,
                  "hate_speech_detected": False, "hate_speech_score": 0.0}

    t0 = time.time()
    verdict = review_content_with_llm(literary_text, flagged, ro_signals)
    elapsed = time.time() - t0
    report("safe" in verdict, f"Returns 'safe' field (latency: {elapsed:.2f}s)")
    report("reason" in verdict, "Returns 'reason' field")
    report(verdict.get("safe") is True, "Dark poetry → safe=True (literary context)")
    if "reason" in verdict:
        print(f"      Reason: {verdict['reason'][:100]}")

    toxic_text = "Te voi gasi si te voi bate pana nu te mai misti. Esti mort."
    flagged_toxic = {"violence_and_threats": 0.9}
    verdict_toxic = review_content_with_llm(toxic_text, flagged_toxic, ro_signals)
    report(verdict_toxic.get("safe") is False, "Direct threat → safe=False")
    if "reason" in verdict_toxic:
        print(f"      Reason: {verdict_toxic['reason'][:100]}")


# ═══════════════════════════════════════════
# MODERATION — FULL PIPELINE
# ═══════════════════════════════════════════
def test_moderation_pipeline():
    section("Moderation — Full Pipeline (end-to-end)")
    from app.moderation import _moderate_text, moderate_post, moderate_comment, ModerationStatus, client

    if not client:
        skip("All pipeline tests", "Mistral client not configured")
        return

    # Safe content → approved by Pass 1
    safe_text = "Primavara vine cu flori si speranta. Copiii alearga prin gradini."
    result = asyncio.run(_moderate_text(safe_text))
    report(result.status == ModerationStatus.APPROVED, f"Safe text → {result.status.value}")
    report("Pass 1" in result.reason, f"Approved at Pass 1: {result.reason[:80]}")

    # Literary dark content → Pass 1 may flag, Pass 2 should approve
    dark_poetry = (
        "Sangele curge pe peretii gandurilor mele,\n"
        "Ca o ploaie rosie peste orasul adormit.\n"
        "Violenta sta ascunsa in metafore —\n"
        "Dar eu o transform in arta, nu in fapte."
    )
    result = asyncio.run(_moderate_text(dark_poetry))
    report(result.status == ModerationStatus.APPROVED, f"Dark poetry → {result.status.value}")
    if result.status == ModerationStatus.APPROVED and "Pass 2" in result.reason:
        print(f"      (Approved at Pass 2 — literary context recognized)")

    # Genuinely toxic → both passes reject → FLAGGED
    toxic_text = (
        "Te voi gasi la tine acasa si iti voi rupe capul. "
        "Esti un gunoi uman. Mori!"
    )
    result = asyncio.run(_moderate_text(toxic_text))
    report(result.status == ModerationStatus.FLAGGED, f"Toxic content → {result.status.value}")
    if result.details:
        flagged_cats = result.details.get("pass1_flagged", {})
        if flagged_cats:
            print(f"      Pass 1 flagged: {list(flagged_cats.keys())}")
        verdict = result.details.get("pass2_verdict", {})
        if verdict:
            print(f"      Pass 2 reason: {verdict.get('reason', 'N/A')[:80]}")

    # Post moderation
    result = asyncio.run(moderate_post(
        "O seara de toamna",
        "Frunzele cad usor pe aleea din parc. Batranul sta pe banca si priveste apusul."
    ))
    report(result.status == ModerationStatus.APPROVED, f"Normal post → {result.status.value}")

    # Comment moderation
    result = asyncio.run(moderate_comment("Ce frumos ai scris! Felicitari!"))
    report(result.status == ModerationStatus.APPROVED, f"Normal comment → {result.status.value}")


# ═══════════════════════════════════════════
# MODERATION — ERROR HANDLING
# ═══════════════════════════════════════════
def test_moderation_errors():
    section("Moderation — Error Handling & Edge Cases")
    from app.moderation import _moderate_text, ModerationStatus

    result = asyncio.run(_moderate_text(""))
    report(result.status == ModerationStatus.APPROVED, f"Empty text → {result.status.value} (fail-safe)")

    result = asyncio.run(_moderate_text("da"))
    report(result.status == ModerationStatus.APPROVED, f"Very short text → {result.status.value}")

    result = asyncio.run(_moderate_text("Cafe ☕ Romania — tara frumoasa! «literatura»"))
    report(result.status == ModerationStatus.APPROVED, f"Unicode/emoji text → {result.status.value}")


# ═══════════════════════════════════════════
# THEME ANALYSIS — CONFIGURATION
# ═══════════════════════════════════════════
def test_theme_config():
    section("Theme Analysis — Configuration")
    from app import theme_analysis

    report(theme_analysis.THEME_ANALYSIS_ENABLED, "THEME_ANALYSIS_ENABLED is True")
    report(theme_analysis.THEME_ANALYSIS_MODEL != "",
           f"Theme analysis model: {theme_analysis.THEME_ANALYSIS_MODEL}")
    report(theme_analysis.client is not None, "Mistral client initialized for theme analysis")


# ═══════════════════════════════════════════
# THEME ANALYSIS — LLM EXTRACTION
# ═══════════════════════════════════════════
def test_theme_extraction():
    section("Theme Analysis — LLM Extraction")
    from app.theme_analysis import extract_themes_from_text, client

    if not client:
        skip("All theme extraction tests", "Mistral client not configured")
        return

    love_poem = (
        "Te iubesc cu fiece zi mai mult,\n"
        "Ca un rau ce creste din topirea zapezii.\n"
        "Inima mea bate doar pentru tine,\n"
        "Si fiecare gand e o declaratie de dragoste."
    )
    t0 = time.time()
    result = extract_themes_from_text(love_poem, [], [])
    elapsed = time.time() - t0
    report(isinstance(result, dict), f"Returns dict (latency: {elapsed:.2f}s)")
    report(len(result.get("themes", [])) > 0, f"Love poem themes: {result.get('themes', [])}")
    report(len(result.get("feelings", [])) > 0, f"Love poem feelings: {result.get('feelings', [])}")
    report(all(isinstance(t, str) for t in result.get("themes", [])), "All themes are strings")
    report(all(isinstance(f, str) for f in result.get("feelings", [])), "All feelings are strings")

    nature_poem = (
        "Padurea sopteste in amurg,\n"
        "Frunzele danseaza in vant.\n"
        "Pasarile canta ultimul cantec,\n"
        "Iar soarele se ascunde dupa munti."
    )
    result2 = extract_themes_from_text(nature_poem, [], [])
    report(len(result2.get("themes", [])) > 0, f"Nature poem themes: {result2.get('themes', [])}")
    report(len(result2.get("feelings", [])) > 0, f"Nature poem feelings: {result2.get('feelings', [])}")

    # Test with existing terms — should prefer reusing them
    result3 = extract_themes_from_text(love_poem, ["dragoste", "natura", "timp"], ["iubire", "bucurie", "tristete"])
    report(isinstance(result3, dict), "Works with existing terms provided")
    report(len(result3.get("themes", [])) > 0, f"With existing terms — themes: {result3.get('themes', [])}")

    # Test max 5 constraint
    report(len(result.get("themes", [])) <= 5, f"Themes count <= 5 ({len(result.get('themes', []))})")
    report(len(result.get("feelings", [])) <= 5, f"Feelings count <= 5 ({len(result.get('feelings', []))})")


# ═══════════════════════════════════════════
# THEME ANALYSIS — CRUD FUNCTIONS
# ═══════════════════════════════════════════
def test_theme_db_functions():
    section("Theme Analysis — CRUD Functions")
    try:
        from app.database import SessionLocal
        from app import crud

        db = SessionLocal()
        try:
            themes = crud.get_distinct_themes(db)
            report(isinstance(themes, list), f"get_distinct_themes returns list ({len(themes)} themes)")
            if themes:
                report(all(isinstance(t, str) for t in themes), f"All themes are strings: {themes[:5]}")

            feelings = crud.get_distinct_feelings(db)
            report(isinstance(feelings, list), f"get_distinct_feelings returns list ({len(feelings)} feelings)")
            if feelings:
                report(all(isinstance(f, str) for f in feelings), f"All feelings are strings: {feelings[:5]}")

            # Test that sample data has themes populated
            report(len(themes) > 0, "Sample posts have themes populated")
            report(len(feelings) > 0, "Sample posts have feelings populated")
        finally:
            db.close()
    except Exception as e:
        report(False, "Theme CRUD functions", str(e))


# ═══════════════════════════════════════════
# THEME ANALYSIS — DATABASE SCHEMA
# ═══════════════════════════════════════════
def test_theme_database():
    section("Theme Analysis — Database Schema")
    try:
        from sqlalchemy import create_engine, text
        DB_USER = os.getenv("DB_USER")
        DB_PASSWORD = os.getenv("DB_PASSWORD")
        DB_HOST = os.getenv("DB_HOST", "localhost")
        DB_PORT = os.getenv("DB_PORT", "5432")
        DB_NAME = os.getenv("DB_NAME", "calimara_db")

        url = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        engine = create_engine(url)

        with engine.connect() as conn:
            # Check columns exist
            cols = conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'posts' AND column_name IN ('themes', 'feelings', 'theme_analysis_status')"
            ))
            col_names = [r[0] for r in cols]
            report("themes" in col_names, "Column 'themes' exists in posts table")
            report("feelings" in col_names, "Column 'feelings' exists in posts table")
            report("theme_analysis_status" in col_names, "Column 'theme_analysis_status' exists in posts table")

            # Check GIN indexes exist
            indexes = conn.execute(text(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'posts' "
                "AND indexname IN ('idx_posts_themes', 'idx_posts_feelings', 'idx_posts_theme_analysis_status')"
            ))
            idx_names = [r[0] for r in indexes]
            report("idx_posts_themes" in idx_names, "GIN index on themes exists")
            report("idx_posts_feelings" in idx_names, "GIN index on feelings exists")
            report("idx_posts_theme_analysis_status" in idx_names, "Index on theme_analysis_status exists")

            # Verify sample data has themes
            themed_count = conn.execute(text(
                "SELECT COUNT(*) FROM posts WHERE theme_analysis_status = 'completed' AND themes != '[]'::jsonb"
            )).scalar()
            report(themed_count > 0, f"Sample posts with themes: {themed_count}")

        engine.dispose()
    except Exception as e:
        report(False, "Theme database schema", str(e))


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════
def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "all"

    print("=" * 50)
    print("  CALIMARA2 TEST SUITE")
    print("=" * 50)

    tests = {
        "db": test_database,
        "imports": test_imports,
        "api": test_api,
        "auth": test_auth,
        "security": test_security,
        "moderation": [
            test_moderation_config,
            test_moderation_patterns,
            test_moderation_pass1,
            test_moderation_pass2,
            test_moderation_pipeline,
            test_moderation_errors,
        ],
        "themes": [
            test_theme_config,
            test_theme_extraction,
            test_theme_db_functions,
            test_theme_database,
        ],
    }

    if target == "all":
        for key, fn in tests.items():
            if isinstance(fn, list):
                for sub in fn:
                    sub()
            else:
                fn()
    elif target in tests:
        fn = tests[target]
        if isinstance(fn, list):
            for sub in fn:
                sub()
        else:
            fn()
    else:
        print(f"Unknown target: {target}")
        print(f"Available: {', '.join(tests.keys())}, all")
        sys.exit(1)

    print("\n" + "=" * 50)
    total = results["passed"] + results["failed"] + results["skipped"]
    print(f"  {results['passed']} passed, {results['failed']} failed, {results['skipped']} skipped  ({total} total)")
    print("=" * 50)
    sys.exit(1 if results["failed"] > 0 else 0)


if __name__ == "__main__":
    main()
