import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import {
  deleteConversation,
  fetchConversation,
  sendMessageInConversation,
} from "@/api/messages";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
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
import { Stage } from "@/components/ui/stage";
import { formatRelativeTime } from "@/lib/utils";
import { MAX_MESSAGE_LENGTH } from "@/lib/constants";

export default function ConversationPage() {
  const { conversationId } = useParams<{ conversationId: string }>();
  const { user } = useAuth();
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const endRef = useRef<HTMLDivElement>(null);

  const [content, setContent] = useState("");
  const [showDelete, setShowDelete] = useState(false);

  const idIsValid =
    Boolean(conversationId) && !Number.isNaN(Number(conversationId));

  const { data, isLoading } = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => fetchConversation(Number(conversationId)),
    enabled: idIsValid,
    refetchInterval: 5000,
  });

  const sendMutation = useMutation({
    mutationFn: () =>
      sendMessageInConversation(Number(conversationId), content),
    onSuccess: () => {
      setContent("");
      queryClient.invalidateQueries({ queryKey: ["conversation", conversationId] });
      queryClient.invalidateQueries({ queryKey: ["messages", "unread"] });
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteConversation(Number(conversationId)),
    onSuccess: () => {
      showToast("Conversație ștearsă.", "success");
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      navigate("/messages");
    },
  });

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [data?.messages?.length]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (
      e.key === "Enter" &&
      e.ctrlKey &&
      content.trim() &&
      !sendMutation.isPending
    ) {
      e.preventDefault();
      sendMutation.mutate();
    }
  };

  if (!idIsValid) return <Navigate to={user ? "/messages" : "/"} replace />;
  if (isLoading) return <PageLoader />;

  const messages = data?.messages ?? [];

  return (
    <>
      <Helmet>
        <title>Conversație | călimara.ro</title>
      </Helmet>

      <Stage variant="single">
        <div style={{ maxWidth: 680, width: "100%", margin: "0 auto" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 24,
            }}
          >
            <Link
              to={user ? "/messages" : "/"}
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: "var(--color-ink-faint)",
                textDecoration: "none",
              }}
            >
              ← înapoi la mesaje
            </Link>
            <Button variant="ghost" size="sm" onClick={() => setShowDelete(true)}>
              șterge conversația
            </Button>
          </div>

          <div className="piece-kind-row">
            <span className="piece-kind-badge">conversație</span>
            <span className="piece-kind-sep" />
            <span className="piece-kind-meta">{messages.length} mesaje</span>
          </div>

          <div
            style={{
              border: "1px solid var(--color-hairline)",
              borderRadius: 10,
              background: "rgba(255,255,255,0.6)",
              padding: 16,
              minHeight: "40vh",
              maxHeight: "60vh",
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
          >
            {messages.map((msg) => {
              const mine = msg.sender_id === user?.id;
              return (
                <div
                  key={msg.id}
                  style={{
                    display: "flex",
                    justifyContent: mine ? "flex-end" : "flex-start",
                  }}
                >
                  <div
                    style={{
                      maxWidth: "75%",
                      padding: "10px 14px",
                      borderRadius: 10,
                      border: "1px solid",
                      borderColor: mine
                        ? "var(--color-ink)"
                        : "var(--color-hairline)",
                      background: mine
                        ? "var(--color-ink)"
                        : "var(--color-paper)",
                      color: mine
                        ? "var(--color-paper)"
                        : "var(--color-ink-soft)",
                    }}
                  >
                    <p
                      style={{
                        fontFamily: "var(--font-serif)",
                        fontSize: 14,
                        lineHeight: 1.5,
                        whiteSpace: "pre-wrap",
                        margin: 0,
                      }}
                    >
                      {msg.content}
                    </p>
                    <p
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 10,
                        letterSpacing: "0.12em",
                        color: mine
                          ? "rgba(255,255,255,0.55)"
                          : "var(--color-ink-faint)",
                        margin: "4px 0 0",
                      }}
                    >
                      {formatRelativeTime(msg.created_at)}
                    </p>
                  </div>
                </div>
              );
            })}
            <div ref={endRef} />
          </div>

          <div
            style={{ marginTop: 16, display: "flex", gap: 8, alignItems: "stretch" }}
          >
            <Textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="scrie un mesaj… (Ctrl+Enter pentru a trimite)"
              maxLength={MAX_MESSAGE_LENGTH}
              rows={2}
              style={{ flex: 1, resize: "none" }}
            />
            <Button
              onClick={() => sendMutation.mutate()}
              disabled={!content.trim() || sendMutation.isPending}
              style={{ alignSelf: "flex-end" }}
            >
              trimite
            </Button>
          </div>
          <p
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              letterSpacing: "0.14em",
              textAlign: "right",
              color: "var(--color-ink-faint)",
              marginTop: 6,
            }}
          >
            {content.length}/{MAX_MESSAGE_LENGTH}
          </p>
        </div>
      </Stage>

      <Dialog open={showDelete} onOpenChange={setShowDelete}>
        <DialogContent>
          <DialogHeader>
            <div className="auth-kicker">confirmare</div>
            <DialogTitle>Șterge conversația</DialogTitle>
          </DialogHeader>
          <p
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: 14,
              color: "var(--color-ink-mute)",
            }}
          >
            Această acțiune este permanentă.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDelete(false)}>
              anulează
            </Button>
            <Button
              variant="danger"
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "se șterge…" : "șterge"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
