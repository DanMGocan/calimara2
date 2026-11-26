import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { fetchUnreadMessageCount } from "./api/messages.js";
import { fetchUnreadNotificationCount } from "./api/notifications.js";
import { fetchPlatformStats } from "./api/stats.js";
import { fetchMe } from "./api/users.js";
import { AuthLoginModal, AuthModalProvider } from "./app/auth-modal.jsx";
import { AUTHOR_SUBDOMAIN_ROUTES } from "./app/constants.js";
import { AdSenseProvider, ErrorBoundary, FloatingBackgroundShapes, Footer, NavBar, NotificationPanel, PageShell, SideMenu, SiteTestBanner } from "./app/layout.jsx";
import { ListeningOverlay, useListeningPlayer } from "./app/listening-player.jsx";
import { RouteView, routeForLocation } from "./app/router.jsx";
import { blogUrl, canUseAuthorSubdomains, mainPath, subdomainUsername } from "./app/paths.js";
import { PostActionTools } from "./app/post-actions.jsx";
import { useRouteSeo } from "./app/seo.js";

function stripAuthModalParams(url) {
  url.searchParams.delete("auth_modal");
  url.searchParams.delete("return_to");
  return url;
}

function authReturnParam(url) {
  const returnTo = url.searchParams.get("return_to");
  return returnTo?.trim() || "";
}

const BACKGROUND_QUOTE = "Când viața însăși pare a fi un delir, cine știe unde sălășluiește nebunia? Poate că a fi prea practic este o nebunie. Să renunți la visuri, aceasta poate fi nebunie. Prea multă luciditate poate fi nebunie, iar cea mai mare nebunie dintre toate: să vezi viața așa cum este, și nu așa cum ar trebui să fie!";

function BackgroundQuote() {
  return (
    <figure className="bg-quote">
      <blockquote>
        <span className="bg-quote-mark bg-quote-mark-open" aria-hidden="true">“</span>
        <span className="bg-quote-text">{BACKGROUND_QUOTE}</span>
        <span className="bg-quote-mark bg-quote-mark-close" aria-hidden="true">”</span>
      </blockquote>
      <figcaption>Miguel de Cervantes</figcaption>
    </figure>
  );
}

export function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [routeVersion, setRouteVersion] = useState(0);
  const [auth, setAuth] = useState({ loaded: false, user: null });
  const [authModal, setAuthModal] = useState({ open: false, returnTo: "" });
  const [authPostId, setAuthPostId] = useState(null);
  const [platformStats, setPlatformStats] = useState(null);
  const [footerPostActions, setFooterPostActions] = useState(null);
  const [profilePanelOpen, setProfilePanelOpen] = useState(false);
  const [notificationCount, setNotificationCount] = useState(0);
  const [messageCount, setMessageCount] = useState(0);

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
  useRouteSeo(route);
  const loggedIn = Boolean(auth.user);
  const postSurface = route.name === "landing" || route.name === "post" ? "reader" : undefined;
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
    setProfilePanelOpen(false);
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
  const refreshNotifications = useCallback(async () => {
    if (!auth.user) {
      setNotificationCount(0);
      return 0;
    }
    try {
      const data = await fetchUnreadNotificationCount();
      const nextCount = Number(data?.unread_count ?? 0);
      const safeCount = Number.isFinite(nextCount) ? Math.max(0, nextCount) : 0;
      setNotificationCount(safeCount);
      return safeCount;
    } catch (error) {
      if (error?.status === 401) setNotificationCount(0);
      return null;
    }
  }, [auth.user?.id]);
  const refreshMessages = useCallback(async () => {
    if (!auth.user) {
      setMessageCount(0);
      return 0;
    }
    try {
      const data = await fetchUnreadMessageCount();
      const nextCount = Number(data?.unread_count ?? 0);
      const safeCount = Number.isFinite(nextCount) ? Math.max(0, nextCount) : 0;
      setMessageCount(safeCount);
      return safeCount;
    } catch (error) {
      if (error?.status === 401) setMessageCount(0);
      return null;
    }
  }, [auth.user?.id]);
  const toggleMenu = useCallback(() => {
    setProfilePanelOpen(false);
    setMenuOpen((open) => !open);
  }, []);
  const openProfilePanel = useCallback(() => {
    if (!auth.user) return;
    setMenuOpen(false);
    setProfilePanelOpen(true);
  }, [auth.user?.id]);
  const closeProfilePanel = useCallback(() => {
    setProfilePanelOpen(false);
  }, []);

  useEffect(() => {
    if (!auth.user) {
      setNotificationCount(0);
      setMessageCount(0);
      setProfilePanelOpen(false);
      return undefined;
    }

    refreshNotifications();
    refreshMessages();
    const intervalId = window.setInterval(() => {
      refreshNotifications();
      refreshMessages();
    }, 60000);
    const onFocus = () => {
      refreshNotifications();
      refreshMessages();
    };
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener("focus", onFocus);
    };
  }, [auth.user?.id, refreshMessages, refreshNotifications]);

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
    let cancelled = false;
    fetchPlatformStats()
      .then((stats) => {
        if (!cancelled) setPlatformStats(stats);
      })
      .catch(() => {
        if (!cancelled) setPlatformStats(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handlePlatformStatsChange = useCallback((stats) => {
    if (stats) setPlatformStats(stats);
  }, []);

  useEffect(() => {
    if (route.name !== "landing" && route.name !== "post") setFooterPostActions(null);
  }, [route.name]);

  const listeningPlayer = useListeningPlayer(auth.user, auth.loaded, refreshAuthUser);
  const authModalContext = useMemo(() => ({
    openAuthModal
  }), [openAuthModal]);

  return (
    <AuthModalProvider value={authModalContext}>
      <div className="site" data-logged={loggedIn ? "in" : "out"} data-bg="on" data-post-surface={postSurface}>
        <div className="bg-atmos" aria-hidden="true">
          <FloatingBackgroundShapes />
          <BackgroundQuote />
        </div>
        <div className="site-top-stack">
          <SiteTestBanner />
          <NavBar
            loggedIn={loggedIn}
            user={auth.user}
            onMenu={toggleMenu}
            menuOpen={menuOpen}
            onProfileNotifications={openProfilePanel}
            profilePanelOpen={profilePanelOpen}
            notificationCount={notificationCount}
            messageCount={messageCount}
            onOpenAudioPlayer={listeningPlayer.openListening}
            audioPlayerDisabled={!listeningPlayer.canListen}
            audioPlayerTitle={listeningPlayer.canListen ? "Player audio" : listeningPlayer.disabledMessage}
            audioPlayerOpen={listeningPlayer.open}
          />
        </div>
        <AdSenseProvider route={route} user={auth.user} authLoaded={auth.loaded}>
          <ErrorBoundary key={`${route.name}:${route.slug || route.username || route.categoryKey || ""}`}>
            <Suspense fallback={<PageShell kicker="călimara.ro" title="Se încarcă" sub="Pregătim pagina." />}>
              <RouteView
                route={route}
                user={auth.user}
                authLoaded={auth.loaded}
                onUserUpdate={updateAuthUser}
                onUserRefresh={refreshAuthUser}
                onMessagesRefresh={refreshMessages}
                onAuthPostIdChange={setAuthPostId}
                onLandingStatsChange={handlePlatformStatsChange}
                onFooterPostActionsChange={setFooterPostActions}
                onStartAuthorListening={listeningPlayer.startAuthorListening}
                onStartPlaylistListening={listeningPlayer.startPlaylistListening}
              />
            </Suspense>
          </ErrorBoundary>
        </AdSenseProvider>
        <ListeningOverlay {...listeningPlayer.overlayProps} />
        {footerPostActions?.post ? (
          <div className={`footer-post-actions-row ${footerPostActions.transitioning ? "is-reader-switching" : ""}`.trim()}>
            <PostActionTools
              post={footerPostActions.post}
              user={auth.user}
              onPostChange={footerPostActions.onPostChange}
              pdfHref={footerPostActions.pdfHref}
              switching={Boolean(footerPostActions.transitioning)}
              className={`footer-post-tools ${footerPostActions.transitioning ? "is-reader-switching" : ""}`.trim()}
            />
          </div>
        ) : null}
        <Footer user={auth.user} authLoaded={auth.loaded} platformStats={platformStats} />
        <SideMenu open={menuOpen} onClose={() => setMenuOpen(false)} user={auth.user} />
        <NotificationPanel
          open={profilePanelOpen}
          user={auth.user}
          notificationCount={notificationCount}
          onNotificationsRefresh={refreshNotifications}
          onClose={closeProfilePanel}
        />
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
