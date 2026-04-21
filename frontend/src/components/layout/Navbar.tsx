import { useEffect, useCallback } from "react";
import { Home, User, Menu, X, PenLine, LayoutDashboard, Mail, Bell, Shield, LogOut, Grid3X3, ChevronRight } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useUnreadCount } from "@/hooks/useUnreadCount";
import { useUiStore } from "@/stores/uiStore";
import { Button } from "@/components/ui/button";
import { DebugLabel } from "@/components/ui/debug-label";
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
      <div className="sticky top-0 z-40 border-b border-primary bg-white/95 backdrop-blur-sm">
        <DebugLabel name="Navbar" />
        <div className="flex items-center justify-between px-4 py-3 sm:px-6 relative">
          <DebugLabel name="NavbarInner" />
          {/* Left: Home + Title */}
          <div className="flex items-center gap-3 relative">
            <DebugLabel name="NavbarLeft" />
            <Button asChild variant="iconRound" size="icon" aria-label="Acasă">
              <a href={mainUrl} className="no-underline">
                <Home className="h-[18px] w-[18px]" />
              </a>
            </Button>
            <a href={mainUrl} className="font-display text-lg text-primary no-underline">
              Călimara
            </a>
          </div>

          {/* Right: Profile + Burger */}
          <div className="flex items-center gap-2 relative">
            <DebugLabel name="NavbarRight" />
            {isAuthenticated && user ? (
              <a
                href={`${blogUrl}/dashboard`}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-white transition-colors hover:bg-primary-light no-underline"
                aria-label="Panoul meu"
              >
                <User className="h-[18px] w-[18px]" />
              </a>
            ) : (
              <a
                href="/auth/google"
                className="flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-white transition-colors hover:bg-primary-light no-underline"
              >
                Autentificare
              </a>
            )}

            <Button
              variant="iconRound"
              size="icon"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Meniu"
              aria-expanded={mobileMenuOpen}
              className="relative"
            >
              <Menu className="h-[18px] w-[18px]" />
              {isAuthenticated && unreadCount > 0 && (
                <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-danger" />
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Backdrop */}
      <div
        className={`menu-overlay-backdrop ${mobileMenuOpen ? "open" : ""}`}
        onClick={closeMenu}
      />

      {/* Slide-in overlay menu — light glass */}
      <div className={`menu-overlay ${mobileMenuOpen ? "open" : ""}`}>
        <DebugLabel name="MobileMenuOverlay" />
        <div className="mb-8 flex justify-end">
          <Button
            variant="iconRound"
            size="icon"
            onClick={closeMenu}
            aria-label="Închide meniul"
            className="text-secondary hover:text-primary"
          >
            <X className="h-5 w-5" />
          </Button>
        </div>

        <nav className="relative flex flex-col" aria-label="Meniu site">
          <DebugLabel name="MobileMenuNav" />
          <MenuLink href={mainUrl} icon={<Home className="h-5 w-5" />} onClick={closeMenu}>
            Acasă
          </MenuLink>
          <MenuLink href={`${mainUrl}/category/poezie`} icon={<Grid3X3 className="h-5 w-5" />} onClick={closeMenu}>
            Categorii
          </MenuLink>
          {isAuthenticated && user && (
            <>
              <hr className="my-3 border-border" />
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
                  <hr className="my-3 border-border" />
                  <MenuLink href={`${mainUrl}/admin/moderation`} icon={<Shield className="h-5 w-5" />} onClick={closeMenu}>
                    Moderare
                  </MenuLink>
                </>
              )}

              <hr className="my-3 border-border" />
              <button
                type="button"
                onClick={() => { closeMenu(); handleLogout(); }}
                className="flex w-full cursor-pointer items-center gap-3 border-b border-border py-4 text-base font-medium tracking-wide text-danger transition-all hover:pl-2"
              >
                <LogOut className="h-5 w-5" />
                Deconectare
              </button>
            </>
          )}

          {!isAuthenticated && (
            <>
              <hr className="my-3 border-border" />
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
      className="flex items-center gap-3 border-b border-border py-4 text-base font-medium tracking-wide text-primary transition-all hover:pl-2 hover:text-primary no-underline"
    >
      {icon}
      {children}
      {badge !== undefined && badge > 0 && (
        <span className="ml-auto rounded-full bg-primary px-2 py-0.5 text-xs font-bold text-white">
          {badge}
        </span>
      )}
      <ChevronRight className="ml-auto h-4 w-4 text-muted-foreground" />
    </a>
  );
}
