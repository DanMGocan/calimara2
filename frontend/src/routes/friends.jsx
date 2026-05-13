import { useEffect, useState } from "react";
import { FiCheck, FiSearch, FiUserMinus, FiUserPlus, FiUsers, FiX } from "react-icons/fi";
import { acceptFriendRequest, deleteFriendRequest, fetchFriendsState, removeFriend, sendFriendRequest } from "../api/friends.js";
import { searchUsers } from "../api/users.js";
import { usernameHandle } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { AuthRequired, PageShell, StatusPanel } from "../app/layout.jsx";
import { blogUrl, mainPath, profileAvatarUrl } from "../app/paths.js";

export function FriendIdentity({ user }) {
  return (
    <a className="friend-identity" href={blogUrl(user.username)}>
      <img className="friend-avatar profile-picture" src={profileAvatarUrl(user, 64)} alt="" aria-hidden="true" />
      <span className="friend-copy">
        <span className="friend-name">{usernameHandle(user.username)}</span>
        {user.subtitle ? <span className="friend-subtitle">{user.subtitle}</span> : null}
      </span>
    </a>
  );
}

export function FriendActions({ user, status, friendshipId, busy, onAction }) {
  if (status === "self") return null;
  if (status === "friends") {
    return (
      <button className="cal-btn compact" type="button" disabled={busy} onClick={() => onAction("remove", user.id)}>
        <FiUserMinus aria-hidden="true" />
        <span>Elimină</span>
      </button>
    );
  }
  if (status === "incoming_pending") {
    return (
      <>
        <button className="cal-btn primary compact" type="button" disabled={busy || !friendshipId} onClick={() => onAction("accept", friendshipId)}>
          <FiCheck aria-hidden="true" />
          <span>Acceptă</span>
        </button>
        <button className="cal-btn compact" type="button" disabled={busy || !friendshipId} onClick={() => onAction("delete", friendshipId)}>
          <FiX aria-hidden="true" />
          <span>Refuză</span>
        </button>
      </>
    );
  }
  if (status === "outgoing_pending") {
    return (
      <button className="cal-btn compact" type="button" disabled={busy || !friendshipId} onClick={() => onAction("delete", friendshipId)}>
        <FiX aria-hidden="true" />
        <span>Anulează</span>
      </button>
    );
  }
  return (
    <button className="cal-btn primary compact" type="button" disabled={busy} onClick={() => onAction("send", user.id)}>
      <FiUserPlus aria-hidden="true" />
      <span>Adaugă</span>
    </button>
  );
}

function FriendCard({ item, result, busyKey, onAction }) {
  const user = result || item.user;
  const status = result ? result.friendship_status : item.status === "accepted" ? "friends" : `${item.direction}_pending`;
  const friendshipId = result ? result.friendship_id : item.id;
  const busy = Boolean(busyKey);
  return (
    <div className="friend-card">
      <FriendIdentity user={user} />
      <div className="friend-actions">
        <FriendActions user={user} status={status} friendshipId={friendshipId} busy={busy} onAction={onAction} />
      </div>
    </div>
  );
}

function FriendSection({ title, items, empty, busyKey, onAction }) {
  return (
    <section className="friends-section">
      <div className="profile-panel-heading">
        <FiUserPlus aria-hidden="true" />
        <div className="piece-card-kicker">{title}</div>
      </div>
      {items.length ? (
        <div className="friends-list">
          {items.map((item) => <FriendCard key={item.id} item={item} busyKey={busyKey} onAction={onAction} />)}
        </div>
      ) : (
        <div className="friend-empty">{empty}</div>
      )}
    </section>
  );
}

function FriendSearch({ busyKey, onAction, refreshKey }) {
  const [query, setQuery] = useState("");
  const [state, setState] = useState({ results: [], loading: false, error: "" });

  useEffect(() => {
    const term = query.trim();
    if (term.length < 3) {
      setState({ results: [], loading: false, error: "" });
      return undefined;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setState((current) => ({ ...current, loading: true, error: "" }));
      searchUsers(term)
        .then((results) => {
          if (!cancelled) setState({ results: Array.isArray(results) ? results : [], loading: false, error: "" });
        })
        .catch((error) => {
          if (!cancelled) setState({ results: [], loading: false, error: error.message || "Nu am putut căuta utilizatori." });
        });
    }, 220);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query, refreshKey]);

  return (
    <section className="friends-section">
      <label className="auth-field profile-inline-label" htmlFor="friends-search"><FiSearch aria-hidden="true" />Caută utilizatori</label>
      <input
        id="friends-search"
        className="cal-input"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        minLength="3"
        maxLength="80"
      />
      {state.loading ? <div className="friend-empty">Se caută</div> : null}
      {state.error ? <div className="inline-error">{state.error}</div> : null}
      {!state.loading && !state.error && state.results.length ? (
        <div className="friends-list">
          {state.results.map((result) => <FriendCard key={result.id} result={result} busyKey={busyKey} onAction={onAction} />)}
        </div>
      ) : null}
    </section>
  );
}

export default function FriendsRoute({ user, onUserRefresh }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const [busyKey, setBusyKey] = useState("");
  const [actionError, setActionError] = useState("");
  const { data, error, loading } = useAsync(fetchFriendsState, [refreshKey, user?.id]);

  if (!user) return <AuthRequired />;

  const reload = async () => {
    setRefreshKey((key) => key + 1);
    await onUserRefresh?.();
  };

  const runAction = async (kind, value) => {
    const key = `${kind}:${value}`;
    if (busyKey) return;
    setBusyKey(key);
    setActionError("");
    try {
      if (kind === "send") await sendFriendRequest(value);
      if (kind === "accept") await acceptFriendRequest(value);
      if (kind === "delete") await deleteFriendRequest(value);
      if (kind === "remove") await removeFriend(value);
      await reload();
    } catch (requestError) {
      setActionError(requestError.message || "Nu am putut actualiza prietenia.");
    } finally {
      setBusyKey("");
    }
  };

  return (
    <PageShell kicker="prieteni" title="Prieteni">
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca prietenii">{error}</StatusPanel> : null}
      {actionError ? <div className="inline-error">{actionError}</div> : null}
      {data ? (
        <div className="friends-page">
          <div className="friends-toolbar">
            <a className="cal-btn compact" href={mainPath("/utilizatori")}>
              <FiUsers aria-hidden="true" />
              <span>Toți utilizatorii</span>
            </a>
          </div>
          <FriendSection title="cereri primite" items={data.incoming_requests || []} empty="Nu ai cereri primite" busyKey={busyKey} onAction={runAction} />
          <FriendSection title="prieteni" items={data.friends || []} empty="Nu ai prieteni adăugați" busyKey={busyKey} onAction={runAction} />
          <FriendSection title="cereri trimise" items={data.outgoing_requests || []} empty="Nu ai cereri trimise" busyKey={busyKey} onAction={runAction} />
          <FriendSearch busyKey={busyKey} onAction={runAction} refreshKey={refreshKey} />
        </div>
      ) : null}
    </PageShell>
  );
}
