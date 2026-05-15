from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_frontend(path: str) -> str:
    return (ROOT / "frontend" / "src" / path).read_text(encoding="utf-8")


def test_app_wires_notifications_into_the_shell():
    source = read_frontend("App.jsx")

    assert "fetchUnreadNotificationCount" in source
    assert "NotificationPanel" in source
    assert "profilePanelOpen" in source
    assert "notificationCount" in source
    assert "<NotificationPanel" in source
    assert "onProfileNotifications={openProfilePanel}" in source
    assert "onNotificationsRefresh={refreshNotifications}" in source


def test_navbar_splits_calimara_and_notifications_controls():
    source = read_frontend("app/layout.jsx")

    assert "onProfileNotifications" in source
    assert "FiBell" in source
    assert "BsPen" in source
    assert 'href={blogUrl(user.username)} label="Călimara mea"' in source
    assert 'aria-controls="profile-notification-panel"' in source
    assert 'label="Notificări"' in source
    assert "notificări necitite" in source
    assert "unreadNotifications > 9 ? \"9+\"" in source
    assert source.index('label="Călimara mea"') < source.index('label="Notificări"')
