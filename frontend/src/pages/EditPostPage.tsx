import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import TipTapLink from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import { deletePost, updatePost, type Post } from "@/api/posts";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast-context";
import { EditorToolbar } from "@/components/ui/editor-toolbar";
import { Stage } from "@/components/ui/stage";
import { PageLoader } from "@/components/layout/LoadingSpinner";

export default function EditPostPage() {
  const { postId } = useParams<{ postId: string }>();
  const idIsValid = Boolean(postId) && !Number.isNaN(Number(postId));

  const { data: post, isLoading } = useQuery({
    queryKey: ["post", "edit", postId],
    queryFn: () => api.get<Post>(`/api/posts/${postId}`),
    enabled: idIsValid,
  });

  if (!idIsValid) return <Navigate to="/dashboard" replace />;
  if (isLoading || !post) return <PageLoader />;

  return <EditForm key={post.id} post={post} />;
}

function EditForm({ post }: { post: Post }) {
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [title, setTitle] = useState(post.title);
  const [showDelete, setShowDelete] = useState(false);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      TipTapLink.configure({ openOnClick: false }),
      Placeholder.configure({ placeholder: "editează textul…" }),
    ],
    content: post.content,
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      updatePost(post.id, {
        title: title.trim(),
        content: editor?.getHTML() ?? "",
      }),
    onSuccess: (updated) => {
      showToast("Text actualizat.", "success");
      navigate(`/${updated.slug}`);
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deletePost(post.id),
    onSuccess: () => {
      showToast("Text șters.", "success");
      navigate("/dashboard");
    },
  });

  return (
    <>
      <Helmet>
        <title>Editează: {post.title} | călimara.ro</title>
      </Helmet>

      <Stage variant="single">
        <div style={{ maxWidth: 780, width: "100%", margin: "0 auto" }}>
          <Link
            to="/dashboard"
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 10,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "var(--color-ink-faint)",
              textDecoration: "none",
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              marginBottom: 16,
            }}
          >
            ← înapoi la panou
          </Link>

          <div className="piece-kind-row">
            <span className="piece-kind-badge">editare</span>
            <span className="piece-kind-sep" />
            <span className="piece-kind-meta">{post.category_name ?? post.category}</span>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!updateMutation.isPending) updateMutation.mutate();
            }}
            className="flex flex-col gap-6"
          >
            <div>
              <label className="auth-field">Titlu</label>
              <input
                className="cal-input"
                style={{
                  height: 56,
                  fontFamily: "var(--font-serif)",
                  fontSize: 28,
                  fontWeight: 500,
                  letterSpacing: "-0.02em",
                  border: "1px solid var(--color-hairline)",
                }}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={200}
                required
              />
            </div>

            <div>
              <label className="auth-field">Conținut</label>
              <div
                style={{
                  border: "1px solid var(--color-hairline)",
                  borderRadius: 10,
                  background: "rgba(255,255,255,0.6)",
                }}
              >
                <EditorToolbar editor={editor} />
                <EditorContent editor={editor} className="min-h-[320px]" />
              </div>
            </div>

            <div className="flex items-center justify-between">
              <Button
                type="button"
                variant="danger"
                onClick={() => setShowDelete(true)}
              >
                șterge textul
              </Button>
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? "analiză în curs…" : "salvează"}
              </Button>
            </div>
          </form>
        </div>
      </Stage>

      <Dialog open={showDelete} onOpenChange={setShowDelete}>
        <DialogContent>
          <DialogHeader>
            <div className="auth-kicker">confirmare</div>
            <DialogTitle>Șterge textul</DialogTitle>
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
