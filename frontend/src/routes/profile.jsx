import { Fragment, useMemo, useState } from "react";
import { FaCoins, FaShirt } from "react-icons/fa6";
import { FiAward, FiBookOpen, FiEdit3, FiExternalLink, FiHeadphones, FiHeart, FiMapPin, FiMessageCircle, FiSettings, FiUsers } from "react-icons/fi";
import { SiYoutube } from "react-icons/si";
import { fetchAllWorks, fetchBlog } from "../api/public.js";
import { ALL_WORKS_SORT_OPTIONS, PROFILE_LINK_MISSING_MESSAGE } from "../app/constants.js";
import { AuthorLink, EquippedStrip, PostCard, RichTextContent } from "../app/content.jsx";
import { categoryLabel, formatNumber, usernameHandle } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { AdSlot, PageShell, StatusPanel } from "../app/layout.jsx";
import { authorPath, blogUrl, mainPath, profileAvatarUrl, profileCoverUrl } from "../app/paths.js";
import { SOCIAL_PROFILE_LINKS, SUPPORT_PROFILE_LINKS, profileLinks, profileTierBadge } from "../app/profile-links.jsx";

function ExternalProfileLinks({ links, className = "", children }) {
  if (!links.length && !children) return null;
  return (
    <div className={`profile-link-row ${className}`.trim()}>
      {links.map((link) => {
        const Icon = link.Icon || FiExternalLink;
        const classes = `profile-link-btn ${link.className || ""} ${link.url ? "is-active" : "is-inactive"}`.trim();
        if (link.url) {
          return (
            <a key={link.field} className={classes} href={link.url} target="_blank" rel="noreferrer" aria-label={link.label} title={link.label}>
              <Icon aria-hidden="true" />
            </a>
          );
        }
        return (
          <span
            key={link.field}
            className={classes}
            role="button"
            aria-disabled="true"
            aria-label={`${link.label}: ${PROFILE_LINK_MISSING_MESSAGE}`}
            title={PROFILE_LINK_MISSING_MESSAGE}
            data-tooltip={PROFILE_LINK_MISSING_MESSAGE}
            tabIndex={0}
          >
            <Icon aria-hidden="true" />
          </span>
        );
      })}
      {children}
    </div>
  );
}
function ProfileStat({ Icon, value, label }) {
  return (
    <span className="profile-stat">
      <Icon aria-hidden="true" />
      <span>
        <strong>{formatNumber(value)}</strong>
        {label}
      </span>
    </span>
  );
}
function ProfileStatLink({ Icon, href, label }) {
  return (
    <a className="profile-stat" href={href}>
      <Icon aria-hidden="true" />
      <span>
        <strong>{label}</strong>
      </span>
    </a>
  );
}
function ProfileHero({ data, postCount, user }) {
  const owner = data?.blog_owner;
  if (!owner) return null;
  const profileIconLinks = profileLinks(owner, [...SOCIAL_PROFILE_LINKS, ...SUPPORT_PROFILE_LINKS]);
  const coverUrl = profileCoverUrl(owner);
  const coverStyle = coverUrl ? { backgroundImage: `url(${coverUrl})` } : undefined;
  const tierBadge = profileTierBadge(owner);
  const isOwnProfile = Boolean(user?.username && owner.username && user.username.toLowerCase() === owner.username.toLowerCase());

  return (
    <section className={`profile-hero ${coverUrl ? "has-cover" : ""} ${tierBadge.className}`} aria-label="Profil autor">
      <div className="profile-cover" style={coverStyle}>
        <div className="profile-identity">
          <img className="profile-avatar profile-picture" src={profileAvatarUrl(owner)} alt="" aria-hidden="true" />
          <div className="profile-identity-main">
            <h1 className="profile-username">{usernameHandle(owner.username)}</h1>
            <div className="profile-name-row">
              <span className={`profile-tier-badge ${tierBadge.className}`}>{tierBadge.label}</span>
            </div>
          </div>
        </div>
      </div>
      <ExternalProfileLinks links={profileIconLinks} className="profile-icon-row">
        {isOwnProfile ? (
          <a className="profile-link-btn profile-settings-btn" href={authorPath(user, "/profil")} aria-label="Setări profil" title="Setări profil">
            <FiSettings aria-hidden="true" />
          </a>
        ) : null}
      </ExternalProfileLinks>
      {owner.subtitle ? (
        <blockquote className="profile-motto">
          <span className="profile-motto-mark">„</span>
          <RichTextContent html={owner.subtitle} className="profile-motto-text" />
          <span className="profile-motto-mark">”</span>
        </blockquote>
      ) : null}
      {owner.location ? (
        <div className="profile-location">
          <FiMapPin aria-hidden="true" />
          <span>{owner.location}</span>
        </div>
      ) : null}
      <div className="profile-stat-row" aria-label="Statistici autor">
        <ProfileStat Icon={FiBookOpen} value={postCount} label="texte" />
        <ProfileStat Icon={FiHeart} value={data.total_likes} label="aprecieri" />
        <ProfileStat Icon={FiMessageCircle} value={data.total_comments} label="comentarii" />
        <ProfileStat Icon={FiHeadphones} value={owner.seconds_listened} label="secunde ascultate" />
        <ProfileStat Icon={FaCoins} value={owner.gologani_balance} label="Gologani" />
        {isOwnProfile ? (
          <a className="profile-write-btn" href={authorPath(user, "/panou")}>
            <FiEdit3 aria-hidden="true" />
            <span>Scrie</span>
          </a>
        ) : null}
      </div>
      <div className="profile-stat-row profile-economy-row" aria-label="Opere și inventar">
        <ProfileStatLink Icon={FiBookOpen} href={`${blogUrl(owner.username)}/toate-operele`} label="Toate operele" />
        <ProfileStatLink Icon={FaShirt} href={`${blogUrl(owner.username)}/inventar`} label="Inventar" />
      </div>
      {owner.youtube_playlist_url ? (
        <a className="profile-playlist-link" href={owner.youtube_playlist_url} target="_blank" rel="noreferrer">
          <SiYoutube aria-hidden="true" />
          <span>Playlist YouTube</span>
        </a>
      ) : null}
    </section>
  );
}
function ProfileHighlights({ data }) {
  const friends = data?.best_friends || [];
  const awards = data?.user_awards || [];
  if (!friends.length && !awards.length) return null;
  return (
    <section className="profile-highlights" aria-label="Repere profil">
      {friends.length ? (
        <div className="profile-panel">
          <div className="profile-panel-heading">
            <FiUsers aria-hidden="true" />
            <div className="piece-card-kicker">prieteni apropiați</div>
          </div>
          <div className="profile-chip-list">
            {friends.map((entry) => (
              <a className="profile-chip" key={entry.user.username} href={blogUrl(entry.user.username)}>
                <FiUsers aria-hidden="true" />
                {usernameHandle(entry.user.username)}
              </a>
            ))}
          </div>
        </div>
      ) : null}
      {awards.length ? (
        <div className="profile-panel">
          <div className="profile-panel-heading">
            <FiAward aria-hidden="true" />
            <div className="piece-card-kicker">distincții</div>
          </div>
          <div className="profile-chip-list">
            {awards.slice(0, 4).map((award) => (
              <span className="profile-chip" key={award.id}><FiAward aria-hidden="true" />{award.award_title}</span>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
function ProfileSeriesList({ series }) {
  if (!series?.length) return null;
  return (
    <section className="profile-series" aria-label="Serii">
      <div className="profile-panel-heading">
        <FiBookOpen aria-hidden="true" />
        <div className="piece-card-kicker">serii</div>
      </div>
      <div className="profile-series-grid">
        {series.map((item) => (
          <a className="profile-series-card" key={item.id} href={mainPath(`/serii/${item.slug}`)}>
            <span className="profile-series-title">{item.title}</span>
            <span className="profile-series-meta">{formatNumber(item.post_count)} texte</span>
            {item.description ? <span className="profile-series-description">{item.description}</span> : null}
          </a>
        ))}
      </div>
    </section>
  );
}
function BlogView({ username, user }) {
  const { data, error, loading } = useAsync(() => fetchBlog(username), [username]);
  const posts = data ? [...(data.featured_posts || []), ...(data.latest_posts || []), ...(data.all_posts || [])] : [];
  const uniquePosts = posts.filter((post, index, all) => all.findIndex((item) => item.id === post.id) === index);
  const totalPostCount = (data?.category_counts || []).reduce((sum, item) => sum + Number(item.count || 0), 0) || uniquePosts.length;
  return (
    <PageShell kicker="profil" title={data ? null : usernameHandle(username)}>
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca blogul">{error}</StatusPanel> : null}
      {data ? (
        <>
          <ProfileHero data={data} postCount={totalPostCount} user={user} />
          <EquippedStrip items={data.blog_owner?.equipped_items} />
          <ProfileHighlights data={data} />
          <ProfileSeriesList series={data.series} />
        </>
      ) : null}
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
function AllWorksView({ username }) {
  const { data, error, loading } = useAsync(() => fetchAllWorks(username), [username]);
  const [category, setCategory] = useState("toate");
  const [sortBy, setSortBy] = useState("newest");
  const owner = data?.blog_owner;
  const categories = (data?.category_counts || []).filter((item) => item.count > 0);
  const posts = useMemo(() => {
    const source = data?.posts || [];
    const filtered = category === "toate" ? source : source.filter((post) => post.category === category);
    const valueForSort = (post) => {
      if (sortBy === "comments") return Number(post.comments_count || 0);
      if (sortBy === "likes") return Number(post.likes_count || 0);
      if (sortBy === "super_likes") return Number(post.super_likes_count || 0);
      return new Date(post.created_at || 0).getTime();
    };
    return [...filtered].sort((a, b) => {
      const primary = valueForSort(b) - valueForSort(a);
      if (primary !== 0) return primary;
      return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
    });
  }, [data?.posts, category, sortBy]);

  return (
    <PageShell
      kicker="opere"
      title={owner?.username ? `Toate operele lui ${usernameHandle(owner.username)}` : "Toate operele"}
      sub={owner ? `${formatNumber(data?.posts?.length || 0)} texte publicate.` : ""}
    >
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca operele">{error}</StatusPanel> : null}
      {data ? (
        <div className="all-works-controls" aria-label="Filtre opere">
          <label className="profile-inline-label" htmlFor="all-works-category">Categorie</label>
          <select id="all-works-category" className="cal-input" value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="toate">Toate</option>
            {categories.map((item) => (
              <option key={item.category} value={item.category}>
                {item.category_name} · {formatNumber(item.count)}
              </option>
            ))}
          </select>
          <label className="profile-inline-label" htmlFor="all-works-sort">Sortare</label>
          <select id="all-works-sort" className="cal-input" value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
            {ALL_WORKS_SORT_OPTIONS.map((option) => (
              <option key={option.key} value={option.key}>{option.label}</option>
            ))}
          </select>
        </div>
      ) : null}
      {posts.length ? (
        <div className="list-grid">
          {posts.map((post, index) => (
            <Fragment key={post.id}>
              <PostCard post={{ ...post, owner }} />
              {index === 1 ? <AdSlot placement="inline" /> : null}
            </Fragment>
          ))}
        </div>
      ) : data && !loading && !error ? <StatusPanel title="Nu există texte pentru filtrul ales" /> : null}
    </PageShell>
  );
}

export default function ProfileRoute({ route, user }) {
  if (route.name === "allWorks") return <AllWorksView username={route.username} />;
  return <BlogView username={route.username} user={user} />;
}
