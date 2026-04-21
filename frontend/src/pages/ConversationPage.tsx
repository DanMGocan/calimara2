import { useState, useEffect, useRef } from "react";
import { useParams, Navigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { ArrowLeft, Send, Trash2 } from "lucide-react";
import { fetchConversation, sendMessageInConversation, deleteConversation } from "@/api/messages";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast-context";
import { DebugLabel } from "@/components/ui/debug-label";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { formatRelativeTime, getBlogUrl } from "@/lib/utils";
import { MAX_MESSAGE_LENGTH } from "@/lib/constants";

export default function ConversationPage() {
  const { conversationId } = useParams<{ conversationId: string }>();
  const { user } = useAuth();
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [content, setContent] = useState("");
  const [showDelete, setShowDelete] = useState(false);

  const idIsValid = Boolean(conversationId) && !Number.isNaN(Number(conversationId));

  const { data, isLoading } = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => fetchConversation(Number(conversationId)),
    enabled: idIsValid,
    refetchInterval: 5000,
  });

  const sendMutation = useMutation({
    mutationFn: () => sendMessageInConversation(Number(conversationId), content),
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
      showToast("Conversatie stearsa!", "success");
      window.location.href = `${getBlogUrl(user!.username)}/messages`;
    },
  });

  // Auto scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [data?.messages?.length]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && e.ctrlKey && content.trim() && !sendMutation.isPending) {
      e.preventDefault();
      sendMutation.mutate();
    }
  };

  if (!idIsValid) return <Navigate to={user ? `${getBlogUrl(user.username)}/messages` : "/"} replace />;
  if (isLoading) return <PageLoader />;

  const messages = data?.messages ?? [];

  return (
    <>
      <Helmet>
        <title>Conversatie | Calimara</title>
      </Helmet>

      <div className="relative mx-auto max-w-3xl px-4 py-8">
        <DebugLabel name="ConversationPage" />
        {/* Header */}
        <div className="relative flex items-center justify-between mb-6">
          <DebugLabel name="ConversationHeader" />
          <a href={`${getBlogUrl(user!.username)}/messages`} className="inline-flex items-center gap-1 text-sm text-muted hover:text-primary no-underline">
            <ArrowLeft className="h-4 w-4" /> Inapoi la mesaje
          </a>
          <Button variant="ghost" size="sm" className="text-danger" aria-label="Șterge conversația" onClick={() => setShowDelete(true)}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>

        {/* Messages */}
        <Card className="relative space-y-3 mb-6 min-h-[40vh] max-h-[60vh] overflow-y-auto p-4">
          <DebugLabel name="MessagesList" />
          {messages.map((msg) => {
            const isMine = msg.sender_id === user?.id;
            return (
              <div key={msg.id} className={`flex ${isMine ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${
                  isMine
                    ? "bg-primary text-white rounded-br-md"
                    : "bg-surface border border-border text-primary rounded-bl-md"
                }`}>
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  <p className={`text-xs mt-1 ${isMine ? "text-white/60" : "text-muted"}`}>
                    {formatRelativeTime(msg.created_at)}
                  </p>
                </div>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </Card>

        {/* Input */}
        <div className="relative flex gap-2">
          <DebugLabel name="MessageInput" />
          <Textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Scrie un mesaj... (Ctrl+Enter pentru a trimite)"
            maxLength={MAX_MESSAGE_LENGTH}
            rows={2}
            className="flex-1 resize-none"
          />
          <Button
            onClick={() => sendMutation.mutate()}
            disabled={!content.trim() || sendMutation.isPending}
            aria-label="Trimite mesajul"
            className="self-end"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
        <p className="mt-1 text-xs text-muted text-right">{content.length}/{MAX_MESSAGE_LENGTH}</p>
      </div>

      <Dialog open={showDelete} onOpenChange={setShowDelete}>
        <DialogContent>
          <DialogHeader><DialogTitle>Sterge conversatia</DialogTitle></DialogHeader>
          <p className="text-sm text-muted">Aceasta actiune este permanenta.</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDelete(false)}>Anuleaza</Button>
            <Button variant="danger" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>Sterge</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
