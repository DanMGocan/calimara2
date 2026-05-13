import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { fetchMe } from "./api/users.js";
import { AuthLoginModal, AuthModalProvider } from "./app/auth-modal.jsx";
import { AUTHOR_SUBDOMAIN_ROUTES } from "./app/constants.js";
import { AdSenseProvider, ErrorBoundary, FloatingBackgroundShapes, Footer, NavBar, PageShell, SideMenu } from "./app/layout.jsx";
import { ListeningOverlay, useListeningPlayer } from "./app/listening-player.jsx";
import { RouteView, routeForLocation } from "./app/router.jsx";
import { blogUrl, canUseAuthorSubdomains, mainPath, subdomainUsername } from "./app/paths.js";
import { PostActionTools } from "./app/post-actions.jsx";

function stripAuthModalParams(url) {
  url.searchParams.delete("auth_modal");
  url.searchParams.delete("return_to");
  return url;
}

function authReturnParam(url) {
  const returnTo = url.searchParams.get("return_to");
  return returnTo?.trim() || "";
}

export function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [routeVersion, setRouteVersion] = useState(0);
  const [auth, setAuth] = useState({ loaded: false, user: null });
  const [authModal, setAuthModal] = useState({ open: false, returnTo: "" });
  const [authPostId, setAuthPostId] = useState(null);
  const [landingStats, setLandingStats] = useState(null);
  const [footerPostActions, setFooterPostActions] = useState(null);

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
  const buildLandingReturnTo = useCallback((postId = null) => {
    const destination = new URL(mainPath("/"), window.location.href);
    const pinnedPostId = postId || authPostId;
    if (pinnedPostId) {
      destination.searchParams.set("post", String(pinnedPostId));
    }
    return destination.toString();
  }, [authPostId]);
  const buildAuthReturnTo = useCallback((postId = null) => {
    if (postId || authPostId) return buildLandingReturnTo(postId);
    return window.location.href;
  }, [buildLandingReturnTo]);
  const openAuthModal = useCallback((options = {}) => {
    const explicitReturnTo = typeof options.returnTo === "string" ? options.returnTo.trim() : "";
    setMenuOpen(false);
    setAuthModal({
      open: true,
      returnTo: explicitReturnTo || buildAuthReturnTo(options.postId)
    });
  }, [buildAuthReturnTo]);
  const closeAuthModal = useCallback(() => {
    setAuthModal((current) => ({ ...current, open: false }));
  }, []);
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

  useEffect(() => {
    if (route.name !== "authLogin") return;
    const authUrl = new URL(window.location.href);
    const returnTo = authReturnParam(authUrl) || mainPath("/");
    const destination = new URL(mainPath("/"), window.location.href);
    if (destination.origin !== window.location.origin) {
      destination.searchParams.set("auth_modal", "1");
      if (returnTo) destination.searchParams.set("return_to", returnTo);
      window.location.replace(destination.toString());
      return;
    }
    window.history.replaceState({}, "", `${destination.pathname}${destination.search}${destination.hash}`);
    setRouteVersion((version) => version + 1);
    if (!loggedIn) openAuthModal({ returnTo });
  }, [buildAuthReturnTo, loggedIn, openAuthModal, route.name]);

  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get("auth_modal") !== "1") return;
    const returnTo = authReturnParam(url) || buildAuthReturnTo();
    stripAuthModalParams(url);
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
    setRouteVersion((version) => version + 1);
    if (!loggedIn) openAuthModal({ returnTo });
  }, [buildAuthReturnTo, loggedIn, openAuthModal, routeVersion]);

  useEffect(() => {
    if (route.name !== "landing" && route.name !== "post") setAuthPostId(null);
  }, [route.name]);

  useEffect(() => {
    if (route.name !== "landing") setLandingStats(null);
  }, [route.name]);

  useEffect(() => {
    if (route.name !== "landing" && route.name !== "post") setFooterPostActions(null);
  }, [route.name]);

  const listeningPlayer = useListeningPlayer(auth.user, auth.loaded);
  const authModalContext = useMemo(() => ({
    openAuthModal
  }), [openAuthModal]);

  return (
    <AuthModalProvider value={authModalContext}>
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
              <RouteView
                route={route}
                user={auth.user}
                authLoaded={auth.loaded}
                onUserUpdate={updateAuthUser}
                onUserRefresh={refreshAuthUser}
                onAuthPostIdChange={setAuthPostId}
                onLandingStatsChange={setLandingStats}
                onFooterPostActionsChange={setFooterPostActions}
              />
            </Suspense>
          </ErrorBoundary>
        </AdSenseProvider>
        <ListeningOverlay {...listeningPlayer.overlayProps} />
        {footerPostActions?.post ? (
          <div className="footer-post-actions-row">
            <PostActionTools
              key={footerPostActions.key}
              post={footerPostActions.post}
              user={auth.user}
              onPostChange={footerPostActions.onPostChange}
              pdfHref={footerPostActions.pdfHref}
              className="footer-post-tools"
            />
          </div>
        ) : null}
        <Footer user={auth.user} authLoaded={auth.loaded} landingStats={landingStats} showLandingInfo={route.name === "landing"} />
        <SideMenu open={menuOpen} onClose={() => setMenuOpen(false)} user={auth.user} />
        <AuthLoginModal
          open={authModal.open}
          returnTo={authModal.returnTo}
          onClose={closeAuthModal}
          onAuthenticated={refreshAuthUser}
        />
      </div>
    </AuthModalProvider>
  );
}
