import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addPostToCollection,
  createCollection,
  fetchMyCollections,
  type CollectionSummary,
} from "@/api/collections";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast-context";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  post: { id: number; title: string; user_id: number } | null;
  currentUserId: number | null;
  /** Filter the user's collections before listing — e.g. exclude ones that already contain the post. */
  excludeCollectionIds?: number[];
}

export function AddToCollectionDialog({
  open,
  onOpenChange,
  post,
  currentUserId,
  excludeCollectionIds,
}: Props) {
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");

  const myCollectionsQuery = useQuery({
    queryKey: ["collections", "mine"],
    queryFn: fetchMyCollections,
    enabled: open && !!currentUserId,
  });

  const collections: CollectionSummary[] = useMemo(() => {
    const all = myCollectionsQuery.data?.collections ?? [];
    if (!excludeCollectionIds || excludeCollectionIds.length === 0) return all;
    const excluded = new Set(excludeCollectionIds);
    return all.filter((c) => !excluded.has(c.id));
  }, [myCollectionsQuery.data, excludeCollectionIds]);

  const isAuthor = !!post && !!currentUserId && post.user_id === currentUserId;

  const createMutation = useMutation({
    mutationFn: () =>
      createCollection({ title: newTitle.trim(), description: newDescription.trim() || null }),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["collections", "mine"] });
      setSelected(created.id);
      setShowCreate(false);
      setNewTitle("");
      setNewDescription("");
      showToast("Colecție creată.", "success");
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  const addMutation = useMutation({
    mutationFn: () => {
      if (!post || selected == null) throw new Error("Alege o colecție.");
      return addPostToCollection(selected, post.id);
    },
    onSuccess: (entry) => {
      queryClient.invalidateQueries({ queryKey: ["collections", "mine"] });
      queryClient.invalidateQueries({ queryKey: ["collections", "pending"] });
      if (post) {
        queryClient.invalidateQueries({ queryKey: ["post", post.id, "collections"] });
      }
      const message =
        entry.status === "accepted"
          ? "Postarea a fost adăugată în colecție."
          : isAuthor
            ? "Propunerea a fost trimisă proprietarului colecției."
            : "Invitația a fost trimisă autorului.";
      showToast(message, "success");
      onOpenChange(false);
      setSelected(null);
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  const actionLabel = isAuthor ? "Sugerează" : "Adaugă";
  const titleLabel = isAuthor ? "Sugerează într-o colecție" : "Adaugă la o colecție";
  const description = isAuthor
    ? "Alege una dintre colecțiile tale. Dacă proprietarul e alt utilizator, va primi o propunere de aprobat."
    : "Alege una dintre colecțiile tale. Dacă postarea e a altui autor, va primi o invitație de aprobat.";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[520px]">
        <DialogHeader>
          <DialogTitle>{titleLabel}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        {myCollectionsQuery.isLoading ? (
          <p className="text-sm text-[color:var(--color-ink-mute)]">Se încarcă…</p>
        ) : collections.length === 0 && !showCreate ? (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-[color:var(--color-ink-mute)]">
              Nu ai nicio colecție încă. Creează una mai jos.
            </p>
            <Button type="button" variant="default" onClick={() => setShowCreate(true)}>
              Creează colecție
            </Button>
          </div>
        ) : (
          <>
            {collections.length > 0 ? (
              <ul className="flex flex-col gap-2 max-h-[280px] overflow-y-auto">
                {collections.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => setSelected(c.id)}
                      className={`w-full text-left rounded-[8px] border px-3 py-2 transition-colors ${
                        selected === c.id
                          ? "border-[color:var(--color-ink)] bg-black/[0.04]"
                          : "border-[color:var(--color-hairline)] hover:border-[color:var(--color-ink-mute)]"
                      }`}
                    >
                      <div
                        style={{
                          fontFamily: "var(--font-serif)",
                          fontSize: 16,
                          color: "var(--color-ink)",
                        }}
                      >
                        {c.title}
                      </div>
                      <div
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 10,
                          letterSpacing: "0.18em",
                          textTransform: "uppercase",
                          color: "var(--color-ink-faint)",
                          marginTop: 4,
                        }}
                      >
                        {c.post_count} {c.post_count === 1 ? "piesă" : "piese"}
                        {c.pending_count > 0 ? ` · ${c.pending_count} în așteptare` : ""}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}

            {showCreate ? (
              <div className="flex flex-col gap-2 pt-3 border-t border-[color:var(--color-hairline)]">
                <Input
                  placeholder="Titlul colecției"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  maxLength={120}
                />
                <Textarea
                  placeholder="Descriere (opțional)"
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  rows={2}
                  maxLength={2000}
                />
                <div className="flex gap-2">
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => createMutation.mutate()}
                    disabled={createMutation.isPending || !newTitle.trim()}
                  >
                    {createMutation.isPending ? "se creează…" : "creează"}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => setShowCreate(false)}
                  >
                    renunță
                  </Button>
                </div>
              </div>
            ) : (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setShowCreate(true)}
              >
                + colecție nouă
              </Button>
            )}
          </>
        )}

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="ghost" size="sm">
              anulează
            </Button>
          </DialogClose>
          <Button
            type="button"
            size="sm"
            disabled={selected == null || addMutation.isPending}
            onClick={() => addMutation.mutate()}
          >
            {addMutation.isPending ? "se trimite…" : actionLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
