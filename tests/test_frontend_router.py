import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_route_view_forwards_auth_loaded_to_public_routes():
    source = (ROOT / "frontend" / "src" / "app" / "router.jsx").read_text(encoding="utf-8")

    assert "export function RouteView({ route, user, authLoaded" in source
    assert "authLoaded={authLoaded}" in source


def _frontend_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "frontend" / "src").rglob("*")
        if path.suffix in {".js", ".jsx"}
    )


def test_frontend_copy_keeps_common_romanian_diacritics():
    source = "\n".join(
        [
            _frontend_source(),
            (ROOT / "app" / "moderation.py").read_text(encoding="utf-8"),
            (ROOT / "app" / "routers" / "admin_routes.py").read_text(encoding="utf-8"),
            (ROOT / "app" / "routers" / "auth_routes.py").read_text(encoding="utf-8"),
            (ROOT / "scripts" / "browser_smoke.mjs").read_text(encoding="utf-8"),
        ]
    )
    forbidden = {
        "Sterge": "Șterge",
        "Stergi": "Ștergi",
        "Editeaza": "Editează",
        "Creeaza": "Creează",
        "Converteste": "Convertește",
        "Postari": "Postări",
        "Postare noua": "Postare nouă",
        "Serii si volume": "Serii și volume",
        "Dezvoltat si hostat": "Dezvoltat și hostat",
        "in Uniunea Europeana": "în Uniunea Europeană",
        "Selecteaza una din optiunile": "Selectează una din opțiunile",
        "Textul a fost trimis in Franta": "Textul a fost trimis în Franța",
        "se intoarce imediat si va aparea": "se întoarce imediat și va apărea",
        "Daca Mistral": "Dacă Mistral",
        "catre un moderator uman": "către un moderator uman",
        "Toti utilizatorii": "Toți utilizatorii",
        "Pagina nu a putut fi afisata": "Pagina nu a putut fi afișată",
        "prefixelor Calimara": "prefixelor Călimara",
        "obiectelor Calimara": "obiectelor Călimara",
        "pentru Calimara": "pentru Călimara",
        "Sesiune stearsa": "Sesiune ștearsă",
        "Descriere optionala": "Descriere opțională",
        "Raporteaza": "Raportează",
        "Autentifica-te": "Autentifică-te",
        "Inapoi": "Înapoi",
        "Inchide": "Închide",
        "Setari": "Setări",
        "Cauta": "Caută",
        "Adauga": "Adaugă",
        "Raspuns": "Răspuns",
        "Discutie": "Discuție",
        "Continut": "Conținut",
        "Notificari": "Notificări",
        "Vizualizari": "Vizualizări",
        "Conversatie": "Conversație",
    }

    missing = {bad: good for bad, good in forbidden.items() if bad in source}

    assert missing == {}


def _router_source() -> str:
    return (ROOT / "frontend" / "src" / "app" / "router.jsx").read_text(encoding="utf-8")


def _constants_source() -> str:
    return (ROOT / "frontend" / "src" / "app" / "constants.js").read_text(encoding="utf-8")


def _route_component_names() -> set[str]:
    return set(re.findall(r"^\s*([A-Za-z0-9_]+):\s*lazy", _router_source(), re.MULTILINE))


def _route_return_names() -> set[str]:
    return set(re.findall(r'return \{ name: "([^"]+)"', _router_source()))


def _route_name_set_constant(name: str) -> set[str]:
    match = re.search(rf"{name} = new Set\(\[(.*?)\]\)", _constants_source(), re.DOTALL)
    assert match is not None
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def test_invitation_setup_uses_radio_cards_and_password_manager_hints():
    source = (ROOT / "frontend" / "src" / "routes" / "auth.jsx").read_text(encoding="utf-8")
    api_auth_source = (ROOT / "frontend" / "src" / "api" / "auth.js").read_text(encoding="utf-8")
    docs = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")
    setup_view = source.split("function AuthSetupView", 1)[1].split("function AuthCallbackView", 1)[0]
    invite_view = source.split("function InvitationView", 1)[1].split("export default function AuthRoute", 1)[0]

    assert 'name="blog_name"' in setup_view
    assert 'autoComplete="nickname"' in setup_view
    assert "addSetupDiacritics" in source
    assert 'api.post("/api/autentificare/configurare/diacritice", data)' in api_auth_source
    assert "Adaugă automat diacritice în descriere?" in setup_view
    assert "Verifică diacriticele" in setup_view
    assert "Imaginea de profil și coperta pot fi modificate ulterior din setările profilului." in setup_view
    assert 'type="button"' in setup_view
    assert "aria-pressed={selected}" in setup_view
    assert 'name="setup-avatar-choice"' not in setup_view
    assert 'name="setup-cover-choice"' not in setup_view
    assert "onClick={() => setAvatarChoice(option.key)}" in setup_view
    assert "onClick={() => setCoverChoice(option.key)}" in setup_view
    assert "avatarPreviewUrl(option.seed)" in setup_view
    assert "coverPreviewUrl(option.seed, 640)" in setup_view
    assert "usernameSeed" not in setup_view
    assert "GeneratedChoicePreview" in setup_view
    assert "avatar_seed: avatarSeed" in setup_view
    assert "cover_seed: coverSeed" in setup_view
    assert "/api/autentificare/configurare/diacritice" in docs
    assert "return_to către pagina invitației" in docs

    assert 'className="form-stack invite-password-form"' in invite_view
    assert "window.location.replace(blogUrl(user.username))" in invite_view
    assert "Te trimitem către Călimara ta." in invite_view
    assert 'autoComplete="off"' in invite_view
    assert 'name="username"' in invite_view
    assert 'autoComplete="username"' in invite_view
    assert 'name="invite-temporary-password"' in invite_view
    assert 'autoComplete="one-time-code"' in invite_view
    assert 'data-1p-ignore="true"' in invite_view
    assert 'data-lpignore="true"' in invite_view


def test_diacritics_composers_offer_raw_submit_fallback():
    sources = {
        "auth": (ROOT / "frontend" / "src" / "routes" / "auth.jsx").read_text(encoding="utf-8"),
        "create": (ROOT / "frontend" / "src" / "routes" / "create.jsx").read_text(encoding="utf-8"),
        "forum": (ROOT / "frontend" / "src" / "routes" / "forum.jsx").read_text(encoding="utf-8"),
        "messages": (ROOT / "frontend" / "src" / "routes" / "messages.jsx").read_text(encoding="utf-8"),
        "profile": (ROOT / "frontend" / "src" / "routes" / "profile.jsx").read_text(encoding="utf-8"),
        "profile_settings": (ROOT / "frontend" / "src" / "routes" / "profile-settings.jsx").read_text(encoding="utf-8"),
        "post_actions": (ROOT / "frontend" / "src" / "app" / "post-actions.jsx").read_text(encoding="utf-8"),
        "theatre": (ROOT / "frontend" / "src" / "routes" / "theatre.jsx").read_text(encoding="utf-8"),
    }

    expected = {
        "auth": "Finalizează fără Diacritice",
        "create": "Publică fără Diacritice",
        "forum": "Publică fără Diacritice",
        "messages": "Trimite fără Diacritice",
        "profile": "Trimite fără Diacritice",
        "profile_settings": "Salvează fără Diacritice",
        "post_actions": "Trimite fără Diacritice",
        "theatre": "Pasul următor fără Diacritice",
    }

    missing = {name: label for name, label in expected.items() if label not in sources[name]}

    assert missing == {}


def test_literal_frontend_links_have_router_entries():
    frontend_source = _frontend_source()
    router_source = _router_source()
    literal_links = set(re.findall(r"(?:mainPath|authorPath)\([^)]*\"(/[^\"]+)\"", frontend_source))
    literal_links.update(
        path
        for path in re.findall(r"href=\"(/[^\"]+)\"", frontend_source)
        if not path.startswith("/api/")
    )

    exact_routes = set(re.findall(r'path === "([^"]+)"', router_source))
    prefix_routes = set(re.findall(r'path\.startsWith\("([^"]+)"\)', router_source))
    missing = sorted(
        path
        for path in literal_links
        if path not in exact_routes and not any(path == prefix or path.startswith(f"{prefix}/") for prefix in prefix_routes)
    )

    assert missing == []


def test_route_components_and_route_names_stay_in_sync():
    components = _route_component_names()
    returned_names = _route_return_names()

    assert sorted(returned_names - components) == []
    assert sorted(components - returned_names - {"notFound"}) == []


def test_route_name_constants_reference_known_routes():
    known_routes = _route_component_names()
    unknown = {}
    for constant_name in ("PROTECTED_ROUTES", "AUTHOR_SUBDOMAIN_ROUTES", "AD_SUPPORTED_ROUTES"):
        missing = sorted(_route_name_set_constant(constant_name) - known_routes)
        if missing:
            unknown[constant_name] = missing

    assert unknown == {}


def test_referrals_route_surfaces_reward_progress_fields():
    router_source = _router_source()
    constants_source = _constants_source()
    page_source = (ROOT / "frontend" / "src" / "routes" / "referrals.jsx").read_text(encoding="utf-8")
    layout_source = (ROOT / "frontend" / "src" / "app" / "layout.jsx").read_text(encoding="utf-8")
    premium_source = (ROOT / "frontend" / "src" / "routes" / "premium.jsx").read_text(encoding="utf-8")

    assert 'referrals: lazy(() => import("../routes/referrals.jsx"))' in router_source
    assert 'path === "/invitatii"' in router_source
    assert '"referrals"' in constants_source
    assert 'mainPath("/invitatii")' not in layout_source
    assert 'href={mainPath("/invitatii")}>Detalii</a>' in premium_source
    assert "fetchMyReferrals" in page_source
    assert "post_count" in page_source
    assert "gologani_balance" in page_source
    assert "remaining_gologani" in page_source
    assert "progress_percent" in page_source


def test_audio_playlists_route_menu_and_player_wiring():
    router_source = _router_source()
    constants_source = _constants_source()
    layout_source = (ROOT / "frontend" / "src" / "app" / "layout.jsx").read_text(encoding="utf-8")
    page_source = (ROOT / "frontend" / "src" / "routes" / "playlists.jsx").read_text(encoding="utf-8")
    player_source = (ROOT / "frontend" / "src" / "app" / "listening-player.jsx").read_text(encoding="utf-8")

    assert 'playlists: lazy(() => import("../routes/playlists.jsx"))' in router_source
    assert 'path === "/playlisturi"' in router_source
    assert '"playlists"' in constants_source
    assert 'mainPath("/playlisturi")' in layout_source
    assert "fetchAudioPlaylistPlayback" in player_source
    assert "onStartPlaylistListening" in page_source
    assert "has_author_audio_access" in page_source
    assert "Selectează una din opțiunile de mai sus" in player_source
    assert "disabled={loading}" in player_source
    assert "disabled={loading || (!track && !error && !activeMode)}" not in player_source


def test_post_actions_expose_rapsod_playlist_modal_for_ready_audio():
    source = (ROOT / "frontend" / "src" / "app" / "post-actions.jsx").read_text(encoding="utf-8")

    assert "Adaugă în playlist" in source
    assert "fetchAudioPlaylists" in source
    assert "createAudioPlaylist" in source
    assert "addPostToAudioPlaylist" in source
    assert "user?.has_author_audio_access && audioAvailable" in source
    assert "playlistModalOpen" in source


def test_profile_play_button_uses_author_scoped_audio_overlay():
    source = (ROOT / "frontend" / "src" / "routes" / "profile.jsx").read_text(encoding="utf-8")
    api_source = (ROOT / "frontend" / "src" / "api" / "audio.js").read_text(encoding="utf-8")

    assert "ProfileAudioPlayButton" in source
    assert "FiPlay" in source
    assert "profile-audio-row" in source
    assert "Ascultă opere de acest autor" in source
    assert "ready_audio_count" in source
    assert "onStartAuthorListening?.(owner.username)" in source
    assert "Necesită abonament Cronicar sau Rapsod" in source
    assert "fetchAuthorListeningRandomAudio" in api_source


def test_profile_award_chips_wrap_at_word_boundaries():
    source = (ROOT / "frontend" / "src" / "routes" / "profile.jsx").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")

    assert 'className="profile-chip-label"' in source
    assert ".profile-chip-label {" in styles
    assert "overflow-wrap: normal;" in styles
    assert "word-break: normal;" in styles
    assert "hyphens: none;" in styles


def test_profile_page_keeps_full_archive_on_all_works_route():
    source = (ROOT / "frontend" / "src" / "routes" / "profile.jsx").read_text(encoding="utf-8")
    blog_view = source.split("function BlogView", 1)[1].split("function AllWorksView", 1)[0]
    all_works_view = source.split("function AllWorksView", 1)[1].split("function FollowUserCard", 1)[0]
    docs = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")

    assert "ProfilePromotions" in blog_view
    assert "ProfilePromotionEditor" in blog_view
    assert "data.latest_posts" not in blog_view
    assert "data.all_posts" not in blog_view
    assert "uniquePosts" not in blog_view
    assert "fetchAllWorks(username)" in all_works_view
    assert "data?.posts || []" in all_works_view
    assert "Toate operele" in all_works_view
    assert "fetchPromotions" in source
    assert "searchPromotions" in source
    assert "promotePost" in source
    assert "Îți poți promova până la" in source
    assert 'authorPath(owner, "/panou")' in source
    assert "Textele tale (" not in source.split("function ProfilePromotionEditor", 1)[1].split("function ProfileSeriesList", 1)[0]
    assert "Autorul își selectează textele proprii promovate din /panou" in docs


def test_post_card_links_excerpt_to_post_page():
    content = (ROOT / "frontend" / "src" / "app" / "content.jsx").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")
    post_card = content.split("export function PostCard", 1)[1].split("export function EquippedStrip", 1)[0]

    assert "const href = postHref(post);" in post_card
    assert "const excerpt = htmlToText(post.content);" in post_card
    assert '<a className="piece-card-excerpt piece-card-excerpt-link" href={href}>{excerpt}</a>' in post_card
    assert '<p className="piece-card-excerpt">{excerpt}</p>' in post_card
    assert ".piece-card-excerpt-link" in styles
    assert ".piece-card-excerpt-link:focus-visible" in styles


def test_dashboard_posts_can_toggle_own_promotions():
    source = (ROOT / "frontend" / "src" / "routes" / "dashboard.jsx").read_text(encoding="utf-8")
    settings_source = (ROOT / "frontend" / "src" / "routes" / "profile-settings.jsx").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")
    docs = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")

    assert "fetchPromotions" in source
    assert "promotePost(post.id)" in source
    assert "unpromotePost(post.id)" in source
    assert "promotedOwnPostIds.has(post.id)" in source
    assert "Promovează în Călimara mea" in source
    assert "Poți promova cel mult" in source
    assert "dashboard-promote-btn" in source
    assert ".dashboard-promote-btn.is-promoted" in styles
    assert "Textele tale (" not in settings_source.split("function PromotionSettingsPanel", 1)[1].split("function ProfileSettingsView", 1)[0]
    assert 'mainPath("/panou")' in settings_source
    assert "fiecare text aprobat" in docs
    assert "autorii promovați trebuie să aibă texte publice aprobate" in docs


def test_forum_new_thread_prefills_active_section():
    source = (ROOT / "frontend" / "src" / "routes" / "forum.jsx").read_text(encoding="utf-8")
    docs = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")

    assert "function forumCreateHref(section)" in source
    assert '`?section=${encodeURIComponent(section)}`' in source
    assert "const createHref = forumCreateHref(section);" in source
    assert 'new URLSearchParams(window.location.search).get("section")' in source
    assert "const [section, setSection] = useState(initialForumSection);" in source
    assert "Butonul Discuție nouă păstrează secțiunea activă" in docs


def test_forum_and_message_report_buttons_are_wired():
    forum_api = (ROOT / "frontend" / "src" / "api" / "forum.js").read_text(encoding="utf-8")
    message_api = (ROOT / "frontend" / "src" / "api" / "messages.js").read_text(encoding="utf-8")
    forum_source = (ROOT / "frontend" / "src" / "routes" / "forum.jsx").read_text(encoding="utf-8")
    messages_source = (ROOT / "frontend" / "src" / "routes" / "messages.jsx").read_text(encoding="utf-8")
    docs = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")

    assert "reportForumThread" in forum_api
    assert "/api/forum/discutii/" in forum_api and "/raportari" in forum_api
    assert "reportForumReply" in forum_api
    assert "/api/forum/raspunsuri/" in forum_api
    assert "reportMessage" in message_api
    assert "/api/mesaje/" in message_api and "/raportari" in message_api
    assert "ReportModal" in forum_source
    assert "forum-report-btn" in forum_source
    assert "allowPlagiarism={false}" in forum_source
    assert 'reasonType: "offensive"' in forum_source
    assert "ReportModal" in messages_source
    assert "message-report-btn" in messages_source
    assert "allowPlagiarism={false}" in messages_source
    assert 'reasonType: "offensive"' in messages_source
    assert "Mesajele primite pot fi raportate" in docs
    assert "Threadurile și răspunsurile aprobate au steag roșu de raportare" in docs


def test_private_messages_expose_diacritics_option():
    messages_source = (ROOT / "frontend" / "src" / "routes" / "messages.jsx").read_text(encoding="utf-8")
    profile_source = (ROOT / "frontend" / "src" / "routes" / "profile.jsx").read_text(encoding="utf-8")
    docs = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")
    legal = (ROOT / "frontend" / "src" / "routes" / "legal.jsx").read_text(encoding="utf-8")

    assert "DiacriticsControl" in messages_source
    assert 'addDiacritics({ kind: "private_message", content })' in messages_source
    assert 'label="Adaugă automat diacritice în mesaj?"' in messages_source
    assert "diacriticsSubmitLabel" in messages_source
    assert 'addDiacritics({ kind: "private_message", content })' in profile_source
    assert "PRIVATE_MESSAGE_CHARACTER_LIMIT" in profile_source
    assert "toate compozitoarele de mesaje private pot folosi Diacritice" in docs
    assert "mesaje private, teatru" in legal


def test_admin_email_tab_exposes_notification_test_button():
    api_source = (ROOT / "frontend" / "src" / "api" / "admin.js").read_text(encoding="utf-8")
    admin_source = (ROOT / "frontend" / "src" / "routes" / "admin.jsx").read_text(encoding="utf-8")
    docs = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")

    assert "sendAdminNotificationTestEmail" in api_source
    assert 'api.post("/api/admin/email/test-notification", {})' in api_source
    assert "sendNotificationTestEmail" in admin_source
    assert "Trimite notificare test" in admin_source
    assert "contact@calimara.ro" in admin_source
    assert "/api/admin/email/test-notification" in docs


def test_admin_reference_group_exposes_qa_report():
    api_source = (ROOT / "frontend" / "src" / "api" / "admin.js").read_text(encoding="utf-8")
    admin_source = (ROOT / "frontend" / "src" / "routes" / "admin.jsx").read_text(encoding="utf-8")
    docs = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")

    assert "fetchAdminQaReport" in api_source
    assert 'api.get(`/api/admin/referinta/raport-qa${buildQuery(params)}`)' in api_source
    assert "Raport QA" in admin_source
    assert 'setActiveTab("qaReport")' in admin_source
    assert "/api/admin/referinta/raport-qa" in docs
    assert "excluse din Sesizări" in docs


def test_admin_site_feedback_reply_flow_is_wired_to_system_messages():
    api_source = (ROOT / "frontend" / "src" / "api" / "admin.js").read_text(encoding="utf-8")
    admin_source = (ROOT / "frontend" / "src" / "routes" / "admin.jsx").read_text(encoding="utf-8")
    messages_source = (ROOT / "frontend" / "src" / "routes" / "messages.jsx").read_text(encoding="utf-8")
    docs = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")

    assert "fetchAdminSiteFeedbackThread" in api_source
    assert "/api/admin/site-feedback/${encodeURIComponent(feedbackId)}/thread" in api_source
    assert "replyAdminSiteFeedback" in api_source
    assert "/api/admin/site-feedback/${encodeURIComponent(feedbackId)}/reply" in api_source
    assert "SiteFeedbackReplyModal" in admin_source
    assert "Răspunde" in admin_source
    assert "submissionsUnreadReplyCount" in admin_source
    assert "admin-tab-alert-badge" in admin_source
    assert "răspunsuri noi la sesizări" in admin_source
    assert "latest_unread_reply_preview" in admin_source
    assert "admin-feedback-has-unread" in admin_source
    assert "Deschise + răspunsuri noi" in admin_source
    assert "Răspunsul a fost trimis ca mesaj direct de la Călimara." in admin_source
    assert 'if (user?.is_system) return "Călimara";' in messages_source
    assert "!mine && !otherUser.is_system" in messages_source
    assert "badge roșu cu numărul răspunsurilor noi de la utilizatori" in docs
    assert "rămân vizibile în filtrul Deschise + răspunsuri noi" in docs
    assert "conversații de suport cu Călimara" in docs
    assert "nu închide automat sesizarea" in docs


def test_admin_performance_panel_is_wired_to_live_metrics():
    api_source = (ROOT / "frontend" / "src" / "api" / "admin.js").read_text(encoding="utf-8")
    admin_source = (ROOT / "frontend" / "src" / "routes" / "admin.jsx").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")
    docs = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")

    assert "fetchAdminPerformanceLive" in api_source
    assert 'api.get("/api/admin/performance/live")' in api_source
    assert "fetchAdminPerformanceHistory" in api_source
    assert "/api/admin/performance/history" in api_source
    assert '"performance", "Performanță"' in admin_source
    assert 'activeTab === "performance"' in admin_source
    assert "window.setInterval" in admin_source
    assert "10000" in admin_source
    assert "performanceUsers.active_now" in admin_source
    assert "performanceUsers.active_24h" in admin_source
    assert "Utilizatori activi" in admin_source
    assert "Activi 24h" in admin_source
    assert "admin-performance-table" in admin_source
    assert "admin-performance-history" in styles
    assert "/api/admin/performance/live" in docs
    assert "/api/admin/performance/history" in docs
    assert "admin_performance_snapshots" in docs
    assert "utilizatori activi 24h" in docs


def test_admin_panel_links_operational_entities():
    admin_source = (ROOT / "frontend" / "src" / "routes" / "admin.jsx").read_text(encoding="utf-8")
    docs = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")

    assert 'import { blogUrl, mainPath } from "../app/paths.js";' in admin_source
    assert "function contentHref" in admin_source
    assert "function reportHref" in admin_source
    assert "function AdminTextLink" in admin_source
    assert "titleHref={contentHref(item)}" in admin_source
    assert "previewHref={contentHref(item)}" in admin_source
    assert "titleHref={log.target_url}" in admin_source
    assert "titleHref={job.target_url}" in admin_source
    assert "reference.target_url" in admin_source
    assert "admin-title-link" in styles
    assert "admin-preview-link" in styles
    assert "duc direct către elementul inspectat" in docs


def test_public_frontend_avoids_legacy_stats_and_best_friend_wrappers():
    stats_api = (ROOT / "frontend" / "src" / "api" / "stats.js").read_text(encoding="utf-8")
    users_api = (ROOT / "frontend" / "src" / "api" / "users.js").read_text(encoding="utf-8")
    docs = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")

    assert "fetchOverviewStats" not in stats_api
    assert "/api/statistici/ansamblu" not in stats_api
    assert "updateBestFriends" not in users_api
    assert "Best friends" not in docs
    assert "Autorii promovați sunt o structură de profil" in docs


def test_theatre_list_exposes_pending_invitations():
    api_source = (ROOT / "frontend" / "src" / "api" / "theatre.js").read_text(encoding="utf-8")
    theatre_source = (ROOT / "frontend" / "src" / "routes" / "theatre.jsx").read_text(encoding="utf-8")

    assert "fetchMyTheatreInvitations" in api_source
    assert 'api.get("/api/utilizator/teatru/in-asteptare")' in api_source
    assert "Invitațiile tale" in theatre_source
    assert "respondToInvitation" in theatre_source
    assert "Acceptă" in theatre_source
    assert "Refuză" in theatre_source


def test_profile_description_exposes_diacritics_option():
    profile_source = (ROOT / "frontend" / "src" / "routes" / "profile-settings.jsx").read_text(encoding="utf-8")
    auth_source = (ROOT / "frontend" / "src" / "routes" / "auth.jsx").read_text(encoding="utf-8")
    constants_source = (ROOT / "frontend" / "src" / "app" / "constants.js").read_text(encoding="utf-8")
    docs = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")

    assert "PROFILE_DESCRIPTION_CHARACTER_LIMIT = 400" in constants_source
    assert "DiacriticsControl" in profile_source
    assert 'label="Adaugă automat diacritice în descriere?"' in profile_source
    assert 'addDiacritics({ kind: "profile_description", content: form.subtitle })' in profile_source
    assert "Verifică diacriticele" in profile_source
    assert "profileDescriptionText.length" in profile_source
    assert "subtitleText.length" in auth_source
    assert "field-counter" in profile_source
    assert "field-counter" in auth_source
    assert "maximum 250" not in docs
    assert "descriere cu opțiune Diacritice, de maximum 400 de caractere" in docs


def test_explanatory_note_uses_title_question_button():
    source = (ROOT / "frontend" / "src" / "app" / "content.jsx").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")
    meta_section = source.split('<div className="piece-meta">', 1)[1].split('<div className="piece-scroll-wrap">', 1)[0]

    assert 'className="piece-title-actions"' in source
    assert 'aria-label="Notă explicativă"' in source
    assert ">\n        ?\n      </button>" in source
    assert '<ExplanatoryNoteBubble note={piece.explanatoryNote} />' in source
    assert "ExplanatoryNoteBubble" not in meta_section
    assert ".title-promotion-toggle,\n.piece-note-trigger" in styles
    assert "width: 30px;" in styles
    assert "width: 32px;" in styles


def test_piece_reader_omits_author_domain_row_above_title():
    source = (ROOT / "frontend" / "src" / "app" / "content.jsx").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")

    assert "authorDomainHandle" in source
    assert '`${usernameHandle(name)}.calimara.ro`' in source
    assert "authorDomainHandle(piece.author)" in source
    assert "sourceUrlLabel" not in source
    assert "piece-kind-meta" not in source
    assert "piece-kind-meta" not in styles
    assert "sourceUrl: authorUrl" not in source
    assert 'sourceUrl: "#"' not in source
    assert "{titleHeading}" in source
    assert source.index("{titleHeading}") < source.index('<div className="piece-meta">')


def test_author_blog_star_promotes_author_not_favorite():
    source = (ROOT / "frontend" / "src" / "routes" / "profile.jsx").read_text(encoding="utf-8")
    docs = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")
    promote_button = source.split("function PromoteAuthorButton", 1)[1].split("function ProfileFollowButton", 1)[0]

    assert "promoteAuthor(owner.id)" in promote_button
    assert "unpromoteAuthor(owner.id)" in promote_button
    assert "Promovează autorul pe profilul tău" in promote_button
    assert "Elimină promovarea autorului de pe profilul tău" in promote_button
    assert "favorite" not in promote_button.lower()
    assert "promovarea autorului pe profilul tău" in docs


def test_pending_post_moderation_uses_reader_overlay():
    post_route = (ROOT / "frontend" / "src" / "routes" / "post.jsx").read_text(encoding="utf-8")
    dashboard_route = (ROOT / "frontend" / "src" / "routes" / "dashboard.jsx").read_text(encoding="utf-8")
    content = (ROOT / "frontend" / "src" / "app" / "content.jsx").read_text(encoding="utf-8")
    post_actions = (ROOT / "frontend" / "src" / "app" / "post-actions.jsx").read_text(encoding="utf-8")
    forum_route = (ROOT / "frontend" / "src" / "routes" / "forum.jsx").read_text(encoding="utf-8")
    constants = (ROOT / "frontend" / "src" / "app" / "constants.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")
    docs = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")

    assert "Textul a fost trimis în Franța, la Mistral, pentru moderare" in constants
    assert 'export const MODERATING_STATUSES = new Set(["pending", "flagged"]);' in constants
    assert '<StatusPanel title="Text în curs de moderare">' not in post_route
    assert 'moderationOverlayText={MODERATING_STATUSES.has(data.post.moderation_status) ? TEXT_MODERATION_MESSAGE : ""}' in post_route
    assert 'moderationOverlayText = ""' in content
    assert "if (post.moderation_status === \"rejected\") return null;" in content
    assert "export function ModerationOverlay" in content
    assert 'className={`piece-moderation-overlay ${className}`.trim()}' in content
    assert "piece-card-excerpt-wrap" in content
    assert "ModerationOverlay className=\"piece-card-moderation-overlay\"" in dashboard_route
    assert '<span className="piece-card-status">{post.moderation_status}</span>' not in dashboard_route
    assert ".piece-moderation-overlay" in styles
    assert ".piece-card-moderation-overlay" in styles
    assert ".piece-card-status.status-pending" in styles
    assert "comment-moderation-overlay" in post_actions
    assert 'comments.filter((comment) => comment.moderation_status !== "rejected")' in post_actions
    assert "forum-moderation-overlay" in forum_route
    assert "forum-card-moderation-overlay" in forum_route
    assert 'data.threads.filter((thread) => thread.moderation_status !== "rejected")' in forum_route
    assert 'data.replies.filter((item) => item.moderation_status !== "rejected")' in forum_route
    assert '<StatusPanel title="Mesaj în curs de moderare">' not in forum_route
    assert "Comentariul este în curs de moderare" not in constants
    assert "Mesajul este în curs de moderare" not in constants
    assert "backdrop-filter: blur(6px) grayscale(0.3);" in styles
    assert "inset: -10px;" in styles
    assert "background: rgba(232, 232, 232, 0.54);" in styles
    assert ".comment-body-wrap.has-moderation-overlay" in styles
    assert ".comment-body-wrap.has-moderation-overlay {\n  margin-top: 24px;" in styles
    assert ".forum-body-wrap.has-moderation-overlay" in styles
    assert "overlay translucid" in docs


def test_docs_describe_audio_playlists_and_profile_playback():
    source = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")

    assert "buton Play cu FiPlay" in source
    assert "audio_playlists și audio_playlist_items" in source
    assert "/api/audio/playlisturi/{playlist_id}/lista-redare" in source
    assert "toate cer Rapsod și owner-only" in source


def test_docs_describe_unknown_author_subdomain_404():
    source = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")

    assert "Subdomeniile de autor folosesc wildcard DNS" in source
    assert "subdomeniile fără autor existent primesc 404" in source


def test_backend_does_not_reject_current_spa_paths():
    main_source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    legacy_paths = set(re.findall(r'^\s*"([^"]+)",$', main_source, re.MULTILINE))
    legacy_prefixes_match = re.search(r"LEGACY_FRONTEND_PREFIXES = \((.*?)\)", main_source, re.DOTALL)
    legacy_prefixes = set(re.findall(r'"([^"]+)"', legacy_prefixes_match.group(1) if legacy_prefixes_match else ""))

    current_paths = {"/", *re.findall(r'path === "([^"]+)"', _router_source())}
    blocked = sorted(
        path
        for path in current_paths
        if path in legacy_paths or any(path == prefix or path.startswith(f"{prefix}/") for prefix in legacy_prefixes)
    )

    assert blocked == []


def test_frontend_seo_metadata_wiring():
    app_source = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    seo_source = (ROOT / "frontend" / "src" / "app" / "seo.js").read_text(encoding="utf-8")
    post_source = (ROOT / "frontend" / "src" / "routes" / "post.jsx").read_text(encoding="utf-8")
    profile_source = (ROOT / "frontend" / "src" / "routes" / "profile.jsx").read_text(encoding="utf-8")
    index_source = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    assert "useRouteSeo(route)" in app_source
    assert "setDocumentSeo" in seo_source
    assert "rel=\"canonical\"" in seo_source
    assert "application/ld+json" in seo_source
    assert "noindex, nofollow" in seo_source
    assert "postSeo(data.post, data.blog_owner)" in post_source
    assert "profileSeo(displayData.blog_owner" in profile_source
    assert 'data-seo="description"' in index_source
    assert 'property="og:title"' in index_source


def test_rich_text_editor_uses_tiptap_instead_of_quill():
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    editor_source = (ROOT / "frontend" / "src" / "RichTextEditor.jsx").read_text(encoding="utf-8")
    vite_config = (ROOT / "frontend" / "vite.config.js").read_text(encoding="utf-8")
    styles = (ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")
    docs = (ROOT / "frontend" / "src" / "routes" / "docs.jsx").read_text(encoding="utf-8")

    dependencies = package["dependencies"]
    assert "quill" not in dependencies
    assert "@tiptap/react" in dependencies
    assert "@tiptap/starter-kit" in dependencies
    assert "@tiptap/extension-character-count" in dependencies
    assert "@tiptap/extension-underline" in dependencies
    assert 'from "@tiptap/react"' in editor_source
    assert "StarterKit.configure" in editor_source
    assert "CharacterCount.configure" in editor_source
    assert "handlePaste" in editor_source
    assert 'pasteMode = "prose"' in editor_source
    assert 'pasteMode={category === "poezie" ? "poetry" : "prose"}' in (ROOT / "frontend" / "src" / "routes" / "create.jsx").read_text(encoding="utf-8")
    assert "cleanEditorContent" in editor_source
    assert "canonicalPasteHtmlFromText" in editor_source
    assert "insertContent(cleaned)" in editor_source
    assert 'name: "editor"' in vite_config
    assert "@tiptap" in vite_config
    assert "prosemirror-" in vite_config
    assert "maxSize: 900 * 1024" in vite_config
    assert "tiptap-editor" in styles
    assert "ql-" not in styles
    assert "Tiptap" in docs
    assert "Lipirea în editor este unificată" in docs
