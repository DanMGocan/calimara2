import { Component, createContext, useContext, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { createSiteFeedback } from "../api/feedback.js";
import { deleteNotification, fetchNotifications, markAllNotificationsRead, markNotificationRead, markNotificationUnread } from "../api/notifications.js";
import { BsPen } from "react-icons/bs";
import { FaCoins, FaFacebookF } from "react-icons/fa6";
import { FiBell, FiCheck, FiLock, FiLogIn, FiLogOut, FiMail, FiMessageCircle, FiMonitor, FiPlay, FiTrash2, FiUserPlus, FiX } from "react-icons/fi";
import { IoMdPaperPlane } from "react-icons/io";
import { IoShirtOutline } from "react-icons/io5";
import { LiaBugSolid } from "react-icons/lia";
import { MdOutlineFeedback } from "react-icons/md";
import { PiMaskSad } from "react-icons/pi";
import { RiTeamLine } from "react-icons/ri";
import { SiEuropeanunion } from "react-icons/si";
import { useAuthModal } from "./auth-modal.jsx";
import { ADS_ENABLED, ADSENSE_CLIENT_ID, ADSENSE_SLOTS, AD_SUPPORTED_ROUTES } from "./constants.js";
import { formatDateTime, usernameHandle } from "./format.js";
import { authorPath, blogUrl, mainPath } from "./paths.js";
import { cssZoomOf, PAGE_ZOOM_CHANGE_EVENT } from "./zoom.js";

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
const NAV_TOOLTIP_DELAY_MS = 160;
const NAV_LOCKED_TOOLTIP_DELAY_MS = 30;
const NAV_TOOLTIP_VIEWPORT_GAP = 8;

function NavTooltip({ id, anchorRef, locked, label }) {
  const tooltipRef = useRef(null);

  useLayoutEffect(() => {
    const tooltip = tooltipRef.current;
    const anchor = anchorRef.current;
    if (!tooltip || !anchor) return;
    // Work in the tooltip's own CSS px: window coordinates divided by the page zoom.
    const zoom = cssZoomOf(tooltip);
    const rect = anchor.getBoundingClientRect();
    const width = tooltip.offsetWidth;
    const center = (rect.left + rect.width / 2) / zoom;
    const maxLeft = window.innerWidth / zoom - width - NAV_TOOLTIP_VIEWPORT_GAP;
    const left = Math.max(NAV_TOOLTIP_VIEWPORT_GAP, Math.min(center - width / 2, maxLeft));
    tooltip.style.top = `${Math.round(rect.bottom / zoom + 8)}px`;
    tooltip.style.left = `${Math.round(left)}px`;
    tooltip.style.setProperty("--nav-tooltip-arrow-x", `${Math.round(center - left)}px`);
  }, [anchorRef, label, locked]);

  return createPortal(
    <span ref={tooltipRef} id={id} role="tooltip" className={`nav-tooltip ${locked ? "is-locked" : ""}`.trim()}>
      {locked ? (
        <>
          <FiLock className="nav-tooltip-lock" aria-hidden="true" />
          <span>Conectează-te pentru a folosi funcția <strong>{label}</strong></span>
        </>
      ) : label}
    </span>,
    document.body
  );
}

function useNavTooltip(locked) {
  const [open, setOpen] = useState(false);
  const timerRef = useRef(0);

  const hide = () => {
    window.clearTimeout(timerRef.current);
    setOpen(false);
  };
  const show = () => {
    window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => setOpen(true), locked ? NAV_LOCKED_TOOLTIP_DELAY_MS : NAV_TOOLTIP_DELAY_MS);
  };

  useEffect(() => () => window.clearTimeout(timerRef.current), []);

  useEffect(() => {
    if (!open) return undefined;
    window.addEventListener("scroll", hide, true);
    window.addEventListener("resize", hide);
    return () => {
      window.removeEventListener("scroll", hide, true);
      window.removeEventListener("resize", hide);
    };
  }, [open]);

  return {
    open,
    hide,
    handlers: {
      // Touch taps also emit pointer events; tooltips are for mouse hover and keyboard focus only.
      onPointerEnter: (event) => {
        if (event.pointerType === "mouse") show();
      },
      onPointerLeave: hide,
      onFocus: (event) => {
        if (event.currentTarget.matches(":focus-visible")) show();
      },
      onBlur: hide
    }
  };
}

/**
 * Nav icon with a custom hover tooltip. When `locked` (logged-out visitor on a
 * members-only feature) the icon is greyed out, the tooltip invites the visitor
 * to sign in, and clicking opens the auth modal instead of navigating.
 * `pending` (session still loading) keeps the normal look but stays inert, so
 * signed-in members don't see their icons flash grey on every page load.
 */
function NavItem({ href, label, children, className = "", locked = false, pending = false, onClick, ...props }) {
  const { openAuthModal } = useAuthModal();
  const anchorRef = useRef(null);
  const tooltipId = useId();
  const { open, hide, handlers } = useNavTooltip(locked);
  const classes = ["icon-btn", "nav-action", locked ? "is-locked" : "", className].filter(Boolean).join(" ");
  const shared = {
    ref: anchorRef,
    className: classes,
    "aria-label": label,
    "aria-describedby": open ? tooltipId : undefined,
    ...handlers
  };
  const tooltip = open ? <NavTooltip id={tooltipId} anchorRef={anchorRef} locked={locked} pending={pending} label={label} /> : null;

  if (pending) {
    return (
      <>
        <button {...shared} type="button" aria-disabled="true">
          {children}
        </button>
        {tooltip}
      </>
    );
  }

  if (locked) {
    return (
      <>
        <button
          {...shared}
          type="button"
          aria-label={`${label} (conectează-te pentru a folosi funcția)`}
          aria-describedby={undefined}
          onClick={() => {
            hide();
            openAuthModal?.();
          }}
        >
          {children}
        </button>
        {tooltip}
      </>
    );
  }

  if (href) {
    return (
      <>
        <a {...shared} href={href} onClick={onClick}>
          {children}
        </a>
        {tooltip}
      </>
    );
  }

  return (
    <>
      <button
        {...shared}
        type="button"
        onClick={(event) => {
          hide();
          onClick?.(event);
        }}
        {...props}
      >
        {children}
      </button>
      {tooltip}
    </>
  );
}

function countBadge(count, noun) {
  if (!(count > 0)) return null;
  return (
    <span className="profile-notification-badge" aria-label={`${count} ${noun}`}>
      {count > 9 ? "9+" : count}
    </span>
  );
}

export function NavBar({
  loggedIn,
  user,
  onMenu,
  menuOpen,
  onProfileNotifications,
  profilePanelOpen = false,
  notificationCount = 0,
  messageCount = 0,
  onOpenAudioPlayer,
  audioPlayerDisabled = true,
  audioPlayerTitle = "Player audio",
  audioPlayerOpen = false,
  authLoaded = true
}) {
  const { openAuthModal } = useAuthModal();
  const member = Boolean(loggedIn && user);
  const pending = !member && !authLoaded;
  const locked = !member && authLoaded;
  const unreadNotifications = Math.max(0, Number(notificationCount) || 0);
  const unreadMessages = Math.max(0, Number(messageCount) || 0);
  const friendRequests = Math.max(0, Number(user?.incoming_friend_request_count) || 0);
  const audioRequiresAuth = !loggedIn;
  const audioButtonDisabled = Boolean(audioPlayerDisabled);
  const audioButtonInteractive = !audioRequiresAuth && !audioButtonDisabled;
  const audioTooltipId = "nav-audio-auth-tooltip";
  const handleAudioPlayerClick = (event) => {
    if (!audioButtonInteractive) {
      event.preventDefault();
      return;
    }
    onOpenAudioPlayer?.();
  };
  return (
    <nav className="nav">
      <div className="nav-left">
        <NavItem href={mainPath("/")} label="Acasă" className="nav-home">
          <IconHouse className="nav-home-icon" />
        </NavItem>
        {/* Logged-out (or session still loading): the login icon sits right after Acasă, before the greyed-out icons. */}
        {member ? null : (
          <NavItem label="Autentificare" className="login" onClick={() => openAuthModal?.()}>
            <FiLogIn aria-hidden="true" />
          </NavItem>
        )}
        <NavItem href={member ? blogUrl(user.username) : undefined} label="Călimara mea" className="inkwell" locked={locked} pending={pending}>
          <BsPen aria-hidden="true" />
        </NavItem>
        <NavItem href={member ? authorPath(user, "/panou") : undefined} label="Panou de control" locked={locked} pending={pending}>
          <FiMonitor aria-hidden="true" />
        </NavItem>
        <NavItem
          label="Notificări"
          locked={locked} pending={pending}
          onClick={onProfileNotifications}
          aria-haspopup="dialog"
          aria-expanded={profilePanelOpen || undefined}
          aria-controls="profile-notification-panel"
        >
          <FiBell aria-hidden="true" />
          {member ? countBadge(unreadNotifications, "notificări necitite") : null}
        </NavItem>
        <NavItem href={mainPath("/discutii")} label="Discuții" className="mobile-menu-only" locked={locked} pending={pending}>
          <FiMessageCircle aria-hidden="true" />
        </NavItem>
        <NavItem href={member ? authorPath(user, "/mesaje") : undefined} label="Mesaje" className="mobile-menu-only" locked={locked} pending={pending}>
          <FiMail aria-hidden="true" />
          {member ? countBadge(unreadMessages, "mesaje necitite") : null}
        </NavItem>
        <NavItem href={mainPath("/prieteni")} label="Prieteni" locked={locked} pending={pending}>
          <FiUserPlus aria-hidden="true" />
          {member ? countBadge(friendRequests, "cereri de prietenie") : null}
        </NavItem>
        <NavItem href={mainPath("/cluburi")} label="Cluburi" className="mobile-menu-only" locked={locked} pending={pending}>
          <RiTeamLine aria-hidden="true" />
        </NavItem>
        <NavItem href={mainPath("/teatru")} label="Teatru colaborativ" className="mobile-menu-only" locked={locked} pending={pending}>
          <PiMaskSad aria-hidden="true" />
        </NavItem>
        <NavItem href={mainPath("/stafeta")} label="Ștafeta" className="mobile-menu-only" locked={locked} pending={pending}>
          <IoMdPaperPlane aria-hidden="true" />
        </NavItem>
        <NavItem href={mainPath("/inventar")} label="Inventar" className="mobile-menu-only" locked={locked} pending={pending}>
          <IoShirtOutline aria-hidden="true" />
        </NavItem>
        <NavItem href={mainPath("/premium")} label="Premium" className="premium mobile-menu-only" locked={locked} pending={pending}>
          <FaCoins aria-hidden="true" />
        </NavItem>
        {member ? (
          <NavItem href="/api/deconectare" label="Deconectare" className="danger logout mobile-menu-only">
            <FiLogOut aria-hidden="true" />
          </NavItem>
        ) : null}
      </div>
      <div className="nav-right">
        <span className={`nav-audio-wrap ${audioRequiresAuth ? "requires-auth" : ""}`.trim()}>
          <button
            className={`nav-audio-player ${audioRequiresAuth ? "is-disabled" : ""}`.trim()}
            type="button"
            onClick={handleAudioPlayerClick}
            disabled={!audioRequiresAuth && audioButtonDisabled}
            aria-disabled={audioRequiresAuth ? "true" : undefined}
            title={audioRequiresAuth ? undefined : audioPlayerTitle}
            aria-label="Player audio"
            aria-haspopup="dialog"
            aria-expanded={audioPlayerOpen || undefined}
            aria-controls="landing-listen-player"
            aria-describedby={audioRequiresAuth ? audioTooltipId : undefined}
          >
            <FiPlay aria-hidden="true" />
            <span>Player audio</span>
          </button>
          {audioRequiresAuth ? (
            <span className="nav-audio-tooltip" id={audioTooltipId} role="tooltip">
              Pentru a utiliza player-ul audio, vă rugăm să vă{" "}
              <button className="nav-audio-tooltip-link" type="button" onClick={() => openAuthModal?.()}>
                conectați
              </button>
              .
            </span>
          ) : null}
        </span>
        <button className={`icon-btn burger ${menuOpen ? "open" : ""}`} onClick={onMenu} aria-label="Meniu" type="button" aria-expanded={menuOpen}>
          <span />
          <span />
          <span />
        </button>
      </div>
    </nav>
  );
}
export function ActionRow({ number, icon, label, sub, active, disabled, compact, className = "", onClick }) {
  const classes = ["action-row", active ? "active" : "", icon ? "has-icon" : "", compact ? "compact" : "", className].filter(Boolean).join(" ");

  return (
    <button className={classes} onClick={onClick} disabled={disabled} type="button" aria-label={label} title={label}>
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
export function NotificationPanel({ open, user, notificationCount = 0, onNotificationsRefresh, onClose }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [busyNotification, setBusyNotification] = useState("");

  const loadNotifications = () => {
    if (!user) return;
    setLoading(true);
    setStatus("");
    setBusyNotification("");
    fetchNotifications()
      .then((data) => setItems(Array.isArray(data.notifications) ? data.notifications : []))
      .catch((error) => setStatus(error.message || "Nu am putut încărca notificările."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (open && user) loadNotifications();
    if (!user) setItems([]);
  }, [open, user?.id]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return undefined;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  if (!user) return null;

  const openNotification = async (notification) => {
    try {
      if (!notification.is_read) {
        await markNotificationRead(notification.id);
        setItems((current) => current.map((item) => (
          item.id === notification.id ? { ...item, is_read: true } : item
        )));
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

  const updateNotificationState = async (notification, action) => {
    const busyKey = `${action}:${notification.id}`;
    if (busyNotification) return;
    setBusyNotification(busyKey);
    setStatus("");
    try {
      if (action === "read") {
        await markNotificationRead(notification.id);
        setItems((current) => current.map((item) => (
          item.id === notification.id ? { ...item, is_read: true } : item
        )));
      } else if (action === "unread") {
        await markNotificationUnread(notification.id);
        setItems((current) => current.map((item) => (
          item.id === notification.id ? { ...item, is_read: false } : item
        )));
      } else if (action === "delete") {
        await deleteNotification(notification.id);
        setItems((current) => current.filter((item) => item.id !== notification.id));
      }
      await onNotificationsRefresh?.();
    } catch (error) {
      setStatus(error.message || "Nu am putut actualiza notificarea.");
    } finally {
      setBusyNotification("");
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
    <>
      <div className={`profile-panel-scrim ${open ? "open" : ""}`} onClick={onClose} aria-hidden="true" />
      <aside
        id="profile-notification-panel"
        className={`profile-notification-panel ${open ? "open" : ""}`}
        aria-hidden={!open}
        aria-label="Notificări"
      >
        <div className="profile-notification-head">
          <div>
            <span className="menu-kicker">notificări</span>
            <h2 className="profile-notification-title">Notificări</h2>
          </div>
          <button className="menu-close" onClick={onClose} aria-label="Închide" type="button">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className="profile-notification-toolbar">
          <span className="profile-notification-count">
            {notificationCount > 0 ? `${notificationCount} necitite` : "Toate citite"}
          </span>
          <div className="profile-notification-actions">
            {status ? <button className="menu-mark-read" type="button" onClick={loadNotifications}>Reîncarcă</button> : null}
            {notificationCount > 0 ? (
              <button className="menu-mark-read" type="button" onClick={markAll}>Citește toate</button>
            ) : null}
          </div>
        </div>
        {loading ? <div className="menu-notification-empty">Se încarcă...</div> : null}
        {status ? <div className="menu-notification-empty error">{status}</div> : null}
        {!loading && !status && items.length ? (
          <div className="menu-notification-list">
            {items.map((notification) => (
              <article
                key={notification.id}
                className={`menu-notification ${notification.is_read ? "read" : "unread"}`.trim()}
              >
                <button
                  className="menu-notification-main"
                  type="button"
                  onClick={() => openNotification(notification)}
                >
                  <span className="menu-notification-title">{notification.title}</span>
                  {notification.message ? <span className="menu-notification-message">{notification.message}</span> : null}
                  {notification.created_at ? <span className="menu-notification-date">{formatDateTime(notification.created_at)}</span> : null}
                </button>
                <span className="menu-notification-controls" aria-label="Acțiuni notificare">
                  {notification.is_read ? (
                    <button
                      className="menu-notification-control unread-action"
                      type="button"
                      onClick={() => updateNotificationState(notification, "unread")}
                      disabled={Boolean(busyNotification)}
                      aria-label="Marchează ca necitită"
                      title="Marchează ca necitită"
                    >
                      <FiX aria-hidden="true" />
                    </button>
                  ) : (
                    <button
                      className="menu-notification-control read-action"
                      type="button"
                      onClick={() => updateNotificationState(notification, "read")}
                      disabled={Boolean(busyNotification)}
                      aria-label="Marchează ca citită"
                      title="Marchează ca citită"
                    >
                      <FiCheck aria-hidden="true" />
                    </button>
                  )}
                  <button
                    className="menu-notification-control delete-action"
                    type="button"
                    onClick={() => updateNotificationState(notification, "delete")}
                    disabled={Boolean(busyNotification)}
                    aria-label="Șterge notificarea"
                    title="Șterge notificarea"
                  >
                    <FiTrash2 aria-hidden="true" />
                  </button>
                </span>
              </article>
            ))}
          </div>
        ) : null}
        {!loading && !status && !items.length ? <div className="menu-notification-empty">Nu ai notificări.</div> : null}
      </aside>
    </>
  );
}

export function SideMenu({ open, onClose, user }) {
  const { openAuthModal } = useAuthModal();
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
        ["Călimara mea", "profilul tău public", blogUrl(user.username)],
        ["Scrie", "adaugă un text nou", authorPath(user, "/scrie")],
        ["Panou", "textele tale", authorPath(user, "/panou")],
        ...(user.has_author_audio_access ? [["Playlisturi", "audio salvat", mainPath("/playlisturi")]] : []),
        ["Prieteni", "cereri și listă", mainPath("/prieteni")],
        ...adminItems,
        ["Mesaje", "conversații", authorPath(user, "/mesaje")],
        ["Cluburi", "comunități", mainPath("/cluburi")],
        ["Teatru colaborativ", "piese scrise pe rând", mainPath("/teatru")],
        ["Ștafeta", "texte continuate pe rând", mainPath("/stafeta")],
        ["Discuții", "forum și întrebări", mainPath("/discutii")],
        ["Magazin", "cosmetice cu Gologani", mainPath("/magazin")],
        ["Inventar", "obiectele tale", mainPath("/inventar")],
        [user.is_premium ? "Premium" : "Devino Premium", "abonament și super-aprecieri", mainPath("/premium")],
        ["Deconectare", "", "/api/deconectare", true]
      ]
    : [
        ["Acasă", "pagina principală", mainPath("/")]
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
          {!user ? (
            <button
              className="menu-item"
              type="button"
              onClick={() => {
                onClose();
                openAuthModal?.();
              }}
              style={{ transitionDelay: open ? `${0.1 + menuItems.length * 0.035}s` : "0s" }}
            >
              <span className="menu-num">{String(menuItems.length + 1).padStart(2, "0")}</span>
              <span className="menu-body">
                <span className="menu-label">Autentificare</span>
                <span className="menu-desc">intră în cont</span>
              </span>
              <span className="menu-arrow" aria-hidden="true">
                <svg width="14" height="10" viewBox="0 0 14 10" fill="none">
                  <path d="M1 5h11m0 0L9 1m3 4l-3 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
            </button>
          ) : null}
        </nav>
      </aside>
    </>
  );
}
const SITE_FEEDBACK_ENTRIES = {
  feedback: { kind: "feedback", label: "Sugestii", Icon: MdOutlineFeedback },
  bug: { kind: "bug", label: "Gândaci", Icon: LiaBugSolid }
};
const CALIMARA_FACEBOOK_URL = "https://www.facebook.com/calimararo";
const EU_FOOTER_MESSAGE = "Dezvoltat și hostat, cu dragoste, în Uniunea Europeană";

function feedbackClientContext() {
  if (typeof window === "undefined") return {};
  const timezone = (() => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    } catch {
      return "";
    }
  })();
  return {
    viewport: `${window.innerWidth}x${window.innerHeight}`,
    language: navigator.language || "",
    platform: navigator.platform || "",
    timezone
  };
}

function SiteFeedbackModal({ open, entry, user, authLoaded, onClose }) {
  const { openAuthModal } = useAuthModal();
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const activeEntry = entry ?? SITE_FEEDBACK_ENTRIES.feedback;

  useEffect(() => {
    setMessage("");
    setStatus("");
    setError("");
    setSubmitting(false);
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const submit = async (event) => {
    event.preventDefault();
    if (!user || submitting) return;
    const text = message.trim();
    if (!text) {
      setError("Mesajul este obligatoriu.");
      return;
    }
    setSubmitting(true);
    setStatus("");
    setError("");
    try {
      await createSiteFeedback({
        kind: activeEntry.kind,
        message: text,
        page_url: window.location.href,
        client_context: feedbackClientContext()
      });
      setMessage("");
      setStatus("Mesajul a fost trimis.");
    } catch (requestError) {
      setError(requestError.message || "Nu am putut trimite mesajul.");
    } finally {
      setSubmitting(false);
    }
  };

  const Icon = activeEntry.Icon;
  return (
    <div className="feedback-modal-scrim" role="presentation" onClick={onClose}>
      <section className="feedback-modal" role="dialog" aria-modal="true" aria-labelledby="site-feedback-title" onClick={(event) => event.stopPropagation()}>
        <button className="feedback-modal-close" type="button" aria-label="Închide" onClick={onClose}>x</button>
        <div className="feedback-modal-head">
          <span className="feedback-modal-icon" aria-hidden="true"><Icon /></span>
          <h2 id="site-feedback-title" className="feedback-modal-title">{activeEntry.label}</h2>
        </div>
        {!authLoaded ? (
          <p className="feedback-modal-body">Se verifică sesiunea...</p>
        ) : !user ? (
          <div className="feedback-auth">
            <p className="feedback-modal-body">Autentificarea este necesară pentru trimitere.</p>
            <button
              className="cal-btn primary"
              type="button"
              onClick={() => {
                onClose();
                openAuthModal?.();
              }}
            >
              Autentificare
            </button>
          </div>
        ) : (
          <form className="feedback-form" onSubmit={submit}>
            <label className="cal-label" htmlFor="site-feedback-message">Mesaj</label>
            <textarea
              id="site-feedback-message"
              className="cal-textarea feedback-textarea"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              maxLength={2000}
              rows={6}
              required
            />
            <div className="feedback-form-foot">
              <span className="feedback-counter">{message.trim().length}/2000</span>
              <button className="cal-btn primary" type="submit" disabled={submitting || !message.trim()}>
                {submitting ? "Se trimite..." : "Trimite"}
              </button>
            </div>
            {status ? <div className="inline-status">{status}</div> : null}
            {error ? <div className="inline-error">{error}</div> : null}
          </form>
        )}
      </section>
    </div>
  );
}

export function Footer({ user, authLoaded = false, platformStats = null }) {
  const [feedbackEntry, setFeedbackEntry] = useState(null);
  const stats = platformStats;
  const openFeedback = (entry) => setFeedbackEntry(entry);
  return (
    <>
      <footer className="site-foot">
        <div className="foot-inner">
          <nav className="foot-links">
            <a href={mainPath("/confidentialitate")}>Politica de confidențialitate</a>
            <a href={mainPath("/termeni")}>Termeni și condiții</a>
          </nav>
          <div className="foot-mark">© 2026 călimara.ro</div>
          {stats ? (
            <div className="footer-stat-list">
              <div className="footer-stat">
                <span className="footer-stat-label">Texte</span>
                <span className="footer-stat-count">{Number(stats.total_posts ?? 0).toLocaleString("ro-RO")}</span>
              </div>
              <div className="footer-stat">
                <span className="footer-stat-label">Autori</span>
                <span className="footer-stat-count">{Number(stats.total_authors ?? 0).toLocaleString("ro-RO")}</span>
              </div>
            </div>
          ) : null}
          <div className="foot-actions" aria-label="Informații și acțiuni călimara.ro">
            <button className="footer-icon-btn footer-feedback-btn" type="button" aria-label="Sugestii" title="Sugestii" onClick={() => openFeedback(SITE_FEEDBACK_ENTRIES.feedback)}>
              <MdOutlineFeedback aria-hidden="true" />
            </button>
            <button className="footer-icon-btn footer-feedback-btn" type="button" aria-label="Gândaci" title="Gândaci" onClick={() => openFeedback(SITE_FEEDBACK_ENTRIES.bug)}>
              <LiaBugSolid aria-hidden="true" />
            </button>
            <a className="footer-icon-btn footer-help-btn" href={mainPath("/ce-este-calimara")} aria-label="Ce este calimara.ro?" title="Ce este calimara.ro?">?</a>
            <a href={CALIMARA_FACEBOOK_URL} className="footer-icon-btn social-facebook" aria-label="Facebook" title="Facebook">
              <FaFacebookF aria-hidden="true" />
            </a>
            <a href="mailto:contact@calimara.ro" className="footer-icon-btn social-email" aria-label="Contact" title="Contact">
              <FiMail aria-hidden="true" />
            </a>
            <button
              className="footer-icon-btn footer-eu-btn"
              type="button"
              aria-label={EU_FOOTER_MESSAGE}
              aria-describedby="footer-eu-tooltip"
              onClick={(event) => event.currentTarget.focus()}
            >
              <SiEuropeanunion aria-hidden="true" />
              <span id="footer-eu-tooltip" className="footer-eu-tooltip" role="tooltip">
                {EU_FOOTER_MESSAGE}
              </span>
            </button>
          </div>
        </div>
      </footer>
      <SiteFeedbackModal open={Boolean(feedbackEntry)} entry={feedbackEntry} user={user} authLoaded={authLoaded} onClose={() => setFeedbackEntry(null)} />
    </>
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
export function PageShell({ kicker, title, sub, side, titleAction = null, className = "", children }) {
  const shellClassName = ["stage", "page-stage", side ? "" : "stage-single", className].filter(Boolean).join(" ");
  return (
    <main className={shellClassName}>
      {side ? <div className="left-col">{side}</div> : null}
      <section className="page-col">
        <div className="piece-kind-row">
          <span className="piece-kind-badge">{kicker}</span>
          <span className="piece-kind-sep" />
        </div>
        {titleAction ? (
          <div className="page-title-row">
            {title ? <h1 className="page-title">{title}</h1> : null}
            <div className="page-title-action">{titleAction}</div>
          </div>
        ) : title ? <h1 className="page-title">{title}</h1> : null}
        {sub ? (
          typeof sub === "string" ? <p className="page-sub">{sub}</p> : <div className="page-sub">{sub}</div>
        ) : null}
        {children}
      </section>
    </main>
  );
}
export function AuthRequired({ className = "" }) {
  const { openAuthModal } = useAuthModal();
  return (
    <PageShell kicker="cont" title="Autentificare necesară" sub="Această zonă folosește sesiunea ta călimara.ro." className={className}>
      <button className="cal-btn primary" type="button" onClick={() => openAuthModal?.()}>Autentificare</button>
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
  { kind: "circle", size: 200, left: "78%", top: "82%", velocityX: -12, velocityY: -14, rotation: "0deg", spin: 1 },
  { kind: "square", size: 8, left: "18%", top: "24%", velocityX: -16, velocityY: 19, rotation: "-6deg", spin: 4.5 },
  { kind: "triangle", size: 12, left: "62%", top: "16%", velocityX: 21, velocityY: -15, rotation: "20deg", spin: -4 },
  { kind: "circle", size: 22, left: "92%", top: "72%", velocityX: -18, velocityY: 12, rotation: "0deg", spin: 2 },
  { kind: "line", width: 54, height: 8, left: "26%", top: "34%", velocityX: 15, velocityY: 22, rotation: "31deg", spin: -2.5 },
  { kind: "square", size: 36, left: "44%", top: "62%", velocityX: -14, velocityY: -20, rotation: "18deg", spin: 3.2 },
  { kind: "triangle", size: 52, left: "14%", top: "8%", velocityX: 19, velocityY: 14, rotation: "8deg", spin: -3.5 },
  { kind: "circle", size: 70, left: "88%", top: "6%", velocityX: -13, velocityY: 21, rotation: "0deg", spin: 1.8 },
  { kind: "line", width: 90, height: 8, left: "41%", top: "46%", velocityX: 23, velocityY: -16, rotation: "-34deg", spin: 2.2 },
  { kind: "square", size: 102, left: "2%", top: "28%", velocityX: 12, velocityY: 18, rotation: "25deg", spin: -1.8 },
  { kind: "triangle", size: 120, left: "53%", top: "4%", velocityX: -21, velocityY: 11, rotation: "-10deg", spin: 1.6 },
  { kind: "circle", size: 132, left: "17%", top: "86%", velocityX: 16, velocityY: -22, rotation: "0deg", spin: 1.2 },
  { kind: "line", width: 136, height: 8, left: "86%", top: "55%", velocityX: -15, velocityY: -18, rotation: "14deg", spin: -1.4 },
  { kind: "square", size: 168, left: "46%", top: "91%", velocityX: 14, velocityY: -12, rotation: "-16deg", spin: 1.1 },
  { kind: "triangle", size: 188, left: "70%", top: "18%", velocityX: -11, velocityY: 13, rotation: "28deg", spin: -0.9 },
  { kind: "circle", size: 220, left: "24%", top: "54%", velocityX: 10, velocityY: -16, rotation: "0deg", spin: 0.8 }
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
      // Shapes move in page CSS px, which are smaller than window px under the desktop zoom.
      const zoom = cssZoomOf(document.documentElement);
      const viewportWidth = window.innerWidth / zoom;
      const viewportHeight = window.innerHeight / zoom;
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
    // The desktop scale can flip without a resize (mouse attached/detached), which changes
    // how many page px the window holds.
    window.addEventListener(PAGE_ZOOM_CHANGE_EVENT, handleResize);
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", handleMotionPreference);
    } else {
      mediaQuery.addListener(handleMotionPreference);
    }

    return () => {
      stopAnimation();
      window.removeEventListener("resize", handleResize);
      window.removeEventListener(PAGE_ZOOM_CHANGE_EVENT, handleResize);
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
