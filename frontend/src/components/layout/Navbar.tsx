import { Link, useLocation } from "react-router-dom";
import { Menu, X, PenLine, LayoutDashboard, Mail, Shield, LogOut } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useUnreadCount } from "@/hooks/useUnreadCount";
import { useSubdomain } from "@/hooks/useSubdomain";
import { useUiStore } from "@/stores/uiStore";
import { getAvatarUrl, getBlogUrl, getMainUrl } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export function Navbar() {
  const { user, isAuthenticated } = useAuth();
  const unreadCount = useUnreadCount(isAuthenticated);
  const { isSubdomain, username } = useSubdomain();
  const { mobileMenuOpen, toggleMobileMenu, setMobileMenuOpen } = useUiStore();
  const location = useLocation();

  const mainUrl = getMainUrl();
  const blogUrl = user ? getBlogUrl(user.username) : "#";

  const handleLogout = () => {
    window.location.href = "/api/logout";
  };

  return (
    <nav className="sticky top-0 z-40 border-b border-border bg-surface-raised/80 backdrop-blur-md">
      <div className="mx-auto max-w-6xl px-4">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <a
            href={mainUrl}
            className="font-display text-2xl font-bold tracking-tight text-primary no-underline"
          >
            Calimara
          </a>

          {/* Desktop Nav */}
          <div className="hidden items-center gap-1 md:flex">
            {isSubdomain && username && (
              <NavLink to="/" current={location.pathname === "/"}>
                Blog
              </NavLink>
            )}
            {!isSubdomain && (
              <>
                <NavLink to="/" current={location.pathname === "/"}>
                  Acasa
                </NavLink>
                <NavLink to="/category/poezie" current={location.pathname.startsWith("/category")}>
                  Categorii
                </NavLink>
              </>
            )}

            {isAuthenticated && user && (
              <>
                <a href={`${getBlogUrl(user.username)}/create-post`} className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:bg-surface hover:text-primary no-underline">
                  <PenLine className="h-4 w-4" />
                  Scrie
                </a>
                <a href={`${getBlogUrl(user.username)}/dashboard`} className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:bg-surface hover:text-primary no-underline">
                  <LayoutDashboard className="h-4 w-4" />
                  Panou
                </a>
                <a href={`${getBlogUrl(user.username)}/messages`} className="relative flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:bg-surface hover:text-primary no-underline">
                  <Mail className="h-4 w-4" />
                  Mesaje
                  {unreadCount > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-bold text-white">
                      {unreadCount}
                    </span>
                  )}
                </a>
                {(user.is_admin || user.is_moderator) && (
                  <a href={`${mainUrl}/admin/moderation`} className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:bg-surface hover:text-primary no-underline">
                    <Shield className="h-4 w-4" />
                    Moderare
                  </a>
                )}
              </>
            )}
          </div>

          {/* Right side */}
          <div className="hidden items-center gap-3 md:flex">
            {isAuthenticated && user ? (
              <div className="flex items-center gap-3">
                <a href={blogUrl} className="flex items-center gap-2 no-underline">
                  <img
                    src={getAvatarUrl(user.avatar_seed, 32)}
                    alt={user.username}
                    className="h-8 w-8 rounded-full"
                  />
                  <span className="text-sm font-medium text-primary">{user.username}</span>
                </a>
                <button
                  onClick={handleLogout}
                  className="rounded-lg p-2 text-muted transition-colors hover:bg-surface hover:text-primary cursor-pointer"
                  title="Deconectare"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <Button asChild size="sm">
                <a href="/auth/google" className="no-underline">Autentificare</a>
              </Button>
            )}
          </div>

          {/* Mobile toggle */}
          <button
            className="rounded-lg p-2 md:hidden cursor-pointer"
            onClick={toggleMobileMenu}
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="border-t border-border py-4 md:hidden">
            <div className="flex flex-col gap-1">
              {!isSubdomain && (
                <>
                  <MobileNavLink to="/" onClick={() => setMobileMenuOpen(false)}>Acasa</MobileNavLink>
                  <MobileNavLink to="/category/poezie" onClick={() => setMobileMenuOpen(false)}>Categorii</MobileNavLink>
                </>
              )}
              {isAuthenticated && user && (
                <>
                  <a href={`${getBlogUrl(user.username)}/create-post`} className="rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:bg-surface no-underline" onClick={() => setMobileMenuOpen(false)}>Scrie</a>
                  <a href={`${getBlogUrl(user.username)}/dashboard`} className="rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:bg-surface no-underline" onClick={() => setMobileMenuOpen(false)}>Panou</a>
                  <a href={`${getBlogUrl(user.username)}/messages`} className="rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:bg-surface no-underline" onClick={() => setMobileMenuOpen(false)}>
                    Mesaje {unreadCount > 0 && `(${unreadCount})`}
                  </a>
                  <button onClick={handleLogout} className="rounded-lg px-3 py-2 text-left text-sm text-danger transition-colors hover:bg-surface cursor-pointer">Deconectare</button>
                </>
              )}
              {!isAuthenticated && (
                <a href="/auth/google" className="rounded-lg px-3 py-2 text-sm font-medium text-accent no-underline">Autentificare</a>
              )}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}

function NavLink({ to, current, children }: { to: string; current: boolean; children: React.ReactNode }) {
  return (
    <Link
      to={to}
      className={`rounded-lg px-3 py-2 text-sm transition-colors no-underline ${
        current ? "bg-accent/10 text-accent font-medium" : "text-muted hover:bg-surface hover:text-primary"
      }`}
    >
      {children}
    </Link>
  );
}

function MobileNavLink({ to, onClick, children }: { to: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <Link to={to} onClick={onClick} className="rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:bg-surface no-underline">
      {children}
    </Link>
  );
}
