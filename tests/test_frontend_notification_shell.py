from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_frontend(path: str) -> str:
    return (ROOT / "frontend" / "src" / path).read_text(encoding="utf-8")


def test_app_wires_notifications_into_the_shell():
    source = read_frontend("App.jsx")

    assert "fetchUnreadNotificationCount" in source
    assert "fetchUnreadMessageCount" in source
    assert "NotificationPanel" in source
    assert "profilePanelOpen" in source
    assert "notificationCount" in source
    assert "messageCount" in source
    assert "<NotificationPanel" in source
    assert "onProfileNotifications={openProfilePanel}" in source
    assert "onNotificationsRefresh={refreshNotifications}" in source
    assert "messageCount={messageCount}" in source
    assert "onMessagesRefresh={refreshMessages}" in source


def test_navbar_splits_calimara_and_notifications_controls():
    source = read_frontend("app/layout.jsx")

    assert "onProfileNotifications" in source
    assert "messageCount = 0" in source
    assert "FiBell" in source
    assert "FiMail" in source
    assert "BsPen" in source
    assert "IoMdPaperPlane" in source
    assert 'from "react-icons/io"' in source
    assert "FiRepeat" not in source
    assert 'href={blogUrl(user.username)} label="Călimara mea"' in source
    assert 'href={authorPath(user, "/mesaje")} label="Mesaje"' in source
    assert 'aria-controls="profile-notification-panel"' in source
    assert 'label="Notificări"' in source
    assert "notificări necitite" in source
    assert "mesaje necitite" in source
    assert "unreadNotifications > 9 ? \"9+\"" in source
    assert "unreadMessages > 9 ? \"9+\"" in source
    assert source.index('label="Călimara mea"') < source.index('label="Notificări"')


def test_navbar_has_dashboard_icon_after_calimara_mea():
    source = read_frontend("app/layout.jsx")

    assert "FiMonitor" in source
    assert 'href={member ? authorPath(user, "/panou") : undefined} label="Panou de control"' in source
    calimara = source.index('label="Călimara mea"')
    panou = source.index('label="Panou de control"')
    assert calimara < panou < source.index('label="Notificări"')
    assert "<FiMonitor" in source[panou:source.index('label="Notificări"')]


def test_notification_panel_styles_read_unread_and_item_actions():
    source = read_frontend("app/layout.jsx")
    api_source = read_frontend("api/notifications.js")
    styles = read_frontend("index.css")

    assert "markNotificationUnread" in api_source
    assert "deleteNotification" in api_source
    assert "/api/notificari/${encodeURIComponent(notificationId)}/necitita" in api_source
    assert "api.delete(`/api/notificari/${encodeURIComponent(notificationId)}`)" in api_source
    assert "FiCheck" in source
    assert "FiX" in source
    assert "FiTrash2" in source
    assert "Marchează ca citită" in source
    assert "Marchează ca necitită" in source
    assert "Șterge notificarea" in source
    assert "<span>Delete</span>" not in source
    assert 'className={`menu-notification ${notification.is_read ? "read" : "unread"}`.trim()}' in source
    assert ".menu-notification.unread {\n  border-color: var(--accent);" in styles
    assert ".menu-notification.unread .menu-notification-title {\n  color: var(--accent);" in styles
    assert ".menu-notification.read {\n  border-color: rgba(91, 91, 91, 0.24);" in styles
    assert "background: rgba(255, 255, 255, 0.28);" in styles
    assert "opacity: 0.58;" in styles
    assert "color: rgba(63, 63, 63, 0.58);" in styles
    assert ".menu-notification-control.delete-action {\n  color: #4a4a4a;\n  width: 32px;\n  padding: 0;" in styles
    assert ".menu-notification-control.unread-action {\n  color: #b7352c;" in styles


def test_navbar_keeps_logged_out_audio_player_visible_with_auth_tooltip():
    source = read_frontend("app/layout.jsx")
    styles = read_frontend("index.css")

    assert "audioRequiresAuth = !loggedIn" in source
    assert "nav-audio-tooltip" in source
    assert "Pentru a utiliza player-ul audio, vă rugăm să vă" in source
    assert "conectați" in source
    assert "openAuthModal?.()" in source
    assert "aria-disabled={audioRequiresAuth ? \"true\" : undefined}" in source
    assert "nav-audio-wrap.requires-auth:hover .nav-audio-tooltip" in styles
    assert ".nav-audio-tooltip-link" in styles


def test_navbar_audio_button_is_plain_and_burger_aligned():
    styles = read_frontend("index.css")
    audio_block = styles.split(".nav-audio-player {", 1)[1].split("}", 1)[0]

    assert "height: 44px;" in audio_block
    assert "border: 0;" in audio_block
    assert "border-radius: 0;" in audio_block
    assert "background: transparent;" in audio_block
    assert "  .nav-audio-player {\n    height: 42px;\n    gap: 5px;" in styles
    assert "width: auto;" in styles
    assert "  .nav-audio-player {\n    width: auto;\n    height: 36px;" in styles
    assert ".nav-audio-player span {\n    position: absolute;" not in styles


def test_listening_overlay_surfaces_current_track_and_author_actions():
    source = read_frontend("app/listening-player.jsx")
    styles = read_frontend("index.css")

    assert "Poți lăsa browserul în fundal sau bloca telefonul" in source
    assert "target=\"_blank\" rel=\"noreferrer\"" in source
    assert "followUser" in source
    assert "sendFriendRequest" in source
    assert "Azi doresc să ascult" in source
    assert "landing-player-top" in source
    assert "landing-player-bottom" in source
    assert "landing-player-divider" in source
    assert "landing-player-mode-link" in source
    assert "listenAutoplayNonce" in source
    assert "setListenAutoplayNonce((nonce) => nonce + 1)" in source
    assert "FiSkipBack" in source
    assert "FiSkipForward" in source
    assert "goToPreviousTrack" in source
    assert "goToNextTrack" in source
    assert "canGoPrevious" in source
    assert "canGoNext" in source
    assert 'aria-label="Anterior"' in source
    assert 'aria-label="Următor"' in source
    assert "[listenAutoplayNonce, listenMode, listenTrack?.audio_id, listenTrack?.playback_url]" in source
    assert "landing-player-keepalive" in styles
    assert "landing-player-mode-stack" in styles
    assert "grid-template-rows: minmax(0, 1fr) auto minmax(0, 1fr)" in styles
    assert "landing-player-divider" in styles
    assert "landing-player-transport" in styles
    assert ".landing-player-skip {" in styles
    assert "width: 48px;" in styles
    assert "  .landing-player-skip {\n    width: 42px;" in styles
    assert "landing-player-relationships" in styles
    assert "landing-player-action" in styles
    assert ".landing-listen-overlay .landing-player-toggle" in styles


def test_admin_invitation_form_reports_local_status():
    source = read_frontend("routes/admin.jsx")

    assert "parseInvitationEmails" in source
    assert "INVITATION_EMAIL_PATTERN" in source
    assert "inviteStatus" in source
    assert "Adaugă cel puțin un email pentru invitație." in source
    assert "Email invalid:" in source
    assert "Zilele premium trebuie să fie între 1 și 3650." in source
    assert 'onSubmit={sendInvitations} noValidate' in source
    assert 'id="admin-invite-status"' in source
    assert 'aria-live="polite"' in source


def test_footer_uses_global_platform_stats():
    app_source = read_frontend("App.jsx")
    layout_source = read_frontend("app/layout.jsx")

    assert "fetchPlatformStats" in app_source
    assert "platformStats={platformStats}" in app_source
    assert "showLandingInfo" not in layout_source
    assert "const stats = platformStats" in layout_source
    assert 'aria-label="Gândaci"' in layout_source
    assert "SiEuropeanunion" in layout_source
    assert "Dezvoltat și hostat, cu dragoste, în Uniunea Europeană" in layout_source
    assert "footer-eu-tooltip" in layout_source


def test_site_test_banner_is_removed():
    app_source = read_frontend("App.jsx")
    layout_source = read_frontend("app/layout.jsx")
    styles = read_frontend("index.css")
    docs = read_frontend("routes/docs.jsx")

    assert "SiteTestBanner" not in app_source
    assert "SiteTestBanner" not in layout_source
    assert '<div className="site-top-stack">' in app_source
    assert "Platforma este în perioada de testare." not in layout_source
    assert "site-test-banner" not in layout_source
    assert "site-test-banner" not in styles
    assert ".site-top-stack {\n  position: sticky;" in styles
    assert "bannerul galben de testare" not in docs


def test_navbar_logged_out_puts_login_right_after_home():
    source = read_frontend("app/layout.jsx")
    styles = read_frontend("index.css")

    home = source.index('label="Acasă"')
    login = source.index('label="Autentificare"')
    first_locked = source.index('label="Călimara mea"')
    assert home < login < first_locked
    assert "{member ? null : (" in source[home:login]
    # DOM order now handles placement; the mobile-only CSS reordering is gone.
    assert ".nav-left > .nav-action.login" not in styles


def test_mobile_navbar_only_shows_home_and_login_or_logout():
    source = read_frontend("app/layout.jsx")
    styles = read_frontend("index.css")
    mobile = styles.split("@media (max-width: 820px) {\n  :root {\n    --nav-h: 58px;", 1)[1]
    mobile = mobile.split("\n}\n", 1)[0]

    rule = "  .nav-left > .nav-action:not(.nav-home):not(.login):not(.logout),\n  .nav-audio-wrap {\n    display: none;\n  }"
    assert rule in mobile
    assert "mobile-menu-only" not in source
    assert "mobile-menu-only" not in styles
    # Logout must not be hidden on mobile any more.
    assert 'label="Deconectare" className="danger logout">' in source
    assert 'label="Autentificare" className="login"' in source
    assert 'label="Acasă" className="nav-home"' in source


def test_burger_menu_holds_every_hidden_mobile_nav_entry():
    source = read_frontend("app/layout.jsx")
    app = read_frontend("App.jsx")
    menu = source[source.index("export function SideMenu("):source.index("const SITE_FEEDBACK_ENTRIES")]

    for label in ("Călimara mea", "Panou", "Notificări", "Player audio", "Prieteni", "Mesaje", "Cluburi",
                  "Teatru colaborativ", "Ștafeta", "Discuții", "Inventar", "Premium", "Deconectare", "Autentificare"):
        assert f'label: "{label}"' in menu or f'"{label}"' in menu, label
    assert "onClick: onNotifications" in menu
    assert "onClick: onOpenAudioPlayer" in menu
    assert "onNotifications={openProfilePanel}" in app
    assert "onOpenAudioPlayer={listeningPlayer.canListen ? listeningPlayer.openListening : undefined}" in app
    assert "notificationCount={notificationCount}" in app[app.index("<SideMenu"):]


def test_site_feedback_modal_confirms_then_closes_after_submit():
    source = read_frontend("app/layout.jsx")
    modal = source[source.index("function SiteFeedbackModal("):source.index("export function Footer(")]

    assert "const SITE_FEEDBACK_CLOSE_DELAY_MS = 2000;" in source
    # Successful submit flips to a confirmation view instead of leaving the form open.
    assert "setSent(true);" in modal
    assert ") : sent ? (" in modal
    assert 'role="status">Mulțumim! Mesajul a fost trimis.</p>' in modal
    # The confirmation closes the modal on a timer that is cleared on unmount/close.
    assert "window.setTimeout(() => onCloseRef.current(), SITE_FEEDBACK_CLOSE_DELAY_MS)" in modal
    assert "return () => window.clearTimeout(timer);" in modal
    assert "}, [open, sent]);" in modal
    # Reopening the modal starts from a fresh form.
    assert "setSent(false);" in modal
