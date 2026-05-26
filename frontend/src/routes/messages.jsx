import { useCallback, useEffect, useRef, useState } from "react";
import { FaFlag } from "react-icons/fa";
import { FiArrowLeft, FiEdit3, FiRefreshCcw, FiSearch, FiSend, FiX } from "react-icons/fi";
import { fetchConversation, fetchConversations, reportMessage, sendConversationMessage, sendMessage } from "../api/messages.js";
import { searchUsers } from "../api/users.js";
import { addDiacritics } from "../api/writing.js";
import { PRIVATE_MESSAGE_CHARACTER_LIMIT } from "../app/constants.js";
import { DiacriticsControl, DiacriticsProgressOverlay, DiacriticsReviewPanel, diacriticsSubmitLabel, useDiacriticsProgress, useDiacriticsQuota } from "../app/diacritics.jsx";
import { formatDateTime, usernameHandle } from "../app/format.js";
import { AuthRequired, PageShell, StatusPanel } from "../app/layout.jsx";
import { blogUrl, profileAvatarUrl } from "../app/paths.js";
import { ReportModal } from "../app/post-actions.jsx";

function messageTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  if (sameDay) {
    return new Intl.DateTimeFormat("ro-RO", { hour: "2-digit", minute: "2-digit" }).format(date);
  }
  return formatDateTime(value);
}

function conversationPreview(conversation) {
  const latest = conversation?.latest_message;
  if (!latest?.content) return "Fără mesaje încă.";
  return latest.content;
}

function messageUserLabel(user) {
  if (user?.is_system) return "Călimara";
  return usernameHandle(user?.username);
}

function requestedConversationId() {
  if (typeof window === "undefined") return undefined;
  const params = new URLSearchParams(window.location.search);
  const raw = params.get("conversatie") || params.get("conversation") || params.get("conversation_id");
  const parsed = Number.parseInt(raw || "", 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
}

function ConversationListItem({ conversation, active, onSelect }) {
  const otherUser = conversation.other_user || {};
  const unread = Number(conversation.unread_count || 0);
  return (
    <button
      className={`message-conversation ${active ? "active" : ""} ${unread ? "unread" : ""}`.trim()}
      type="button"
      onClick={() => onSelect(conversation.id)}
      aria-pressed={active}
    >
      <img className="message-avatar profile-picture" src={profileAvatarUrl(otherUser, 72)} alt="" aria-hidden="true" />
      <span className="message-conversation-main">
        <span className="message-conversation-head">
          <strong>{messageUserLabel(otherUser)}</strong>
          <span>{messageTime(conversation.latest_message?.created_at || conversation.updated_at)}</span>
        </span>
        <span className="message-conversation-preview">{conversationPreview(conversation)}</span>
      </span>
      {unread ? <span className="message-unread-badge" aria-label={`${unread} mesaje necitite`}>{unread > 9 ? "9+" : unread}</span> : null}
    </button>
  );
}

function UserResultButton({ result, onSelect }) {
  return (
    <button className="message-user-result" type="button" onClick={() => onSelect(result)} aria-label={`Alege ${usernameHandle(result.username)}`}>
      <img className="message-avatar profile-picture" src={profileAvatarUrl(result, 56)} alt="" aria-hidden="true" />
      <span>
        <strong>{usernameHandle(result.username)}</strong>
        {result.subtitle ? <small>{result.subtitle}</small> : null}
      </span>
    </button>
  );
}

function NewMessageModal({ user, open, onClose, onCreated }) {
  const [recipient, setRecipient] = useState("");
  const [selectedUser, setSelectedUser] = useState(null);
  const [message, setMessage] = useState("");
  const [searchState, setSearchState] = useState({ results: [], loading: false, error: "" });
  const [submitState, setSubmitState] = useState({ loading: false, error: "" });
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
    setRecipient("");
    setSelectedUser(null);
    setMessage("");
    setSearchState({ results: [], loading: false, error: "" });
    setSubmitState({ loading: false, error: "" });
    setAutoDiacritics(false);
    setDiacriticsReview(null);
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
    const term = recipient.trim().replace(/^@/, "");
    if (selectedUser?.username && selectedUser.username.toLowerCase() === term.toLowerCase()) {
      setSearchState({ results: [], loading: false, error: "" });
      return undefined;
    }
    if (term.length < 3) {
      setSearchState({ results: [], loading: false, error: "" });
      return undefined;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setSearchState((current) => ({ ...current, loading: true, error: "" }));
      searchUsers(term)
        .then((results) => {
          if (!cancelled) setSearchState({ results: Array.isArray(results) ? results : [], loading: false, error: "" });
        })
        .catch((error) => {
          if (!cancelled) setSearchState({ results: [], loading: false, error: error.message || "Nu am putut căuta utilizatori." });
        });
    }, 220);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [open, recipient, selectedUser?.username]);

  if (!open) return null;

  const selectUser = (result) => {
    setSelectedUser(result);
    setRecipient(result.username);
    setSearchState({ results: [], loading: false, error: "" });
  };

  const submit = async (event, { skipDiacritics = false } = {}) => {
    event?.preventDefault();
    const recipientUsername = (selectedUser?.username || recipient).trim().replace(/^@/, "");
    const content = message.trim();
    if (!recipientUsername || !content || submitState.loading) return;
    setSubmitState({ loading: true, error: "" });
    try {
      if (!skipDiacritics && user && autoDiacritics && !diacriticsReview) {
        startDiacriticsProgress({ content });
        const converted = await addDiacritics({ kind: "private_message", content });
        finishDiacriticsProgress();
        applyDiacriticsQuota(converted.quota);
        setMessage(converted.content ?? message);
        setDiacriticsReview({ originalContent: message, changed: converted.changed });
        setSubmitState({ loading: false, error: "" });
        return;
      }
      const response = await sendMessage({ recipient_username: recipientUsername, content });
      await onCreated?.(response?.conversation_id);
    } catch (error) {
      failDiacriticsProgress();
      setSubmitState({ loading: false, error: error.message || "Nu am putut trimite mesajul." });
      return;
    }
    setSubmitState({ loading: false, error: "" });
  };

  return (
    <>
      <DiacriticsProgressOverlay {...diacriticsProgress} />
      <div className="access-modal-scrim" role="presentation" onClick={onClose}>
        <section className="access-modal message-modal" role="dialog" aria-modal="true" aria-labelledby="new-message-title" onClick={(event) => event.stopPropagation()}>
          <button className="access-modal-close" type="button" aria-label="Închide" onClick={onClose}>x</button>
          <h2 id="new-message-title" className="access-modal-title">Mesaj nou</h2>
          <form className="message-modal-form" onSubmit={submit}>
            <label className="cal-label" htmlFor="new-message-recipient">Destinatar</label>
            <div className="message-recipient-field">
              <FiSearch aria-hidden="true" />
              <input
                id="new-message-recipient"
                className="cal-input"
                value={recipient}
                onChange={(event) => {
                  setRecipient(event.target.value);
                  setSelectedUser(null);
                }}
                placeholder="Caută după username"
                autoComplete="off"
                maxLength="80"
              />
            </div>
            {selectedUser ? (
              <div className="message-selected-user">
                <img className="message-avatar profile-picture" src={profileAvatarUrl(selectedUser, 48)} alt="" aria-hidden="true" />
                <span>{usernameHandle(selectedUser.username)}</span>
                <button type="button" aria-label="Schimbă destinatarul" onClick={() => setSelectedUser(null)}>
                  <FiX aria-hidden="true" />
                </button>
              </div>
            ) : null}
            {searchState.loading ? <div className="theatre-suggestions-note">Se caută utilizatori...</div> : null}
            {searchState.error ? <div className="inline-error">{searchState.error}</div> : null}
            {!searchState.loading && searchState.results.length ? (
              <div className="message-user-results">
                {searchState.results.map((result) => <UserResultButton key={result.id} result={result} onSelect={selectUser} />)}
              </div>
            ) : null}
            <label className="cal-label" htmlFor="new-message-content">Mesaj</label>
            <textarea
              id="new-message-content"
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
              <button className="cal-btn primary" type="submit" disabled={submitState.loading || !message.trim() || !(selectedUser?.username || recipient.trim())}>
                <FiSend aria-hidden="true" />
                {diacriticsSubmitLabel({
                  submitting: submitState.loading,
                  reviewing: Boolean(diacriticsReview),
                  enabled: Boolean(user && autoDiacritics),
                  submitLabel: "Trimite"
                })}
              </button>
              {user && autoDiacritics && !diacriticsReview ? (
                <button className="cal-btn" type="button" onClick={() => submit(null, { skipDiacritics: true })} disabled={submitState.loading || !message.trim() || !(selectedUser?.username || recipient.trim())}>
                  Trimite fără Diacritice
                </button>
              ) : null}
            </div>
            {submitState.error ? <div className="inline-error">{submitState.error}</div> : null}
          </form>
        </section>
      </div>
    </>
  );
}

function ChatPanel({
  user,
  thread,
  loading,
  error,
  activeConversationId,
  reply,
  sending,
  replyAutoDiacritics,
  replyReview,
  diacriticsQuota,
  diacriticsQuotaLoading,
  diacriticsQuotaError,
  onReplyChange,
  onReplyAutoDiacriticsChange,
  onReplyReviewChange,
  onSend,
  onBack,
  onRefresh
}) {
  const endRef = useRef(null);
  const otherUser = thread?.conversation?.other_user || {};
  const messages = thread?.messages || [];
  const otherUserLabel = messageUserLabel(otherUser);
  const [reportModal, setReportModal] = useState(null);
  const [reportDetails, setReportDetails] = useState("");
  const [reportEvidenceUrl, setReportEvidenceUrl] = useState("");
  const [reportBusy, setReportBusy] = useState("");
  const [reportStatus, setReportStatus] = useState("");

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [activeConversationId, messages.length]);

  useEffect(() => {
    setReportModal(null);
    setReportDetails("");
    setReportEvidenceUrl("");
    setReportBusy("");
    setReportStatus("");
  }, [activeConversationId]);

  const openReportModal = (message) => {
    setReportStatus("");
    setReportDetails("");
    setReportEvidenceUrl("");
    setReportModal({ message, reasonType: "offensive" });
  };

  const selectReportReason = (reasonType) => {
    setReportModal((current) => current ? { ...current, reasonType } : current);
    setReportDetails("");
    setReportEvidenceUrl("");
  };

  const closeReportModal = () => {
    if (reportBusy) return;
    setReportModal(null);
    setReportDetails("");
    setReportEvidenceUrl("");
  };

  const submitReport = async (event) => {
    event.preventDefault();
    if (!reportModal?.message?.id || !reportModal.reasonType || reportBusy) return;
    setReportBusy("report");
    setReportStatus("");
    try {
      await reportMessage(reportModal.message.id, {
        reason_type: reportModal.reasonType,
        details: reportDetails,
        evidence_url: reportModal.reasonType === "plagiarism" ? reportEvidenceUrl : ""
      });
      setReportStatus("Raportarea a fost trimisă către moderatori.");
      setReportModal(null);
      setReportDetails("");
      setReportEvidenceUrl("");
    } catch (requestError) {
      setReportStatus(requestError.message || "Nu am putut trimite raportarea.");
    } finally {
      setReportBusy("");
    }
  };

  if (!activeConversationId) {
    return (
      <section className="message-chat-panel empty" aria-label="Conversație">
        <StatusPanel title="Alege o conversație">Selectează un fir din istoric sau pornește unul nou.</StatusPanel>
      </section>
    );
  }

  return (
    <section className="message-chat-panel" aria-label="Conversație">
      <header className="message-chat-head">
        <button className="message-back-btn" type="button" onClick={onBack} aria-label="Înapoi la conversații">
          <FiArrowLeft aria-hidden="true" />
        </button>
        {otherUser.is_system ? (
          <div className="message-chat-user">
            <img className="message-avatar profile-picture" src={profileAvatarUrl(otherUser, 64)} alt="" aria-hidden="true" />
            <span>
              <strong>{otherUserLabel}</strong>
              <small>Conversație de suport</small>
            </span>
          </div>
        ) : (
          <a className="message-chat-user" href={otherUser.username ? blogUrl(otherUser.username) : "#"}>
            <img className="message-avatar profile-picture" src={profileAvatarUrl(otherUser, 64)} alt="" aria-hidden="true" />
            <span>
              <strong>{otherUserLabel}</strong>
              <small>Conversație privată</small>
            </span>
          </a>
        )}
        <button className="message-refresh-btn" type="button" onClick={onRefresh} aria-label="Reîmprospătează conversația" title="Reîmprospătează conversația">
          <FiRefreshCcw aria-hidden="true" />
        </button>
      </header>
      {loading && !thread ? <div className="message-thread-note">Se încarcă conversația...</div> : null}
      {error ? <div className="inline-error message-thread-error">{error}</div> : null}
      {reportStatus ? <div className="inline-status message-thread-status">{reportStatus}</div> : null}
      <div className="message-thread" aria-live="polite">
        {messages.map((message) => {
          const mine = Boolean(message.is_mine);
          const avatarUser = mine ? user : otherUser;
          return (
            <div className={`message-row ${mine ? "mine" : "theirs"}`.trim()} key={message.id}>
              <img className="message-avatar profile-picture" src={profileAvatarUrl(avatarUser, 44)} alt="" aria-hidden="true" />
              <div className={`message-bubble ${!mine ? "has-report-action" : ""}`.trim()}>
                <p>{message.content}</p>
                <div className="message-bubble-foot">
                  <time dateTime={message.created_at}>{messageTime(message.created_at)}</time>
                  {!mine && !otherUser.is_system ? (
                    <button className="message-report-btn" type="button" onClick={() => openReportModal(message)} disabled={Boolean(reportBusy)} title="Raportează" aria-label="Raportează mesajul">
                      <FaFlag aria-hidden="true" />
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
          );
        })}
        {!loading && !messages.length ? <div className="message-thread-note">Nu există mesaje încă.</div> : null}
        <div ref={endRef} />
      </div>
      <form className="message-reply-form" onSubmit={onSend}>
        <textarea
          className="cal-textarea message-reply-input"
          value={reply}
          onChange={(event) => onReplyChange(event.target.value)}
          maxLength={PRIVATE_MESSAGE_CHARACTER_LIMIT}
          rows={2}
          placeholder="Scrie un mesaj"
          aria-label="Scrie un mesaj"
        />
        <button className="cal-btn primary message-send-btn" type="submit" disabled={sending || !reply.trim()}>
          <FiSend aria-hidden="true" />
          <span>
            {diacriticsSubmitLabel({
              submitting: sending,
              reviewing: Boolean(replyReview),
              enabled: Boolean(user && replyAutoDiacritics),
              submitLabel: "Trimite"
            })}
          </span>
        </button>
        {user && replyAutoDiacritics && !replyReview ? (
          <button className="cal-btn message-send-btn" type="button" onClick={() => onSend(null, { skipDiacritics: true })} disabled={sending || !reply.trim()}>
            Trimite fără Diacritice
          </button>
        ) : null}
        <div className="message-diacritics-block">
          <DiacriticsControl
            user={user}
            enabled={replyAutoDiacritics}
            disabled={Boolean(replyReview)}
            label="Adaugă automat diacritice în mesaj?"
            quota={diacriticsQuota}
            quotaLoading={diacriticsQuotaLoading}
            quotaError={diacriticsQuotaError}
            onChange={(checked) => {
              onReplyAutoDiacriticsChange(checked);
              onReplyReviewChange(null);
            }}
          />
          <DiacriticsReviewPanel
            active={Boolean(replyReview)}
            changed={Boolean(replyReview?.changed)}
            onReset={replyReview ? () => {
              onReplyChange(replyReview.originalContent);
              onReplyReviewChange(null);
            } : null}
          />
        </div>
      </form>
      <ReportModal
        modal={reportModal}
        busy={reportBusy}
        details={reportDetails}
        evidenceUrl={reportEvidenceUrl}
        allowPlagiarism={false}
        onDetailsChange={setReportDetails}
        onEvidenceUrlChange={setReportEvidenceUrl}
        onSelectReason={selectReportReason}
        onClose={closeReportModal}
        onSubmit={submitReport}
      />
    </section>
  );
}

function MessagesView({ user, onMessagesRefresh }) {
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [thread, setThread] = useState(null);
  const [listState, setListState] = useState({ loading: true, error: "" });
  const [threadState, setThreadState] = useState({ loading: false, error: "" });
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);
  const [newMessageOpen, setNewMessageOpen] = useState(false);
  const [replyAutoDiacritics, setReplyAutoDiacritics] = useState(false);
  const [replyReview, setReplyReview] = useState(null);
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

  const loadConversations = useCallback(async (preferredId = undefined, options = {}) => {
    if (!options.silent) setListState({ loading: true, error: "" });
    try {
      const data = await fetchConversations();
      const nextConversations = Array.isArray(data?.conversations) ? data.conversations : [];
      setConversations(nextConversations);
      setActiveConversationId((current) => {
        const desired = preferredId === undefined ? current : preferredId;
        if (desired && nextConversations.some((conversation) => conversation.id === desired)) return desired;
        return null;
      });
      if (!options.silent) setListState({ loading: false, error: "" });
      return nextConversations;
    } catch (error) {
      if (!options.silent) setListState({ loading: false, error: error.message || "Nu am putut încărca mesajele." });
      return [];
    }
  }, []);

  const loadThread = useCallback(async (conversationId, options = {}) => {
    if (!conversationId) {
      setThread(null);
      return null;
    }
    if (!options.silent) setThreadState({ loading: true, error: "" });
    try {
      const data = await fetchConversation(conversationId);
      setThread(data);
      onMessagesRefresh?.();
      if (!options.silent) setThreadState({ loading: false, error: "" });
      return data;
    } catch (error) {
      if (!options.silent) setThreadState({ loading: false, error: error.message || "Nu am putut încărca conversația." });
      return null;
    }
  }, [onMessagesRefresh]);

  useEffect(() => {
    if (!user) return undefined;
    let cancelled = false;
    loadConversations(requestedConversationId()).then(() => {
      if (cancelled) return;
    });
    return () => {
      cancelled = true;
    };
  }, [loadConversations, user]);

  useEffect(() => {
    if (!activeConversationId) {
      setThread(null);
      setReply("");
      setReplyReview(null);
      return;
    }
    setReply("");
    setReplyReview(null);
    setReplyAutoDiacritics(false);
    loadThread(activeConversationId).then(() => loadConversations(activeConversationId, { silent: true }));
  }, [activeConversationId, loadConversations, loadThread]);

  useEffect(() => {
    if (!user) return undefined;
    const onFocus = () => {
      loadConversations(activeConversationId, { silent: true });
      if (activeConversationId) loadThread(activeConversationId, { silent: true });
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [activeConversationId, loadConversations, loadThread, user]);

  useEffect(() => {
    if (!activeConversationId) return undefined;
    const intervalId = window.setInterval(() => {
      loadThread(activeConversationId, { silent: true }).then(() => loadConversations(activeConversationId, { silent: true }));
    }, 10000);
    return () => window.clearInterval(intervalId);
  }, [activeConversationId, loadConversations, loadThread]);

  if (!user) return <AuthRequired />;

  const selectConversation = (conversationId) => {
    setActiveConversationId(conversationId);
  };

  const changeReply = (value) => {
    setReply(value);
    if (replyReview) setReplyReview(null);
  };

  const sendReply = async (event, { skipDiacritics = false } = {}) => {
    event?.preventDefault();
    const content = reply.trim();
    if (!activeConversationId || !content || sending) return;
    setSending(true);
    setThreadState((current) => ({ ...current, error: "" }));
    try {
      if (!skipDiacritics && user && replyAutoDiacritics && !replyReview) {
        startDiacriticsProgress({ content });
        const converted = await addDiacritics({ kind: "private_message", content });
        finishDiacriticsProgress();
        applyDiacriticsQuota(converted.quota);
        setReply(converted.content ?? reply);
        setReplyReview({ originalContent: reply, changed: converted.changed });
        setSending(false);
        return;
      }
      await sendConversationMessage(activeConversationId, { content });
      setReply("");
      setReplyReview(null);
      await loadThread(activeConversationId);
      await loadConversations(activeConversationId, { silent: true });
    } catch (error) {
      failDiacriticsProgress();
      setThreadState({ loading: false, error: error.message || "Nu am putut trimite mesajul." });
    } finally {
      setSending(false);
    }
  };

  const handleNewConversation = async (conversationId) => {
    setNewMessageOpen(false);
    await loadConversations(conversationId);
    if (conversationId) await loadThread(conversationId);
  };

  return (
    <PageShell
      kicker="mesaje"
      title="Conversații"
      sub="Mesajele private ale contului tău."
      className="messages-page"
      titleAction={(
        <button className="cal-btn primary" type="button" onClick={() => setNewMessageOpen(true)}>
          <FiEdit3 aria-hidden="true" />
          Mesaj nou
        </button>
      )}
    >
      <DiacriticsProgressOverlay {...diacriticsProgress} />
      <div className={`messages-layout ${activeConversationId ? "has-active" : ""}`.trim()}>
        <aside className="messages-list-panel" aria-label="Istoric mesaje">
          {listState.loading ? <div className="message-thread-note">Se încarcă istoricul...</div> : null}
          {listState.error ? <StatusPanel title="Nu am putut încărca mesajele">{listState.error}</StatusPanel> : null}
          {!listState.loading && !listState.error && conversations.length ? (
            <div className="messages-list">
              {conversations.map((conversation) => (
                <ConversationListItem
                  key={conversation.id}
                  conversation={conversation}
                  active={conversation.id === activeConversationId}
                  onSelect={selectConversation}
                />
              ))}
            </div>
          ) : null}
          {!listState.loading && !listState.error && !conversations.length ? (
            <StatusPanel
              title="Nu ai conversații încă"
              action={<button className="cal-btn primary" type="button" onClick={() => setNewMessageOpen(true)}>Mesaj nou</button>}
            />
          ) : null}
        </aside>
        <ChatPanel
          user={user}
          thread={thread}
          loading={threadState.loading}
          error={threadState.error}
          activeConversationId={activeConversationId}
          reply={reply}
          sending={sending}
          replyAutoDiacritics={replyAutoDiacritics}
          replyReview={replyReview}
          diacriticsQuota={diacriticsQuota}
          diacriticsQuotaLoading={diacriticsQuotaLoading}
          diacriticsQuotaError={diacriticsQuotaError}
          onReplyChange={changeReply}
          onReplyAutoDiacriticsChange={setReplyAutoDiacritics}
          onReplyReviewChange={setReplyReview}
          onSend={sendReply}
          onBack={() => setActiveConversationId(null)}
          onRefresh={() => loadThread(activeConversationId).then(() => loadConversations(activeConversationId, { silent: true }))}
        />
      </div>
      <NewMessageModal user={user} open={newMessageOpen} onClose={() => setNewMessageOpen(false)} onCreated={handleNewConversation} />
    </PageShell>
  );
}

export default function MessagesRoute({ user, onMessagesRefresh }) {
  return <MessagesView user={user} onMessagesRefresh={onMessagesRefresh} />;
}
