import { useCallback, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useUnreadCount } from "@/hooks/useUnreadCount";
import { useUiStore } from "@/stores/uiStore";
import { getBlogUrl, getMainUrl } from "@/lib/utils";
import { SmartLink } from "@/components/ui/smart-link";

type MenuItem = {
  label: string;
  desc?: string;
  href?: string;
  onClick?: () => void;
  danger?: boolean;
  badge?: number;
};

export function SideMenu() {
  const { user, isAuthenticated } = useAuth();
  const unreadCount = useUnreadCount(isAuthenticated);
  const { mobileMenuOpen, setMobileMenuOpen } = useUiStore();

  const close = useCallback(() => setMobileMenuOpen(false), [setMobileMenuOpen]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  useEffect(() => {
    document.body.style.overflow = mobileMenuOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileMenuOpen]);

  const mainUrl = getMainUrl();
  const blogUrl = user ? getBlogUrl(user.username) : "#";

  const items: MenuItem[] = isAuthenticated && user
    ? [
        { label: "Acasă", desc: "pagina principală", href: mainUrl },
        { label: "Categorii", desc: "răsfoiește după gen", href: `${mainUrl}/category/poezie` },
        { label: "Scrie", desc: "adaugă un text nou", href: `${blogUrl}/create-post` },
        { label: "Panou", desc: "textele tale", href: `${blogUrl}/dashboard` },
        { label: "Colecții", desc: "grupurile tale", href: `${blogUrl}/dashboard?tab=collections` },
        { label: "Cluburi", desc: "comunități", href: `${mainUrl}/cluburi` },
        { label: "Mesaje", desc: "conversații", href: `${blogUrl}/messages`, badge: unreadCount },
        {
          label: user.is_premium ? "Premium" : "Devino Premium",
          desc: user.is_premium ? "gestionează abonamentul" : "3 super-aprecieri/săptămână",
          href: `${mainUrl}/premium`,
        },
        ...(user.is_admin || user.is_moderator
          ? [{ label: "Moderare", desc: "panou de moderare", href: `${mainUrl}/admin/moderation` }]
          : []),
        {
          label: "Deconectare",
          danger: true,
          onClick: () => {
            window.location.href = "/api/logout";
          },
        },
      ]
    : [
        { label: "Acasă", desc: "pagina principală", href: mainUrl },
        { label: "Categorii", desc: "răsfoiește după gen", href: `${mainUrl}/category/poezie` },
        { label: "Cluburi", desc: "comunități", href: `${mainUrl}/cluburi` },
        { label: "Premium", desc: "3 super-aprecieri/săptămână", href: `${mainUrl}/premium` },
        { label: "Autentificare", desc: "intră în cont", href: "/auth/google" },
      ];

  return (
    <>
      <div
        className={`menu-scrim ${mobileMenuOpen ? "open" : ""}`}
        onClick={close}
        aria-hidden="true"
      />
      <aside
        className={`menu-panel ${mobileMenuOpen ? "open" : ""}`}
        aria-hidden={!mobileMenuOpen}
        aria-label="Meniu site"
      >
        <div className="menu-head">
          <span className="menu-kicker">meniu</span>
          <button
            type="button"
            className="menu-close"
            onClick={close}
            aria-label="Închide meniul"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path
                d="M3 3l10 10M13 3L3 13"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>

        <nav className="menu-list">
          {items.map((item, i) => {
            const n = String(i + 1).padStart(2, "0");
            const delay = mobileMenuOpen ? `${0.1 + i * 0.035}s` : "0s";
            const classes = `menu-item ${item.danger ? "danger" : ""}`;
            const body = (
              <>
                <span className="menu-num">{n}</span>
                <span className="menu-body">
                  <span className="menu-label">{item.label}</span>
                  {item.desc ? <span className="menu-desc">{item.desc}</span> : null}
                </span>
                {item.badge !== undefined && item.badge > 0 ? (
                  <span className="menu-badge">{item.badge}</span>
                ) : null}
                <span className="menu-arrow" aria-hidden>
                  <svg width="14" height="10" viewBox="0 0 14 10" fill="none">
                    <path
                      d="M1 5h11m0 0L9 1m3 4l-3 4"
                      stroke="currentColor"
                      strokeWidth="1.2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
              </>
            );

            if (item.onClick) {
              return (
                <button
                  key={item.label}
                  type="button"
                  className={classes}
                  onClick={() => {
                    close();
                    item.onClick?.();
                  }}
                  style={{ transitionDelay: delay }}
                >
                  {body}
                </button>
              );
            }
            return (
              <SmartLink
                key={item.label}
                href={item.href!}
                onClick={close}
                className={classes}
                style={{ transitionDelay: delay }}
              >
                {body}
              </SmartLink>
            );
          })}
        </nav>

        <div className="menu-foot">
          <div className="menu-foot-brand">
            călimara
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--color-ink-faint)",
              }}
            >
              .ro
            </span>
          </div>
          <div className="menu-foot-note">Esc pentru a închide</div>
        </div>
      </aside>
    </>
  );
}
