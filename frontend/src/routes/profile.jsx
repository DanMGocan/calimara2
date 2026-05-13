import { Fragment, useEffect, useMemo, useState } from "react";
import { FaCoins, FaShirt } from "react-icons/fa6";
import { FiAward, FiBookOpen, FiCheck, FiEdit3, FiExternalLink, FiHeadphones, FiHeart, FiMapPin, FiMessageCircle, FiSettings, FiStar, FiUserCheck, FiUserMinus, FiUserPlus, FiUsers, FiX } from "react-icons/fi";
import { SiYoutube } from "react-icons/si";
import { acceptFriendRequest, deleteFriendRequest, removeFriend, sendFriendRequest } from "../api/friends.js";
import { fetchFollowers, fetchFollowing, followUser, unfollowUser } from "../api/follows.js";
import { fetchAllWorks, fetchBlog } from "../api/public.js";
import { promoteAuthor, unpromoteAuthor } from "../api/users.js";
import { useAuthModal } from "../app/auth-modal.jsx";
import { ALL_WORKS_SORT_OPTIONS, PROFILE_LINK_MISSING_MESSAGE } from "../app/constants.js";
import { AuthorLink, EquippedStrip, PostCard, RichTextContent } from "../app/content.jsx";
import { categoryLabel, formatNumber, usernameHandle } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { AdSlot, PageShell, StatusPanel } from "../app/layout.jsx";
import { authorPath, blogUrl, mainPath, profileAvatarUrl, profileCoverUrl } from "../app/paths.js";
import { SOCIAL_PROFILE_LINKS, SUPPORT_PROFILE_LINKS, profileLinks, profileTierBadge, safeExternalUrl } from "../app/profile-links.jsx";

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
function ProfileCountLink({ Icon, href, value, label }) {
  return (
    <a className="profile-stat" href={href}>
      <Icon aria-hidden="true" />
      <span>
        <strong>{formatNumber(value)}</strong>
        {label}
      </span>
    </a>
  );
}
function PromoteAuthorButton({ owner, user, initialPromoted }) {
  const [promoted, setPromoted] = useState(Boolean(initialPromoted));
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setPromoted(Boolean(initialPromoted));
    setBusy(false);
  }, [owner?.id, user?.id, initialPromoted]);

  if (!owner || !user || owner.id === user.id) return null;

  const toggle = async () => {
    if (busy) return;
    setBusy(true);
    try {
      if (promoted) {
        await unpromoteAuthor(owner.id);
        setPromoted(false);
      } else {
        await promoteAuthor(owner.id);
        setPromoted(true);
      }
    } catch {
      setPromoted((current) => current);
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      className={`profile-link-btn profile-promote-author ${promoted ? "is-promoted" : ""}`.trim()}
      type="button"
      onClick={toggle}
      disabled={busy}
      aria-pressed={promoted}
      aria-label={promoted ? "Elimină autorul din promovări" : "Promovează autorul pe Călimara mea"}
      title={promoted ? "Elimină autorul din promovări" : "Promovează autorul pe Călimara mea"}
    >
      <FiStar aria-hidden="true" />
    </button>
  );
}
function ProfileFollowButton({ owner, user, initialFollowing, onFollowingChange, onUserRefresh }) {
  const { openAuthModal } = useAuthModal();
  const [following, setFollowing] = useState(Boolean(initialFollowing));
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setFollowing(Boolean(initialFollowing));
    setBusy(false);
  }, [owner?.id, user?.id, initialFollowing]);

  if (!owner || owner.id === user?.id) return null;

  const toggle = async () => {
    if (busy) return;
    if (!user) {
      openAuthModal?.();
      return;
    }
    setBusy(true);
    try {
      if (following) {
        await unfollowUser(owner.id);
        setFollowing(false);
        onFollowingChange?.(false);
      } else {
        await followUser(owner.id);
        setFollowing(true);
        onFollowingChange?.(true);
      }
      await onUserRefresh?.();
    } catch (error) {
      if (import.meta.env.DEV) console.warn("Follow action failed", error);
    } finally {
      setBusy(false);
    }
  };

  const label = following ? "Urmărești" : "Urmărește";
  return (
    <button
      className={`profile-link-btn profile-follow-action ${following ? "is-following" : ""}`.trim()}
      type="button"
      onClick={toggle}
      disabled={busy}
      aria-pressed={Boolean(user && following)}
      aria-label={user ? label : "Autentifică-te pentru a urmări"}
      title={user ? label : "Autentifică-te pentru a urmări"}
    >
      {following ? <FiUserCheck aria-hidden="true" /> : <FiUserPlus aria-hidden="true" />}
      <span>{label}</span>
    </button>
  );
}
function ProfileFriendActions({ owner, user, initialStatus, initialFriendshipId, onUserRefresh }) {
  const [status, setStatus] = useState(initialStatus || "none");
  const [friendshipId, setFriendshipId] = useState(initialFriendshipId || null);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    setStatus(initialStatus || "none");
    setFriendshipId(initialFriendshipId || null);
    setBusy("");
  }, [owner?.id, user?.id, initialStatus, initialFriendshipId]);

  if (!owner || !user || owner.id === user.id) return null;

  const syncFromResponse = (response) => {
    setStatus(response?.status || "none");
    setFriendshipId(response?.friendship?.id || response?.friendship_id || null);
  };

  const run = async (kind) => {
    if (busy) return;
    setBusy(kind);
    try {
      if (kind === "send") syncFromResponse(await sendFriendRequest(owner.id));
      if (kind === "accept" && friendshipId) syncFromResponse(await acceptFriendRequest(friendshipId));
      if (kind === "delete" && friendshipId) {
        await deleteFriendRequest(friendshipId);
        setStatus("none");
        setFriendshipId(null);
      }
      if (kind === "remove") {
        await removeFriend(owner.id);
        setStatus("none");
        setFriendshipId(null);
      }
      await onUserRefresh?.();
    } catch (error) {
      if (import.meta.env.DEV) console.warn("Friendship action failed", error);
    } finally {
      setBusy("");
    }
  };

  if (status === "incoming_pending") {
    return (
      <>
        <button className="profile-link-btn profile-friend-action accept" type="button" onClick={() => run("accept")} disabled={Boolean(busy) || !friendshipId} aria-label="Acceptă cererea de prietenie" title="Acceptă cererea de prietenie">
          <FiCheck aria-hidden="true" />
        </button>
        <button className="profile-link-btn profile-friend-action" type="button" onClick={() => run("delete")} disabled={Boolean(busy) || !friendshipId} aria-label="Refuză cererea de prietenie" title="Refuză cererea de prietenie">
          <FiX aria-hidden="true" />
        </button>
      </>
    );
  }

  if (status === "outgoing_pending") {
    return (
      <button className="profile-link-btn profile-friend-action pending" type="button" onClick={() => run("delete")} disabled={Boolean(busy) || !friendshipId} aria-label="Anulează cererea de prietenie" title="Anulează cererea de prietenie">
        <FiX aria-hidden="true" />
      </button>
    );
  }

  if (status === "friends") {
    return (
      <button className="profile-link-btn profile-friend-action friends" type="button" onClick={() => run("remove")} disabled={Boolean(busy)} aria-label="Elimină din prieteni" title="Elimină din prieteni">
        <FiUserMinus aria-hidden="true" />
      </button>
    );
  }

  return (
    <button className="profile-link-btn profile-friend-action" type="button" onClick={() => run("send")} disabled={Boolean(busy)} aria-label="Trimite cerere de prietenie" title="Trimite cerere de prietenie">
      <FiUserPlus aria-hidden="true" />
    </button>
  );
}
function ProfileHero({ data, postCount, user, onUserRefresh }) {
  const owner = data?.blog_owner;
  const [followerCount, setFollowerCount] = useState(data?.follower_count || 0);
  useEffect(() => {
    setFollowerCount(data?.follower_count || 0);
  }, [owner?.id, data?.follower_count]);
  if (!owner) return null;
  const profileIconLinks = profileLinks(owner, [...SOCIAL_PROFILE_LINKS, ...SUPPORT_PROFILE_LINKS]);
  const coverUrl = profileCoverUrl(owner);
  const coverStyle = coverUrl ? { backgroundImage: `url(${coverUrl})` } : undefined;
  const tierBadge = profileTierBadge(owner);
  const isOwnProfile = Boolean(user?.username && owner.username && user.username.toLowerCase() === owner.username.toLowerCase());
  const playlistUrl = safeExternalUrl(owner.youtube_playlist_url);

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
        ) : (
          <>
            <ProfileFollowButton
              owner={owner}
              user={user}
              initialFollowing={data.viewer_following}
              onFollowingChange={(nextFollowing) => setFollowerCount((current) => Math.max(0, current + (nextFollowing ? 1 : -1)))}
              onUserRefresh={onUserRefresh}
            />
            <ProfileFriendActions owner={owner} user={user} initialStatus={data.viewer_friendship_status} initialFriendshipId={data.viewer_friendship_id} onUserRefresh={onUserRefresh} />
            <PromoteAuthorButton owner={owner} user={user} initialPromoted={data.viewer_promoted_author} />
          </>
        )}
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
        <ProfileStat Icon={FiUsers} value={data.friend_count} label="prieteni" />
        <ProfileCountLink Icon={FiUserPlus} href={`${blogUrl(owner.username)}/urmaritori`} value={followerCount} label="urmăritori" />
        <ProfileCountLink Icon={FiUserCheck} href={`${blogUrl(owner.username)}/urmariti`} value={data.following_count} label="urmăriți" />
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
      {playlistUrl ? (
        <a className="profile-playlist-link" href={playlistUrl} target="_blank" rel="noreferrer">
          <SiYoutube aria-hidden="true" />
          <span>Playlist YouTube</span>
        </a>
      ) : null}
    </section>
  );
}
function ProfileHighlights({ data }) {
  const awards = data?.user_awards || [];
  if (!awards.length) return null;
  return (
    <section className="profile-highlights" aria-label="Repere profil">
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
    </section>
  );
}
function ProfilePromotions({ data }) {
  const limits = data?.promotion_limits || { own_posts: 2, authors: 3, other_posts: 3 };
  const ownPosts = (data?.promoted_own_posts || data?.featured_posts || []).slice(0, limits.own_posts ?? 2);
  const authors = (data?.promoted_authors || data?.best_friends || []).slice(0, limits.authors ?? 3);
  const otherPosts = (data?.promoted_external_posts || []).slice(0, limits.other_posts ?? 3);
  if (!ownPosts.length && !authors.length && !otherPosts.length) return null;
  return (
    <section className="profile-promotions" aria-label="Promovări pe Călimara mea">
      <div className="profile-panel-heading">
        <FiStar aria-hidden="true" />
        <div className="piece-card-kicker">promovări pe Călimara mea</div>
      </div>
      <div className="profile-promotion-sections">
        {ownPosts.length ? (
          <div className="profile-promotion-block">
            <div className="profile-promotion-label">Postari proprii promovate</div>
            <div className="profile-promotion-grid">
              {ownPosts.map((post) => <PostCard key={`own-${post.id}`} post={post} />)}
            </div>
          </div>
        ) : null}
        {authors.length ? (
          <div className="profile-promotion-block">
            <div className="profile-promotion-label">Autori pe care ii promovez</div>
            <div className="profile-chip-list">
              {authors.map((entry) => (
                <a className="profile-chip" key={entry.user.username} href={blogUrl(entry.user.username)}>
                  <FiUsers aria-hidden="true" />
                  {usernameHandle(entry.user.username)}
                </a>
              ))}
            </div>
          </div>
        ) : null}
        {otherPosts.length ? (
          <div className="profile-promotion-block">
            <div className="profile-promotion-label">Lucrarile altor autori pe care le promovez</div>
            <div className="profile-promotion-grid compact">
              {otherPosts.map((post) => <PostCard key={`other-${post.id}`} post={post} />)}
            </div>
          </div>
        ) : null}
      </div>
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
function BlogView({ username, user, onUserRefresh }) {
  const { data, error, loading } = useAsync(() => fetchBlog(username), [username]);
  const promotedOwnIds = new Set((data?.promoted_own_posts || data?.featured_posts || []).map((post) => post.id));
  const posts = data ? [...(data.latest_posts || []), ...(data.all_posts || [])] : [];
  const uniquePosts = posts.filter((post, index, all) => !promotedOwnIds.has(post.id) && all.findIndex((item) => item.id === post.id) === index);
  const totalPostCount = (data?.category_counts || []).reduce((sum, item) => sum + Number(item.count || 0), 0) || uniquePosts.length;
  return (
    <PageShell kicker="profil" title={data ? null : usernameHandle(username)}>
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca blogul">{error}</StatusPanel> : null}
      {data ? (
        <>
          <ProfileHero data={data} postCount={totalPostCount} user={user} onUserRefresh={onUserRefresh} />
          <EquippedStrip items={data.blog_owner?.equipped_items} />
          <ProfilePromotions data={data} />
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

function FollowUserCard({ user }) {
  return (
    <a className="friend-card follow-user-card" href={blogUrl(user.username)}>
      <span className="friend-identity">
        <img className="friend-avatar profile-picture" src={profileAvatarUrl(user, 64)} alt="" aria-hidden="true" />
        <span className="friend-copy">
          <span className="friend-name">{usernameHandle(user.username)}</span>
          {user.subtitle ? <span className="friend-subtitle">{user.subtitle}</span> : null}
        </span>
      </span>
    </a>
  );
}

function FollowListView({ username, kind }) {
  const isFollowers = kind === "followers";
  const { data, error, loading } = useAsync(
    () => (isFollowers ? fetchFollowers(username) : fetchFollowing(username)),
    [username, isFollowers],
  );
  const owner = data?.owner;
  const users = isFollowers ? data?.followers || [] : data?.following || [];
  const title = isFollowers ? "Urmăritori" : "Urmăriți";
  const empty = isFollowers ? "Nu există urmăritori încă" : "Nu urmărește pe nimeni încă";
  const count = data?.count ?? users.length;

  return (
    <PageShell
      kicker="profil"
      title={owner?.username ? `${title} · ${usernameHandle(owner.username)}` : title}
      sub={data ? `${formatNumber(count)} ${isFollowers ? "urmăritori" : "urmăriți"}.` : ""}
    >
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca lista">{error}</StatusPanel> : null}
      {users.length ? (
        <div className="friends-list follow-list">
          {users.map((item) => <FollowUserCard key={item.id} user={item} />)}
        </div>
      ) : data && !loading && !error ? <StatusPanel title={empty} /> : null}
    </PageShell>
  );
}

export default function ProfileRoute({ route, user, onUserRefresh }) {
  if (route.name === "allWorks") return <AllWorksView username={route.username} />;
  if (route.name === "followers") return <FollowListView username={route.username} kind="followers" />;
  if (route.name === "following") return <FollowListView username={route.username} kind="following" />;
  return <BlogView username={route.username} user={user} onUserRefresh={onUserRefresh} />;
}
