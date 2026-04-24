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
import { useToast } from "@/components/ui/toast-context";
import { EditorToolbar } from "@/components/ui/editor-toolbar";
import { Stage } from "@/components/ui/stage";

export default function CreatePostPage() {
  const { showToast } = useToast();
  const navigate = useNavigate();

  const [title, setTitle] = useState("");
  const [aiCritic, setAiCritic] = useState(false);

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

  const formData = { title, aiCritic, content: editor?.getHTML() ?? "" };
  const { load, clear } = useAutoSave("calimara_createPost", formData);

  const restoreDraft = useCallback(() => {
    const draft = load();
    if (draft) {
      setTitle(draft.title || "");
      setAiCritic(Boolean(draft.aiCritic));
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
      ai_critic: aiCritic,
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

            <label className="ai-critic-toggle">
              <input
                type="checkbox"
                checked={aiCritic}
                onChange={(e) => setAiCritic(e.target.checked)}
              />
              <span>
                <strong>Ce zice robotul?</strong>
                <span className="ai-critic-toggle-hint">
                  primește o opinie scurtă de la AI după publicare
                </span>
              </span>
            </label>

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
