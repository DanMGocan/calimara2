import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { useMutation } from "@tanstack/react-query";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import TipTapLink from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import { createPost, type PostCreateData } from "@/api/posts";
import { useAutoSave } from "@/hooks/useAutoSave";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast-context";
import { EditorToolbar } from "@/components/ui/editor-toolbar";
import { Stage } from "@/components/ui/stage";
import { MAX_TAGS, MAX_TAG_LENGTH } from "@/lib/constants";

export default function CreatePostPage() {
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
      Placeholder.configure({ placeholder: "scrie ceva frumos…" }),
    ],
    content: "",
  });

  const formData = { title, tags, content: editor?.getHTML() ?? "" };
  const { load, clear } = useAutoSave("calimara_createPost", formData);

  const restoreDraft = useCallback(() => {
    const draft = load();
    if (draft) {
      setTitle(draft.title || "");
      setTags(draft.tags || []);
      if (editor && draft.content) editor.commands.setContent(draft.content);
      showToast("Ciornă restaurată.", "info");
    }
  }, [load, editor, showToast]);

  const mutation = useMutation({
    mutationFn: (data: PostCreateData) => createPost(data),
    onSuccess: (post) => {
      clear();
      showToast("Text publicat.", "success");
      navigate(`/${post.slug}`);
    },
    onError: (err: Error) => showToast(err.message, "danger"),
  });

  const addTag = () => {
    const t = tagInput.trim().toLowerCase();
    if (t && tags.length < MAX_TAGS && t.length <= MAX_TAG_LENGTH && !tags.includes(t)) {
      setTags([...tags, t]);
      setTagInput("");
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (mutation.isPending || !editor) return;
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

  return (
    <>
      <Helmet>
        <title>Text nou | călimara.ro</title>
      </Helmet>

      <Stage variant="single">
        <div style={{ maxWidth: 780, width: "100%", margin: "0 auto" }}>
          <div className="piece-kind-row">
            <span className="piece-kind-badge">text nou</span>
            <span className="piece-kind-sep" />
            <span className="piece-kind-meta">poezie sau proză</span>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-6">
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
                placeholder="titlul textului…"
                maxLength={200}
                required
              />
              <p
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  letterSpacing: "0.16em",
                  textAlign: "right",
                  color: "var(--color-ink-faint)",
                  marginTop: 4,
                }}
              >
                {title.length}/200
              </p>
            </div>

            <div>
              <label className="auth-field">
                Etichete ({tags.length}/{MAX_TAGS})
              </label>
              <div className="flex flex-wrap gap-2 mb-2">
                {tags.map((tag) => (
                  <span
                    key={tag}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "4px 10px",
                      border: "1px solid var(--color-hairline-strong)",
                      borderRadius: 999,
                      background: "var(--color-paper-2)",
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      letterSpacing: "0.06em",
                      color: "var(--color-ink-soft)",
                    }}
                  >
                    {tag}
                    <button
                      type="button"
                      aria-label={`elimină ${tag}`}
                      onClick={() => setTags(tags.filter((t) => t !== tag))}
                      style={{
                        color: "var(--color-ink-faint)",
                        fontSize: 14,
                        lineHeight: 1,
                      }}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <div className="flex gap-2">
                <Input
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      addTag();
                    }
                  }}
                  placeholder="adaugă o etichetă…"
                  maxLength={MAX_TAG_LENGTH}
                  disabled={tags.length >= MAX_TAGS}
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={addTag}
                  disabled={tags.length >= MAX_TAGS}
                >
                  adaugă
                </Button>
              </div>
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
              <Button type="button" variant="ghost" onClick={restoreDraft}>
                restaurează ciorna
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? "analiză în curs…" : "publică"}
              </Button>
            </div>
          </form>
        </div>
      </Stage>
    </>
  );
}
