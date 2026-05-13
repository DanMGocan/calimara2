import { useEffect, useState } from "react";
import { FiBookOpen, FiEye, FiFilter, FiMessageCircle, FiSearch, FiUserCheck, FiUserPlus, FiUsers } from "react-icons/fi";
import { acceptFriendRequest, deleteFriendRequest, removeFriend, sendFriendRequest } from "../api/friends.js";
import { followUser, unfollowUser } from "../api/follows.js";
import { fetchUsersDirectory } from "../api/users.js";
import { formatNumber, usernameHandle } from "../app/format.js";
import { AuthRequired, PageShell, StatusPanel } from "../app/layout.jsx";
import { blogUrl, profileAvatarUrl } from "../app/paths.js";
import { FriendActions } from "./friends.jsx";

const RELATIONSHIP_OPTIONS = [
  { value: "all", label: "Toți" },
  { value: "not_friends", label: "Nu sunt prieteni" },
  { value: "friends", label: "Prieteni" },
  { value: "incoming_pending", label: "Cereri primite" },
  { value: "outgoing_pending", label: "Cereri trimise" },
  { value: "following", label: "Urmăriți" },
  { value: "followers", label: "Urmăritori" }
];

const SORT_OPTIONS = [
  { value: "newest", label: "Noi" },
  { value: "oldest", label: "Vechi" },
  { value: "username", label: "Nume" },
  { value: "posts", label: "Texte" },
  { value: "views", label: "Vizualizări" },
  { value: "comments", label: "Comentarii" },
  { value: "followers", label: "Urmăritori" }
];

function DirectoryStat({ Icon, value, label }) {
  return (
    <span>
      <Icon aria-hidden="true" />
      <strong>{formatNumber(value)}</strong>
      {label}
    </span>
  );
}

function DirectoryUserCard({ item, busyKey, onFriendAction, onFollowAction }) {
  const friendBusy = Boolean(busyKey);
  const followBusy = Boolean(busyKey);
  const followLabel = item.viewer_following ? "Urmărit" : "Urmărește";

  return (
    <div className="friend-card users-directory-card">
      <div className="users-directory-main">
        <a className="friend-identity" href={blogUrl(item.username)}>
          <img className="friend-avatar profile-picture" src={profileAvatarUrl(item, 64)} alt="" aria-hidden="true" />
          <span className="friend-copy">
            <span className="friend-name">{usernameHandle(item.username)}</span>
            {item.subtitle ? <span className="friend-subtitle">{item.subtitle}</span> : null}
          </span>
        </a>
        <div className="users-directory-metrics" aria-label="Statistici utilizator">
          <DirectoryStat Icon={FiBookOpen} value={item.approved_post_count} label="texte" />
          <DirectoryStat Icon={FiUsers} value={item.follower_count} label="urmăritori" />
          <DirectoryStat Icon={FiEye} value={item.total_view_count} label="vizualizări" />
          <DirectoryStat Icon={FiMessageCircle} value={item.approved_comment_count} label="comentarii" />
          {item.viewer_followed_by ? <span>Te urmărește</span> : null}
        </div>
      </div>
      <div className="friend-actions users-directory-actions">
        <button
          className={`cal-btn compact ${item.viewer_following ? "" : "primary"}`.trim()}
          type="button"
          disabled={followBusy}
          onClick={() => onFollowAction(item)}
          aria-pressed={Boolean(item.viewer_following)}
        >
          {item.viewer_following ? <FiUserCheck aria-hidden="true" /> : <FiUserPlus aria-hidden="true" />}
          <span>{followLabel}</span>
        </button>
        <FriendActions
          user={item}
          status={item.friendship_status || "none"}
          friendshipId={item.friendship_id}
          busy={friendBusy}
          onAction={onFriendAction}
        />
      </div>
    </div>
  );
}

export default function UsersDirectoryRoute({ user, onUserRefresh }) {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState({ q: "", relationship: "all", sort: "newest" });
  const [state, setState] = useState({ users: [], total: 0, hasMore: false, loading: true, loadingMore: false, error: "" });
  const [busyKey, setBusyKey] = useState("");
  const [actionError, setActionError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const nextQuery = query.trim();
      setFilters((current) => (current.q === nextQuery ? current : { ...current, q: nextQuery }));
    }, 220);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    if (!user) return undefined;
    let cancelled = false;
    setState((current) => ({ ...current, loading: true, loadingMore: false, error: "" }));
    fetchUsersDirectory({ ...filters, offset: 0, limit: 24 })
      .then((data) => {
        if (cancelled) return;
        setState({
          users: Array.isArray(data.users) ? data.users : [],
          total: data.total || 0,
          hasMore: Boolean(data.has_more),
          loading: false,
          loadingMore: false,
          error: ""
        });
      })
      .catch((requestError) => {
        if (!cancelled) {
          setState({ users: [], total: 0, hasMore: false, loading: false, loadingMore: false, error: requestError.message || "Nu am putut încărca utilizatorii." });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [filters, refreshKey, user]);

  if (!user) return <AuthRequired />;

  const refreshDirectory = async () => {
    setRefreshKey((key) => key + 1);
    await onUserRefresh?.();
  };

  const loadMore = async () => {
    if (state.loading || state.loadingMore || !state.hasMore) return;
    setState((current) => ({ ...current, loadingMore: true, error: "" }));
    try {
      const data = await fetchUsersDirectory({ ...filters, offset: state.users.length, limit: 24 });
      const nextUsers = Array.isArray(data.users) ? data.users : [];
      setState((current) => ({
        users: [...current.users, ...nextUsers],
        total: data.total || current.total,
        hasMore: Boolean(data.has_more),
        loading: false,
        loadingMore: false,
        error: ""
      }));
    } catch (requestError) {
      setState((current) => ({ ...current, loadingMore: false, error: requestError.message || "Nu am putut încărca mai mulți utilizatori." }));
    }
  };

  const runFriendAction = async (kind, value) => {
    const key = `${kind}:${value}`;
    if (busyKey) return;
    setBusyKey(key);
    setActionError("");
    try {
      if (kind === "send") await sendFriendRequest(value);
      if (kind === "accept") await acceptFriendRequest(value);
      if (kind === "delete") await deleteFriendRequest(value);
      if (kind === "remove") await removeFriend(value);
      await refreshDirectory();
    } catch (requestError) {
      setActionError(requestError.message || "Nu am putut actualiza prietenia.");
    } finally {
      setBusyKey("");
    }
  };

  const runFollowAction = async (item) => {
    if (busyKey) return;
    setBusyKey(`follow:${item.id}`);
    setActionError("");
    try {
      if (item.viewer_following) await unfollowUser(item.id);
      else await followUser(item.id);
      await refreshDirectory();
    } catch (requestError) {
      setActionError(requestError.message || "Nu am putut actualiza urmărirea.");
    } finally {
      setBusyKey("");
    }
  };

  return (
    <PageShell kicker="utilizatori" title="Utilizatori" sub={`${formatNumber(state.total)} utilizatori găsiți`}>
      <div className="friends-page users-directory-page">
        <div className="users-directory-controls">
          <label className="users-directory-field" htmlFor="users-directory-search">
            <span><FiSearch aria-hidden="true" />Caută</span>
            <input
              id="users-directory-search"
              className="cal-input"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              maxLength="80"
            />
          </label>
          <label className="users-directory-field" htmlFor="users-directory-relationship">
            <span><FiUsers aria-hidden="true" />Relație</span>
            <select id="users-directory-relationship" className="cal-input" value={filters.relationship} onChange={(event) => setFilters((current) => ({ ...current, relationship: event.target.value }))}>
              {RELATIONSHIP_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <label className="users-directory-field" htmlFor="users-directory-sort">
            <span><FiFilter aria-hidden="true" />Sortare</span>
            <select id="users-directory-sort" className="cal-input" value={filters.sort} onChange={(event) => setFilters((current) => ({ ...current, sort: event.target.value }))}>
              {SORT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
        </div>

        {state.loading ? <StatusPanel title="Se încarcă" /> : null}
        {state.error ? <StatusPanel title="Nu am putut încărca utilizatorii">{state.error}</StatusPanel> : null}
        {actionError ? <div className="inline-error">{actionError}</div> : null}
        {!state.loading && !state.error && state.users.length ? (
          <div className="friends-list">
            {state.users.map((item) => (
              <DirectoryUserCard
                key={item.id}
                item={item}
                busyKey={busyKey}
                onFriendAction={runFriendAction}
                onFollowAction={runFollowAction}
              />
            ))}
          </div>
        ) : null}
        {!state.loading && !state.error && !state.users.length ? <StatusPanel title="Nu există utilizatori pentru filtrul ales" /> : null}
        {state.hasMore ? (
          <button className="cal-btn compact users-directory-more" type="button" onClick={loadMore} disabled={state.loadingMore}>
            {state.loadingMore ? "Se încarcă..." : "Încarcă mai mulți"}
          </button>
        ) : null}
      </div>
    </PageShell>
  );
}
