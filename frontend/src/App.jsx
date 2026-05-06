import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { fetchUnreadNotificationCount } from "./api/notifications.js";
import { fetchMe } from "./api/users.js";
import { AUTHOR_SUBDOMAIN_ROUTES } from "./app/constants.js";
import { AdSenseProvider, ErrorBoundary, FloatingBackgroundShapes, Footer, NavBar, PageShell, SideMenu } from "./app/layout.jsx";
import { RouteView, routeForLocation } from "./app/router.jsx";
import { blogUrl, canUseAuthorSubdomains, subdomainUsername } from "./app/paths.js";

export function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [routeVersion, setRouteVersion] = useState(0);
  const [auth, setAuth] = useState({ loaded: false, user: null });
  const [notificationCount, setNotificationCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchMe()
      .then((data) => {
        if (!cancelled) setAuth({ loaded: true, user: data.authenticated ? data.user : null });
      })
      .catch(() => {
        if (!cancelled) setAuth({ loaded: true, user: null });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const onPopState = () => setRouteVersion((version) => version + 1);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const route = useMemo(routeForLocation, [routeVersion]);
  const loggedIn = Boolean(auth.user);
  const updateAuthUser = useCallback((nextUser) => {
    setAuth((current) => ({ ...current, user: nextUser }));
  }, []);
  const refreshNotificationCount = useCallback(() => {
    if (!auth.user) {
      setNotificationCount(0);
      return Promise.resolve();
    }
    return fetchUnreadNotificationCount()
      .then((data) => setNotificationCount(Number(data.unread_count || 0)))
      .catch(() => {});
  }, [auth.user?.id]);

  useEffect(() => {
    if (!auth.loaded || !auth.user) {
      setNotificationCount(0);
      return undefined;
    }

    refreshNotificationCount();
    const interval = window.setInterval(refreshNotificationCount, 60000);
    const onFocus = () => refreshNotificationCount();
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", onFocus);
    };
  }, [auth.loaded, auth.user?.id, refreshNotificationCount]);

  useEffect(() => {
    if (!auth.loaded || !auth.user) return;
    if (subdomainUsername()) return;
    if (!canUseAuthorSubdomains()) return;
    if (!AUTHOR_SUBDOMAIN_ROUTES.has(route.name)) return;

    const destination = `${blogUrl(auth.user.username)}${window.location.pathname}${window.location.search}${window.location.hash}`;
    window.location.replace(destination);
  }, [auth.loaded, auth.user?.username, route.name]);

  return (
    <div className="site" data-logged={loggedIn ? "in" : "out"} data-bg="on">
      <div className="bg-atmos" aria-hidden="true">
        <FloatingBackgroundShapes />
      </div>
      <NavBar loggedIn={loggedIn} user={auth.user} notificationCount={notificationCount} onMenu={() => setMenuOpen((open) => !open)} menuOpen={menuOpen} />
      <AdSenseProvider route={route} user={auth.user} authLoaded={auth.loaded}>
        <ErrorBoundary key={`${route.name}:${route.slug || route.username || route.categoryKey || ""}`}>
          <Suspense fallback={<PageShell kicker="călimara.ro" title="Se încarcă" sub="Pregătim pagina." />}>
            <RouteView route={route} user={auth.user} authLoaded={auth.loaded} onUserUpdate={updateAuthUser} />
          </Suspense>
        </ErrorBoundary>
      </AdSenseProvider>
      <Footer />
      <SideMenu open={menuOpen} onClose={() => setMenuOpen(false)} user={auth.user} notificationCount={notificationCount} onNotificationsRefresh={refreshNotificationCount} />
    </div>
  );
}
