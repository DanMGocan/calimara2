import { Component, createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { AUTH_GOOGLE_PATH } from "../api/auth.js";
import { fetchNotifications, markAllNotificationsRead, markNotificationRead } from "../api/notifications.js";
import { ADS_ENABLED, ADSENSE_CLIENT_ID, ADSENSE_SLOTS, AD_SUPPORTED_ROUTES } from "./constants.js";
import { formatDateTime, usernameHandle } from "./format.js";
import { authorPath, blogUrl, mainPath } from "./paths.js";

const AdsContext = createContext({
  enabled: false,
  clientId: "",
  routeKey: "",
  slots: ADSENSE_SLOTS
});

export function routeAllowsAds(route) {
  return Boolean(route && AD_SUPPORTED_ROUTES.has(route.name));
}
export function adRouteKey(route) {
  if (!route) return "";
  return [route.name, route.slug, route.username, route.categoryKey].filter(Boolean).join(":");
}
export function canShowAds(route, user, authLoaded) {
  return Boolean(
    authLoaded &&
    ADS_ENABLED &&
    ADSENSE_CLIENT_ID &&
    routeAllowsAds(route) &&
    !user?.is_premium
  );
}
export function AdSenseProvider({ route, user, authLoaded, children }) {
  const enabled = canShowAds(route, user, authLoaded);
  const routeKey = adRouteKey(route);

  useEffect(() => {
    if (!enabled) return;
    const scriptId = "adsense-script";
    if (document.getElementById(scriptId)) return;

    const script = document.createElement("script");
    script.id = scriptId;
    script.async = true;
    script.crossOrigin = "anonymous";
    script.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(ADSENSE_CLIENT_ID)}`;
    document.head.appendChild(script);
  }, [enabled]);

  const value = useMemo(() => ({
    enabled,
    clientId: ADSENSE_CLIENT_ID,
    routeKey,
    slots: ADSENSE_SLOTS
  }), [enabled, routeKey]);

  return <AdsContext.Provider value={value}>{children}</AdsContext.Provider>;
}
export function AdSlot({ placement, className = "" }) {
  const { enabled, clientId, routeKey, slots } = useContext(AdsContext);
  const adRef = useRef(null);
  const slot = slots[placement] || "";

  useEffect(() => {
    if (!enabled || !slot || !adRef.current) return;
    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    } catch (error) {
      if (import.meta.env.DEV) console.warn("AdSense slot failed", error);
    }
  }, [enabled, slot, routeKey]);

  if (!enabled || !slot) return null;

  return (
    <aside className={`ad-slot ad-slot-${placement} ${className}`.trim()} aria-label="Publicitate">
      <div className="ad-label">Publicitate</div>
      <ins
        key={`${placement}-${routeKey}`}
        ref={adRef}
        className="adsbygoogle"
        style={{ display: "block" }}
        data-ad-client={clientId}
        data-ad-slot={slot}
        data-ad-format="auto"
        data-full-width-responsive="true"
      />
    </aside>
  );
}
export function IconHouse(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M3 11.5 12 4l9 7.5" />
      <path d="M5 10.5V20h14V10.5" />
      <path d="M10 20v-5h4v5" />
    </svg>
  );
}
function notificationBadgeLabel(count) {
  const value = Number(count || 0);
  if (value <= 0) return "";
  return value > 99 ? "99+" : String(value);
}

export function NavBar({ loggedIn, user, notificationCount = 0, onMenu, menuOpen }) {
  const badgeLabel = notificationBadgeLabel(notificationCount);
  const profileLabel = loggedIn && user
    ? `Conectat ca ${usernameHandle(user.username)}${badgeLabel ? `, ${badgeLabel} notificări necitite` : ""}`
    : "Autentificare";
  return (
    <nav className="nav">
      <a href={mainPath("/")} className="nav-home" aria-label="Acasă">
        <IconHouse className="nav-home-icon" width="22" height="22" />
        <span className="nav-brand">
          călimara<span className="nav-brand-dot">.ro</span>
        </span>
      </a>
      <div className="nav-right">
        <button
          className="icon-btn profile-btn"
          aria-label={profileLabel}
          title={loggedIn && user ? `Conectat ca ${usernameHandle(user.username)}` : "Autentificare"}
          onClick={() => {
            if (loggedIn) onMenu();
            else window.location.href = AUTH_GOOGLE_PATH;
          }}
          type="button"
        >
          <svg viewBox="0 0 18 18" fill="none" aria-hidden="true">
            <circle cx="9" cy="7" r="3" stroke="currentColor" strokeWidth="1.3" />
            <path d="M3 15.5c1-2.6 3.2-4 6-4s5 1.4 6 4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
          <span className="profile-dot" />
          {badgeLabel ? <span className="profile-notification-badge" aria-hidden="true">{badgeLabel}</span> : null}
        </button>
        <button className={`icon-btn burger ${menuOpen ? "open" : ""}`} onClick={onMenu} aria-label="Meniu" type="button" aria-expanded={menuOpen}>
          <span />
          <span />
          <span />
        </button>
      </div>
    </nav>
  );
}
export function ActionRow({ number, icon, label, sub, active, disabled, compact, onClick }) {
  const className = ["action-row", active ? "active" : "", icon ? "has-icon" : "", compact ? "compact" : ""].filter(Boolean).join(" ");

  return (
    <button className={className} onClick={onClick} disabled={disabled} type="button" aria-label={label} title={label}>
      {icon ? <span className="action-icon" aria-hidden="true">{icon}</span> : <span className="action-num">{number}</span>}
      <span className="action-body">
        <span className="action-label">{label}</span>
        {sub ? <span className="action-sub">{sub}</span> : null}
      </span>
      <span className="action-arrow" aria-hidden="true">
        <svg width="14" height="10" viewBox="0 0 14 10" fill="none">
          <path d="M1 5h11m0 0L9 1m3 4l-3 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    </button>
  );
}
function MenuNotifications({ open, user, notificationCount = 0, onNotificationsRefresh, onClose }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");

  const loadNotifications = () => {
    if (!user) return;
    setLoading(true);
    setStatus("");
    fetchNotifications()
      .then((data) => setItems(Array.isArray(data.notifications) ? data.notifications : []))
      .catch((error) => setStatus(error.message || "Nu am putut încărca notificările."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (open && user) loadNotifications();
    if (!user) setItems([]);
  }, [open, user?.id]);

  if (!user) return null;

  const markOne = async (notification) => {
    try {
      if (!notification.is_read) {
        await markNotificationRead(notification.id);
      }
      await onNotificationsRefresh?.();
      if (notification.link) {
        window.location.href = notification.link;
      }
      onClose();
    } catch (error) {
      setStatus(error.message || "Nu am putut marca notificarea.");
    }
  };

  const markAll = async () => {
    try {
      await markAllNotificationsRead();
      setItems((current) => current.map((item) => ({ ...item, is_read: true })));
      await onNotificationsRefresh?.();
    } catch (error) {
      setStatus(error.message || "Nu am putut marca notificările.");
    }
  };

  return (
    <section className="menu-notifications" aria-label="Notificări">
      <div className="menu-notifications-head">
        <span className="menu-kicker">notificări</span>
        {notificationCount > 0 ? (
          <button className="menu-mark-read" type="button" onClick={markAll}>Citește toate</button>
        ) : null}
      </div>
      {loading ? <div className="menu-notification-empty">Se încarcă...</div> : null}
      {status ? <div className="menu-notification-empty error">{status}</div> : null}
      {!loading && !status && items.length ? (
        <div className="menu-notification-list">
          {items.slice(0, 5).map((notification) => (
            <button
              key={notification.id}
              className={`menu-notification ${notification.is_read ? "" : "unread"}`.trim()}
              type="button"
              onClick={() => markOne(notification)}
            >
              <span className="menu-notification-title">{notification.title}</span>
              {notification.message ? <span className="menu-notification-message">{notification.message}</span> : null}
              {notification.created_at ? <span className="menu-notification-date">{formatDateTime(notification.created_at)}</span> : null}
            </button>
          ))}
        </div>
      ) : null}
      {!loading && !status && !items.length ? <div className="menu-notification-empty">Nu ai notificări.</div> : null}
    </section>
  );
}

export function SideMenu({ open, onClose, user, notificationCount = 0, onNotificationsRefresh }) {
  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  const adminItems = user?.is_admin
    ? [["Admin", "operațiuni și moderare", mainPath("/moderare")]]
    : user?.is_moderator
      ? [["Moderare", "moderare", mainPath("/moderare")]]
      : [];
  const menuItems = user
    ? [
        ["Acasă", "pagina principală", mainPath("/")],
        ["Calimara mea", "profilul tău public", blogUrl(user.username)],
        ["Categorii", "răsfoiește după gen", mainPath("/categorie/poezie")],
        ["Scrie", "adaugă un text nou", authorPath(user, "/scrie")],
        ["Panou", "textele tale", authorPath(user, "/panou")],
        ...adminItems,
        ["Mesaje", "conversații", authorPath(user, "/mesaje")],
        ["Cluburi", "comunități", mainPath("/cluburi")],
        ["Discuții", "forum și întrebări", mainPath("/discutii")],
        ["Magazin", "cosmetice cu Gologani", mainPath("/magazin")],
        ["Inventar", "obiectele tale", mainPath("/inventar")],
        [user.is_premium ? "Premium" : "Devino Premium", "abonament și super-aprecieri", mainPath("/premium")],
        ["Deconectare", "", "/api/deconectare", true]
      ]
    : [
        ["Acasă", "pagina principală", mainPath("/")],
        ["Categorii", "răsfoiește după gen", mainPath("/categorie/poezie")],
        ["Cluburi", "comunități", mainPath("/cluburi")],
        ["Discuții", "forum și întrebări", mainPath("/discutii")],
        ["Premium", "abonament și super-aprecieri", mainPath("/premium")],
        ["Autentificare", "intră în cont", AUTH_GOOGLE_PATH]
      ];

  return (
    <>
      <div className={`menu-scrim ${open ? "open" : ""}`} onClick={onClose} aria-hidden="true" />
      <aside className={`menu-panel ${open ? "open" : ""}`} aria-hidden={!open} aria-label="Meniu site">
        <div className="menu-head">
          <span className="menu-kicker">meniu</span>
          <button className="menu-close" onClick={onClose} aria-label="Închide" type="button">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <nav className="menu-list">
          {menuItems.map(([label, desc, href, danger], index) => (
            <a key={label} href={href} className={`menu-item ${danger ? "danger" : ""}`} onClick={onClose} style={{ transitionDelay: open ? `${0.1 + index * 0.035}s` : "0s" }}>
              <span className="menu-num">{String(index + 1).padStart(2, "0")}</span>
              <span className="menu-body">
                <span className="menu-label">{label}</span>
                {desc ? <span className="menu-desc">{desc}</span> : null}
              </span>
              <span className="menu-arrow" aria-hidden="true">
                <svg width="14" height="10" viewBox="0 0 14 10" fill="none">
                  <path d="M1 5h11m0 0L9 1m3 4l-3 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
            </a>
          ))}
        </nav>
        <MenuNotifications
          open={open}
          user={user}
          notificationCount={notificationCount}
          onNotificationsRefresh={onNotificationsRefresh}
          onClose={onClose}
        />
      </aside>
    </>
  );
}
export function Footer() {
  return (
    <footer className="site-foot">
      <div className="foot-inner">
        <nav className="foot-links">
          <a href={mainPath("/confidentialitate")}>Politica de confidențialitate</a>
          <a href={mainPath("/termeni")}>Termeni și condiții</a>
          <a href="mailto:contact@calimara.ro">Contact</a>
        </nav>
        <div className="foot-mark">© 2026 călimara.ro</div>
        <div className="foot-social">
          <a href="https://facebook.com" className="social-btn" aria-label="Facebook">f</a>
          <a href="https://x.com" className="social-btn" aria-label="X">x</a>
        </div>
      </div>
    </footer>
  );
}
export function StatusPanel({ title, children, action }) {
  return (
    <div className="status-panel">
      <div className="auth-kicker">călimara.ro</div>
      <h1 className="auth-title">{title}</h1>
      {children ? <div className="auth-sub">{children}</div> : null}
      {action ? <div className="button-row">{action}</div> : null}
    </div>
  );
}
export function PageShell({ kicker, title, sub, side, children }) {
  return (
    <main className={`stage page-stage ${side ? "" : "stage-single"}`}>
      {side ? <div className="left-col">{side}</div> : null}
      <section className="page-col">
        <div className="piece-kind-row">
          <span className="piece-kind-badge">{kicker}</span>
          <span className="piece-kind-sep" />
        </div>
        {title ? <h1 className="page-title">{title}</h1> : null}
        {sub ? (
          typeof sub === "string" ? <p className="page-sub">{sub}</p> : <div className="page-sub">{sub}</div>
        ) : null}
        {children}
      </section>
    </main>
  );
}
export function AuthRequired() {
  return (
    <PageShell kicker="cont" title="Autentificare necesară" sub="Această zonă folosește sesiunea ta călimara.ro.">
      <a className="cal-btn primary" href={AUTH_GOOGLE_PATH}>Autentificare cu Google</a>
    </PageShell>
  );
}
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error) {
    console.error(error);
  }

  render() {
    if (this.state.error) {
      return (
        <PageShell kicker="eroare" title="Pagina nu a putut fi afișată" sub="A apărut o eroare în interfață.">
          <div className="inline-error">{this.state.error.message || "Eroare necunoscută."}</div>
          <a className="cal-btn primary" href={mainPath("/")}>Înapoi acasă</a>
        </PageShell>
      );
    }
    return this.props.children;
  }
}

export const FLOATING_BACKGROUND_SHAPES = [
  { kind: "circle", size: 5, left: "7%", top: "18%", velocityX: 14, velocityY: -18, rotation: "0deg", spin: 4 },
  { kind: "square", size: 14, left: "83%", top: "13%", velocityX: -20, velocityY: 16, rotation: "12deg", spin: -5 },
  { kind: "line", width: 42, height: 8, left: "48%", top: "21%", velocityX: -18, velocityY: 23, rotation: "-18deg", spin: 3 },
  { kind: "triangle", size: 28, left: "21%", top: "72%", velocityX: 22, velocityY: -17, rotation: "-14deg", spin: 5 },
  { kind: "circle", size: 44, left: "72%", top: "61%", velocityX: -24, velocityY: -14, rotation: "0deg", spin: 2 },
  { kind: "line", width: 76, height: 8, left: "5%", top: "64%", velocityX: 21, velocityY: -19, rotation: "24deg", spin: -3 },
  { kind: "square", size: 64, left: "12%", top: "46%", velocityX: 17, velocityY: 20, rotation: "-8deg", spin: 3 },
  { kind: "triangle", size: 88, left: "90%", top: "36%", velocityX: -22, velocityY: 16, rotation: "18deg", spin: -4 },
  { kind: "line", width: 118, height: 8, left: "65%", top: "29%", velocityX: -19, velocityY: 15, rotation: "9deg", spin: 2 },
  { kind: "circle", size: 116, left: "36%", top: "8%", velocityX: 13, velocityY: 17, rotation: "0deg", spin: 1.5 },
  { kind: "line", width: 156, height: 8, left: "30%", top: "88%", velocityX: 18, velocityY: -13, rotation: "-7deg", spin: -2 },
  { kind: "square", size: 148, left: "58%", top: "76%", velocityX: -15, velocityY: -18, rotation: "10deg", spin: 2 },
  { kind: "triangle", size: 176, left: "3%", top: "80%", velocityX: 16, velocityY: -12, rotation: "-22deg", spin: 2.5 },
  { kind: "line", width: 192, height: 8, left: "74%", top: "48%", velocityX: -17, velocityY: -11, rotation: "-28deg", spin: 1 },
  { kind: "circle", size: 200, left: "78%", top: "82%", velocityX: -12, velocityY: -14, rotation: "0deg", spin: 1 }
];

export function clampNumber(value, min, max) {
  return Math.min(Math.max(value, min), max);
}
export function resolveViewportOffset(value, viewportSize) {
  const text = String(value).trim();
  if (text.endsWith("%")) return (Number.parseFloat(text) / 100) * viewportSize;
  return Number.parseFloat(text) || 0;
}
export function FloatingShapeIcon({ kind }) {
  if (kind === "line") {
    return <line className="bg-shape-outline" x1="4" y1="50" x2="96" y2="50" />;
  }
  if (kind === "triangle") {
    return <polygon className="bg-shape-outline" points="50 8 92 88 8 88" />;
  }
  if (kind === "square") {
    return <rect className="bg-shape-outline" x="8" y="8" width="84" height="84" />;
  }
  return <circle className="bg-shape-outline" cx="50" cy="50" r="44" />;
}
export function FloatingBackgroundShapes() {
  const shapeRefs = useRef([]);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const items = FLOATING_BACKGROUND_SHAPES.map((shape, index) => {
      const width = shape.width ?? shape.size;
      const height = shape.height ?? shape.size;
      return {
        el: shapeRefs.current[index],
        shape,
        width,
        height,
        x: null,
        y: null,
        velocityX: shape.velocityX,
        velocityY: shape.velocityY,
        angle: Number.parseFloat(shape.rotation) || 0,
        spin: shape.spin || 0,
        baseX: 0,
        baseY: 0,
        maxX: 0,
        maxY: 0
      };
    }).filter((item) => item.el);
    let animationFrame = 0;
    let lastTime = 0;

    const applyTransform = (item) => {
      item.el.style.transform = `translate3d(${item.x - item.baseX}px, ${item.y - item.baseY}px, 0) rotate(${item.angle}deg)`;
    };

    const syncBounds = (resetPosition = false) => {
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      items.forEach((item) => {
        item.baseX = resolveViewportOffset(item.shape.left, viewportWidth);
        item.baseY = resolveViewportOffset(item.shape.top, viewportHeight);
        item.maxX = Math.max(0, viewportWidth - item.width);
        item.maxY = Math.max(0, viewportHeight - item.height);
        if (resetPosition || item.x === null || item.y === null) {
          item.x = clampNumber(item.baseX, 0, item.maxX);
          item.y = clampNumber(item.baseY, 0, item.maxY);
        } else {
          item.x = clampNumber(item.x, 0, item.maxX);
          item.y = clampNumber(item.y, 0, item.maxY);
        }
        applyTransform(item);
      });
    };

    const step = (time) => {
      if (!lastTime) lastTime = time;
      const deltaSeconds = Math.min((time - lastTime) / 1000, 0.05);
      lastTime = time;

      items.forEach((item) => {
        item.x += item.velocityX * deltaSeconds;
        item.y += item.velocityY * deltaSeconds;
        item.angle += item.spin * deltaSeconds;

        if (item.x <= 0) {
          item.x = 0;
          item.velocityX = Math.abs(item.velocityX);
        } else if (item.x >= item.maxX) {
          item.x = item.maxX;
          item.velocityX = -Math.abs(item.velocityX);
        }

        if (item.y <= 0) {
          item.y = 0;
          item.velocityY = Math.abs(item.velocityY);
        } else if (item.y >= item.maxY) {
          item.y = item.maxY;
          item.velocityY = -Math.abs(item.velocityY);
        }

        applyTransform(item);
      });

      animationFrame = window.requestAnimationFrame(step);
    };

    const startAnimation = () => {
      if (mediaQuery.matches || animationFrame) return;
      lastTime = 0;
      animationFrame = window.requestAnimationFrame(step);
    };

    const stopAnimation = () => {
      if (!animationFrame) return;
      window.cancelAnimationFrame(animationFrame);
      animationFrame = 0;
    };

    const handleMotionPreference = () => {
      if (mediaQuery.matches) {
        stopAnimation();
        syncBounds(true);
      } else {
        startAnimation();
      }
    };
    const handleResize = () => syncBounds(false);

    syncBounds(true);
    handleMotionPreference();
    window.addEventListener("resize", handleResize);
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", handleMotionPreference);
    } else {
      mediaQuery.addListener(handleMotionPreference);
    }

    return () => {
      stopAnimation();
      window.removeEventListener("resize", handleResize);
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener("change", handleMotionPreference);
      } else {
        mediaQuery.removeListener(handleMotionPreference);
      }
    };
  }, []);

  return (
    <div className="bg-shape-scene">
      {FLOATING_BACKGROUND_SHAPES.map((shape, index) => (
        <span
          className={`bg-shape bg-shape-${shape.kind}`}
          ref={(node) => {
            shapeRefs.current[index] = node;
          }}
          key={`${shape.kind}-${shape.size ?? shape.width}-${index}`}
          style={{
            "--shape-size": `${shape.size ?? shape.width}px`,
            "--shape-width": `${shape.width ?? shape.size}px`,
            "--shape-height": `${shape.height ?? shape.size}px`,
            "--shape-left": shape.left,
            "--shape-top": shape.top,
            "--shape-rotation": shape.rotation
          }}
        >
          <svg className="bg-shape-svg" viewBox="0 0 100 100" focusable="false">
            <FloatingShapeIcon kind={shape.kind} />
          </svg>
        </span>
      ))}
    </div>
  );
}

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
      <NavBar loggedIn={loggedIn} user={auth.user} onMenu={() => setMenuOpen((open) => !open)} menuOpen={menuOpen} />
      <AdSenseProvider route={route} user={auth.user} authLoaded={auth.loaded}>
        <ErrorBoundary key={`${route.name}:${route.slug || route.username || route.categoryKey || ""}`}>
          <Suspense fallback={<PageShell kicker="călimara.ro" title="Se încarcă" sub="Pregătim pagina." />}>
            <RouteView route={route} user={auth.user} authLoaded={auth.loaded} onUserUpdate={updateAuthUser} />
          </Suspense>
        </ErrorBoundary>
      </AdSenseProvider>
      <Footer />
      <SideMenu open={menuOpen} onClose={() => setMenuOpen(false)} user={auth.user} />
    </div>
  );
}
