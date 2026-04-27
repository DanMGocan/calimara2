import { Component, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AUTH_GOOGLE_PATH,
  completeAuthSetup,
  createForumReply,
  createForumThread,
  createPost,
  fetchArchive,
  fetchBlog,
  fetchCategory,
  fetchClub,
  fetchClubs,
  fetchConversations,
  fetchForumThread,
  fetchForumThreads,
  fetchLanding,
  fetchMe,
  fetchPostAudioStatus,
  fetchPostDetail,
  fetchRandomClub,
  fetchRandomUser,
  openPremiumPortal,
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
    summary: "Super-aprecieri și funcțiile premium de bază."
  },
  {
    key: "audio",
    name: "Membru Junimea",
    summary: "Include ascultarea fișierelor audio generate pentru texte."
  },
  {
    key: "author_audio",
    name: "La cenaclu' Flacăra",
    summary: "Include ascultare audio și încărcări audio ale autorului."
  }
];

const PROTECTED_ROUTES = new Set(["dashboard", "create", "messages", "forum", "forumCreate", "forumThread"]);

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

function forumSectionLabel(section) {
  return FORUM_SECTIONS.find((item) => item.key === section)?.label ?? section ?? "Forum";
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

function SideActions({ kind, onPoem, onStory, onAuthor, onClub, disabled, busy }) {
  return (
    <aside className="side-col">
      <div className="side-kicker">alege un text</div>
      <div className="actions-group">
        <ActionRow number="01" label="Poezie la întâmplare" active={kind === "poem"} disabled={disabled} onClick={onPoem} />
        <ActionRow number="02" label="Proză scurtă la întâmplare" active={kind === "story"} disabled={disabled} onClick={onStory} />
        <ActionRow number="03" label="Un autor la întâmplare" sub="deschide blogul unui scriitor" disabled={busy === "author"} onClick={onAuthor} />
        <ActionRow number="04" label="Club la întâmplare" sub="o comunitate aleatorie" disabled={busy === "club"} onClick={onClub} />
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
        <span className="rail-sub">poezie și proză</span>
      </div>
      <div className="rail-stat">
        <span className="rail-label">Autori</span>
        <span className="rail-count">{Number(stats.total_authors ?? 0).toLocaleString("ro-RO")}</span>
        <span className="rail-sub">autori activi</span>
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

  const menuItems = user
    ? [
        ["Acasă", "pagina principală", mainPath("/")],
        ["Categorii", "răsfoiește după gen", mainPath("/category/poezie")],
        ["Scrie", "adaugă un text nou", mainPath("/create-post")],
        ["Panou", "textele tale", mainPath("/dashboard")],
        ["Mesaje", "conversații", mainPath("/messages")],
        ["Cluburi", "comunități", mainPath("/cluburi")],
        ["Discuții", "forum și întrebări", mainPath("/discutii")],
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
  const href = post.owner ? `${blogUrl(post.owner.username)}/${post.slug}` : post.url || "#";
  return (
    <a className="piece-card" href={href}>
      <div className="piece-card-kicker">{post.category_name ?? categoryLabel(post.category)}</div>
      <h2 className="piece-card-title">{post.title}</h2>
      <p className="piece-card-excerpt">{htmlToText(post.content)}</p>
      <div className="piece-card-meta">
        {post.owner?.username ? <span>{post.owner.username}</span> : null}
        {post.created_at ? <span>{formatDateTime(post.created_at)}</span> : null}
      </div>
    </a>
  );
}

function LandingView() {
  const [kind, setKind] = useState("poem");
  const [piece, setPiece] = useState(fallbackPiece("poem"));
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
      setPiece(post ? postToPiece(post) : fallbackPiece(nextKind));
      setAnimKey((key) => key + 1);
    } catch (requestError) {
      setError(requestError.message || "Nu am putut încărca textul.");
      setKind(nextKind);
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

  const openRandomClub = async () => {
    setBusy("club");
    try {
      const club = await fetchRandomClub();
      window.location.href = mainPath(`/cluburi/${club.slug}`);
    } catch (requestError) {
      setError(requestError.message || "Nu am putut deschide un club.");
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
          onClub={openRandomClub}
          disabled={transitioning || loading}
          busy={busy}
        />
        <Rail stats={stats} />
        {error ? <div className="inline-error">{error}</div> : null}
      </div>
      <div className={`piece-wrap ${transitioning ? "transitioning" : ""}`}>
        <PieceCol piece={piece} animKey={animKey} />
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
          {data.posts.map((post) => <PostCard key={post.id} post={post} />)}
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
          {data.clubs.map((club) => (
            <a className="piece-card" key={club.id} href={mainPath(`/cluburi/${club.slug}`)}>
              <div className="piece-card-kicker">{categoryLabel(club.speciality)}</div>
              <h2 className="piece-card-title">{club.title}</h2>
              <p className="piece-card-excerpt">{club.description || club.motto || "Club literar pe călimara.ro."}</p>
              <div className="piece-card-meta">
                <span>{club.member_count} membri</span>
                {club.owner?.username ? <span>{club.owner.username}</span> : null}
              </div>
            </a>
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
      {uniquePosts.length ? (
        <div className="list-grid">
          {uniquePosts.map((post) => <PostCard key={post.id} post={{ ...post, owner: data.blog_owner }} />)}
        </div>
      ) : !loading && !error ? <StatusPanel title="Nu există texte încă" /> : null}
    </PageShell>
  );
}

function audioStatusText(status) {
  if (status === "pending") return "Fișierul audio este în coada de generare.";
  if (status === "processing") return "Fișierul audio se generează.";
  if (status === "failed") return "Generarea audio a eșuat.";
  if (status === "post_pending") return "Audio devine disponibil după aprobarea postării.";
  if (status === "missing") return "Nu există încă fișier audio pentru acest text.";
  return "Audio indisponibil momentan.";
}

function AudioStatusPanel({ postId, user }) {
  const { data, error, loading } = useAsync(() => fetchPostAudioStatus(postId), [postId, user?.id, user?.has_audio_access]);

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
            <p className="auth-sub">{data.message || "Ai nevoie de planul Membru Junimea pentru ascultare."}</p>
          </div>
          <a className="cal-btn" href={mainPath("/premium")}>Vezi Premium</a>
        </div>
      ) : null}
      {data && !data.available ? <p className="auth-sub">{data.message || audioStatusText(data.status)}</p> : null}
    </section>
  );
}

function PostDetailView({ username, slug, user }) {
  const { data, error, loading } = useAsync(() => fetchPostDetail(username, slug), [username, slug]);
  const piece = data ? postToPiece({ ...data.post, owner: data.blog_owner }) : null;
  return (
    <main className="stage stage-single">
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca textul">{error}</StatusPanel> : null}
      {piece ? (
        <div className="piece-wrap">
          <div className="detail-stack">
            <PieceCol piece={piece} animKey={slug} />
            <AudioStatusPanel postId={data.post.id} user={user} />
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
  const { data, error, loading } = useAsync(fetchArchive, []);
  if (!user) return <AuthRequired />;
  return (
    <PageShell kicker="panou" title="Textele tale" sub={`Conectat ca ${user.username}.`}>
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca panoul">{error}</StatusPanel> : null}
      {data?.posts?.length ? (
        <div className="list-grid">
          {data.posts.map((post) => <PostCard key={post.id} post={post} />)}
        </div>
      ) : !loading && !error ? <StatusPanel title="Nu ai texte publicate încă" /> : null}
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
      setStatus(created.moderation_status === "approved" ? "" : "Răspunsul este în moderare.");
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
    <PageShell kicker="premium" title={user?.is_premium ? "Abonamentul tău" : "Devino Premium"} sub="Alege planul potrivit pentru super-aprecieri și audio.">
      <div className="status-panel">
        {user?.is_premium ? (
          <p className="auth-sub">Plan activ: {PREMIUM_TIERS.find((tier) => tier.key === user.premium_tier)?.name ?? "Premium"}.</p>
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
  if (path.startsWith("/category/")) return { name: "category", categoryKey: decodeURIComponent(path.split("/")[2] || "poezie") };
  if (path === "/cluburi") return { name: "clubs" };
  if (path.startsWith("/cluburi/")) return { name: "club", slug: decodeURIComponent(path.split("/")[2] || "") };
  if (path === "/discutii" || path === "/forum") return { name: "forum" };
  if (path === "/discutii/nou" || path === "/discutii/new" || path === "/forum/nou" || path === "/forum/new") return { name: "forumCreate" };
  if (path.startsWith("/discutii/")) return { name: "forumThread", slug: decodeURIComponent(path.split("/")[2] || "") };
  if (path.startsWith("/forum/")) return { name: "forumThread", slug: decodeURIComponent(path.split("/")[2] || "") };
  if (path === "/premium") return { name: "premium" };
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

  if (route.name === "landing") return <LandingView />;
  if (route.name === "category") return <CategoryView categoryKey={route.categoryKey} />;
  if (route.name === "clubs") return <ClubsView />;
  if (route.name === "club") return <ClubDetailView slug={route.slug} />;
  if (route.name === "blog") return <BlogView username={route.username} />;
  if (route.name === "post") return <PostDetailView username={route.username} slug={route.slug} user={user} />;
  if (route.name === "dashboard") return <DashboardView user={user} />;
  if (route.name === "create") return <CreatePostView user={user} />;
  if (route.name === "messages") return <MessagesView user={user} />;
  if (route.name === "forum") return <ForumListView user={user} />;
  if (route.name === "forumCreate") return <ForumThreadCreateView user={user} />;
  if (route.name === "forumThread") return <ForumThreadDetailView user={user} slug={route.slug} />;
  if (route.name === "premium") return <PremiumView user={user} />;
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

  return (
    <div className="site" data-logged={loggedIn ? "in" : "out"} data-bg="on">
      <div className="bg-atmos" aria-hidden="true">
        <div className="bg-sky" />
      </div>
      <NavBar loggedIn={loggedIn} user={auth.user} onMenu={() => setMenuOpen((open) => !open)} menuOpen={menuOpen} />
      <ErrorBoundary key={`${route.name}:${route.slug || route.username || route.categoryKey || ""}`}>
        <RouteView route={route} user={auth.user} authLoaded={auth.loaded} />
      </ErrorBoundary>
      <Footer />
      <SideMenu open={menuOpen} onClose={() => setMenuOpen(false)} user={auth.user} />
    </div>
  );
}
