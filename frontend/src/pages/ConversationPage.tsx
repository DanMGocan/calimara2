import { useState, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { ArrowLeft, Send, Trash2 } from "lucide-react";
import { fetchConversation, sendMessageInConversation, deleteConversation } from "@/api/messages";
import { useAuth } from "@/hooks/useAuth";
import { useSubdomain } from "@/hooks/useSubdomain";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { getAvatarUrl, formatRelativeTime, getBlogUrl } from "@/lib/utils";
import { MAX_MESSAGE_LENGTH } from "@/lib/constants";

export default function ConversationPage() {
  const { conversationId } = useParams<{ conversationId: string }>();
  const { user } = useAuth();
  const { username } = useSubdomain();
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [content, setContent] = useState("");
  const [showDelete, setShowDelete] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => fetchConversation(Number(conversationId)),
    enabled: !!conversationId,
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
  }, [data?.messages]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && e.ctrlKey && content.trim()) {
      e.preventDefault();
      sendMutation.mutate();
    }
  };

  if (isLoading) return <PageLoader />;

  const messages = data?.messages ?? [];

  return (
    <>
      <Helmet>
        <title>Conversatie | Calimara</title>
      </Helmet>

      <div className="mx-auto max-w-3xl px-4 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <a href={`${getBlogUrl(user!.username)}/messages`} className="inline-flex items-center gap-1 text-sm text-muted hover:text-primary no-underline">
            <ArrowLeft className="h-4 w-4" /> Inapoi la mesaje
          </a>
          <Button variant="ghost" size="sm" className="text-danger" onClick={() => setShowDelete(true)}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>

        {/* Messages */}
        <div className="space-y-3 mb-6 min-h-[40vh] max-h-[60vh] overflow-y-auto rounded-xl border border-border bg-surface-raised p-4">
          {messages.map((msg) => {
            const isMine = msg.sender_id === user?.id;
            return (
              <div key={msg.id} className={`flex ${isMine ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${
                  isMine
                    ? "bg-accent text-white rounded-br-md"
                    : "bg-surface border border-border text-primary rounded-bl-md"
                }`}>
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  <p className={`text-[10px] mt-1 ${isMine ? "text-white/60" : "text-muted"}`}>
                    {formatRelativeTime(msg.created_at)}
                  </p>
                </div>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="flex gap-2">
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
