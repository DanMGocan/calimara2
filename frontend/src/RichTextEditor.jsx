import { useEffect, useRef, useState } from "react";
import Quill from "quill";
import "quill/dist/quill.snow.css";

const SOFT_BREAK_BLOT = "softBreak";
const SOFT_BREAK_CLASS = "cal-soft-break";
const Delta = Quill.import("delta");
const Parchment = Quill.import("parchment");

class SoftBreakBlot extends Parchment.EmbedBlot {
  static value() {
    return true;
  }

  html() {
    return "<br>";
  }
}

SoftBreakBlot.blotName = SOFT_BREAK_BLOT;
SoftBreakBlot.tagName = "BR";
SoftBreakBlot.className = SOFT_BREAK_CLASS;
Quill.register(SoftBreakBlot, true);

const TOOLBAR_OPTIONS = [
  ["bold", "italic", "underline"],
  ["blockquote"],
  [{ list: "ordered" }, { list: "bullet" }],
  ["clean"]
];

const FORMATS = ["bold", "italic", "underline", "blockquote", "list", SOFT_BREAK_BLOT];
const HTML_RE = /<[a-zA-Z][^>]*>/;
const SOFT_BREAK_RE = new RegExp(`<br\\b[^>]*class=["'][^"']*\\b${SOFT_BREAK_CLASS}\\b[^"']*["'][^>]*>`, "gi");

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function plainTextToSoftBreakHtml(value) {
  const normalized = String(value || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
  if (!normalized) return "";

  return normalized
    .split(/\n{2,}/)
    .map((block) => {
      const lines = block.split("\n").map((line) => escapeHtml(line));
      return `<p>${lines.join("<br>")}</p>`;
    })
    .join("");
}

function normalizeSoftBreakHtml(html) {
  return (html || "").replace(SOFT_BREAK_RE, "<br>");
}

function normalizeHtml(html, plainText) {
  if (!plainText) return "";
  return normalizeSoftBreakHtml(html).trim();
}

function readEditorHtml(quill) {
  const plainText = quill.getText().replace(/\u00a0/g, " ").trim();
  const html = typeof quill.getSemanticHTML === "function"
    ? quill.getSemanticHTML()
    : quill.root.innerHTML;
  return normalizeHtml(html, plainText);
}

function writeEditorHtml(quill, value, enterMode = "paragraph") {
  const nextValue = (value || "").trim();
  if (!nextValue) {
    quill.setText("", "silent");
    return;
  }

  if (HTML_RE.test(nextValue)) {
    quill.clipboard.dangerouslyPasteHTML(nextValue, "silent");
  } else if (enterMode === "soft-break") {
    quill.clipboard.dangerouslyPasteHTML(plainTextToSoftBreakHtml(nextValue), "silent");
  } else {
    quill.setText(nextValue, "silent");
  }
}

function isAfterSoftBreak(quill, index) {
  if (index <= 0) return false;
  const [leaf] = quill.getLeaf(index - 1);
  return leaf?.statics?.blotName === SOFT_BREAK_BLOT;
}

function handleSoftBreakEnter(range, context) {
  if (context.format.list || context.format.blockquote) return true;

  let index = range.index;
  this.quill.history.cutoff();

  if (range.length) {
    this.quill.deleteText(index, range.length, Quill.sources.USER);
  }

  if (isAfterSoftBreak(this.quill, index)) {
    this.quill.deleteText(index - 1, 1, Quill.sources.USER);
    index -= 1;
    this.quill.insertText(index, "\n", Quill.sources.USER);
  } else {
    this.quill.insertEmbed(index, SOFT_BREAK_BLOT, true, Quill.sources.USER);
  }

  this.quill.history.cutoff();
  this.quill.setSelection(index + 1, 0, Quill.sources.SILENT);
  this.quill.scrollSelectionIntoView();
  return false;
}

function createSoftBreakMatcher() {
  return new Delta().insert({ [SOFT_BREAK_BLOT]: true });
}

function editorModules(enterMode) {
  const modules = {
    toolbar: TOOLBAR_OPTIONS
  };

  if (enterMode === "soft-break") {
    modules.clipboard = {
      matchers: [["br", createSoftBreakMatcher]]
    };
    modules.keyboard = {
      bindings: {
        "soft break enter": {
          key: "Enter",
          format: { list: false, blockquote: false },
          handler: handleSoftBreakEnter
        }
      }
    };
  }

  return modules;
}

export function RichTextEditor({
  id,
  value,
  onChange,
  className = "",
  disabled = false,
  maxLength,
  enterMode = "paragraph",
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
      modules: editorModules(enterMode)
    });
    quillRef.current = quill;
    quill.root.id = id;
    quill.root.setAttribute("aria-multiline", "true");
    writeEditorHtml(quill, valueRef.current, enterMode);
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
  }, [id, maxLength, enterMode]);

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
      writeEditorHtml(quill, nextValue, enterMode);
      if (selection && quill.hasFocus()) {
        quill.setSelection(Math.min(selection.index, quill.getLength() - 1), selection.length, "silent");
      }
    }
    setEmpty(!readEditorHtml(quill));
  }, [value, enterMode]);

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
