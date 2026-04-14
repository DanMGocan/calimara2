import { useState, useCallback } from "react";
import { Helmet } from "react-helmet-async";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import TipTapLink from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import { Bold, Italic, Underline as UnderlineIcon, Strikethrough, List, ListOrdered, Quote, Code2, Link as LinkIcon, AlignLeft, AlignCenter, AlignRight, Heading1, Heading2, Loader2 } from "lucide-react";
import { createPost, type PostCreateData } from "@/api/posts";
import { useAuth } from "@/hooks/useAuth";
import { useAutoSave } from "@/hooks/useAutoSave";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { getCategoryName } from "@/lib/categories";
import { MAX_TAGS, MAX_TAG_LENGTH } from "@/lib/constants";
import { getBlogUrl } from "@/lib/utils";

export default function CreatePostPage() {
  const { user } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [title, setTitle] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      TipTapLink.configure({ openOnClick: false }),
      Placeholder.configure({ placeholder: "Scrie ceva frumos..." }),
    ],
    content: "",
  });

  // Auto-save
  const formData = { title, tags, content: editor?.getHTML() ?? "" };
  const { load, clear } = useAutoSave("calimara_createPost", formData);

  // Restore draft
  const restoreDraft = useCallback(() => {
    const draft = load();
    if (draft) {
      setTitle(draft.title || "");
      setTags(draft.tags || []);
      if (editor && draft.content) editor.commands.setContent(draft.content);
      showToast("Ciornă restaurată!", "info");
    }
  }, [load, editor, showToast]);

  // Submit
  const mutation = useMutation({
    mutationFn: (data: PostCreateData) => createPost(data),
    onSuccess: (post) => {
      clear();
      showToast("Postare publicată!", "success");
      if (user) window.location.href = `${getBlogUrl(user.username)}/${post.slug}`;
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editor) return;
    const content = editor.getHTML();
    if (!title.trim() || !content.trim() || content === "<p></p>") {
      showToast("Titlul și conținutul sunt obligatorii.", "danger");
      return;
    }
    mutation.mutate({
      title: title.trim(),
      content,
      tags: tags.length > 0 ? tags : undefined,
    });
  };

  const addTag = () => {
    const t = tagInput.trim().toLowerCase();
    if (t && tags.length < MAX_TAGS && t.length <= MAX_TAG_LENGTH && !tags.includes(t)) {
      setTags([...tags, t]);
      setTagInput("");
    }
  };

  return (
    <>
      <Helmet>
        <title>Postare nouă | Calimara</title>
      </Helmet>

      <div className="mx-auto max-w-4xl px-4 py-8">
        <h1 className="font-display text-2xl font-medium text-primary mb-6">Postare nouă</h1>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-primary mb-1">Titlu</label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Titlul postării"
              maxLength={200}
              required
            />
            <p className="mt-1 text-xs text-muted text-right">{title.length}/200</p>
          </div>

          {/* Tags */}
          <div>
            <label className="block text-sm font-medium text-primary mb-1">Etichete ({tags.length}/{MAX_TAGS})</label>
            <div className="flex flex-wrap gap-2 mb-2">
              {tags.map((tag) => (
                <span key={tag} className="inline-flex items-center gap-1 rounded-full bg-accent/10 px-2.5 py-0.5 text-xs text-accent">
                  {tag}
                  <button type="button" onClick={() => setTags(tags.filter((t) => t !== tag))} className="hover:text-danger cursor-pointer">&times;</button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <Input
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); addTag(); } }}
                placeholder="Adaugă o etichetă..."
                maxLength={MAX_TAG_LENGTH}
                disabled={tags.length >= MAX_TAGS}
              />
              <Button type="button" variant="outline" onClick={addTag} disabled={tags.length >= MAX_TAGS}>+</Button>
            </div>
          </div>

          {/* Editor */}
          <div>
            <label className="block text-sm font-medium text-primary mb-1">Conținut</label>
            <Card>
              {/* Toolbar */}
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

          <div className="flex items-center justify-between">
            <Button type="button" variant="ghost" onClick={restoreDraft}>Restaurează ciorna</Button>
            <Button type="submit" disabled={mutation.isPending} className="min-w-[140px]">
              {mutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Analiză AI...
                </>
              ) : (
                "Publică"
              )}
            </Button>
          </div>
        </form>
      </div>
    </>
  );
}

function ToolbarBtn({ onClick, active, children }: { onClick: () => void; active?: boolean; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded p-1.5 transition-colors cursor-pointer ${active ? "bg-accent/10 text-accent" : "text-muted hover:bg-surface hover:text-primary"}`}
    >
      {children}
    </button>
  );
}
