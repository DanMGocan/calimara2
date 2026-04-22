import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createCollection,
  deleteCollection,
  fetchMyCollectionManage,
  fetchMyCollections,
  fetchMyPendingApprovals,
  removeCollectionEntry,
  respondCollectionEntry,
  updateCollection,
  type CollectionSummary,
} from "@/api/collections";
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
import { formatDate, getBlogUrl } from "@/lib/utils";

export function CollectionsSection() {
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  const myQuery = useQuery({
    queryKey: ["collections", "mine"],
    queryFn: fetchMyCollections,
  });
  const pendingQuery = useQuery({
    queryKey: ["collections", "pending"],
    queryFn: fetchMyPendingApprovals,
  });

  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [managedId, setManagedId] = useState<number | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  const [deleteCandidate, setDeleteCandidate] = useState<CollectionSummary | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      createCollection({ title: newTitle.trim(), description: newDescription.trim() || null }),
    onSuccess: () => {
      setNewTitle("");
      setNewDescription("");
      setCreating(false);
      queryClient.invalidateQueries({ queryKey: ["collections", "mine"] });
      showToast("Colecție creată.", "success");
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteCollection(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections", "mine"] });
      setDeleteCandidate(null);
      showToast("Colecția a fost ștearsă.", "success");
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  const respondMutation = useMutation({
    mutationFn: (vars: { collectionId: number; postId: number; action: "accept" | "reject" }) =>
      respondCollectionEntry(vars.collectionId, vars.postId, vars.action),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ["collections", "pending"] });
      queryClient.invalidateQueries({ queryKey: ["collections", "mine"] });
      queryClient.invalidateQueries({ queryKey: ["collections", "manage", vars.collectionId] });
      showToast(vars.action === "accept" ? "Acceptat." : "Refuzat.", "success");
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  const pending = pendingQuery.data?.items ?? [];
  const collections = myQuery.data?.collections ?? [];

  return (
    <div className="flex flex-col gap-8">
      <header className="flex items-baseline justify-between gap-4 flex-wrap">
        <div>
          <div className="piece-kind-row">
            <span className="piece-kind-badge">colecții</span>
            <span className="piece-kind-sep" />
            <span className="piece-kind-meta">
              {collections.length} proprii · {pending.length} în așteptare
            </span>
          </div>
          <h1
            className="piece-title"
            style={{ fontSize: "clamp(32px, 4vw, 52px)", marginTop: 8 }}
          >
            Colecțiile mele
          </h1>
        </div>
        <Button type="button" onClick={() => setCreating(true)}>
          colecție nouă
        </Button>
      </header>

      {pending.length > 0 ? (
        <section>
          <div className="piece-kind-row" style={{ marginBottom: 12 }}>
            <span className="piece-kind-badge">aprobări</span>
            <span className="piece-kind-sep" />
            <span className="piece-kind-meta">{pending.length} în așteptare</span>
          </div>
          <div
            style={{
              border: "1px solid var(--color-hairline)",
              borderRadius: 10,
              background: "rgba(255,255,255,0.6)",
            }}
          >
            {pending.map((item, i) => (
              <div
                key={item.entry.id}
                style={{
                  padding: "14px 16px",
                  borderBottom:
                    i < pending.length - 1 ? "1px solid var(--color-hairline)" : "none",
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 12,
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      letterSpacing: "0.22em",
                      textTransform: "uppercase",
                      color: "var(--color-ink-faint)",
                    }}
                  >
                    {item.direction === "invitation" ? "invitație" : "sugestie"}
                  </div>
                  <div
                    style={{
                      fontFamily: "var(--font-serif)",
                      fontSize: 16,
                      color: "var(--color-ink)",
                      marginTop: 2,
                    }}
                  >
                    <a
                      href={
                        item.post.owner
                          ? `${getBlogUrl(item.post.owner.username)}/${item.post.slug}`
                          : "#"
                      }
                      style={{ textDecoration: "none", color: "inherit" }}
                    >
                      {item.post.title}
                    </a>
                  </div>
                  <div
                    style={{
                      fontFamily: "var(--font-sans)",
                      fontSize: 12,
                      color: "var(--color-ink-mute)",
                      marginTop: 4,
                    }}
                  >
                    {item.direction === "invitation"
                      ? `propusă pentru colecția "${item.collection.title}" (${item.collection.owner?.username})`
                      : `sugerată de ${item.post.owner?.username} pentru colecția ta "${item.collection.title}"`}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={() =>
                      respondMutation.mutate({
                        collectionId: item.entry.collection_id,
                        postId: item.entry.post_id,
                        action: "accept",
                      })
                    }
                    disabled={respondMutation.isPending}
                  >
                    acceptă
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={() =>
                      respondMutation.mutate({
                        collectionId: item.entry.collection_id,
                        postId: item.entry.post_id,
                        action: "reject",
                      })
                    }
                    disabled={respondMutation.isPending}
                  >
                    refuză
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section>
        {collections.length === 0 ? (
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
            Nu ai nicio colecție încă.
          </div>
        ) : (
          <div className="grid gap-3">
            {collections.map((c) => (
              <div
                key={c.id}
                className="rounded-[10px] border border-[color:var(--color-hairline)] p-4"
                style={{ background: "rgba(255,255,255,0.6)" }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    gap: 12,
                    flexWrap: "wrap",
                  }}
                >
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <Link
                      to={`/colectii/${c.slug}`}
                      style={{
                        fontFamily: "var(--font-serif)",
                        fontSize: 20,
                        color: "var(--color-ink)",
                        letterSpacing: "-0.01em",
                        textDecoration: "none",
                      }}
                    >
                      {c.title}
                    </Link>
                    {c.description ? (
                      <p
                        style={{
                          fontFamily: "var(--font-sans)",
                          fontSize: 13,
                          color: "var(--color-ink-mute)",
                          marginTop: 4,
                        }}
                      >
                        {c.description}
                      </p>
                    ) : null}
                    <div
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 10,
                        letterSpacing: "0.22em",
                        textTransform: "uppercase",
                        color: "var(--color-ink-faint)",
                        marginTop: 6,
                      }}
                    >
                      {c.post_count} {c.post_count === 1 ? "piesă" : "piese"} ·{" "}
                      {c.pending_count} în așteptare · creată {formatDate(c.created_at)}
                    </div>
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    <Button size="sm" variant="outline" onClick={() => setManagedId(c.id)}>
                      gestionează
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setEditId(c.id)}>
                      editează
                    </Button>
                    <Button size="sm" variant="danger" onClick={() => setDeleteCandidate(c)}>
                      șterge
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent>
          <DialogHeader>
            <div className="auth-kicker">nouă</div>
            <DialogTitle>Colecție nouă</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <Input
              placeholder="Titlu"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              maxLength={120}
            />
            <Textarea
              placeholder="Descriere (opțional)"
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              rows={3}
              maxLength={2000}
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreating(false)}>
              anulează
            </Button>
            <Button
              onClick={() => createMutation.mutate()}
              disabled={!newTitle.trim() || createMutation.isPending}
            >
              {createMutation.isPending ? "se creează…" : "creează"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteCandidate !== null} onOpenChange={() => setDeleteCandidate(null)}>
        <DialogContent>
          <DialogHeader>
            <div className="auth-kicker">confirmare</div>
            <DialogTitle>Șterge colecția</DialogTitle>
          </DialogHeader>
          <p
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: 14,
              color: "var(--color-ink-mute)",
            }}
          >
            Vei șterge <strong>{deleteCandidate?.title}</strong>. Acțiunea este permanentă,
            postările rămân intacte.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteCandidate(null)}>
              anulează
            </Button>
            <Button
              variant="danger"
              onClick={() => deleteCandidate && deleteMutation.mutate(deleteCandidate.id)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "se șterge…" : "șterge"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {editId !== null ? (
        <EditCollectionDialog collectionId={editId} onClose={() => setEditId(null)} />
      ) : null}

      {managedId !== null ? (
        <ManageCollectionDialog collectionId={managedId} onClose={() => setManagedId(null)} />
      ) : null}
    </div>
  );
}

function EditCollectionDialog({
  collectionId,
  onClose,
}: {
  collectionId: number;
  onClose: () => void;
}) {
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ["collections", "manage", collectionId],
    queryFn: () => fetchMyCollectionManage(collectionId),
  });
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (data && !initialized) {
      setTitle(data.title ?? "");
      setDescription(data.description ?? "");
      setInitialized(true);
    }
  }, [data, initialized]);

  const mutation = useMutation({
    mutationFn: () =>
      updateCollection(collectionId, {
        title: title.trim() || undefined,
        description: description.trim() || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections", "mine"] });
      queryClient.invalidateQueries({ queryKey: ["collections", "manage", collectionId] });
      showToast("Colecție actualizată.", "success");
      onClose();
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  return (
    <Dialog open={true} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <div className="auth-kicker">editează</div>
          <DialogTitle>Editează colecția</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <Input
            placeholder="Titlu"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={120}
          />
          <Textarea
            placeholder="Descriere"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            maxLength={2000}
          />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            anulează
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            {mutation.isPending ? "se salvează…" : "salvează"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ManageCollectionDialog({
  collectionId,
  onClose,
}: {
  collectionId: number;
  onClose: () => void;
}) {
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["collections", "manage", collectionId],
    queryFn: () => fetchMyCollectionManage(collectionId),
  });

  const respondMutation = useMutation({
    mutationFn: (vars: { postId: number; action: "accept" | "reject" }) =>
      respondCollectionEntry(collectionId, vars.postId, vars.action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections", "manage", collectionId] });
      queryClient.invalidateQueries({ queryKey: ["collections", "pending"] });
      queryClient.invalidateQueries({ queryKey: ["collections", "mine"] });
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  const removeMutation = useMutation({
    mutationFn: (postId: number) => removeCollectionEntry(collectionId, postId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections", "manage", collectionId] });
      queryClient.invalidateQueries({ queryKey: ["collections", "mine"] });
      showToast("Postare eliminată.", "success");
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  return (
    <Dialog open={true} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-[640px]">
        <DialogHeader>
          <div className="auth-kicker">gestionare</div>
          <DialogTitle>{data?.title ?? "Colecție"}</DialogTitle>
        </DialogHeader>
        {isLoading || !data ? (
          <p className="text-sm text-[color:var(--color-ink-mute)]">Se încarcă…</p>
        ) : (
          <div className="flex flex-col gap-5 max-h-[60vh] overflow-y-auto">
            <section>
              <div className="piece-kind-row" style={{ marginBottom: 8 }}>
                <span className="piece-kind-badge">incluse</span>
                <span className="piece-kind-sep" />
                <span className="piece-kind-meta">{data.accepted.length}</span>
              </div>
              {data.accepted.length === 0 ? (
                <p
                  style={{
                    fontFamily: "var(--font-sans)",
                    fontSize: 13,
                    color: "var(--color-ink-faint)",
                  }}
                >
                  Colecția este încă goală.
                </p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {data.accepted.map((entry) => (
                    <li
                      key={entry.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "8px 10px",
                        border: "1px solid var(--color-hairline)",
                        borderRadius: 8,
                        gap: 10,
                      }}
                    >
                      <div style={{ minWidth: 0 }}>
                        <div
                          style={{
                            fontFamily: "var(--font-serif)",
                            fontSize: 15,
                            color: "var(--color-ink)",
                          }}
                        >
                          {entry.post?.title}
                        </div>
                        <div
                          style={{
                            fontFamily: "var(--font-sans)",
                            fontSize: 12,
                            color: "var(--color-ink-faint)",
                          }}
                        >
                          {entry.post?.owner?.username}
                          {entry.post?.category ? ` · ${entry.post.category}` : ""}
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="danger"
                        disabled={removeMutation.isPending}
                        onClick={() => entry.post && removeMutation.mutate(entry.post.id)}
                      >
                        scoate
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {data.pending.length > 0 ? (
              <section>
                <div className="piece-kind-row" style={{ marginBottom: 8 }}>
                  <span className="piece-kind-badge">în așteptare</span>
                  <span className="piece-kind-sep" />
                  <span className="piece-kind-meta">{data.pending.length}</span>
                </div>
                <ul className="flex flex-col gap-2">
                  {data.pending.map((entry) => (
                    <li
                      key={entry.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "8px 10px",
                        border: "1px dashed var(--color-hairline-strong)",
                        borderRadius: 8,
                        gap: 10,
                      }}
                    >
                      <div style={{ minWidth: 0 }}>
                        <div
                          style={{
                            fontFamily: "var(--font-serif)",
                            fontSize: 15,
                            color: "var(--color-ink)",
                          }}
                        >
                          {entry.post?.title}
                        </div>
                        <div
                          style={{
                            fontFamily: "var(--font-sans)",
                            fontSize: 12,
                            color: "var(--color-ink-faint)",
                          }}
                        >
                          {entry.post?.owner?.username} · inițiator{" "}
                          {entry.initiator_id === data.owner_id ? "(tu)" : "(autor)"}
                        </div>
                      </div>
                      <div className="flex gap-2">
                        {entry.initiator_id !== data.owner_id && entry.post ? (
                          <Button
                            size="sm"
                            disabled={respondMutation.isPending}
                            onClick={() =>
                              respondMutation.mutate({
                                postId: entry.post!.id,
                                action: "accept",
                              })
                            }
                          >
                            acceptă
                          </Button>
                        ) : null}
                        <Button
                          size="sm"
                          variant="danger"
                          disabled={respondMutation.isPending || removeMutation.isPending}
                          onClick={() => entry.post && removeMutation.mutate(entry.post.id)}
                        >
                          scoate
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            închide
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
