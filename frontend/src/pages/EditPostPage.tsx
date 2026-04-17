import { useState } from "react";
import { useParams, Navigate } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Helmet } from "react-helmet-async";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import TipTapLink from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import { Bold, Italic, Underline as UnderlineIcon, Strikethrough, List, ListOrdered, Quote, Code2, Link as LinkIcon, AlignLeft, AlignCenter, AlignRight, Heading1, Heading2, ArrowLeft, Trash2, Loader2 } from "lucide-react";
import { updatePost, deletePost } from "@/api/posts";
import { useAuth } from "@/hooks/useAuth";
import type { CurrentUser } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast-context";
import { PageLoader } from "@/components/layout/LoadingSpinner";
import { getBlogUrl } from "@/lib/utils";
import { api } from "@/api/client";
import type { Post } from "@/api/posts";

export default function EditPostPage() {
  const { postId } = useParams<{ postId: string }>();
  const { user } = useAuth();

  const idIsValid = Boolean(postId) && !Number.isNaN(Number(postId));

  const { data: post, isLoading } = useQuery({
    queryKey: ["post", "edit", postId],
    queryFn: () => api.get<Post>(`/api/posts/${postId}`),
    enabled: idIsValid,
  });

  if (!idIsValid) return <Navigate to={user ? `${getBlogUrl(user.username)}/dashboard` : "/"} replace />;
  if (isLoading || !post || !user) return <PageLoader />;

  return <EditPostForm key={post.id} post={post} user={user} />;
}

function EditPostForm({ post, user }: { post: Post; user: CurrentUser }) {
  const { showToast } = useToast();
  const [title, setTitle] = useState(post.title);
  const [showDelete, setShowDelete] = useState(false);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      TipTapLink.configure({ openOnClick: false }),
      Placeholder.configure({ placeholder: "Editeaza postarea..." }),
    ],
    content: post.content,
  });

  const updateMutation = useMutation({
    mutationFn: () => updatePost(post.id, {
      title: title.trim(),
      content: editor?.getHTML() ?? "",
    }),
    onSuccess: (updated) => {
      showToast("Postare actualizata!", "success");
      window.location.href = `${getBlogUrl(user.username)}/${updated.slug}`;
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deletePost(post.id),
    onSuccess: () => {
      showToast("Postare stearsa!", "success");
      window.location.href = `${getBlogUrl(user.username)}/dashboard`;
    },
  });

  return (
    <>
      <Helmet>
        <title>Editeaza: {post.title} | Calimara</title>
      </Helmet>

      <div className="mx-auto max-w-4xl px-4 py-8">
        <a href={`${getBlogUrl(user.username)}/dashboard`} className="inline-flex items-center gap-1 text-sm text-muted hover:text-primary mb-6 no-underline">
          <ArrowLeft className="h-4 w-4" /> Inapoi la panou
        </a>

        <div className="flex items-center justify-between mb-6">
          <h1 className="font-display text-2xl font-medium text-primary">Editeaza postarea</h1>
          <Button variant="danger" size="sm" onClick={() => setShowDelete(true)}>
            <Trash2 className="h-4 w-4" /> Sterge
          </Button>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); if (!updateMutation.isPending) updateMutation.mutate(); }} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-primary mb-1">Titlu</label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} required />
          </div>

          <div>
            <label className="block text-sm font-medium text-primary mb-1">Continut</label>
            <Card>
              <div className="flex flex-wrap gap-1 border-b border-border p-2">
                <ToolbarBtn onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()} active={editor?.isActive("heading", { level: 1 })}><Heading1 className="h-4 w-4" /></ToolbarBtn>
                <ToolbarBtn onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()} active={editor?.isActive("heading", { level: 2 })}><Heading2 className="h-4 w-4" /></ToolbarBtn>
                <span className="mx-1 w-px bg-border" />
                <ToolbarBtn onClick={() => editor?.chain().focus().toggleBold().run()} active={editor?.isActive("bold")}><Bold className="h-4 w-4" /></ToolbarBtn>
                <ToolbarBtn onClick={() => editor?.chain().focus().toggleItalic().run()} active={editor?.isActive("italic")}><Italic className="h-4 w-4" /></ToolbarBtn>
                <ToolbarBtn onClick={() => editor?.chain().focus().toggleUnderline().run()} active={editor?.isActive("underline")}><UnderlineIcon className="h-4 w-4" /></ToolbarBtn>
                <ToolbarBtn onClick={() => editor?.chain().focus().toggleStrike().run()} active={editor?.isActive("strike")}><Strikethrough className="h-4 w-4" /></ToolbarBtn>
                <span className="mx-1 w-px bg-border" />
                <ToolbarBtn onClick={() => editor?.chain().focus().toggleBulletList().run()} active={editor?.isActive("bulletList")}><List className="h-4 w-4" /></ToolbarBtn>
                <ToolbarBtn onClick={() => editor?.chain().focus().toggleOrderedList().run()} active={editor?.isActive("orderedList")}><ListOrdered className="h-4 w-4" /></ToolbarBtn>
                <ToolbarBtn onClick={() => editor?.chain().focus().toggleBlockquote().run()} active={editor?.isActive("blockquote")}><Quote className="h-4 w-4" /></ToolbarBtn>
                <ToolbarBtn onClick={() => editor?.chain().focus().toggleCodeBlock().run()} active={editor?.isActive("codeBlock")}><Code2 className="h-4 w-4" /></ToolbarBtn>
                <span className="mx-1 w-px bg-border" />
                <ToolbarBtn onClick={() => editor?.chain().focus().setTextAlign("left").run()} active={editor?.isActive({ textAlign: "left" })}><AlignLeft className="h-4 w-4" /></ToolbarBtn>
                <ToolbarBtn onClick={() => editor?.chain().focus().setTextAlign("center").run()} active={editor?.isActive({ textAlign: "center" })}><AlignCenter className="h-4 w-4" /></ToolbarBtn>
                <ToolbarBtn onClick={() => editor?.chain().focus().setTextAlign("right").run()} active={editor?.isActive({ textAlign: "right" })}><AlignRight className="h-4 w-4" /></ToolbarBtn>
                <span className="mx-1 w-px bg-border" />
                <ToolbarBtn onClick={() => {
                  const url = window.prompt("URL link:");
                  if (url) editor?.chain().focus().setLink({ href: url }).run();
                }} active={editor?.isActive("link")}><LinkIcon className="h-4 w-4" /></ToolbarBtn>
              </div>
              <CardContent className="p-0">
                <EditorContent editor={editor} className="min-h-[300px]" />
              </CardContent>
            </Card>
          </div>

          <div className="flex justify-end">
            <Button type="submit" disabled={updateMutation.isPending} className="min-w-[160px]">
              {updateMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Analiză AI...
                </>
              ) : (
                "Salvează modificările"
              )}
            </Button>
          </div>
        </form>
      </div>

      <Dialog open={showDelete} onOpenChange={setShowDelete}>
        <DialogContent>
          <DialogHeader><DialogTitle>Sterge postarea</DialogTitle></DialogHeader>
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

function ToolbarBtn({ onClick, active, children }: { onClick: () => void; active?: boolean; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} className={`rounded p-1.5 transition-colors cursor-pointer ${active ? "bg-accent/10 text-accent" : "text-muted hover:bg-surface hover:text-primary"}`}>
      {children}
    </button>
  );
}
