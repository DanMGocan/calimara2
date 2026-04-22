import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { Search } from "lucide-react";
import {
  fetchConversations,
  searchConversations,
  sendNewMessage,
} from "@/api/messages";
import { searchUsers } from "@/api/users";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast-context";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { Stage, LeftCol } from "@/components/ui/stage";
import {
  ActionRow,
  ActionsGroup,
  SideKicker,
} from "@/components/ui/action-row";
import {
  formatRelativeTime,
  getAvatarUrl,
} from "@/lib/utils";
import { MAX_MESSAGE_LENGTH } from "@/lib/constants";

export default function MessagesPage() {
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [searchQuery, setSearchQuery] = useState("");
  const [showNewMessage, setShowNewMessage] = useState(false);
  const [recipient, setRecipient] = useState("");
  const [messageContent, setMessageContent] = useState("");

  const { data: conversations, isLoading } = useQuery({
    queryKey: ["conversations"],
    queryFn: fetchConversations,
  });

  const { data: searchResults } = useQuery({
    queryKey: ["conversations", "search", searchQuery],
    queryFn: () => searchConversations(searchQuery),
    enabled: searchQuery.length >= 2,
  });

  const { data: userResults = [] } = useQuery({
    queryKey: ["users", "search", recipient],
    queryFn: () => searchUsers(recipient),
    enabled: showNewMessage && recipient.length >= 2,
  });

  const sendMutation = useMutation({
    mutationFn: () => sendNewMessage(recipient, messageContent),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      setShowNewMessage(false);
      setRecipient("");
      setMessageContent("");
      showToast("Mesaj trimis.", "success");
      navigate(`/messages/${res.conversation_id}`);
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  if (isLoading) return <PageLoader />;

  const displayList = searchQuery.length >= 2 ? searchResults : conversations;
  const unreadTotal =
    conversations?.reduce((a, c) => a + (c.unread_count ?? 0), 0) ?? 0;

  return (
    <>
      <Helmet>
        <title>Mesaje | călimara.ro</title>
      </Helmet>

      <Stage>
        <LeftCol>
          <aside className="side-col">
            <SideKicker>mesaje</SideKicker>
            <ActionsGroup>
              <ActionRow
                num={1}
                label="Mesaj nou"
                sub="către un scriitor"
                onClick={() => setShowNewMessage(true)}
              />
              <ActionRow
                num={2}
                label="Toate conversațiile"
                sub={`${conversations?.length ?? 0} în total`}
                active
              />
            </ActionsGroup>
            {unreadTotal > 0 ? (
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  letterSpacing: "0.12em",
                  color: "var(--color-accent)",
                  padding: "12px 0",
                  borderTop: "1px solid var(--color-hairline)",
                }}
              >
                {unreadTotal} mesaj{unreadTotal === 1 ? "" : "e"} necitit
                {unreadTotal === 1 ? "" : "e"}
              </div>
            ) : null}
          </aside>
        </LeftCol>

        <div className="piece-col">
          <div className="piece-wrap">
            <div className="piece-kind-row">
              <span className="piece-kind-badge">mesaje</span>
              <span className="piece-kind-sep" />
              <span className="piece-kind-meta">conversații</span>
            </div>
            <h1
              className="piece-title"
              style={{ fontSize: "clamp(32px, 4vw, 52px)", marginBottom: 28 }}
            >
              Mesaje
            </h1>

            <div
              className="relative"
              style={{ marginBottom: 24 }}
            >
              <Search
                className="h-4 w-4"
                style={{
                  position: "absolute",
                  left: 12,
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "var(--color-ink-faint)",
                }}
              />
              <Input
                placeholder="caută conversații…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ paddingLeft: 36 }}
              />
            </div>

            {displayList && displayList.length > 0 ? (
              <div className="flex flex-col gap-2">
                {displayList.map((conv) => (
                  <Link
                    key={conv.id}
                    to={`/messages/${conv.id}`}
                    className="piece-card"
                    style={{ padding: "14px 16px" }}
                  >
                    <div className="flex items-center gap-3">
                      <img
                        src={getAvatarUrl(conv.other_user.avatar_seed, 44)}
                        alt={conv.other_user.username}
                        style={{
                          width: 44,
                          height: 44,
                          borderRadius: "50%",
                          border: "1px solid var(--color-hairline)",
                          flexShrink: 0,
                        }}
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="flex items-baseline justify-between gap-3">
                          <span
                            style={{
                              fontFamily: "var(--font-sans)",
                              fontSize: 14,
                              fontWeight: 600,
                              color: "var(--color-ink)",
                            }}
                          >
                            {conv.other_user.username}
                          </span>
                          {conv.latest_message ? (
                            <span
                              style={{
                                fontFamily: "var(--font-mono)",
                                fontSize: 10,
                                letterSpacing: "0.08em",
                                color: "var(--color-ink-faint)",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {formatRelativeTime(conv.latest_message.created_at)}
                            </span>
                          ) : null}
                        </div>
                        {conv.latest_message ? (
                          <p
                            style={{
                              fontFamily: "var(--font-serif)",
                              fontSize: 14,
                              color: "var(--color-ink-mute)",
                              margin: "4px 0 0",
                              lineHeight: 1.4,
                              display: "-webkit-box",
                              WebkitLineClamp: 1,
                              WebkitBoxOrient: "vertical",
                              overflow: "hidden",
                            }}
                          >
                            {conv.latest_message.content}
                          </p>
                        ) : null}
                      </div>
                      {conv.unread_count > 0 ? (
                        <span
                          style={{
                            minWidth: 22,
                            height: 22,
                            padding: "0 6px",
                            borderRadius: 999,
                            background: "var(--color-accent)",
                            color: "var(--color-paper)",
                            fontFamily: "var(--font-mono)",
                            fontSize: 10,
                            fontWeight: 500,
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            flexShrink: 0,
                          }}
                        >
                          {conv.unread_count}
                        </span>
                      ) : null}
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <div
                style={{
                  padding: "60px 20px",
                  border: "1px dashed var(--color-hairline-strong)",
                  borderRadius: 10,
                  textAlign: "center",
                  color: "var(--color-ink-faint)",
                  fontFamily: "var(--font-serif)",
                  fontStyle: "italic",
                  fontSize: 17,
                }}
              >
                Nicio conversație.
              </div>
            )}
          </div>
        </div>
      </Stage>

      <Dialog open={showNewMessage} onOpenChange={setShowNewMessage}>
        <DialogContent>
          <DialogHeader>
            <div className="auth-kicker">mesaj nou</div>
            <DialogTitle>Scrie unui scriitor</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <div style={{ position: "relative" }}>
              <Input
                placeholder="@nume utilizator"
                value={recipient}
                onChange={(e) => setRecipient(e.target.value)}
              />
              {userResults.length > 0 &&
              recipient.length >= 2 &&
              !userResults.some((u) => u.username === recipient) ? (
                <div
                  style={{
                    position: "absolute",
                    top: "100%",
                    left: 0,
                    right: 0,
                    marginTop: 4,
                    borderRadius: 10,
                    border: "1px solid var(--color-hairline)",
                    background: "var(--color-paper)",
                    zIndex: 10,
                    maxHeight: 180,
                    overflowY: "auto",
                  }}
                >
                  {userResults.map((u) => (
                    <button
                      key={u.username}
                      type="button"
                      onClick={() => setRecipient(u.username)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        width: "100%",
                        padding: "8px 12px",
                        textAlign: "left",
                        fontFamily: "var(--font-sans)",
                        fontSize: 13,
                        color: "var(--color-ink-soft)",
                        borderBottom: "1px solid var(--color-hairline)",
                      }}
                    >
                      <span style={{ fontWeight: 600 }}>{u.username}</span>
                      {u.subtitle ? (
                        <span style={{ color: "var(--color-ink-faint)" }}>
                          · {u.subtitle}
                        </span>
                      ) : null}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
            <Textarea
              placeholder="scrie mesajul…"
              value={messageContent}
              onChange={(e) => setMessageContent(e.target.value)}
              maxLength={MAX_MESSAGE_LENGTH}
              rows={4}
            />
            <p
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                letterSpacing: "0.14em",
                textAlign: "right",
                color: "var(--color-ink-faint)",
              }}
            >
              {messageContent.length}/{MAX_MESSAGE_LENGTH}
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNewMessage(false)}>
              anulează
            </Button>
            <Button
              onClick={() => sendMutation.mutate()}
              disabled={!recipient || !messageContent || sendMutation.isPending}
            >
              trimite
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
