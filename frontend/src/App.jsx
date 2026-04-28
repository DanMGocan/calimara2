import { Component, Fragment, createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import {
  AUTH_GOOGLE_PATH,
  completeAuthSetup,
  createComment,
  createForumReply,
  createForumThread,
  createPost,
  collectionPdfUrl,
  fetchArchive,
  fetchBlog,
  fetchCategory,
  fetchClub,
  fetchClubs,
  fetchCollection,
  fetchAudioConversionQuota,
  fetchConversations,
  fetchForumThread,
  fetchForumThreads,
  fetchLanding,
  fetchMe,
  fetchModerationLogs,
  fetchModerationQueue,
  fetchModerationStats,
  fetchPostAudioStatus,
  fetchPostDetail,
  fetchPendingModerationContent,
  fetchRandomUser,
  fetchShopState,
  fetchExtendedModerationStats,
  postPdfUrl,
  likePost,
  moderateContent,
  addSuperLike,
  removeSuperLike,
  reviewModerationLog,
  purchaseShopItem,
  equipInventoryItem,
  unequipInventorySlot,
  openPremiumPortal,
  requestTtsConversions,
  startPremiumCheckout
} from "./api.js";
import { POEMS, STORIES } from "./content.js";

const KIND_TO_CATEGORY = {
  poem: "poezie",
  story: "proza_scurta"
};

const CATEGORY_LABELS = {
  poezie: "Poezie",
  proza_scurta: "Proză scurtă"
};

const FORUM_SECTIONS = [
  { key: "general", label: "General" },
  { key: "poezie", label: "Poezie" },
  { key: "proza_scurta", label: "Proză scurtă" },
  { key: "feedback", label: "Feedback" },
  { key: "anunturi", label: "Anunțuri" }
];

const PREMIUM_TIERS = [
  {
    key: "premium",
    name: "Cronicar",
    summary: "Super-aprecieri și funcțiile premium de bază. Ascultarea audio este publică."
  },
  {
    key: "audio",
    name: "Membru Junimea",
    summary: "Generează audio pentru textele tale: 100.000 caractere per ciclu de facturare."
  },
  {
    key: "author_audio",
    name: "La cenaclu' Flacăra",
    summary: "Generează 250.000 caractere per ciclu și poți încărca înregistrări audio de autor."
  }
];

const SHOP_SLOT_LABELS = {
  profile_badge: "Insignă profil",
  costume: "Costum",
  frame: "Ramă",
  background: "Fundal",
  title: "Titlu"
};

const CONTENT_TYPE_LABELS = {
  post: "Text",
  comment: "Comentariu",
  audio: "Audio",
  forum_thread: "Thread",
  forum_reply: "Răspuns"
};

const PROTECTED_ROUTES = new Set(["dashboard", "create", "messages", "forum", "forumCreate", "forumThread", "shop", "inventory", "admin"]);
const AUTHOR_SUBDOMAIN_ROUTES = new Set(["dashboard", "create", "messages"]);
const AD_SUPPORTED_ROUTES = new Set(["landing", "category", "clubs", "club", "blog", "post", "collection"]);
const ADS_ENABLED = import.meta.env.VITE_ADS_ENABLED === "true";
const ADSENSE_CLIENT_ID = (import.meta.env.VITE_ADSENSE_CLIENT_ID || "").trim();
const ADSENSE_SLOTS = {
  rail: (import.meta.env.VITE_ADSENSE_SLOT_RAIL || "").trim(),
  inline: (import.meta.env.VITE_ADSENSE_SLOT_INLINE || "").trim(),
  postFooter: (import.meta.env.VITE_ADSENSE_SLOT_POST_FOOTER || "").trim()
};
const TEXT_MODERATION_MESSAGE = "Textul este în curs de moderare și va fi disponibil pe site în câteva secunde, cu voia Robotului.";
const COMMENT_MODERATION_MESSAGE = "Comentariul este în curs de moderare și va fi disponibil în câteva secunde, cu voia Robotului.";
const FORUM_MODERATION_MESSAGE = "Mesajul este în curs de moderare și va fi disponibil în câteva secunde, cu voia Robotului.";
const MODERATION_LABELS = {
  pending: "în moderare",
  flagged: "în revizie",
  rejected: "respins"
};

const AdsContext = createContext({
  enabled: false,
  clientId: "",
  routeKey: "",
  slots: ADSENSE_SLOTS
});

function isIPv4(hostname) {
  return /^\d{1,3}(\.\d{1,3}){3}$/.test(hostname);
}

function rootHost() {
  const host = window.location.hostname;
  if (host.endsWith(".localhost")) return "localhost";
  if (host === "localhost" || isIPv4(host)) return host;
  const parts = host.replace(/^www\./, "").split(".");
  return parts.length > 2 ? parts.slice(-2).join(".") : parts.join(".");
}

function subdomainUsername() {
  const host = window.location.hostname;
  if (host.endsWith(".localhost") && host !== "localhost") {
    return host.slice(0, -".localhost".length);
  }
  if (host === "localhost" || isIPv4(host) || host.startsWith("www.")) return null;
  const parts = host.split(".");
  return parts.length > 2 ? parts[0] : null;
}

function mainUrl() {
  const subdomain = subdomainUsername();
  if (!subdomain) return "";
  const port = window.location.port ? `:${window.location.port}` : "";
  return `${window.location.protocol}//${rootHost()}${port}`;
}

function mainPath(path) {
  return `${mainUrl()}${path}`;
}

function blogUrl(username) {
  const port = window.location.port ? `:${window.location.port}` : "";
  return `${window.location.protocol}//${username}.${rootHost()}${port}`;
}

function canUseAuthorSubdomains() {
  const host = rootHost();
  return host !== "localhost" && !isIPv4(host);
}

function authorPath(user, path) {
  if (!user?.username || !canUseAuthorSubdomains()) return mainPath(path);
  return `${blogUrl(user.username)}${path}`;
}

function htmlToText(html) {
  if (!html) return "";
  if (typeof DOMParser !== "undefined") {
    const doc = new DOMParser().parseFromString(html, "text/html");
    return (doc.body.textContent || "").trim();
  }
  return html.replace(/<[^>]*>/g, "").trim();
}

function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ro-RO", {
    day: "2-digit",
    month: "short",
    year: "numeric"
  }).format(date);
}

function categoryLabel(category) {
  return CATEGORY_LABELS[category] ?? category ?? "Text";
}

function moderationLabel(status) {
  if (!status || status === "approved") return "";
  return MODERATION_LABELS[status] ?? status;
}

function contentTypeLabel(type) {
  return CONTENT_TYPE_LABELS[type] ?? type ?? "Conținut";
}

function decisionLabel(value) {
  if (!value) return "n/a";
  if (value === "approved") return "aprobat";
  if (value === "flagged") return "marcat";
  if (value === "rejected") return "respins";
  if (value === "pending") return "în așteptare";
  return value;
}

function formatScore(value) {
  if (value === null || value === undefined || value === "") return "0%";
  const score = Number(value);
  if (Number.isNaN(score)) return String(value);
  return `${Math.round(score * 100)}%`;
}

function forumSectionLabel(section) {
  return FORUM_SECTIONS.find((item) => item.key === section)?.label ?? section ?? "Forum";
}

function slotLabel(slot) {
  return SHOP_SLOT_LABELS[slot] ?? slot ?? "Cosmetic";
}

function formatGologani(value) {
  return `${Number(value ?? 0).toLocaleString("ro-RO")} Gologani`;
}

function formatNumber(value) {
  return Number(value ?? 0).toLocaleString("ro-RO");
}

function audioStatusLabel(status) {
  if (status === "ready") return "audio disponibil";
  if (status === "pending") return "în coada de generare";
  if (status === "processing") return "se generează";
  if (status === "failed") return "generare eșuată";
  if (status === "rejected") return "audio respins";
  if (status === "flagged") return "în revizuire";
  if (status === "cancelled") return "generare oprită";
  return "fără audio";
}

function postToPiece(post) {
  return {
    title: post.title,
    author: post.owner?.username ?? "anonim",
    year: formatDateTime(post.created_at),
    categoryLabel: post.category_name ?? categoryLabel(post.category),
    body: htmlToText(post.content),
    sourceUrl: post.owner ? `${blogUrl(post.owner.username)}/${post.slug}` : "#"
  };
}

function postHref(post) {
  return post?.owner ? `${blogUrl(post.owner.username)}/${post.slug}` : post?.url || "#";
}

function fallbackPiece(kind) {
  const pool = kind === "poem" ? POEMS : STORIES;
  const item = pool[0];
  return {
    ...item,
    categoryLabel: kind === "poem" ? "Poezie" : "Proză scurtă",
    sourceUrl: "#"
  };
}

function useAsync(loader, deps) {
  const [state, setState] = useState({ data: null, error: "", loading: true });

  useEffect(() => {
    let cancelled = false;
    setState((current) => ({ ...current, error: "", loading: true }));
    loader()
      .then((data) => {
        if (!cancelled) setState({ data, error: "", loading: false });
      })
      .catch((error) => {
        if (!cancelled) {
          setState({ data: null, error: error.message || "Cererea a eșuat.", loading: false });
        }
      });
    return () => {
      cancelled = true;
    };
  }, deps);

  return state;
}

function routeAllowsAds(route) {
  return Boolean(route && AD_SUPPORTED_ROUTES.has(route.name));
}

function adRouteKey(route) {
  if (!route) return "";
  return [route.name, route.slug, route.username, route.categoryKey].filter(Boolean).join(":");
}

function canShowAds(route, user, authLoaded) {
  return Boolean(
    authLoaded &&
    ADS_ENABLED &&
    ADSENSE_CLIENT_ID &&
    routeAllowsAds(route) &&
    !user?.is_premium
  );
}

function AdSenseProvider({ route, user, authLoaded, children }) {
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

function AdSlot({ placement, className = "" }) {
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

function IconHouse(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M3 11.5 12 4l9 7.5" />
      <path d="M5 10.5V20h14V10.5" />
      <path d="M10 20v-5h4v5" />
    </svg>
  );
}

function NavBar({ loggedIn, user, onMenu, menuOpen }) {
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
          aria-label={loggedIn && user ? `Conectat ca ${user.username}` : "Autentificare"}
          title={loggedIn && user ? `Conectat ca ${user.username}` : "Autentificare"}
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

function ActionRow({ number, label, sub, active, disabled, onClick }) {
  return (
    <button className={`action-row ${active ? "active" : ""}`} onClick={onClick} disabled={disabled} type="button">
      <span className="action-num">{number}</span>
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

function SideActions({ kind, onPoem, onStory, onAuthor, disabled, busy }) {
  return (
    <aside className="side-col">
      <div className="side-kicker">alege un text</div>
      <div className="actions-group">
        <ActionRow number="01" label="Poezie la întâmplare" active={kind === "poem"} disabled={disabled} onClick={onPoem} />
        <ActionRow number="02" label="Proză scurtă la întâmplare" active={kind === "story"} disabled={disabled} onClick={onStory} />
        <ActionRow number="03" label="Un autor la întâmplare" disabled={busy === "author"} onClick={onAuthor} />
      </div>
      <div className="side-hint">
        <span className="kbd">P</span>
        <span>poezie</span>
        <span style={{ width: 8 }} />
        <span className="kbd">S</span>
        <span>proză</span>
      </div>
    </aside>
  );
}

function Rail({ stats }) {
  if (!stats) return null;
  return (
    <aside className="rail">
      <div className="rail-stat">
        <span className="rail-label">Texte</span>
        <span className="rail-count">{Number(stats.total_posts ?? 0).toLocaleString("ro-RO")}</span>
      </div>
      <div className="rail-stat">
        <span className="rail-label">Autori</span>
        <span className="rail-count">{Number(stats.total_authors ?? 0).toLocaleString("ro-RO")}</span>
      </div>
    </aside>
  );
}

function JoinReasons() {
  const features = [
    "autorii necunoscuți sunt promovați primii",
    "textele bune ies la suprafață",
    "feedback direct de la cititori",
    "comunități pentru poezie și proză"
  ];
  return (
    <aside className="join-rail">
      <div className="join-title">De ce să ni te alături?</div>
      <div className="join-badges">
        {features.map((feature) => <span className="join-badge" key={feature}>{feature}</span>)}
      </div>
    </aside>
  );
}

function RevealText({ text, keySeed }) {
  const lines = useMemo(() => text.split("\n"), [text]);
  return (
    <div className="reveal-text" key={keySeed}>
      {lines.map((line, index) => {
        if (line.trim() === "") {
          return (
            <div key={index} className="reveal-line reveal-blank">
              &nbsp;
            </div>
          );
        }

        return (
          <div key={index} className="reveal-line" style={{ animationDelay: `${0.08 + index * 0.035}s` }}>
            {line}
          </div>
        );
      })}
    </div>
  );
}

function PieceCol({ piece, animKey }) {
  const scrollRef = useRef(null);
  const [atTop, setAtTop] = useState(true);
  const [atBottom, setAtBottom] = useState(false);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = 0;
    setAtTop(true);
    setAtBottom(el.scrollHeight <= el.clientHeight + 1);
  }, [animKey]);

  const onScroll = (event) => {
    const el = event.currentTarget;
    setAtTop(el.scrollTop < 4);
    setAtBottom(el.scrollTop + el.clientHeight >= el.scrollHeight - 4);
  };

  return (
    <div className="piece-col">
      <div className="piece-kind-row">
        <span className="piece-kind-badge">{piece.categoryLabel}</span>
        <span className="piece-kind-sep" />
        {piece.sourceUrl && piece.sourceUrl !== "#" ? (
          <a className="piece-kind-meta" href={piece.sourceUrl}>
            citește pe blog
          </a>
        ) : null}
      </div>
      <h1 className="piece-title">{piece.title}</h1>
      <div className="piece-meta">
        <span className="piece-author">{piece.author}</span>
        {piece.year ? (
          <>
            <span className="piece-meta-dot" />
            <span className="piece-year">{piece.year}</span>
          </>
        ) : null}
      </div>
      <div className="piece-scroll-wrap">
        <div ref={scrollRef} className={`piece-scroll ${atTop ? "at-top" : ""} ${atBottom ? "at-bottom" : ""}`} onScroll={onScroll}>
          <div className="piece-body-inner">
            <RevealText text={piece.body || ""} keySeed={animKey} />
            <div className="piece-end">
              <span>fin</span>
              <span className="piece-end-mark">· · ·</span>
            </div>
          </div>
        </div>
        <div className={`scroll-hint-wrap ${atBottom ? "hidden" : ""}`} aria-hidden="true">
          <div className="scroll-hint">
            <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
              <path d="M3 5l4 4 4-4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span>derulează</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function SideMenu({ open, onClose, user }) {
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

  const adminItems = user?.is_admin || user?.is_moderator
    ? [["Admin", "moderare", mainPath("/admin")]]
    : [];
  const menuItems = user
    ? [
        ["Acasă", "pagina principală", mainPath("/")],
        ["Categorii", "răsfoiește după gen", mainPath("/category/poezie")],
        ["Scrie", "adaugă un text nou", authorPath(user, "/create-post")],
        ["Panou", "textele tale", authorPath(user, "/dashboard")],
        ...adminItems,
        ["Mesaje", "conversații", authorPath(user, "/messages")],
        ["Cluburi", "comunități", mainPath("/cluburi")],
        ["Discuții", "forum și întrebări", mainPath("/discutii")],
        ["Magazin", "cosmetice cu Gologani", mainPath("/magazin")],
        ["Inventar", "obiectele tale", mainPath("/inventar")],
        [user.is_premium ? "Premium" : "Devino Premium", "abonament și super-aprecieri", mainPath("/premium")],
        ["Deconectare", "", "/api/logout", true]
      ]
    : [
        ["Acasă", "pagina principală", mainPath("/")],
        ["Categorii", "răsfoiește după gen", mainPath("/category/poezie")],
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
      </aside>
    </>
  );
}

function Footer() {
  return (
    <footer className="site-foot">
      <div className="foot-inner">
        <nav className="foot-links">
          <a href={mainPath("/privacy")}>Politica de confidențialitate</a>
          <a href={mainPath("/terms")}>Termeni și condiții</a>
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

function StatusPanel({ title, children, action }) {
  return (
    <div className="status-panel">
      <div className="auth-kicker">călimara.ro</div>
      <h1 className="auth-title">{title}</h1>
      {children ? <div className="auth-sub">{children}</div> : null}
      {action ? <div className="button-row">{action}</div> : null}
    </div>
  );
}

function PageShell({ kicker, title, sub, side, children }) {
  return (
    <main className={`stage page-stage ${side ? "" : "stage-single"}`}>
      {side ? <div className="left-col">{side}</div> : null}
      <section className="page-col">
        <div className="piece-kind-row">
          <span className="piece-kind-badge">{kicker}</span>
          <span className="piece-kind-sep" />
        </div>
        <h1 className="page-title">{title}</h1>
        {sub ? <p className="page-sub">{sub}</p> : null}
        {children}
      </section>
    </main>
  );
}

function PostCard({ post }) {
  const href = postHref(post);
  const moderationText = moderationLabel(post.moderation_status);
  const moderationClass = post.moderation_status ? `status-${post.moderation_status}` : "";
  const moderationTitle = post.moderation_reason
    ? `${moderationText}: ${post.moderation_reason}`
    : moderationText;
  return (
    <a className={`piece-card ${post.super_likes_count > 0 ? "has-super-like" : ""}`} href={href}>
      <div className="piece-card-kicker-row">
        <span className="piece-card-kicker">{post.category_name ?? categoryLabel(post.category)}</span>
        {moderationText ? (
          <span className={`piece-card-status ${moderationClass}`} title={moderationTitle}>
            {moderationText}
          </span>
        ) : null}
      </div>
      <h2 className="piece-card-title">{post.title}</h2>
      <p className="piece-card-excerpt">{htmlToText(post.content)}</p>
      <div className="piece-card-meta">
        {post.owner?.username ? <span>{post.owner.username}</span> : null}
        {post.created_at ? <span>{formatDateTime(post.created_at)}</span> : null}
      </div>
    </a>
  );
}

function AccessModal({ modal, onClose }) {
  if (!modal) return null;
  return (
    <div className="access-modal-scrim" role="presentation" onClick={onClose}>
      <section className="access-modal" role="dialog" aria-modal="true" aria-labelledby="access-modal-title" onClick={(event) => event.stopPropagation()}>
        <button className="access-modal-close" type="button" aria-label="Închide" onClick={onClose}>x</button>
        <div className="piece-card-kicker">{modal.kicker || "călimara.ro"}</div>
        <h2 id="access-modal-title" className="access-modal-title">{modal.title}</h2>
        <p className="access-modal-body">{modal.message}</p>
        <div className="button-row">
          {modal.actionHref ? <a className="cal-btn primary" href={modal.actionHref}>{modal.actionLabel}</a> : null}
          <button className="cal-btn" type="button" onClick={onClose}>Închide</button>
        </div>
      </section>
    </div>
  );
}

function LandingPostActions({ post, user, onPostChange }) {
  const [postState, setPostState] = useState(post);
  const [liked, setLiked] = useState(false);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");
  const [modal, setModal] = useState(null);
  const [audioTrack, setAudioTrack] = useState(null);
  const [commentOpen, setCommentOpen] = useState(false);
  const [commentText, setCommentText] = useState("");

  useEffect(() => {
    setPostState(post);
    setLiked(false);
    setStatus("");
    setAudioTrack(null);
    setCommentOpen(false);
    setCommentText("");
  }, [post?.id]);

  if (!postState) return null;

  const href = postHref(postState);
  const updatePost = (updater) => {
    const next = updater(postState);
    setPostState(next);
    onPostChange?.(next);
  };

  const showLoginModal = (message = "Pentru această acțiune trebuie să intri în cont.") => {
    setModal({
      title: "Autentificare necesară",
      message,
      actionHref: AUTH_GOOGLE_PATH,
      actionLabel: "Autentifică-te"
    });
  };

  const requireUser = (message) => {
    if (user) return true;
    showLoginModal(message);
    return false;
  };

  const pdfHref = postState.owner?.username && postState.slug
    ? postPdfUrl(postState.owner.username, postState.slug)
    : "#";

  const handleLike = async () => {
    setBusy("like");
    setStatus("");
    try {
      await likePost(postState.id);
      setLiked(true);
      updatePost((current) => ({ ...current, likes_count: (current.likes_count ?? 0) + 1 }));
    } catch (requestError) {
      if (requestError.status === 409) {
        setLiked(true);
        setStatus("Ai apreciat deja acest text.");
      } else {
        setStatus(requestError.message || "Nu am putut salva aprecierea.");
      }
    } finally {
      setBusy("");
    }
  };

  const handleSuperLike = async () => {
    if (!requireUser("Pentru super-apreciere trebuie să intri în cont.")) return;
    setBusy("super");
    setStatus("");
    try {
      if (postState.viewer_super_liked) {
        await removeSuperLike(postState.id);
        updatePost((current) => ({
          ...current,
          viewer_super_liked: false,
          super_likes_count: Math.max(0, (current.super_likes_count ?? 0) - 1)
        }));
      } else {
        await addSuperLike(postState.id);
        updatePost((current) => ({
          ...current,
          viewer_super_liked: true,
          super_likes_count: (current.super_likes_count ?? 0) + 1
        }));
      }
    } catch (requestError) {
      setModal({
        kicker: "super-apreciez",
        title: "Super-apreciere indisponibilă",
        message: requestError.message || "Nu am putut salva super-aprecierea.",
        actionHref: requestError.status === 403 ? mainPath("/premium") : null,
        actionLabel: "Vezi Premium"
      });
    } finally {
      setBusy("");
    }
  };

  const handleAudio = async () => {
    setBusy("audio");
    setStatus("");
    try {
      const data = await fetchPostAudioStatus(postState.id);
      if (data.available && data.playback_url) {
        setAudioTrack(data);
      } else {
        setModal({
          kicker: "audio",
          title: "Audio indisponibil",
          message: data.message || audioStatusText(data.status)
        });
      }
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut încărca audio.");
    } finally {
      setBusy("");
    }
  };

  const openComment = () => {
    if (!requireUser("Pentru comentarii trebuie să intri în cont.")) return;
    setCommentOpen((open) => !open);
  };

  const submitComment = async (event) => {
    event.preventDefault();
    const content = commentText.trim();
    if (!content) return;
    setBusy("comment");
    setStatus("");
    try {
      await createComment(postState.id, { content });
      setCommentText("");
      setStatus(COMMENT_MODERATION_MESSAGE);
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut trimite comentariul.");
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="landing-post-tools">
      <div className="piece-actions" aria-label="Acțiuni text">
        <a className="react-btn react-link" href={pdfHref}>PDF</a>
        <button className={`react-btn react-like ${liked ? "on" : ""}`} type="button" onClick={handleLike} disabled={busy === "like"} aria-pressed={liked}>
          Apreciază
          <span className="react-count">{Number(postState.likes_count ?? 0).toLocaleString("ro-RO")}</span>
        </button>
        <button className={`react-btn react-super ${postState.viewer_super_liked ? "on" : ""}`} type="button" onClick={handleSuperLike} disabled={busy === "super"} aria-pressed={Boolean(postState.viewer_super_liked)}>
          Super
          <span className="react-count">{Number(postState.super_likes_count ?? 0).toLocaleString("ro-RO")}</span>
        </button>
        <button className="react-btn" type="button" onClick={handleAudio} disabled={busy === "audio"}>{busy === "audio" ? "Se încarcă..." : "Audio"}</button>
        <button className="react-btn" type="button" onClick={openComment} aria-expanded={commentOpen}>Comentează</button>
        <a className="react-btn react-link" href={href}>Deschide</a>
      </div>

      {audioTrack?.playback_url ? (
        <div className="landing-audio-player">
          <div className="piece-card-kicker">{audioTrack.source === "author" ? "înregistrare autor" : "voce generată"}</div>
          <audio className="audio-player" controls src={audioTrack.playback_url}>
            Browserul tău nu poate reda acest fișier audio.
          </audio>
        </div>
      ) : null}

      {commentOpen ? (
        <form className="landing-comment-panel" onSubmit={submitComment}>
          <label className="auth-field" htmlFor="landing-comment">Comentariu</label>
          <textarea id="landing-comment" className="cal-textarea" value={commentText} onChange={(event) => setCommentText(event.target.value)} maxLength="2000" required />
          <button className="cal-btn primary" type="submit" disabled={busy === "comment"}>{busy === "comment" ? "Se trimite..." : "Trimite comentariul"}</button>
        </form>
      ) : null}

      {status ? <div className="inline-error">{status}</div> : null}
      <AccessModal modal={modal} onClose={() => setModal(null)} />
    </div>
  );
}

function LandingView({ user }) {
  const [kind, setKind] = useState("poem");
  const [piece, setPiece] = useState(fallbackPiece("poem"));
  const [landingPost, setLandingPost] = useState(null);
  const [stats, setStats] = useState(null);
  const [animKey, setAnimKey] = useState(0);
  const [transitioning, setTransitioning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const loadLanding = useCallback(async (nextKind, initial = false) => {
    if (!initial) setTransitioning(true);
    setError("");
    try {
      const data = await fetchLanding(KIND_TO_CATEGORY[nextKind]);
      const post = data.random_posts?.[0];
      setKind(nextKind);
      setStats(data.stats ?? null);
      setLandingPost(post ?? null);
      setPiece(post ? postToPiece(post) : fallbackPiece(nextKind));
      setAnimKey((key) => key + 1);
    } catch (requestError) {
      setError(requestError.message || "Nu am putut încărca textul.");
      setKind(nextKind);
      setLandingPost(null);
      setPiece(fallbackPiece(nextKind));
      setAnimKey((key) => key + 1);
    } finally {
      setLoading(false);
      window.setTimeout(() => setTransitioning(false), initial ? 0 : 80);
    }
  }, []);

  useEffect(() => {
    loadLanding("poem", true);
  }, [loadLanding]);

  useEffect(() => {
    const onKey = (event) => {
      const target = event.target;
      if (target && (["INPUT", "TEXTAREA"].includes(target.tagName) || target.isContentEditable)) return;
      if (event.key === "p" || event.key === "P") {
        event.preventDefault();
        loadLanding("poem");
      }
      if (event.key === "s" || event.key === "S") {
        event.preventDefault();
        loadLanding("story");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [loadLanding]);

  const openRandomAuthor = async () => {
    setBusy("author");
    try {
      const author = await fetchRandomUser();
      window.location.href = blogUrl(author.username);
    } catch (requestError) {
      setError(requestError.message || "Nu am putut deschide un autor.");
    } finally {
      setBusy("");
    }
  };

  return (
    <main className="stage">
      <div className="left-col">
        <SideActions
          kind={kind}
          onPoem={() => loadLanding("poem")}
          onStory={() => loadLanding("story")}
          onAuthor={openRandomAuthor}
          disabled={transitioning || loading}
          busy={busy}
        />
        <Rail stats={stats} />
        <JoinReasons />
        <AdSlot placement="rail" />
        {error ? <div className="inline-error">{error}</div> : null}
      </div>
      <div className={`piece-wrap ${transitioning ? "transitioning" : ""} ${landingPost?.super_likes_count > 0 ? "has-super-like" : ""}`}>
        <PieceCol piece={piece} animKey={animKey} />
        <LandingPostActions post={landingPost} user={user} onPostChange={setLandingPost} />
      </div>
    </main>
  );
}

function CategoryView({ categoryKey }) {
  const { data, error, loading } = useAsync(() => fetchCategory(categoryKey), [categoryKey]);
  return (
    <PageShell
      kicker="categorie"
      title={data?.category_name ?? categoryLabel(categoryKey)}
      sub="Texte publicate în această categorie."
      side={
        <aside className="side-col">
          <div className="side-kicker">categorii</div>
          <div className="actions-group">
            <ActionRow number="01" label="Poezie" active={categoryKey === "poezie"} onClick={() => { window.location.href = mainPath("/category/poezie"); }} />
            <ActionRow number="02" label="Proză scurtă" active={categoryKey === "proza_scurta"} onClick={() => { window.location.href = mainPath("/category/proza_scurta"); }} />
          </div>
        </aside>
      }
    >
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca categoria">{error}</StatusPanel> : null}
      {data?.posts?.length ? (
        <div className="list-grid">
          {data.posts.map((post, index) => (
            <Fragment key={post.id}>
              <PostCard post={post} />
              {index === 1 ? <AdSlot placement="inline" /> : null}
            </Fragment>
          ))}
        </div>
      ) : !loading && !error ? <StatusPanel title="Nu există texte încă" /> : null}
    </PageShell>
  );
}

function ClubsView() {
  const { data, error, loading } = useAsync(fetchClubs, []);
  return (
    <PageShell kicker="cluburi" title="Cluburi literare" sub="Comunități pentru poezie și proză scurtă.">
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca cluburile">{error}</StatusPanel> : null}
      {data?.clubs?.length ? (
        <div className="list-grid">
          {data.clubs.map((club, index) => (
            <Fragment key={club.id}>
              <a className="piece-card" href={mainPath(`/cluburi/${club.slug}`)}>
                <div className="piece-card-kicker">{categoryLabel(club.speciality)}</div>
                <h2 className="piece-card-title">{club.title}</h2>
                <p className="piece-card-excerpt">{club.description || club.motto || "Club literar pe călimara.ro."}</p>
                <div className="piece-card-meta">
                  <span>{club.member_count} membri</span>
                  {club.owner?.username ? <span>{club.owner.username}</span> : null}
                </div>
              </a>
              {index === 1 ? <AdSlot placement="inline" /> : null}
            </Fragment>
          ))}
        </div>
      ) : !loading && !error ? <StatusPanel title="Nu există cluburi încă" /> : null}
    </PageShell>
  );
}

function ClubDetailView({ slug }) {
  const { data, error, loading } = useAsync(() => fetchClub(slug), [slug]);
  return (
    <PageShell kicker="club" title={data?.title ?? "Club"} sub={data?.motto || data?.description}>
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca clubul">{error}</StatusPanel> : null}
      {data ? (
        <div className="detail-stack">
          <div className="rail">
            <div className="rail-stat">
              <span className="rail-label">Membri</span>
              <span className="rail-count">{data.member_count}</span>
              <span className="rail-sub">{categoryLabel(data.speciality)}</span>
            </div>
          </div>
          {data.members?.length ? (
            <div className="list-grid compact">
              {data.members.map((member) => (
                <a className="piece-card" key={member.id} href={blogUrl(member.username)}>
                  <div className="piece-card-kicker">{member.role}</div>
                  <h2 className="piece-card-title">{member.username}</h2>
                  <p className="piece-card-excerpt">{member.contribution_count} contribuții</p>
                </a>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </PageShell>
  );
}

function BlogView({ username }) {
  const { data, error, loading } = useAsync(() => fetchBlog(username), [username]);
  const posts = data ? [...(data.featured_posts || []), ...(data.latest_posts || []), ...(data.all_posts || [])] : [];
  const uniquePosts = posts.filter((post, index, all) => all.findIndex((item) => item.id === post.id) === index);
  return (
    <PageShell kicker="blog" title={data?.blog_owner?.username ?? username} sub={data?.blog_owner?.subtitle ?? "Texte publicate pe călimara.ro."}>
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca blogul">{error}</StatusPanel> : null}
      <EquippedStrip items={data?.blog_owner?.equipped_items} />
      {uniquePosts.length ? (
        <div className="list-grid">
          {uniquePosts.map((post, index) => (
            <Fragment key={post.id}>
              <PostCard post={{ ...post, owner: data.blog_owner }} />
              {index === 1 ? <AdSlot placement="inline" /> : null}
            </Fragment>
          ))}
        </div>
      ) : !loading && !error ? <StatusPanel title="Nu există texte încă" /> : null}
    </PageShell>
  );
}

function CollectionView({ slug }) {
  const { data, error, loading } = useAsync(() => fetchCollection(slug), [slug]);
  const posts = data?.posts?.map((entry) => entry.post).filter(Boolean) ?? [];
  const pdfHref = data?.slug ? collectionPdfUrl(data.slug) : "#";

  return (
    <PageShell
      kicker="colecție"
      title={data?.title ?? "Colecție"}
      sub={data?.description || (data?.owner?.username ? `Colecție de ${data.owner.username}.` : "Texte grupate pe călimara.ro.")}
    >
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca colecția">{error}</StatusPanel> : null}
      {data ? (
        <div className="detail-stack">
          <div className="piece-actions" aria-label="Acțiuni colecție">
            <a className="react-btn react-link" href={pdfHref}>PDF</a>
            {data.owner?.username ? (
              <a className="react-btn react-link" href={blogUrl(data.owner.username)}>Autor</a>
            ) : null}
          </div>
          {posts.length ? (
            <div className="list-grid">
              {posts.map((post, index) => (
                <Fragment key={post.id}>
                  <a className={`piece-card ${post.super_likes_count > 0 ? "has-super-like" : ""}`} href={postHref(post)}>
                    <div className="piece-card-kicker">{categoryLabel(post.category)}</div>
                    <h2 className="piece-card-title">{post.title}</h2>
                    <div className="piece-card-meta">
                      {post.owner?.username ? <span>{post.owner.username}</span> : null}
                    </div>
                  </a>
                  {index === 1 ? <AdSlot placement="inline" /> : null}
                </Fragment>
              ))}
            </div>
          ) : (
            <StatusPanel title="Colecția nu are texte publice încă" />
          )}
        </div>
      ) : null}
    </PageShell>
  );
}

function audioStatusText(status) {
  if (status === "pending") return "Fișierul audio este în coada de generare și va fi disponibil în câteva secunde, cu voia Robotului.";
  if (status === "processing") return "Fișierul audio se generează și va fi disponibil în câteva secunde, cu voia Robotului.";
  if (status === "flagged") return "Fișierul audio este în curs de revizuire.";
  if (status === "failed") return "Generarea audio a eșuat.";
  if (status === "post_pending") return "Audio devine disponibil după aprobarea postării.";
  if (status === "missing") return "Nu există încă fișier audio pentru acest text.";
  return "Audio indisponibil momentan.";
}

function AudioStatusPanel({ postId, user }) {
  const { data, error, loading } = useAsync(() => fetchPostAudioStatus(postId), [postId]);

  return (
    <section className="audio-panel" aria-label="Audio text">
      <div className="piece-card-kicker">audio</div>
      {loading ? <p className="auth-sub">Se verifică fișierul audio...</p> : null}
      {error ? <div className="inline-error">{error}</div> : null}
      {data && data.available && data.playback_url ? (
        <>
          <div className="audio-head">
            <h2 className="audio-title">Ascultă textul</h2>
            <span className="audio-source">{data.source === "author" ? "înregistrare autor" : "voce generată"}</span>
          </div>
          <audio className="audio-player" controls src={data.playback_url}>
            Browserul tău nu poate reda acest fișier audio.
          </audio>
        </>
      ) : null}
      {data && data.available && !data.playback_url ? (
        <div className="audio-head">
          <div>
            <h2 className="audio-title">Audio disponibil</h2>
            <p className="auth-sub">{data.message || "Fișierul audio nu poate fi redat momentan."}</p>
          </div>
        </div>
      ) : null}
      {data && !data.available ? <p className="auth-sub">{data.message || audioStatusText(data.status)}</p> : null}
    </section>
  );
}

function PostDetailView({ username, slug, user }) {
  const { data, error, loading } = useAsync(() => fetchPostDetail(username, slug), [username, slug, user?.id]);
  const piece = data ? postToPiece({ ...data.post, owner: data.blog_owner }) : null;
  const pdfHref = data?.blog_owner?.username && data?.post?.slug
    ? postPdfUrl(data.blog_owner.username, data.post.slug)
    : "#";
  return (
    <main className="stage stage-single">
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca textul">{error}</StatusPanel> : null}
      {piece ? (
        <div className="piece-wrap">
          <div className="detail-stack">
            {data.post.moderation_status !== "approved" ? (
              <StatusPanel title="Text în curs de moderare">{TEXT_MODERATION_MESSAGE}</StatusPanel>
            ) : null}
            <PieceCol piece={piece} animKey={slug} />
            {data.post.moderation_status === "approved" ? (
              <div className="piece-actions detail-actions" aria-label="Acțiuni text">
                <a className="react-btn react-link" href={pdfHref}>PDF</a>
              </div>
            ) : null}
            <AudioStatusPanel postId={data.post.id} user={user} />
            <AdSlot placement="postFooter" />
          </div>
        </div>
      ) : null}
    </main>
  );
}

function AuthRequired() {
  return (
    <PageShell kicker="cont" title="Autentificare necesară" sub="Această zonă folosește sesiunea ta călimara.ro.">
      <a className="cal-btn primary" href={AUTH_GOOGLE_PATH}>Autentificare cu Google</a>
    </PageShell>
  );
}

function DashboardView({ user }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { data, error, loading } = useAsync(
    () => (user ? fetchArchive() : Promise.resolve({ posts: [] })),
    [user?.id, refreshKey]
  );
  const quotaState = useAsync(
    () => (user ? fetchAudioConversionQuota() : Promise.resolve(null)),
    [user?.id, refreshKey]
  );

  if (!user) return <AuthRequired />;

  const posts = data?.posts ?? [];
  const quota = quotaState.data;
  const canRequestAudio = Boolean(quota?.can_request);
  const selectedPosts = posts.filter((post) => selectedIds.has(post.id));
  const selectedCharacters = selectedPosts.reduce((sum, post) => sum + Number(post.audio_tts_character_count ?? 0), 0);
  const remaining = Number(quota?.remaining ?? 0);
  const overQuota = selectedCharacters > remaining;

  const togglePost = (post, checked) => {
    setStatus("");
    setSelectedIds((current) => {
      const next = new Set(current);
      if (checked) next.add(post.id);
      else next.delete(post.id);
      return next;
    });
  };

  const submitAudioRequests = async () => {
    if (!selectedIds.size || overQuota || submitting) return;
    setSubmitting(true);
    setStatus("");
    try {
      const response = await requestTtsConversions([...selectedIds]);
      setSelectedIds(new Set());
      setStatus(
        response.queued.length
          ? `${response.queued.length} texte au fost trimise la generare audio.`
          : "Textele selectate aveau deja audio sau erau deja în coadă."
      );
      setRefreshKey((key) => key + 1);
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut porni generarea audio.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <PageShell kicker="panou" title="Textele tale" sub={`Conectat ca ${user.username}.`}>
      <section className="audio-quota-panel" aria-label="Cotă generare audio">
        <div>
          <div className="piece-card-kicker">generare audio</div>
          {quotaState.loading ? (
            <p className="auth-sub">Se încarcă limita de generare audio...</p>
          ) : canRequestAudio ? (
            <p className="quota-line">
              {formatNumber(quota.used)} / {formatNumber(quota.limit)} caractere folosite
              {quota.period_end ? ` până la ${formatDateTime(quota.period_end)}` : ""}.
            </p>
          ) : (
            <p className="auth-sub">Generarea audio manuală este disponibilă pentru Membru Junimea și La cenaclu' Flacăra.</p>
          )}
        </div>
        {quotaState.loading ? null : canRequestAudio ? (
          <div className="quota-actions">
            <span className={`quota-pill ${overQuota ? "danger" : ""}`}>
              Selectat: {formatNumber(selectedCharacters)} / {formatNumber(remaining)}
            </span>
            <button className="cal-btn primary" type="button" onClick={submitAudioRequests} disabled={!selectedIds.size || overQuota || submitting}>
              {submitting ? "Se trimite..." : "Generează audio"}
            </button>
          </div>
        ) : <a className="cal-btn" href={mainPath("/premium")}>Vezi Premium</a>}
      </section>
      {quotaState.error ? <div className="inline-error">{quotaState.error}</div> : null}
      {status ? <div className={status.includes("Nu am putut") || status.includes("depășită") ? "inline-error" : "inline-status"}>{status}</div> : null}
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca panoul">{error}</StatusPanel> : null}
      {data?.posts?.length ? (
        <div className="dashboard-list">
          {posts.map((post) => {
            const selected = selectedIds.has(post.id);
            const wouldExceed = !selected && selectedCharacters + Number(post.audio_tts_character_count ?? 0) > remaining;
            const disabled = !canRequestAudio || !post.audio_can_request || wouldExceed || submitting;
            return (
              <DashboardPostCard
                key={post.id}
                post={post}
                selected={selected}
                disabled={disabled}
                onToggle={(checked) => togglePost(post, checked)}
              />
            );
          })}
        </div>
      ) : !loading && !error ? <StatusPanel title="Nu ai texte încă" /> : null}
    </PageShell>
  );
}

function DashboardPostCard({ post, selected, disabled, onToggle }) {
  const href = postHref(post);
  const characterCount = Number(post.audio_tts_character_count ?? 0);
  const audioReady = Boolean(post.audio_available && post.audio_playback_url);
  return (
    <article className={`dashboard-post-card ${selected ? "selected" : ""}`}>
      <label className="dashboard-select">
        <input
          type="checkbox"
          checked={selected}
          disabled={disabled}
          onChange={(event) => onToggle(event.target.checked)}
        />
        <span>Selectează pentru audio</span>
      </label>
      <div className="dashboard-post-main">
        <div className="piece-card-kicker-row">
          <span className="piece-card-kicker">{categoryLabel(post.category)}</span>
          <span className="piece-card-status">{post.moderation_status}</span>
        </div>
        <h2 className="piece-card-title"><a href={href}>{post.title}</a></h2>
        <p className="piece-card-excerpt">{htmlToText(post.content)}</p>
        <div className="piece-card-meta">
          <span>{formatNumber(characterCount)} caractere</span>
          <span>{audioStatusLabel(post.audio_status)}</span>
          {post.created_at ? <span>{post.created_at}</span> : null}
        </div>
        {audioReady ? (
          <audio className="audio-player compact" controls src={post.audio_playback_url}>
            Browserul tău nu poate reda acest fișier audio.
          </audio>
        ) : null}
      </div>
    </article>
  );
}

function AdminStat({ label, value, sub }) {
  return (
    <div className="admin-stat">
      <span className="rail-label">{label}</span>
      <span className="rail-count">{Number(value ?? 0).toLocaleString("ro-RO")}</span>
      {sub ? <span className="rail-sub">{sub}</span> : null}
    </div>
  );
}

function AdminWorkRow({ item, mode, busy, onApprove, onReject }) {
  const [rejectReason, setRejectReason] = useState("");
  const isFlagged = mode === "flagged";
  const content = isFlagged ? item.content : item;
  const contentType = isFlagged ? item.content_type : item.type;
  const itemId = isFlagged ? item.log_id : `${contentType}:${item.id}`;
  const title = content?.title || content?.post_title || contentTypeLabel(contentType);
  const preview = content?.content || item.content || "";
  const author = content?.author || item.author || "Unknown";
  const createdAt = content?.created_at || item.created_at || item.flagged_at;
  const score = isFlagged ? item.ai_analysis?.toxicity_score : item.toxicity_score;
  const reason = isFlagged ? item.ai_analysis?.reason : item.moderation_reason;
  const status = isFlagged ? item.ai_analysis?.decision : item.moderation_status;
  const approveBusy = busy === `${mode}:${itemId}:approve`;
  const rejectBusy = busy === `${mode}:${itemId}:reject`;

  const submitReject = () => {
    const reasonText = rejectReason.trim();
    if (!reasonText) return;
    onReject(item, reasonText);
  };

  return (
    <article className="admin-row">
      <div className="admin-row-head">
        <div>
          <div className="admin-badges">
            <span className="piece-card-status">{contentTypeLabel(contentType)}</span>
            {status ? <span className="piece-card-status status-flagged">{decisionLabel(status)}</span> : null}
            {score !== null && score !== undefined ? <span className="piece-card-status">{formatScore(score)}</span> : null}
          </div>
          <h2 className="admin-row-title">{title}</h2>
        </div>
        <div className="admin-row-meta">
          <span>{author}</span>
          {createdAt ? <span>{formatDateTime(createdAt)}</span> : null}
        </div>
      </div>
      {preview ? <p className="admin-preview">{htmlToText(preview)}</p> : null}
      {reason ? <p className="admin-reason">{reason}</p> : null}
      <div className="admin-actions">
        <button className="cal-btn primary" type="button" disabled={Boolean(busy)} onClick={() => onApprove(item)}>
          {approveBusy ? "Se aprobă..." : "Aprobă"}
        </button>
        <div className="admin-reject-row">
          <input
            className="cal-input"
            value={rejectReason}
            onChange={(event) => setRejectReason(event.target.value)}
            placeholder="Motiv respingere"
            aria-label="Motiv respingere"
          />
          <button className="cal-btn" type="button" disabled={Boolean(busy) || !rejectReason.trim()} onClick={submitReject}>
            {rejectBusy ? "Se respinge..." : "Respinge"}
          </button>
        </div>
      </div>
    </article>
  );
}

function AdminJournalRow({ log }) {
  return (
    <article className="admin-row">
      <div className="admin-row-head">
        <div>
          <div className="admin-badges">
            <span className="piece-card-status">{contentTypeLabel(log.content_type)}</span>
            <span className="piece-card-status status-flagged">AI: {decisionLabel(log.ai_decision)}</span>
            <span className="piece-card-status">Om: {decisionLabel(log.human_decision)}</span>
            {log.needs_review ? <span className="piece-card-status status-rejected">review</span> : null}
          </div>
          <h2 className="admin-row-title">{log.content_title || contentTypeLabel(log.content_type)}</h2>
        </div>
        <div className="admin-row-meta">
          {log.content_author ? <span>{log.content_author}</span> : null}
          {log.created_at ? <span>{formatDateTime(log.created_at)}</span> : null}
        </div>
      </div>
      {log.content_preview ? <p className="admin-preview">{htmlToText(log.content_preview)}</p> : null}
      <div className="admin-journal-grid">
        <span>toxicitate {formatScore(log.toxicity_score)}</span>
        {log.moderator ? <span>moderator {log.moderator}</span> : null}
        {log.moderated_at ? <span>moderat {formatDateTime(log.moderated_at)}</span> : null}
      </div>
      {log.ai_reason ? <p className="admin-reason">{log.ai_reason}</p> : null}
      {log.human_reason ? <p className="admin-reason">{log.human_reason}</p> : null}
    </article>
  );
}

function AdminDashboardView({ user }) {
  const [activeTab, setActiveTab] = useState("pending");
  const [state, setState] = useState({
    stats: null,
    extendedStats: null,
    pending: [],
    flagged: [],
    logs: [],
    error: "",
    loading: true
  });
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");

  const canModerate = Boolean(user?.is_admin || user?.is_moderator);

  const loadAdminData = useCallback(async () => {
    if (!canModerate) {
      setState((current) => ({ ...current, loading: false }));
      return;
    }
    setState((current) => ({ ...current, loading: true, error: "" }));
    try {
      const [stats, extendedStats, pending, flagged, logs] = await Promise.all([
        fetchModerationStats(),
        fetchExtendedModerationStats(),
        fetchPendingModerationContent(),
        fetchModerationQueue(),
        fetchModerationLogs({ limit: 100 })
      ]);
      setState({
        stats,
        extendedStats,
        pending: pending.content || [],
        flagged: flagged.queue || [],
        logs: logs.logs || [],
        error: "",
        loading: false
      });
    } catch (requestError) {
      setState((current) => ({
        ...current,
        error: requestError.message || "Nu am putut încărca moderarea.",
        loading: false
      }));
    }
  }, [canModerate]);

  useEffect(() => {
    loadAdminData();
  }, [loadAdminData]);

  if (!user) return <AuthRequired />;
  if (!canModerate) {
    return (
      <PageShell kicker="admin" title="Acces refuzat" sub="Contul curent nu are drepturi de moderare." />
    );
  }

  const runAction = async (key, action) => {
    setBusy(key);
    setStatus("");
    try {
      await action();
      setStatus("Acțiunea a fost salvată.");
      await loadAdminData();
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut salva acțiunea.");
    } finally {
      setBusy("");
    }
  };

  const approvePending = (item) => runAction(
    `pending:${item.type}:${item.id}:approve`,
    () => moderateContent(item.type, item.id, { action: "approve", reason: "Approved from admin dashboard" })
  );
  const rejectPending = (item, reason) => runAction(
    `pending:${item.type}:${item.id}:reject`,
    () => moderateContent(item.type, item.id, { action: "reject", reason })
  );
  const approveFlagged = (item) => runAction(
    `flagged:${item.log_id}:approve`,
    () => reviewModerationLog(item.log_id, { action: "approved", reason: "Approved from admin dashboard" })
  );
  const rejectFlagged = (item, reason) => runAction(
    `flagged:${item.log_id}:reject`,
    () => reviewModerationLog(item.log_id, { action: "rejected", reason })
  );

  const tabs = [
    ["pending", "În așteptare AI", state.pending.length],
    ["flagged", "Marcate", state.flagged.length],
    ["journal", "Jurnal", state.logs.length]
  ];

  return (
    <PageShell kicker="admin" title="Moderare" sub={`Conectat ca ${user.username}.`}>
      <div className="admin-stat-grid">
        <AdminStat label="Pending" value={state.stats?.pending_count} sub="în coadă" />
        <AdminStat label="Marcate" value={state.stats?.flagged_count} sub="AI / manual" />
        <AdminStat label="Azi" value={state.stats?.today_actions} sub="decizii" />
        <AdminStat label="Jurnal" value={state.extendedStats?.total_logs} sub="intrări" />
        <AdminStat label="Review" value={state.extendedStats?.pending_review_count} sub="uman" />
      </div>

      <div className="admin-tabs" role="tablist" aria-label="Moderare">
        {tabs.map(([key, label, count]) => (
          <button
            key={key}
            className={`admin-tab ${activeTab === key ? "active" : ""}`}
            type="button"
            role="tab"
            aria-selected={activeTab === key}
            onClick={() => setActiveTab(key)}
          >
            <span>{label}</span>
            <strong>{Number(count || 0).toLocaleString("ro-RO")}</strong>
          </button>
        ))}
      </div>

      {state.loading ? <StatusPanel title="Se încarcă" /> : null}
      {state.error ? <StatusPanel title="Nu am putut încărca adminul">{state.error}</StatusPanel> : null}
      {status ? <div className="inline-error">{status}</div> : null}

      {!state.loading && !state.error && activeTab === "pending" ? (
        state.pending.length ? (
          <div className="admin-feed">
            {state.pending.map((item) => (
              <AdminWorkRow
                key={`${item.type}-${item.id}`}
                item={item}
                mode="pending"
                busy={busy}
                onApprove={approvePending}
                onReject={rejectPending}
              />
            ))}
          </div>
        ) : <StatusPanel title="Nu există conținut în așteptare AI" />
      ) : null}

      {!state.loading && !state.error && activeTab === "flagged" ? (
        state.flagged.length ? (
          <div className="admin-feed">
            {state.flagged.map((item) => (
              <AdminWorkRow
                key={item.log_id}
                item={item}
                mode="flagged"
                busy={busy}
                onApprove={approveFlagged}
                onReject={rejectFlagged}
              />
            ))}
          </div>
        ) : <StatusPanel title="Nu există conținut marcat" />
      ) : null}

      {!state.loading && !state.error && activeTab === "journal" ? (
        state.logs.length ? (
          <div className="admin-feed">
            {state.logs.map((log) => <AdminJournalRow key={log.id} log={log} />)}
          </div>
        ) : <StatusPanel title="Jurnalul este gol" />
      ) : null}
    </PageShell>
  );
}

function CreatePostView({ user }) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!user) return <AuthRequired />;

  const submit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setStatus("");
    try {
      const post = await createPost({ title, content });
      window.location.href = `${blogUrl(user.username)}/${post.slug}`;
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut publica textul.");
      setSubmitting(false);
    }
  };

  return (
    <PageShell kicker="scrie" title="Text nou" sub="Publică un text în blogul tău. Categoria este detectată automat.">
      <form className="form-stack" onSubmit={submit}>
        <label className="auth-field" htmlFor="post-title">Titlu</label>
        <input id="post-title" className="cal-input" value={title} onChange={(event) => setTitle(event.target.value)} required />
        <label className="auth-field" htmlFor="post-content">Text</label>
        <textarea id="post-content" className="cal-textarea tall" value={content} onChange={(event) => setContent(event.target.value)} required />
        {status ? <div className="inline-error">{status}</div> : null}
        <button className="cal-btn primary" type="submit" disabled={submitting}>{submitting ? "Se publică..." : "Publică"}</button>
      </form>
    </PageShell>
  );
}

function MessagesView({ user }) {
  const { data, error, loading } = useAsync(fetchConversations, []);
  if (!user) return <AuthRequired />;
  return (
    <PageShell kicker="mesaje" title="Conversații" sub="Mesajele contului tău.">
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca mesajele">{error}</StatusPanel> : null}
      {data?.conversations?.length ? (
        <div className="list-grid">
          {data.conversations.map((conversation) => (
            <div className="piece-card" key={conversation.id}>
              <div className="piece-card-kicker">{conversation.unread_count ? `${conversation.unread_count} necitite` : "conversație"}</div>
              <h2 className="piece-card-title">{conversation.other_user?.username}</h2>
              <p className="piece-card-excerpt">{conversation.latest_message?.content || "Fără mesaje încă."}</p>
            </div>
          ))}
        </div>
      ) : !loading && !error ? <StatusPanel title="Nu ai conversații încă" /> : null}
    </PageShell>
  );
}

function CosmeticPreview({ item }) {
  return (
    <div className="cosmetic-preview" aria-hidden="true">
      {item?.asset_url ? <img src={item.asset_url} alt="" /> : <span>{item?.name?.slice(0, 2) || "G"}</span>}
    </div>
  );
}

function EquippedStrip({ items }) {
  if (!items?.length) return null;
  return (
    <div className="cosmetic-strip" aria-label="Cosmetice echipate">
      {items.map((entry) => (
        <span className="cosmetic-chip" key={`${entry.slot}-${entry.item?.id}`}>
          <span>{slotLabel(entry.slot)}</span>
          <strong>{entry.item?.name}</strong>
        </span>
      ))}
    </div>
  );
}

function useShopState(user) {
  const [state, setState] = useState({ data: null, error: "", loading: Boolean(user) });

  const load = useCallback(async () => {
    if (!user) {
      setState({ data: null, error: "", loading: false });
      return;
    }
    setState((current) => ({ ...current, error: "", loading: true }));
    try {
      const data = await fetchShopState();
      setState({ data, error: "", loading: false });
    } catch (requestError) {
      setState({ data: null, error: requestError.message || "Nu am putut încărca magazinul.", loading: false });
    }
  }, [user?.id]);

  useEffect(() => {
    load();
  }, [load]);

  return [state, setState];
}

function ShopView({ user }) {
  const [{ data, error, loading }, setState] = useShopState(user);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");

  if (!user) return <AuthRequired />;

  const purchase = async (item) => {
    setBusy(`purchase-${item.id}`);
    setStatus("");
    try {
      const next = await purchaseShopItem(item.id);
      setState({ data: next, error: "", loading: false });
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut cumpăra obiectul.");
    } finally {
      setBusy("");
    }
  };

  const equip = async (item) => {
    setBusy(`equip-${item.id}`);
    setStatus("");
    try {
      const next = await equipInventoryItem(item.id);
      setState({ data: next, error: "", loading: false });
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut echipa obiectul.");
    } finally {
      setBusy("");
    }
  };

  return (
    <PageShell kicker="magazin" title="Magazin" sub={`${formatGologani(data?.balance ?? user.gologani_balance)} disponibili.`}>
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca magazinul">{error}</StatusPanel> : null}
      {status ? <div className="inline-error">{status}</div> : null}
      {data?.items?.length ? (
        <div className="shop-grid">
          {data.items.map((item) => {
            const canAfford = (data.balance ?? 0) >= item.price;
            return (
              <article className="shop-card" key={item.id}>
                <CosmeticPreview item={item} />
                <div className="piece-card-kicker">{slotLabel(item.slot)}</div>
                <h2 className="piece-card-title">{item.name}</h2>
                <p className="piece-card-excerpt">{item.description || "Obiect cosmetic pentru profil."}</p>
                <div className="shop-card-foot">
                  <span className="shop-price">{formatGologani(item.price)}</span>
                  {item.equipped ? (
                    <button className="cal-btn" type="button" disabled>Echipat</button>
                  ) : item.owned ? (
                    <button className="cal-btn primary" type="button" disabled={busy === `equip-${item.id}`} onClick={() => equip(item)}>
                      {busy === `equip-${item.id}` ? "Se echipează..." : "Echipează"}
                    </button>
                  ) : (
                    <button className="cal-btn primary" type="button" disabled={!canAfford || busy === `purchase-${item.id}`} onClick={() => purchase(item)}>
                      {busy === `purchase-${item.id}` ? "Se cumpără..." : "Cumpără"}
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      ) : !loading && !error ? <StatusPanel title="Magazinul este gol" /> : null}
    </PageShell>
  );
}

function InventoryView({ user }) {
  const [{ data, error, loading }, setState] = useShopState(user);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");

  if (!user) return <AuthRequired />;

  const equip = async (item) => {
    setBusy(`equip-${item.id}`);
    setStatus("");
    try {
      const next = await equipInventoryItem(item.id);
      setState({ data: next, error: "", loading: false });
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut echipa obiectul.");
    } finally {
      setBusy("");
    }
  };

  const unequip = async (slot) => {
    setBusy(`unequip-${slot}`);
    setStatus("");
    try {
      const next = await unequipInventorySlot(slot);
      setState({ data: next, error: "", loading: false });
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut dezechipa obiectul.");
    } finally {
      setBusy("");
    }
  };

  return (
    <PageShell kicker="inventar" title="Inventar" sub={`${formatGologani(data?.balance ?? user.gologani_balance)} disponibili.`}>
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca inventarul">{error}</StatusPanel> : null}
      {status ? <div className="inline-error">{status}</div> : null}
      {data?.equipped?.length ? (
        <section className="inventory-section" aria-label="Echipate">
          <div className="piece-card-kicker">echipate</div>
          <div className="inventory-list">
            {data.equipped.map((entry) => (
              <article className="inventory-row" key={entry.slot}>
                <CosmeticPreview item={entry.item} />
                <div>
                  <div className="inventory-title">{entry.item.name}</div>
                  <div className="inventory-meta">{slotLabel(entry.slot)}</div>
                </div>
                <button className="cal-btn" type="button" disabled={busy === `unequip-${entry.slot}`} onClick={() => unequip(entry.slot)}>
                  {busy === `unequip-${entry.slot}` ? "Se scoate..." : "Dezechipează"}
                </button>
              </article>
            ))}
          </div>
        </section>
      ) : null}
      {data?.inventory?.length ? (
        <section className="inventory-section" aria-label="Inventar">
          <div className="piece-card-kicker">obiecte</div>
          <div className="shop-grid">
            {data.inventory.map((entry) => (
              <article className="shop-card" key={entry.id}>
                <CosmeticPreview item={entry.item} />
                <div className="piece-card-kicker">{slotLabel(entry.item.slot)}</div>
                <h2 className="piece-card-title">{entry.item.name}</h2>
                <p className="piece-card-excerpt">{entry.item.description || "Obiect cosmetic pentru profil."}</p>
                <div className="shop-card-foot">
                  <span className="shop-price">în inventar</span>
                  {entry.item.equipped ? (
                    <button className="cal-btn" type="button" disabled>Echipat</button>
                  ) : (
                    <button className="cal-btn primary" type="button" disabled={busy === `equip-${entry.item.id}`} onClick={() => equip(entry.item)}>
                      {busy === `equip-${entry.item.id}` ? "Se echipează..." : "Echipează"}
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : !loading && !error ? (
        <StatusPanel
          title="Inventarul este gol"
          action={<a className="cal-btn primary" href={mainPath("/magazin")}>Deschide magazinul</a>}
        />
      ) : null}
    </PageShell>
  );
}

function ForumListView({ user }) {
  const [section, setSection] = useState("general");
  const { data, error, loading } = useAsync(
    () => (user ? fetchForumThreads(section) : Promise.resolve({ threads: [] })),
    [user?.id, section]
  );

  if (!user) return <AuthRequired />;

  return (
    <PageShell
      kicker="discuții"
      title="Forum"
      sub="Thread-uri pentru întrebări, feedback și conversații între autori."
      side={
        <aside className="side-col">
          <div className="side-kicker">secțiuni</div>
          <div className="actions-group">
            {FORUM_SECTIONS.map((item, index) => (
              <ActionRow
                key={item.key}
                number={String(index + 1).padStart(2, "0")}
                label={item.label}
                active={section === item.key}
                onClick={() => setSection(item.key)}
              />
            ))}
          </div>
          <a className="cal-btn primary" href={mainPath("/discutii/nou")}>Thread nou</a>
        </aside>
      }
    >
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca forumul">{error}</StatusPanel> : null}
      {data?.threads?.length ? (
        <div className="list-grid">
          {data.threads.map((thread) => (
            <a className="piece-card" key={thread.id} href={mainPath(`/discutii/${thread.slug}`)}>
              <div className="piece-card-kicker">{forumSectionLabel(thread.section)}</div>
              <h2 className="piece-card-title">{thread.title}</h2>
              <div className="piece-card-meta">
                {thread.author?.username ? <span>{thread.author.username}</span> : null}
                <span>{thread.reply_count} răspunsuri</span>
                {thread.last_activity_at ? <span>{formatDateTime(thread.last_activity_at)}</span> : null}
              </div>
            </a>
          ))}
        </div>
      ) : !loading && !error ? <StatusPanel title="Nu există thread-uri aici" /> : null}
    </PageShell>
  );
}

function ForumThreadCreateView({ user }) {
  const [section, setSection] = useState("general");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!user) return <AuthRequired />;

  const submit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setStatus("");
    try {
      const thread = await createForumThread({ section, title, content });
      window.location.href = mainPath(`/discutii/${thread.slug}`);
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut publica thread-ul.");
      setSubmitting(false);
    }
  };

  return (
    <PageShell kicker="discuții" title="Thread nou" sub="Deschide o discuție în forum.">
      <form className="form-stack" onSubmit={submit}>
        <label className="auth-field" htmlFor="forum-section">Secțiune</label>
        <select id="forum-section" className="cal-input" value={section} onChange={(event) => setSection(event.target.value)}>
          {FORUM_SECTIONS.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
        </select>
        <label className="auth-field" htmlFor="forum-title">Titlu</label>
        <input id="forum-title" className="cal-input" value={title} onChange={(event) => setTitle(event.target.value)} maxLength="160" required />
        <label className="auth-field" htmlFor="forum-content">Mesaj</label>
        <textarea id="forum-content" className="cal-textarea tall" value={content} onChange={(event) => setContent(event.target.value)} maxLength="8000" required />
        {status ? <div className="inline-error">{status}</div> : null}
        <button className="cal-btn primary" type="submit" disabled={submitting}>{submitting ? "Se publică..." : "Publică thread"}</button>
      </form>
    </PageShell>
  );
}

function ForumThreadDetailView({ user, slug }) {
  const [reply, setReply] = useState("");
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const { data, error, loading } = useAsync(
    () => (user ? fetchForumThread(slug) : Promise.resolve(null)),
    [user?.id, slug, refreshKey]
  );

  if (!user) return <AuthRequired />;

  const submitReply = async (event) => {
    event.preventDefault();
    if (!data) return;
    setSubmitting(true);
    setStatus("");
    try {
      const created = await createForumReply(data.id, { content: reply });
      setReply("");
      setStatus(created.moderation_status === "approved" ? "" : FORUM_MODERATION_MESSAGE);
      setRefreshKey((key) => key + 1);
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut publica răspunsul.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <PageShell kicker={data ? forumSectionLabel(data.section) : "discuții"} title={data?.title ?? "Forum"} sub={data?.author?.username ? `Pornit de ${data.author.username}` : ""}>
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca thread-ul">{error}</StatusPanel> : null}
      {data ? (
        <div className="detail-stack">
          {data.moderation_status !== "approved" ? (
            <StatusPanel title="Mesaj în curs de moderare">{FORUM_MODERATION_MESSAGE}</StatusPanel>
          ) : null}
          <article className="forum-post">
            <div className="piece-card-meta">
              <span>{data.author?.username ?? "anonim"}</span>
              <span>{formatDateTime(data.created_at)}</span>
              {data.moderation_status !== "approved" ? <span>{data.moderation_status}</span> : null}
            </div>
            <p className="forum-body">{data.content}</p>
          </article>
          <section className="forum-replies" aria-label="Răspunsuri">
            <div className="piece-card-kicker">răspunsuri</div>
            {data.replies?.length ? (
              <div className="reply-list">
                {data.replies.map((item) => (
                  <article className="forum-reply" key={item.id}>
                    <div className="piece-card-meta">
                      <span>{item.author?.username ?? "anonim"}</span>
                      <span>{formatDateTime(item.created_at)}</span>
                      {item.moderation_status !== "approved" ? <span>{item.moderation_status}</span> : null}
                    </div>
                    <p className="forum-body">{item.content}</p>
                  </article>
                ))}
              </div>
            ) : <p className="auth-sub">Nu există răspunsuri încă.</p>}
          </section>
          {data.is_locked ? (
            <StatusPanel title="Thread închis">Nu mai pot fi adăugate răspunsuri.</StatusPanel>
          ) : (
            <form className="form-stack" onSubmit={submitReply}>
              <label className="auth-field" htmlFor="forum-reply">Răspuns</label>
              <textarea id="forum-reply" className="cal-textarea" value={reply} onChange={(event) => setReply(event.target.value)} maxLength="4000" required />
              {status ? <div className="inline-error">{status}</div> : null}
              <button className="cal-btn primary" type="submit" disabled={submitting}>{submitting ? "Se publică..." : "Răspunde"}</button>
            </form>
          )}
        </div>
      ) : null}
    </PageShell>
  );
}

function PremiumView({ user }) {
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [selectedTier, setSelectedTier] = useState("premium");
  const quotaState = useAsync(
    () => (user?.has_audio_access ? fetchAudioConversionQuota() : Promise.resolve(null)),
    [user?.id, user?.has_audio_access, user?.premium_until]
  );

  const openStripe = async () => {
    if (!user) {
      window.location.href = AUTH_GOOGLE_PATH;
      return;
    }
    setBusy(true);
    setStatus("");
    try {
      const response = user.is_premium ? await openPremiumPortal() : await startPremiumCheckout(selectedTier);
      window.location.href = response.url;
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut deschide pagina de plată.");
      setBusy(false);
    }
  };

  return (
    <PageShell kicker="premium" title={user?.is_premium ? "Abonamentul tău" : "Devino Premium"} sub="Alege planul potrivit pentru super-aprecieri și generare audio.">
      <div className="status-panel">
        {user?.is_premium ? (
          <>
            <p className="auth-sub">Plan activ: {PREMIUM_TIERS.find((tier) => tier.key === user.premium_tier)?.name ?? "Premium"}.</p>
            {quotaState.data ? (
              <p className="quota-line">
                Generare audio: {formatNumber(quotaState.data.used)} / {formatNumber(quotaState.data.limit)} caractere folosite
                {quotaState.data.period_end ? ` până la ${formatDateTime(quotaState.data.period_end)}` : ""}.
              </p>
            ) : null}
          </>
        ) : (
          <div className="tier-grid">
            {PREMIUM_TIERS.map((tier) => (
              <button
                key={tier.key}
                className={`tier-card ${selectedTier === tier.key ? "selected" : ""}`}
                type="button"
                onClick={() => setSelectedTier(tier.key)}
              >
                <span className="piece-card-kicker">{tier.key === "premium" ? "premium" : "audio"}</span>
                <span className="tier-title">{tier.name}</span>
                <span className="tier-summary">{tier.summary}</span>
              </button>
            ))}
          </div>
        )}
        {status ? <div className="inline-error">{status}</div> : null}
        <button className="cal-btn primary" onClick={openStripe} disabled={busy} type="button">
          {busy ? "Se deschide..." : user?.is_premium ? "Gestionează abonamentul" : "Continuă către plată"}
        </button>
      </div>
    </PageShell>
  );
}

function PrivacyView() {
  return (
    <PageShell kicker="legal" title="Politica de confidențialitate" sub="Ultima actualizare: 28 aprilie 2026.">
      <div className="legal-copy">
        <section className="legal-section">
          <h2>Datele contului</h2>
          <p>Călimara folosește autentificare Google pentru conturi. Păstrăm datele necesare funcționării platformei: nume public, email, identificator Google, texte publicate, comentarii, reacții, mesaje, abonamente și preferințe de profil.</p>
        </section>
        <section className="legal-section">
          <h2>Cookie-uri și sesiuni</h2>
          <p>Folosim cookie-uri de sesiune pentru autentificare, securitate și funcțiile contului. Aceste cookie-uri sunt necesare pentru conectare și pentru păstrarea sesiunii între domeniul principal și blogurile de autor.</p>
        </section>
        <section className="legal-section">
          <h2>Publicitate</h2>
          <p>Paginile publice gratuite pot afișa reclame prin Google AdSense. Google și partenerii săi pot folosi cookie-uri sau stocare locală pentru afișarea, măsurarea și personalizarea reclamelor, în funcție de consimțământul tău și de setările disponibile în mesajul de confidențialitate Google.</p>
          <p>În Spațiul Economic European, Regatul Unit și Elveția, consimțământul pentru reclame este colectat prin Google Privacy & messaging. Utilizatorii Premium nu văd reclame în interfața publică atunci când sunt conectați.</p>
        </section>
        <section className="legal-section">
          <h2>Plăți</h2>
          <p>Plățile pentru Premium sunt procesate prin Stripe. Călimara nu stochează datele cardului. Păstrăm doar identificatori Stripe și starea abonamentului necesare activării beneficiilor Premium.</p>
        </section>
        <section className="legal-section">
          <h2>Contact</h2>
          <p>Pentru întrebări despre datele tale sau despre această politică, scrie la <a href="mailto:contact@calimara.ro">contact@calimara.ro</a>.</p>
        </section>
      </div>
    </PageShell>
  );
}

function TermsView() {
  return (
    <PageShell kicker="legal" title="Termeni și condiții" sub="Ultima actualizare: 28 aprilie 2026.">
      <div className="legal-copy">
        <section className="legal-section">
          <h2>Utilizarea platformei</h2>
          <p>Călimara este o platformă pentru publicarea și descoperirea textelor literare. Utilizatorii sunt responsabili pentru conținutul pe care îl publică și pentru respectarea drepturilor de autor.</p>
        </section>
        <section className="legal-section">
          <h2>Conținut și moderare</h2>
          <p>Putem modera, respinge sau elimina conținut care încalcă regulile platformei, legea aplicabilă sau siguranța comunității. Funcțiile de comentarii, forum și mesaje trebuie folosite fără hărțuire, spam sau abuz.</p>
        </section>
        <section className="legal-section">
          <h2>Reclame</h2>
          <p>Paginile publice gratuite pot include reclame Google AdSense. Reclamele nu trebuie confundate cu navigația, acțiunile platformei sau conținutul editorial. Conturile Premium conectate beneficiază de experiență fără reclame.</p>
        </section>
        <section className="legal-section">
          <h2>Premium</h2>
          <p>Abonamentele Premium sunt gestionate prin Stripe Checkout și Stripe Customer Portal. Beneficiile Premium sunt active cât timp abonamentul este valid conform stării primite de la Stripe.</p>
        </section>
        <section className="legal-section">
          <h2>Contact</h2>
          <p>Pentru întrebări despre acești termeni, scrie la <a href="mailto:contact@calimara.ro">contact@calimara.ro</a>.</p>
        </section>
      </div>
    </PageShell>
  );
}

function AuthSetupView() {
  const [username, setUsername] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setStatus("");
    try {
      const response = await completeAuthSetup({
        username,
        subtitle,
        avatar_seed: `${username || "calimara"}-shapes`
      });
      window.location.href = blogUrl(response.username);
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut finaliza contul.");
      setSubmitting(false);
    }
  };

  return (
    <PageShell kicker="cont" title="Configurează contul" sub="Alege numele public pentru blogul tău.">
      <form className="form-stack" onSubmit={submit}>
        <label className="auth-field" htmlFor="setup-username">Nume utilizator</label>
        <input id="setup-username" className="cal-input" value={username} onChange={(event) => setUsername(event.target.value)} required pattern="[A-Za-z0-9]+" />
        <label className="auth-field" htmlFor="setup-subtitle">Subtitlu</label>
        <input id="setup-subtitle" className="cal-input" value={subtitle} onChange={(event) => setSubtitle(event.target.value)} />
        {status ? <div className="inline-error">{status}</div> : null}
        <button className="cal-btn primary" type="submit" disabled={submitting}>{submitting ? "Se salvează..." : "Finalizează"}</button>
      </form>
    </PageShell>
  );
}

function AuthCallbackView() {
  return (
    <PageShell kicker="cont" title="Autentificare finalizată" sub="Sesiunea a fost actualizată.">
      <a className="cal-btn primary" href={mainPath("/")}>Continuă</a>
    </PageShell>
  );
}

function NotFoundView() {
  return (
    <PageShell kicker="404" title="Pagina nu există" sub="Ruta nu este disponibilă în noul frontend.">
      <a className="cal-btn primary" href={mainPath("/")}>Înapoi acasă</a>
    </PageShell>
  );
}

function routeForLocation() {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  const userFromHost = subdomainUsername();

  if (userFromHost) {
    if (path === "/") return { name: "blog", username: userFromHost };
    if (path === "/dashboard") return { name: "dashboard" };
    if (path === "/create-post") return { name: "create" };
    if (path === "/messages") return { name: "messages" };
    return { name: "post", username: userFromHost, slug: decodeURIComponent(path.slice(1)) };
  }

  if (path === "/") return { name: "landing" };
  if (path === "/dashboard" || path === "/panou") return { name: "dashboard" };
  if (path === "/create-post" || path === "/scrie") return { name: "create" };
  if (path === "/messages" || path === "/mesaje") return { name: "messages" };
  if (path === "/admin" || path === "/moderare") return { name: "admin" };
  if (path.startsWith("/category/")) return { name: "category", categoryKey: decodeURIComponent(path.split("/")[2] || "poezie") };
  if (path.startsWith("/colectii/")) return { name: "collection", slug: decodeURIComponent(path.split("/")[2] || "") };
  if (path.startsWith("/collections/")) return { name: "collection", slug: decodeURIComponent(path.split("/")[2] || "") };
  if (path === "/cluburi") return { name: "clubs" };
  if (path.startsWith("/cluburi/")) return { name: "club", slug: decodeURIComponent(path.split("/")[2] || "") };
  if (path === "/discutii" || path === "/forum") return { name: "forum" };
  if (path === "/discutii/nou" || path === "/discutii/new" || path === "/forum/nou" || path === "/forum/new") return { name: "forumCreate" };
  if (path.startsWith("/discutii/")) return { name: "forumThread", slug: decodeURIComponent(path.split("/")[2] || "") };
  if (path.startsWith("/forum/")) return { name: "forumThread", slug: decodeURIComponent(path.split("/")[2] || "") };
  if (path === "/magazin" || path === "/shop") return { name: "shop" };
  if (path === "/inventar" || path === "/inventory") return { name: "inventory" };
  if (path === "/premium") return { name: "premium" };
  if (path === "/privacy" || path === "/confidentialitate") return { name: "privacy" };
  if (path === "/terms" || path === "/termeni") return { name: "terms" };
  if (path === "/auth/setup") return { name: "authSetup" };
  if (path === "/auth/callback") return { name: "authCallback" };
  return { name: "notFound" };
}

function RouteView({ route, user, authLoaded }) {
  if (PROTECTED_ROUTES.has(route.name) && !authLoaded) {
    return (
      <PageShell kicker="cont" title="Se verifică sesiunea" sub="Încărcăm starea contului tău." />
    );
  }

  if (PROTECTED_ROUTES.has(route.name) && authLoaded && !user) return <AuthRequired />;

  if (route.name === "landing") return <LandingView user={user} />;
  if (route.name === "category") return <CategoryView categoryKey={route.categoryKey} />;
  if (route.name === "clubs") return <ClubsView />;
  if (route.name === "club") return <ClubDetailView slug={route.slug} />;
  if (route.name === "blog") return <BlogView username={route.username} />;
  if (route.name === "post") return <PostDetailView username={route.username} slug={route.slug} user={user} />;
  if (route.name === "collection") return <CollectionView slug={route.slug} />;
  if (route.name === "dashboard") return <DashboardView user={user} />;
  if (route.name === "admin") return <AdminDashboardView user={user} />;
  if (route.name === "create") return <CreatePostView user={user} />;
  if (route.name === "messages") return <MessagesView user={user} />;
  if (route.name === "forum") return <ForumListView user={user} />;
  if (route.name === "forumCreate") return <ForumThreadCreateView user={user} />;
  if (route.name === "forumThread") return <ForumThreadDetailView user={user} slug={route.slug} />;
  if (route.name === "shop") return <ShopView user={user} />;
  if (route.name === "inventory") return <InventoryView user={user} />;
  if (route.name === "premium") return <PremiumView user={user} />;
  if (route.name === "privacy") return <PrivacyView />;
  if (route.name === "terms") return <TermsView />;
  if (route.name === "authSetup") return <AuthSetupView />;
  if (route.name === "authCallback") return <AuthCallbackView />;
  return <NotFoundView />;
}

class ErrorBoundary extends Component {
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
      <div className="bg-atmos" aria-hidden="true" />
      <NavBar loggedIn={loggedIn} user={auth.user} onMenu={() => setMenuOpen((open) => !open)} menuOpen={menuOpen} />
      <AdSenseProvider route={route} user={auth.user} authLoaded={auth.loaded}>
        <ErrorBoundary key={`${route.name}:${route.slug || route.username || route.categoryKey || ""}`}>
          <RouteView route={route} user={auth.user} authLoaded={auth.loaded} />
        </ErrorBoundary>
      </AdSenseProvider>
      <Footer />
      <SideMenu open={menuOpen} onClose={() => setMenuOpen(false)} user={auth.user} />
    </div>
  );
}
