import { useAuth } from "@/hooks/useAuth";
import { useUnreadCount } from "@/hooks/useUnreadCount";
import { useUiStore } from "@/stores/uiStore";
import { getMainUrl } from "@/lib/utils";

export function Navbar() {
  const { user, isAuthenticated } = useAuth();
  const unreadCount = useUnreadCount(isAuthenticated);
  const { mobileMenuOpen, setMobileMenuOpen } = useUiStore();

  const mainUrl = getMainUrl();

  return (
    <nav className="nav" aria-label="Bara principală">
      <a href={mainUrl} className="nav-home" aria-label="Acasă">
        <svg
          className="nav-home-icon"
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M3 11.5 12 4l9 7.5" />
          <path d="M5 10.5V20h14V10.5" />
          <path d="M10 20v-5h4v5" />
        </svg>
        <span className="nav-brand">
          călimara<span className="nav-brand-dot">.ro</span>
        </span>
      </a>

      <div className="nav-right">
        <button
          type="button"
          className="icon-btn profile-btn"
          title={isAuthenticated && user ? `conectat ca ${user.username}` : "neconectat"}
          aria-label={isAuthenticated && user ? `conectat ca ${user.username}` : "neconectat"}
          onClick={() => {
            if (!isAuthenticated) {
              window.location.href = "/auth/google";
            } else {
              setMobileMenuOpen(true);
            }
          }}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
            <circle cx="9" cy="7" r="3" stroke="currentColor" strokeWidth="1.3" />
            <path
              d="M3 15.5c1-2.6 3.2-4 6-4s5 1.4 6 4"
              stroke="currentColor"
              strokeWidth="1.3"
              strokeLinecap="round"
            />
          </svg>
          <span className="profile-dot" />
        </button>

        <button
          type="button"
          className={`icon-btn burger ${mobileMenuOpen ? "open" : ""}`}
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Meniu"
          aria-expanded={mobileMenuOpen}
        >
          <span />
          <span />
          <span />
          {isAuthenticated && unreadCount > 0 && (
            <span
              aria-hidden="true"
              style={{
                position: "absolute",
                top: 8,
                right: 8,
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: "var(--color-accent)",
              }}
            />
          )}
        </button>
      </div>
    </nav>
  );
}
