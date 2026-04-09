import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { Search, Send, Plus } from "lucide-react";
import { fetchConversations, sendNewMessage, searchConversations } from "@/api/messages";
import { searchUsers } from "@/api/users";
import { useAuth } from "@/hooks/useAuth";
import { useSubdomain } from "@/hooks/useSubdomain";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { getAvatarUrl, formatRelativeTime, getBlogUrl } from "@/lib/utils";
import { MAX_MESSAGE_LENGTH } from "@/lib/constants";

export default function MessagesPage() {
  const { user } = useAuth();
  const { username } = useSubdomain();
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  const [searchQuery, setSearchQuery] = useState("");
  const [showNewMessage, setShowNewMessage] = useState(false);
  const [recipient, setRecipient] = useState("");
  const [messageContent, setMessageContent] = useState("");
  const [userResults, setUserResults] = useState<{ username: string; subtitle: string | null }[]>([]);

  const { data: conversations, isLoading } = useQuery({
    queryKey: ["conversations"],
    queryFn: fetchConversations,
  });

  const { data: searchResults } = useQuery({
    queryKey: ["conversations", "search", searchQuery],
    queryFn: () => searchConversations(searchQuery),
    enabled: searchQuery.length >= 2,
  });

  const sendMutation = useMutation({
    mutationFn: () => sendNewMessage(recipient, messageContent),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      setShowNewMessage(false);
      setRecipient("");
      setMessageContent("");
      showToast("Mesaj trimis!", "success");
      window.location.href = `${getBlogUrl(user!.username)}/messages/${res.conversation_id}`;
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  const handleUserSearch = async (q: string) => {
    setRecipient(q);
    if (q.length >= 2) {
      const results = await searchUsers(q);
      setUserResults(results);
    } else {
      setUserResults([]);
    }
  };

  if (isLoading) return <PageLoader />;

  const displayConversations = searchQuery.length >= 2 ? searchResults : conversations;

  return (
    <>
      <Helmet>
        <title>Mesaje | Calimara</title>
      </Helmet>

      <div className="mx-auto max-w-3xl px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="font-display text-2xl font-bold text-primary">Mesaje</h1>
          <Button onClick={() => setShowNewMessage(true)}>
            <Plus className="h-4 w-4" /> Mesaj nou
          </Button>
        </div>

        {/* Search */}
        <div className="relative mb-6">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input
            className="pl-9"
            placeholder="Cauta conversatii..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        {/* Conversation List */}
        <div className="space-y-2">
          {displayConversations?.map((conv) => (
            <a
              key={conv.id}
              href={`${getBlogUrl(user!.username)}/messages/${conv.id}`}
              className="flex items-center gap-3 rounded-xl border border-border bg-surface-raised p-4 transition-all hover:shadow-sm hover:border-accent/20 no-underline"
            >
              <img
                src={getAvatarUrl(conv.other_user.avatar_seed, 48)}
                alt={conv.other_user.username}
                className="h-12 w-12 rounded-full shrink-0"
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-primary">{conv.other_user.username}</span>
                  {conv.latest_message && (
                    <span className="text-xs text-muted">{formatRelativeTime(conv.latest_message.created_at)}</span>
                  )}
                </div>
                {conv.latest_message && (
                  <p className="text-sm text-muted line-clamp-1 mt-0.5">{conv.latest_message.content}</p>
                )}
              </div>
              {conv.unread_count > 0 && (
                <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-accent px-1.5 text-[10px] font-bold text-white">
                  {conv.unread_count}
                </span>
              )}
            </a>
          ))}

          {(!displayConversations || displayConversations.length === 0) && (
            <div className="rounded-xl border border-border bg-surface-raised p-12 text-center">
              <p className="text-muted">Nicio conversatie.</p>
            </div>
          )}
        </div>
      </div>

      {/* New Message Modal */}
      <Dialog open={showNewMessage} onOpenChange={setShowNewMessage}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Mesaj nou</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="relative">
              <Input
                placeholder="Cauta utilizator..."
                value={recipient}
                onChange={(e) => handleUserSearch(e.target.value)}
              />
              {userResults.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 rounded-lg border border-border bg-surface-raised shadow-lg z-10 max-h-40 overflow-y-auto">
                  {userResults.map((u) => (
                    <button
                      key={u.username}
                      className="flex items-center gap-2 w-full px-3 py-2 text-left text-sm hover:bg-surface cursor-pointer"
                      onClick={() => { setRecipient(u.username); setUserResults([]); }}
                    >
                      <span className="font-medium">{u.username}</span>
                      {u.subtitle && <span className="text-xs text-muted">{u.subtitle}</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div>
              <Textarea
                placeholder="Scrie mesajul..."
                value={messageContent}
                onChange={(e) => setMessageContent(e.target.value)}
                maxLength={MAX_MESSAGE_LENGTH}
                rows={4}
              />
              <p className="mt-1 text-xs text-muted text-right">{messageContent.length}/{MAX_MESSAGE_LENGTH}</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNewMessage(false)}>Anuleaza</Button>
            <Button onClick={() => sendMutation.mutate()} disabled={!recipient || !messageContent || sendMutation.isPending}>
              <Send className="h-4 w-4" /> Trimite
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
