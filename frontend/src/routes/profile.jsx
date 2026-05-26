import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { FaCoins, FaShirt } from "react-icons/fa6";
import { FiAward, FiBookOpen, FiCheck, FiEdit3, FiExternalLink, FiHeadphones, FiHeart, FiMail, FiMapPin, FiMessageCircle, FiPlay, FiSearch, FiSend, FiSettings, FiStar, FiUserCheck, FiUserMinus, FiUserPlus, FiUsers, FiX } from "react-icons/fi";
import { SiYoutube } from "react-icons/si";
import { acceptFriendRequest, deleteFriendRequest, removeFriend, sendFriendRequest } from "../api/friends.js";
import { fetchFollowers, fetchFollowing, followUser, unfollowUser } from "../api/follows.js";
import { sendMessage } from "../api/messages.js";
import { fetchAllWorks, fetchBlog } from "../api/public.js";
import { fetchPromotions, promoteAuthor, promotePost, searchPromotions, unpromoteAuthor, unpromotePost } from "../api/users.js";
import { addDiacritics } from "../api/writing.js";
import { useAuthModal } from "../app/auth-modal.jsx";
import { ALL_WORKS_SORT_OPTIONS, PRIVATE_MESSAGE_CHARACTER_LIMIT, PROFILE_LINK_MISSING_MESSAGE } from "../app/constants.js";
import { AuthorLink, EquippedStrip, PostCard, RichTextContent } from "../app/content.jsx";
import { DiacriticsControl, DiacriticsProgressOverlay, DiacriticsReviewPanel, diacriticsSubmitLabel, useDiacriticsProgress, useDiacriticsQuota } from "../app/diacritics.jsx";
import { categoryLabel, formatNumber, htmlToText, usernameHandle } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { AdSlot, PageShell, StatusPanel } from "../app/layout.jsx";
import { authorPath, blogUrl, mainPath, profileAvatarUrl, profileCoverUrl } from "../app/paths.js";
import { SOCIAL_PROFILE_LINKS, SUPPORT_PROFILE_LINKS, profileLinks, profileTierBadge, safeExternalUrl } from "../app/profile-links.jsx";
import { profileSeo, usePageSeo } from "../app/seo.js";

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
  const { openAuthModal } = useAuthModal();
  const [promoted, setPromoted] = useState(Boolean(initialPromoted));
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setPromoted(Boolean(initialPromoted));
    setBusy(false);
  }, [owner?.id, user?.id, initialPromoted]);

  if (!owner || owner.id === user?.id) return null;

  if (!user) {
    return (
      <button
        className="profile-link-btn profile-promote-author"
        type="button"
        onClick={() => openAuthModal?.()}
        aria-label="Autentifică-te pentru a promova autorul pe profilul tău"
        title="Autentifică-te pentru a promova autorul pe profilul tău"
      >
        <FiStar aria-hidden="true" />
      </button>
    );
  }

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
      aria-label={promoted ? "Elimină promovarea autorului de pe profilul tău" : "Promovează autorul pe profilul tău"}
      title={promoted ? "Elimină promovarea autorului de pe profilul tău" : "Promovează autorul pe profilul tău"}
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
  const { openAuthModal } = useAuthModal();
  const [status, setStatus] = useState(initialStatus || "none");
  const [friendshipId, setFriendshipId] = useState(initialFriendshipId || null);
  const [busy, setBusy] = useState("");

  useEffect(() => {
    setStatus(initialStatus || "none");
    setFriendshipId(initialFriendshipId || null);
    setBusy("");
  }, [owner?.id, user?.id, initialStatus, initialFriendshipId]);

  if (!owner || owner.id === user?.id) return null;

  if (!user) {
    return (
      <button className="profile-link-btn profile-friend-action" type="button" onClick={() => openAuthModal?.()} aria-label="Autentifică-te pentru prietenie" title="Autentifică-te pentru prietenie">
        <FiUserPlus aria-hidden="true" />
      </button>
    );
  }

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

function ProfileMessageModal({ owner, user, open, onClose }) {
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [autoDiacritics, setAutoDiacritics] = useState(false);
  const [diacriticsReview, setDiacriticsReview] = useState(null);
  const {
    diacriticsProgress,
    startDiacriticsProgress,
    finishDiacriticsProgress,
    failDiacriticsProgress
  } = useDiacriticsProgress();
  const {
    diacriticsQuota,
    diacriticsQuotaLoading,
    diacriticsQuotaError,
    applyDiacriticsQuota
  } = useDiacriticsQuota(user);

  useEffect(() => {
    if (!open) return;
    setMessage("");
    setStatus("");
    setError("");
    setSubmitting(false);
    setAutoDiacritics(false);
    setDiacriticsReview(null);
  }, [open, owner?.id, user?.id]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !owner) return null;

  const submit = async (event, { skipDiacritics = false } = {}) => {
    event?.preventDefault();
    const content = message.trim();
    if (!content || submitting) return;
    setSubmitting(true);
    setStatus("");
    setError("");
    try {
      if (!skipDiacritics && user && autoDiacritics && !diacriticsReview) {
        startDiacriticsProgress({ content });
        const converted = await addDiacritics({ kind: "private_message", content });
        finishDiacriticsProgress();
        applyDiacriticsQuota(converted.quota);
        setMessage(converted.content ?? message);
        setDiacriticsReview({ originalContent: message, changed: converted.changed });
        setSubmitting(false);
        return;
      }
      await sendMessage({ recipient_username: owner.username, content });
      setMessage("");
      setDiacriticsReview(null);
      setStatus("Mesajul a fost trimis.");
    } catch (requestError) {
      failDiacriticsProgress();
      setError(requestError.message || "Nu am putut trimite mesajul.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <DiacriticsProgressOverlay {...diacriticsProgress} />
      <div className="access-modal-scrim" role="presentation" onClick={onClose}>
        <section className="access-modal profile-message-modal" role="dialog" aria-modal="true" aria-labelledby="profile-message-title" onClick={(event) => event.stopPropagation()}>
          <button className="access-modal-close" type="button" aria-label="Închide" onClick={onClose}>x</button>
          <h2 id="profile-message-title" className="access-modal-title">Mesaj către {usernameHandle(owner.username)}</h2>
          <form className="profile-message-form" onSubmit={submit}>
            <div className="profile-message-recipient">
              <img className="message-avatar profile-picture" src={profileAvatarUrl(owner, 56)} alt="" aria-hidden="true" />
              <span>{usernameHandle(owner.username)}</span>
            </div>
            <label className="cal-label" htmlFor="profile-private-message">Mesaj</label>
            <textarea
              id="profile-private-message"
              className="cal-textarea message-modal-textarea"
              value={message}
              onChange={(event) => {
                setMessage(event.target.value);
                setDiacriticsReview(null);
              }}
              maxLength={PRIVATE_MESSAGE_CHARACTER_LIMIT}
              rows={5}
              required
            />
            <div className="message-diacritics-block">
              <DiacriticsControl
                user={user}
                enabled={autoDiacritics}
                disabled={Boolean(diacriticsReview)}
                label="Adaugă automat diacritice în mesaj?"
                quota={diacriticsQuota}
                quotaLoading={diacriticsQuotaLoading}
                quotaError={diacriticsQuotaError}
                onChange={(checked) => {
                  setAutoDiacritics(checked);
                  setDiacriticsReview(null);
                }}
              />
              <DiacriticsReviewPanel
                active={Boolean(diacriticsReview)}
                changed={Boolean(diacriticsReview?.changed)}
                onReset={diacriticsReview ? () => {
                  setMessage(diacriticsReview.originalContent);
                  setDiacriticsReview(null);
                } : null}
              />
            </div>
            <div className="message-composer-foot">
              <span>{message.trim().length}/{PRIVATE_MESSAGE_CHARACTER_LIMIT}</span>
              <button className="cal-btn primary" type="submit" disabled={submitting || !message.trim()}>
                <FiSend aria-hidden="true" />
                {diacriticsSubmitLabel({
                  submitting,
                  reviewing: Boolean(diacriticsReview),
                  enabled: Boolean(user && autoDiacritics),
                  submitLabel: "Trimite"
                })}
              </button>
              {user && autoDiacritics && !diacriticsReview ? (
                <button className="cal-btn" type="button" onClick={() => submit(null, { skipDiacritics: true })} disabled={submitting || !message.trim()}>
                  Trimite fără Diacritice
                </button>
              ) : null}
            </div>
            {status ? <div className="inline-status">{status}</div> : null}
            {error ? <div className="inline-error">{error}</div> : null}
          </form>
        </section>
      </div>
    </>
  );
}

function ProfileMessageButton({ owner, user, onOpen }) {
  const { openAuthModal } = useAuthModal();
  if (!owner || owner.id === user?.id) return null;
  const loggedIn = Boolean(user);
  return (
    <button
      className="profile-link-btn profile-message-action"
      type="button"
      onClick={() => (loggedIn ? onOpen() : openAuthModal?.())}
      aria-label={loggedIn ? "Trimite mesaj privat" : "Autentifică-te pentru mesaj privat"}
      title={loggedIn ? "Trimite mesaj privat" : "Autentifică-te pentru mesaj privat"}
    >
      <FiMail aria-hidden="true" />
    </button>
  );
}

function ProfileAudioPlayButton({ owner, user, readyAudioCount, onStartAuthorListening }) {
  const loggedIn = Boolean(user);
  const hasAudio = Number(readyAudioCount || 0) > 0;
  const canListen = Boolean(user?.has_audio_access);
  let title = owner?.username ? `Ascultă textele audio ale lui ${usernameHandle(owner.username)}` : "Play";
  if (!loggedIn) title = "Autentifică-te și activează Cronicar sau Rapsod pentru Play";
  else if (!canListen) title = "Necesită abonament Cronicar sau Rapsod";
  else if (!hasAudio) title = "Autorul nu are audio disponibil";
  const disabled = !loggedIn || !canListen || !hasAudio;

  return (
    <button
      className="profile-write-btn profile-audio-play-btn"
      type="button"
      onClick={() => {
        if (!disabled && owner?.username) onStartAuthorListening?.(owner.username);
      }}
      disabled={disabled}
      aria-label={title}
      title={title}
    >
      <FiPlay aria-hidden="true" />
      <span>Ascultă opere de acest autor</span>
    </button>
  );
}

function ProfileHero({ data, postCount, user, onUserRefresh, onStartAuthorListening }) {
  const owner = data?.blog_owner;
  const [followerCount, setFollowerCount] = useState(data?.follower_count || 0);
  const [messageModalOpen, setMessageModalOpen] = useState(false);
  useEffect(() => {
    setFollowerCount(data?.follower_count || 0);
    setMessageModalOpen(false);
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
      <ExternalProfileLinks links={profileIconLinks} className="profile-icon-row profile-social-row">
        {isOwnProfile ? (
          <a className="profile-link-btn profile-settings-btn" href={authorPath(user, "/profil")} aria-label="Setări profil" title="Setări profil">
            <FiSettings aria-hidden="true" />
          </a>
        ) : null}
      </ExternalProfileLinks>
      {!isOwnProfile ? (
        <div className="profile-link-row profile-action-row" aria-label="Acțiuni sociale">
          <ProfileFollowButton
            owner={owner}
            user={user}
            initialFollowing={data.viewer_following}
            onFollowingChange={(nextFollowing) => setFollowerCount((current) => Math.max(0, current + (nextFollowing ? 1 : -1)))}
            onUserRefresh={onUserRefresh}
          />
          <ProfileFriendActions owner={owner} user={user} initialStatus={data.viewer_friendship_status} initialFriendshipId={data.viewer_friendship_id} onUserRefresh={onUserRefresh} />
          <PromoteAuthorButton owner={owner} user={user} initialPromoted={data.viewer_promoted_author} />
          <ProfileMessageButton owner={owner} user={user} onOpen={() => setMessageModalOpen(true)} />
        </div>
      ) : null}
      <ProfileMessageModal owner={owner} user={user} open={messageModalOpen} onClose={() => setMessageModalOpen(false)} />
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
      </div>
      <div className="profile-stat-row profile-economy-row" aria-label="Opere și inventar">
        {isOwnProfile ? (
          <a className="profile-write-btn" href={authorPath(user, "/panou")}>
            <FiEdit3 aria-hidden="true" />
            <span>Scrie</span>
          </a>
        ) : null}
        <ProfileStatLink Icon={FiBookOpen} href={`${blogUrl(owner.username)}/toate-operele`} label="Toate operele" />
        <ProfileStatLink Icon={FaShirt} href={`${blogUrl(owner.username)}/inventar`} label="Inventar" />
      </div>
      <div className="profile-audio-row" aria-label="Audio autor">
        <ProfileAudioPlayButton owner={owner} user={user} readyAudioCount={data.ready_audio_count} onStartAuthorListening={onStartAuthorListening} />
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
            <span className="profile-chip" key={award.id} title={award.award_description || award.award_title}>
              <FiAward aria-hidden="true" />
              <span className="profile-chip-label">{award.award_title}</span>
            </span>
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
            <div className="profile-promotion-label">Postări proprii promovate</div>
            <div className="profile-promotion-grid">
              {ownPosts.map((post) => <PostCard key={`own-${post.id}`} post={post} />)}
            </div>
          </div>
        ) : null}
        {authors.length ? (
          <div className="profile-promotion-block">
            <div className="profile-promotion-label">Autori pe care îi promovez</div>
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
            <div className="profile-promotion-label">Lucrările altor autori pe care le promovez</div>
            <div className="profile-promotion-grid compact">
              {otherPosts.map((post) => <PostCard key={`other-${post.id}`} post={post} />)}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
function promotedAuthorEntries(authors = []) {
  return authors.map((entry, index) => (
    entry?.user ? entry : { user: entry, position: entry?.position ?? index + 1 }
  )).filter((entry) => entry.user);
}

function applyPromotionPayload(data, promotions) {
  if (!data || !promotions) return data;
  const authorEntries = promotedAuthorEntries(promotions.authors || []);
  return {
    ...data,
    promotion_limits: promotions.limits || data.promotion_limits,
    featured_posts: promotions.own_posts || [],
    promoted_own_posts: promotions.own_posts || [],
    promoted_authors: authorEntries,
    best_friends: authorEntries,
    promoted_external_posts: promotions.other_posts || []
  };
}

function promotionPostUrl(post, owner) {
  const username = post?.owner?.username || owner?.username;
  return username && post?.slug ? `${blogUrl(username)}/${post.slug}` : "#";
}

function PromotionEditorItem({ item, kind, owner, promoted, busy, disabled, onToggle }) {
  const isAuthor = kind === "author";
  const title = isAuthor ? usernameHandle(item.username) : item.title;
  const meta = isAuthor ? htmlToText(item.subtitle || "") : item.owner?.username ? usernameHandle(item.owner.username) : owner?.username ? usernameHandle(owner.username) : "";
  const href = isAuthor ? blogUrl(item.username) : promotionPostUrl(item, owner);
  return (
    <div className="promotion-item">
      <a className="promotion-item-main" href={href}>
        {isAuthor ? <img className="promotion-avatar" src={profileAvatarUrl(item, 64)} alt="" aria-hidden="true" /> : <FiBookOpen aria-hidden="true" />}
        <span>
          <strong>{title}</strong>
          {meta ? <small>{meta}</small> : null}
        </span>
      </a>
      <button className={`cal-btn ${promoted ? "" : "primary"}`.trim()} type="button" onClick={onToggle} disabled={busy || disabled}>
        <FiStar aria-hidden="true" />
        {promoted ? "Elimină" : "Promovează"}
      </button>
    </div>
  );
}

function PromotionEditorGroup({ title, Icon, items, kind, owner, empty, busyKey, promotedIds, limitReached, onToggle }) {
  return (
    <div className="promotion-group">
      <div className="promotion-group-head">
        <Icon aria-hidden="true" />
        <span>{title}</span>
      </div>
      {items.length ? (
        <div className="promotion-item-list">
          {items.map((item) => {
            const promoted = promotedIds.has(item.id);
            return (
              <PromotionEditorItem
                key={`${kind}-${item.id}`}
                item={item}
                kind={kind}
                owner={owner}
                promoted={promoted}
                busy={busyKey === `${kind}-${item.id}`}
                disabled={!promoted && limitReached}
                onToggle={() => onToggle(kind, item, promoted)}
              />
            );
          })}
        </div>
      ) : <p className="auth-sub">{empty}</p>}
    </div>
  );
}

function PromotionResultList({ title, Icon, items, kind, owner, empty, busyKey, promotedIds, limitReached, onToggle }) {
  return (
    <div className="promotion-result-section">
      <div className="promotion-group-head">
        <Icon aria-hidden="true" />
        <span>{title}</span>
      </div>
      {items.length ? (
        <div className="promotion-item-list">
          {items.map((item) => {
            const promoted = promotedIds.has(item.id);
            return (
              <PromotionEditorItem
                key={`result-${kind}-${item.id}`}
                item={item}
                kind={kind}
                owner={owner}
                promoted={promoted}
                busy={busyKey === `${kind}-${item.id}`}
                disabled={!promoted && limitReached}
                onToggle={() => onToggle(kind, item, promoted)}
              />
            );
          })}
        </div>
      ) : <p className="auth-sub">{empty}</p>}
    </div>
  );
}

function ProfilePromotionEditor({ owner, onPromotionsChange }) {
  const [promotions, setPromotions] = useState(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState({ authors: [], other_posts: [] });
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [busyKey, setBusyKey] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setStatus("");
    fetchPromotions()
      .then((promotionData) => {
        if (cancelled) return;
        setPromotions(promotionData);
        onPromotionsChange?.(promotionData);
      })
      .catch((requestError) => {
        if (!cancelled) setStatus(requestError.message || "Nu am putut încărca promovările.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [owner.username, onPromotionsChange]);

  useEffect(() => {
    const term = query.trim();
    if (term.length < 2) {
      setResults({ authors: [], other_posts: [] });
      setSearching(false);
      return undefined;
    }
    let cancelled = false;
    setSearching(true);
    const timer = window.setTimeout(() => {
      searchPromotions(term)
        .then((data) => {
          if (!cancelled) {
            setResults({
              authors: data.authors || [],
              other_posts: data.other_posts || []
            });
          }
        })
        .catch((requestError) => {
          if (!cancelled) setStatus(requestError.message || "Nu am putut căuta promovări.");
        })
        .finally(() => {
          if (!cancelled) setSearching(false);
        });
    }, 180);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query]);

  const limits = promotions?.limits || { own_posts: 2, authors: 3, other_posts: 3 };
  const authorIds = new Set((promotions?.authors || []).map((item) => item.id));
  const otherPostIds = new Set((promotions?.other_posts || []).map((item) => item.id));

  const toggle = async (kind, item, promoted) => {
    const key = `${kind}-${item.id}`;
    setBusyKey(key);
    setStatus("");
    try {
      const response = kind === "author"
        ? (promoted ? await unpromoteAuthor(item.id) : await promoteAuthor(item.id))
        : (promoted ? await unpromotePost(item.id) : await promotePost(item.id));
      setPromotions(response.promotions);
      onPromotionsChange?.(response.promotions);
      setStatus(promoted ? "Promovarea a fost eliminată." : "Promovarea a fost salvată.");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut actualiza promovarea.");
    } finally {
      setBusyKey("");
    }
  };

  return (
    <section className="profile-promotions profile-promotion-editor" aria-label="Editează promovările">
      <div className="profile-panel-heading">
        <FiStar aria-hidden="true" />
        <div className="piece-card-kicker">editează promovările</div>
      </div>
      <p className="auth-sub promotion-editor-note">
        Îți poți promova până la {formatNumber(limits.own_posts)} texte proprii. Pentru a le selecta, te rog alege-le din <a href={authorPath(owner, "/panou")}>„Panou”</a>. Aici poți căuta până la {formatNumber(limits.authors)} autori și {formatNumber(limits.other_posts)} texte ale altor autori pentru Călimara mea.
      </p>
      {loading ? <p className="auth-sub">Se încarcă opțiunile de promovare.</p> : null}
      {promotions ? (
        <div className="promotion-editor-grid">
          <PromotionEditorGroup
            title={`Autori promovați (${promotions.authors.length}/${limits.authors})`}
            Icon={FiUsers}
            items={promotions.authors || []}
            kind="author"
            owner={owner}
            empty="Nu ai autori promovați."
            busyKey={busyKey}
            promotedIds={authorIds}
            limitReached={false}
            onToggle={toggle}
          />
          <PromotionEditorGroup
            title={`Texte promovate de la alți autori (${promotions.other_posts.length}/${limits.other_posts})`}
            Icon={FiBookOpen}
            items={promotions.other_posts || []}
            kind="other-post"
            owner={owner}
            empty="Nu ai texte externe promovate."
            busyKey={busyKey}
            promotedIds={otherPostIds}
            limitReached={false}
            onToggle={toggle}
          />
          <div className="promotion-group promotion-search-group">
            <label className="promotion-group-head" htmlFor="profile-promotion-search">
              <FiSearch aria-hidden="true" />
              <span>Caută autori sau texte</span>
            </label>
            <input
              id="profile-promotion-search"
              className="cal-input"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="nume autor sau titlu"
            />
            <div className="promotion-search-results">
              <PromotionResultList
                title="Autori găsiți"
                Icon={FiUsers}
                items={results.authors || []}
                kind="author"
                owner={owner}
                empty={query.trim().length < 2 ? "Scrie cel puțin 2 caractere." : searching ? "Se caută." : "Niciun autor găsit."}
                busyKey={busyKey}
                promotedIds={authorIds}
                limitReached={(promotions.authors?.length || 0) >= limits.authors}
                onToggle={toggle}
              />
              <PromotionResultList
                title="Texte găsite"
                Icon={FiBookOpen}
                items={results.other_posts || []}
                kind="other-post"
                owner={owner}
                empty={query.trim().length < 2 ? "Scrie cel puțin 2 caractere." : searching ? "Se caută." : "Niciun text găsit."}
                busyKey={busyKey}
                promotedIds={otherPostIds}
                limitReached={(promotions.other_posts?.length || 0) >= limits.other_posts}
                onToggle={toggle}
              />
            </div>
          </div>
        </div>
      ) : null}
      {status ? <div className={status.includes("Nu am putut") || status.includes("Poți") ? "inline-error" : "inline-status"}>{status}</div> : null}
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
function BlogView({ username, user, onUserRefresh, onStartAuthorListening }) {
  const { data, error, loading } = useAsync(() => fetchBlog(username), [username]);
  const [profileData, setProfileData] = useState(null);

  useEffect(() => {
    setProfileData(data);
  }, [data]);

  const handlePromotionsChange = useCallback((promotions) => {
    setProfileData((current) => applyPromotionPayload(current, promotions));
  }, []);

  const displayData = profileData || data;
  const owner = displayData?.blog_owner;
  const isOwnProfile = Boolean(user?.username && owner?.username && user.username.toLowerCase() === owner.username.toLowerCase());
  const totalPostCount = (displayData?.category_counts || []).reduce((sum, item) => sum + Number(item.count || 0), 0);
  usePageSeo(displayData ? profileSeo(displayData.blog_owner, { postCount: totalPostCount }) : null, [displayData?.blog_owner?.id, displayData?.blog_owner?.updated_at, totalPostCount]);
  return (
    <PageShell kicker="profil" title={displayData ? null : usernameHandle(username)}>
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca blogul">{error}</StatusPanel> : null}
      {displayData ? (
        <>
          <ProfileHero data={displayData} postCount={totalPostCount} user={user} onUserRefresh={onUserRefresh} onStartAuthorListening={onStartAuthorListening} />
          <EquippedStrip items={displayData.blog_owner?.equipped_items} />
          {isOwnProfile ? <ProfilePromotionEditor owner={owner} onPromotionsChange={handlePromotionsChange} /> : null}
          <ProfilePromotions data={displayData} />
          <ProfileHighlights data={displayData} />
          <ProfileSeriesList series={displayData.series} />
        </>
      ) : null}
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
  usePageSeo(owner ? profileSeo(owner, { allWorks: true, postCount: data?.posts?.length || 0 }) : null, [owner?.id, owner?.updated_at, data?.posts?.length]);

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

export default function ProfileRoute({ route, user, onUserRefresh, onStartAuthorListening }) {
  if (route.name === "allWorks") return <AllWorksView username={route.username} />;
  if (route.name === "followers") return <FollowListView username={route.username} kind="followers" />;
  if (route.name === "following") return <FollowListView username={route.username} kind="following" />;
  return <BlogView username={route.username} user={user} onUserRefresh={onUserRefresh} onStartAuthorListening={onStartAuthorListening} />;
}
