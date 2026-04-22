import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  postClubBoardMessage,
  deleteClubBoardMessage,
  type ClubBoardMessage,
  type ClubMemberRole,
} from "@/api/clubs";
import { useToast } from "@/components/ui/toast-context";
import { useAuth } from "@/hooks/useAuth";
import { formatRelativeTime, getAvatarUrl } from "@/lib/utils";

interface Props {
  clubId: number;
  clubSlug: string;
  messages: ClubBoardMessage[];
  myRole: ClubMemberRole | null;
}

export function ClubBoard({ clubId, clubSlug, messages, myRole }: Props) {
  const { user } = useAuth();
  const isMember = !!myRole;
  const isModerator = myRole === "owner" || myRole === "admin";
  const { showToast } = useToast();
  const qc = useQueryClient();

  const [composerContent, setComposerContent] = useState("");
  const [replyTo, setReplyTo] = useState<number | null>(null);
  const [replyContent, setReplyContent] = useState("");

  const invalidate = () => qc.invalidateQueries({ queryKey: ["clubs", "bySlug", clubSlug] });

  const postMutation = useMutation({
    mutationFn: (vars: { content: string; parent_id?: number | null }) =>
      postClubBoardMessage(clubId, vars),
    onSuccess: () => {
      setComposerContent("");
      setReplyTo(null);
      setReplyContent("");
      invalidate();
    },
    onError: (e: Error) => showToast(e.message || "Mesajul nu a putut fi trimis", "danger"),
  });

  const deleteMutation = useMutation({
    mutationFn: (messageId: number) => deleteClubBoardMessage(clubId, messageId),
    onSuccess: () => invalidate(),
    onError: (e: Error) => showToast(e.message || "Mesajul nu a putut fi șters", "danger"),
  });

  const submitTopLevel = (e: React.FormEvent) => {
    e.preventDefault();
    if (!composerContent.trim()) return;
    postMutation.mutate({ content: composerContent.trim() });
  };

  const submitReply = (e: React.FormEvent) => {
    e.preventDefault();
    if (!replyContent.trim() || replyTo === null) return;
    postMutation.mutate({ content: replyContent.trim(), parent_id: replyTo });
  };

  const canDelete = (msg: ClubBoardMessage) =>
    isModerator || (user && msg.author?.id === user.id);

  const renderMessage = (msg: ClubBoardMessage, isReply: boolean) => {
    const seed = msg.author?.avatar_seed || `${msg.author?.username ?? "anon"}-shapes`;
    return (
      <div
        key={msg.id}
        style={{
          display: "flex",
          gap: 10,
          padding: "10px 0",
          borderTop: isReply ? "none" : "1px solid var(--color-hairline)",
          marginLeft: isReply ? 36 : 0,
        }}
      >
        <img
          src={getAvatarUrl(seed, 32)}
          width={32}
          height={32}
          alt=""
          style={{ borderRadius: 4, flexShrink: 0, background: "var(--color-paper-2)" }}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              letterSpacing: "0.1em",
              color: "var(--color-ink-mute)",
              display: "flex",
              gap: 8,
              alignItems: "baseline",
            }}
          >
            <span style={{ color: "var(--color-ink-soft)" }}>
              {msg.author?.username ?? "anonim"}
            </span>
            {msg.author?.role && msg.author.role !== "member" ? (
              <span
                style={{
                  fontSize: 9,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                  color: "var(--color-ink-faint)",
                }}
              >
                {msg.author.role}
              </span>
            ) : null}
            <span>{formatRelativeTime(msg.created_at)}</span>
          </div>
          <div
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: 15,
              color: "var(--color-ink)",
              marginTop: 4,
              whiteSpace: "pre-wrap",
              lineHeight: 1.45,
            }}
          >
            {msg.content}
          </div>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--color-ink-faint)",
              marginTop: 6,
              display: "flex",
              gap: 12,
            }}
          >
            {!isReply && isMember ? (
              <button
                type="button"
                onClick={() => {
                  setReplyTo(msg.id);
                  setReplyContent("");
                }}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  font: "inherit",
                  color: "inherit",
                  padding: 0,
                }}
              >
                răspunde
              </button>
            ) : null}
            {canDelete(msg) ? (
              <button
                type="button"
                onClick={() => {
                  if (confirm("Ștergi mesajul?")) deleteMutation.mutate(msg.id);
                }}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  font: "inherit",
                  color: "var(--color-like)",
                  padding: 0,
                }}
              >
                șterge
              </button>
            ) : null}
          </div>
          {!isReply && replyTo === msg.id ? (
            <form onSubmit={submitReply} style={{ marginTop: 10 }}>
              <textarea
                value={replyContent}
                onChange={(e) => setReplyContent(e.target.value)}
                placeholder="Scrie un răspuns..."
                rows={2}
                className="cal-textarea"
                style={{ width: "100%" }}
              />
              <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                <button
                  type="submit"
                  disabled={postMutation.isPending || !replyContent.trim()}
                  className="cal-btn"
                >
                  Trimite răspuns
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setReplyTo(null);
                    setReplyContent("");
                  }}
                  className="cal-btn"
                >
                  Anulează
                </button>
              </div>
            </form>
          ) : null}
          {!isReply && msg.replies.length > 0 ? (
            <div style={{ marginTop: 6 }}>
              {msg.replies.map((r) => renderMessage(r, true))}
            </div>
          ) : null}
        </div>
      </div>
    );
  };

  return (
    <div>
      <h2
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          letterSpacing: "0.22em",
          textTransform: "uppercase",
          color: "var(--color-ink-mute)",
          margin: "24px 0 8px",
        }}
      >
        Discuții
      </h2>

      {isMember ? (
        <form onSubmit={submitTopLevel} style={{ marginBottom: 16 }}>
          <textarea
            value={composerContent}
            onChange={(e) => setComposerContent(e.target.value)}
            placeholder="Scrie un mesaj nou..."
            rows={3}
            className="cal-textarea"
            style={{ width: "100%" }}
          />
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 6 }}>
            <button
              type="submit"
              disabled={postMutation.isPending || !composerContent.trim()}
              className="cal-btn"
            >
              {postMutation.isPending ? "Se trimite..." : "Postează"}
            </button>
          </div>
        </form>
      ) : (
        <p
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: 13,
            color: "var(--color-ink-mute)",
            marginBottom: 12,
          }}
        >
          Doar membrii clubului pot posta mesaje pe panou.
        </p>
      )}

      {messages.length === 0 ? (
        <p
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: 13,
            color: "var(--color-ink-faint)",
          }}
        >
          Nu există încă mesaje pe panou.
        </p>
      ) : (
        <div>{messages.map((m) => renderMessage(m, false))}</div>
      )}
    </div>
  );
}
