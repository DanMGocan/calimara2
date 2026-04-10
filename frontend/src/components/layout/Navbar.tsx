import { useEffect, useCallback } from "react";
import { Home, User, Menu, X, PenLine, LayoutDashboard, Mail, Bell, Shield, LogOut, Grid3X3, Theater, ChevronRight } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useUnreadCount } from "@/hooks/useUnreadCount";
import { useSubdomain } from "@/hooks/useSubdomain";
import { useUiStore } from "@/stores/uiStore";
import { getBlogUrl, getMainUrl } from "@/lib/utils";

export function Navbar() {
  const { user, isAuthenticated } = useAuth();
  const unreadCount = useUnreadCount(isAuthenticated);
  const { mobileMenuOpen, setMobileMenuOpen } = useUiStore();

  const mainUrl = getMainUrl();
  const blogUrl = user ? getBlogUrl(user.username) : "#";

  const closeMenu = useCallback(() => setMobileMenuOpen(false), [setMobileMenuOpen]);

  const handleLogout = () => {
    window.location.href = "/api/logout";
  };

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && mobileMenuOpen) closeMenu();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [mobileMenuOpen, closeMenu]);

  // Lock body scroll when menu is open
  useEffect(() => {
    document.body.style.overflow = mobileMenuOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [mobileMenuOpen]);

  return (
    <>
      {/* Home button — top-left, near content */}
      <div className="fixed top-4 left-4 z-40 md:left-auto md:right-1/2 md:translate-x-[-22rem]">
        <a
          href={mainUrl}
          className="flex h-11 w-11 items-center justify-center rounded-full border border-primary/15 bg-cream/80 text-primary backdrop-blur-md transition-all hover:border-primary/40 hover:bg-primary hover:text-cream no-underline"
          title="Acasă"
        >
          <Home className="h-5 w-5" />
        </a>
      </div>

      {/* Profile + Burger — top-right, near content */}
      <div className="fixed top-4 right-4 z-40 flex items-center gap-2 md:right-auto md:left-1/2 md:translate-x-[22rem]">
        {isAuthenticated && user ? (
          <a
            href={`${blogUrl}/dashboard`}
            className="flex h-11 w-11 items-center justify-center rounded-full border border-green-600/40 bg-green-600 text-white backdrop-blur-md transition-all hover:bg-green-700 hover:border-green-700/40 no-underline"
            title="Profil"
          >
            <User className="h-5 w-5" />
          </a>
        ) : (
          <a
            href="/auth/google"
            className="flex h-11 w-11 items-center justify-center rounded-full border border-red-500/40 bg-red-500 text-white backdrop-blur-md transition-all hover:bg-red-600 hover:border-red-600/40 no-underline"
            title="Autentificare"
          >
            <User className="h-5 w-5" />
          </a>
        )}

        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="relative flex h-11 w-11 cursor-pointer items-center justify-center rounded-full border border-primary/15 bg-cream/80 text-primary backdrop-blur-md transition-all hover:border-primary/40 hover:bg-primary hover:text-cream"
          aria-label="Meniu"
          aria-expanded={mobileMenuOpen}
        >
          <Menu className="h-5 w-5" />
          {isAuthenticated && unreadCount > 0 && (
            <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-danger" />
          )}
        </button>
      </div>

      {/* Backdrop */}
      <div
        className={`menu-overlay-backdrop ${mobileMenuOpen ? "open" : ""}`}
        onClick={closeMenu}
      />

      {/* Slide-in overlay menu */}
      <div className={`menu-overlay ${mobileMenuOpen ? "open" : ""}`}>
        <div className="mb-8 flex justify-end">
          <button
            onClick={closeMenu}
            className="flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border border-white/25 text-white/80 transition-all hover:bg-white hover:text-primary"
            aria-label="Închide meniul"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex flex-col" aria-label="Meniu site">
          <MenuLink href={mainUrl} icon={<Home className="h-5 w-5" />} onClick={closeMenu}>
            Acasă
          </MenuLink>
          <MenuLink href={`${mainUrl}/category/poezie`} icon={<Grid3X3 className="h-5 w-5" />} onClick={closeMenu}>
            Categorii
          </MenuLink>
          <MenuLink href={`${mainUrl}/piese`} icon={<Theater className="h-5 w-5" />} onClick={closeMenu}>
            Piese de Teatru
          </MenuLink>

          {isAuthenticated && user && (
            <>
              <hr className="my-3 border-white/15" />
              <MenuLink href={`${blogUrl}/create-post`} icon={<PenLine className="h-5 w-5" />} onClick={closeMenu}>
                Scrie
              </MenuLink>
              <MenuLink href={`${blogUrl}/dashboard`} icon={<LayoutDashboard className="h-5 w-5" />} onClick={closeMenu}>
                Panou
              </MenuLink>
              <MenuLink href={`${blogUrl}/messages`} icon={<Mail className="h-5 w-5" />} onClick={closeMenu} badge={unreadCount}>
                Mesaje
              </MenuLink>
              <MenuLink href="/notificari" icon={<Bell className="h-5 w-5" />} onClick={closeMenu}>
                Notificări
              </MenuLink>

              {(user.is_admin || user.is_moderator) && (
                <>
                  <hr className="my-3 border-white/15" />
                  <MenuLink href={`${mainUrl}/admin/moderation`} icon={<Shield className="h-5 w-5" />} onClick={closeMenu}>
                    Moderare
                  </MenuLink>
                </>
              )}

              <hr className="my-3 border-white/15" />
              <button
                onClick={() => { closeMenu(); handleLogout(); }}
                className="flex w-full cursor-pointer items-center gap-3 border-b border-white/8 py-4 text-base font-medium text-red-400 tracking-wide transition-all hover:pl-2 hover:text-red-300"
              >
                <LogOut className="h-5 w-5" />
                Deconectare
              </button>
            </>
          )}

          {!isAuthenticated && (
            <>
              <hr className="my-3 border-white/15" />
              <MenuLink href="/auth/google" icon={<User className="h-5 w-5" />} onClick={closeMenu}>
                Autentificare
              </MenuLink>
            </>
          )}
        </nav>
      </div>
    </>
  );
}

function MenuLink({
  href,
  icon,
  children,
  onClick,
  badge,
}: {
  href: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  onClick: () => void;
  badge?: number;
}) {
  return (
    <a
      href={href}
      onClick={onClick}
      className="flex items-center gap-3 border-b border-white/8 py-4 text-base font-medium tracking-wide text-white/85 transition-all hover:pl-2 hover:text-white no-underline"
    >
      {icon}
      {children}
      {badge !== undefined && badge > 0 && (
        <span className="ml-auto rounded-full bg-danger px-2 py-0.5 text-xs font-bold text-white">
          {badge}
        </span>
      )}
      <ChevronRight className="ml-auto h-4 w-4 opacity-30" />
    </a>
  );
}
