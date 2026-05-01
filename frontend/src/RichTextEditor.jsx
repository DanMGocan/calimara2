import { useEffect, useRef, useState } from "react";
import Quill from "quill";
import "quill/dist/quill.snow.css";

const TOOLBAR_OPTIONS = [
  ["bold", "italic", "underline"],
  ["blockquote"],
  [{ list: "ordered" }, { list: "bullet" }],
  ["clean"]
];

const FORMATS = ["bold", "italic", "underline", "blockquote", "list"];
const HTML_RE = /<[a-zA-Z][^>]*>/;

function normalizeHtml(html, plainText) {
  if (!plainText) return "";
  return (html || "").trim();
}

function readEditorHtml(quill) {
  const plainText = quill.getText().replace(/\u00a0/g, " ").trim();
  const html = typeof quill.getSemanticHTML === "function"
    ? quill.getSemanticHTML()
    : quill.root.innerHTML;
  return normalizeHtml(html, plainText);
}

function writeEditorHtml(quill, value) {
  const nextValue = (value || "").trim();
  if (!nextValue) {
    quill.setText("", "silent");
    return;
  }

  if (HTML_RE.test(nextValue)) {
    quill.clipboard.dangerouslyPasteHTML(nextValue, "silent");
  } else {
    quill.setText(nextValue, "silent");
  }
}

export function RichTextEditor({
  id,
  value,
  onChange,
  className = "",
  disabled = false,
  maxLength,
}) {
  const mountRef = useRef(null);
  const quillRef = useRef(null);
  const valueRef = useRef(value || "");
  const onChangeRef = useRef(onChange);
  const [empty, setEmpty] = useState(!value);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;

    const editorNode = document.createElement("div");
    mount.innerHTML = "";
    mount.appendChild(editorNode);

    const quill = new Quill(editorNode, {
      theme: "snow",
      formats: FORMATS,
      modules: {
        toolbar: TOOLBAR_OPTIONS
      }
    });
    quillRef.current = quill;
    quill.root.id = id;
    quill.root.setAttribute("aria-multiline", "true");
    writeEditorHtml(quill, valueRef.current);
    setEmpty(!readEditorHtml(quill));

    const handleTextChange = () => {
      if (maxLength && quill.getLength() > maxLength + 1) {
        const selection = quill.getSelection();
        quill.deleteText(maxLength, quill.getLength(), "silent");
        if (selection) {
          quill.setSelection(Math.min(selection.index, maxLength), 0, "silent");
        }
      }
      const nextValue = readEditorHtml(quill);
      valueRef.current = nextValue;
      setEmpty(!nextValue);
      onChangeRef.current?.(nextValue);
    };

    quill.on("text-change", handleTextChange);
    quill.enable(!disabled);

    return () => {
      quill.off("text-change", handleTextChange);
      quillRef.current = null;
      mount.innerHTML = "";
    };
  }, [id, maxLength]);

  useEffect(() => {
    const quill = quillRef.current;
    const nextValue = value || "";
    valueRef.current = nextValue;
    if (!quill) {
      setEmpty(!nextValue);
      return;
    }

    const currentValue = readEditorHtml(quill);
    if (currentValue !== nextValue.trim()) {
      const selection = quill.getSelection();
      writeEditorHtml(quill, nextValue);
      if (selection && quill.hasFocus()) {
        quill.setSelection(Math.min(selection.index, quill.getLength() - 1), selection.length, "silent");
      }
    }
    setEmpty(!readEditorHtml(quill));
  }, [value]);

  useEffect(() => {
    quillRef.current?.enable(!disabled);
  }, [disabled]);

  return (
    <div
      className={`rich-text-editor ${className}`.trim()}
      data-empty={empty ? "true" : "false"}
      data-disabled={disabled ? "true" : "false"}
    >
      <div ref={mountRef} />
    </div>
  );
}
