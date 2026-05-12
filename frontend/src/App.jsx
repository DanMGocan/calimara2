import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { fetchMe } from "./api/users.js";
import { AUTHOR_SUBDOMAIN_ROUTES } from "./app/constants.js";
import { AdSenseProvider, ErrorBoundary, FloatingBackgroundShapes, Footer, NavBar, PageShell, SideMenu } from "./app/layout.jsx";
import { ListeningOverlay, useListeningPlayer } from "./app/listening-player.jsx";
import { RouteView, routeForLocation } from "./app/router.jsx";
import { blogUrl, canUseAuthorSubdomains, subdomainUsername } from "./app/paths.js";

export function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [routeVersion, setRouteVersion] = useState(0);
  const [auth, setAuth] = useState({ loaded: false, user: null });

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
  const refreshAuthUser = useCallback(async () => {
    const data = await fetchMe();
    const nextUser = data.authenticated ? data.user : null;
    setAuth({ loaded: true, user: nextUser });
    return nextUser;
  }, []);
  const toggleMenu = useCallback(() => {
    setMenuOpen((open) => !open);
  }, []);

  useEffect(() => {
    if (!auth.loaded || !auth.user) return;
    if (subdomainUsername()) return;
    if (!canUseAuthorSubdomains()) return;
    if (!AUTHOR_SUBDOMAIN_ROUTES.has(route.name)) return;

    const destination = `${blogUrl(auth.user.username)}${window.location.pathname}${window.location.search}${window.location.hash}`;
    window.location.replace(destination);
  }, [auth.loaded, auth.user?.username, route.name]);

  const listeningPlayer = useListeningPlayer(auth.user, auth.loaded);

  return (
    <div className="site" data-logged={loggedIn ? "in" : "out"} data-bg="on">
      <div className="bg-atmos" aria-hidden="true">
        <FloatingBackgroundShapes />
      </div>
      <NavBar
        loggedIn={loggedIn}
        user={auth.user}
        onMenu={toggleMenu}
        menuOpen={menuOpen}
        onOpenAudioPlayer={listeningPlayer.openListening}
        audioPlayerDisabled={!listeningPlayer.canListen}
        audioPlayerTitle={listeningPlayer.canListen ? "Player audio" : listeningPlayer.disabledMessage}
        audioPlayerOpen={listeningPlayer.open}
      />
      <AdSenseProvider route={route} user={auth.user} authLoaded={auth.loaded}>
        <ErrorBoundary key={`${route.name}:${route.slug || route.username || route.categoryKey || ""}`}>
          <Suspense fallback={<PageShell kicker="călimara.ro" title="Se încarcă" sub="Pregătim pagina." />}>
            <RouteView route={route} user={auth.user} authLoaded={auth.loaded} onUserUpdate={updateAuthUser} onUserRefresh={refreshAuthUser} />
          </Suspense>
        </ErrorBoundary>
      </AdSenseProvider>
      <ListeningOverlay {...listeningPlayer.overlayProps} />
      <Footer user={auth.user} authLoaded={auth.loaded} />
      <SideMenu open={menuOpen} onClose={() => setMenuOpen(false)} user={auth.user} />
    </div>
  );
}
