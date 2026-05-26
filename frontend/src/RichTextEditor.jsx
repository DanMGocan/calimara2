import { useEffect, useRef, useState } from "react";
import Quill from "quill";
import { FiRefreshCcw } from "react-icons/fi";
import "quill/dist/quill.snow.css";
import { avatarPreviewUrl } from "./app/paths.js";

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
const MENTION_CONTEXT_RE = /(^|[\s([{])@([A-Za-z0-9]{0,40})$/;
const MENTION_MIN_QUERY_LENGTH = 3;
const INVISIBLE_TEXT_RE = /[\u200B-\u200D\uFEFF]/g;
const SOFT_HYPHEN_RE = /\u00ad/g;
const SAFE_FORMAT_RE = /<(strong|em|b|i|u|blockquote|ol|ul|li)\b/i;
const CLEAN_BLOCK_RE = /<(p|blockquote|ol|ul|li)\b/i;
const SAFE_BLOCK_TAGS = new Set(["p", "blockquote", "ol", "ul", "li"]);
const SAFE_INLINE_TAGS = new Set(["strong", "em", "b", "i", "u", "br"]);
const BLOCKISH_TAGS = new Set([
  "address", "article", "aside", "blockquote", "div", "figcaption", "figure", "footer", "h1", "h2", "h3",
  "h4", "h5", "h6", "header", "main", "p", "pre", "section"
]);

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function plainTextToSoftBreakHtml(value) {
  const normalized = normalizePastedText(value);
  if (!normalized) return "";

  return normalized
    .split(/\n{2,}/)
    .map((block) => {
      const lines = block.split("\n").map((line) => escapeHtml(line));
      return `<p>${lines.join("<br>")}</p>`;
    })
    .join("");
}

function normalizePastedText(value) {
  return String(value || "")
    .replace(/\r\n?/g, "\n")
    .replace(/\u00a0/g, " ")
    .replace(INVISIBLE_TEXT_RE, "")
    .replace(SOFT_HYPHEN_RE, "")
    .replace(/[ \t\f\v]+/g, " ")
    .replace(/[ \t]*\n[ \t]*/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function normalizePastedTextFragment(value) {
  return String(value || "")
    .replace(/\r\n?/g, "\n")
    .replace(/\u00a0/g, " ")
    .replace(INVISIBLE_TEXT_RE, "")
    .replace(SOFT_HYPHEN_RE, "")
    .replace(/[ \t\f\v]+/g, " ")
    .replace(/[ \t]*\n[ \t]*/g, "\n");
}

function blockLines(value) {
  return normalizePastedText(value)
    .split(/\n{2,}/)
    .map((block) => block.split("\n").map((line) => line.trim()).filter(Boolean))
    .filter((lines) => lines.length);
}

function plainTextToPostHtml(value, category = "poezie") {
  const blocks = blockLines(value);
  if (!blocks.length) return "";

  return blocks.map((lines) => {
    if (category === "proza_scurta") {
      return `<p>${escapeHtml(lines.join(" "))}</p>`;
    }
    return `<p>${lines.map((line) => escapeHtml(line)).join("<br>")}</p>`;
  }).join("");
}

function sanitizePastedHtmlNode(node) {
  if (node.nodeType === Node.TEXT_NODE) {
    return escapeHtml(normalizePastedTextFragment(node.nodeValue));
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return "";

  const tag = node.tagName.toLowerCase();
  if (tag === "script" || tag === "style" || tag === "meta" || tag === "link" || tag === "img") return "";
  if (tag === "br") return "<br>";

  const children = Array.from(node.childNodes).map(sanitizePastedHtmlNode).join("");
  if (!children.trim()) return "";

  if (SAFE_BLOCK_TAGS.has(tag) || SAFE_INLINE_TAGS.has(tag)) {
    return `<${tag}>${children}</${tag}>`;
  }

  if (BLOCKISH_TAGS.has(tag)) {
    return CLEAN_BLOCK_RE.test(children) ? children : `<p>${children}</p>`;
  }

  return children;
}

function cleanPastedHtml(html) {
  if (!html || typeof document === "undefined") return "";
  const doc = document.implementation.createHTMLDocument("");
  doc.body.innerHTML = String(html || "")
    .replace(INVISIBLE_TEXT_RE, "")
    .replace(SOFT_HYPHEN_RE, "")
    .replace(/\u00a0/g, " ")
    .replace(/&nbsp;/gi, " ");

  return Array.from(doc.body.childNodes).map(sanitizePastedHtmlNode).join("").trim();
}

function cleanPostEditorContent({ html = "", text = "", category = "poezie" } = {}) {
  const plainText = normalizePastedText(text);
  const cleanedHtml = cleanPastedHtml(html);
  const hasSafeFormatting = SAFE_FORMAT_RE.test(cleanedHtml);

  if (plainText && !hasSafeFormatting) {
    return plainTextToPostHtml(plainText, category);
  }

  if (cleanedHtml) return cleanedHtml;
  return plainTextToPostHtml(plainText, category);
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

function insertHtmlAtSelection(quill, html) {
  const range = quill.getSelection(true) || { index: quill.getLength(), length: 0 };
  const beforeLength = quill.getLength();
  quill.history.cutoff();
  if (range.length) {
    quill.deleteText(range.index, range.length, Quill.sources.USER);
  }
  quill.clipboard.dangerouslyPasteHTML(range.index, html, Quill.sources.USER);
  const insertedLength = Math.max(0, quill.getLength() - beforeLength + range.length);
  quill.history.cutoff();
  quill.setSelection(range.index + insertedLength, 0, Quill.sources.SILENT);
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

function detectMention(quill) {
  const range = quill.getSelection();
  if (!range || range.length) return null;

  const lookBehindLength = Math.min(range.index, 80);
  const beforeCursor = quill.getText(range.index - lookBehindLength, lookBehindLength);
  const match = beforeCursor.match(MENTION_CONTEXT_RE);
  if (!match) return null;

  const query = match[2] || "";
  const start = range.index - query.length - 1;
  const bounds = quill.getBounds(range.index);
  const editorWidth = quill.root?.getBoundingClientRect?.().width || window.innerWidth || 360;
  const menuWidth = Math.min(280, Math.max(180, editorWidth - 16), Math.max(180, (window.innerWidth || 360) - 32));
  const left = Math.max(8, Math.min(bounds.left, Math.max(8, editorWidth - menuWidth - 8)));
  return {
    query,
    start,
    end: range.index,
    position: {
      left,
      top: bounds.top + bounds.height + 8
    }
  };
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
  mentionSearch,
  pasteCleanup = "default",
  cleanupCategory = "poezie",
  showFormatCleanup = false,
  formatCleanupLabel = "Curăță formatarea",
  formatCleanupBusy = false,
  onFormatCleanup,
}) {
  const mountRef = useRef(null);
  const quillRef = useRef(null);
  const valueRef = useRef(value || "");
  const onChangeRef = useRef(onChange);
  const mentionSearchRef = useRef(mentionSearch);
  const disabledRef = useRef(disabled);
  const cleanupCategoryRef = useRef(cleanupCategory);
  const [empty, setEmpty] = useState(!value);
  const [mentionState, setMentionState] = useState({
    open: false,
    query: "",
    trigger: null,
    position: null,
    results: [],
    loading: false,
    activeIndex: 0
  });

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    mentionSearchRef.current = mentionSearch;
  }, [mentionSearch]);

  useEffect(() => {
    disabledRef.current = disabled;
  }, [disabled]);

  useEffect(() => {
    cleanupCategoryRef.current = cleanupCategory;
  }, [cleanupCategory]);

  const closeMentionMenu = () => {
    setMentionState((current) => current.open ? {
      open: false,
      query: "",
      trigger: null,
      position: null,
      results: [],
      loading: false,
      activeIndex: 0
    } : current);
  };

  const syncMentionMenu = (quill) => {
    if (!mentionSearchRef.current || disabledRef.current) {
      closeMentionMenu();
      return;
    }

    const match = detectMention(quill);
    if (!match) {
      closeMentionMenu();
      return;
    }

    setMentionState((current) => {
      const sameTrigger = current.trigger?.start === match.start && current.trigger?.end === match.end;
      const sameQuery = current.query === match.query;
      return {
        open: true,
        query: match.query,
        trigger: { start: match.start, end: match.end },
        position: match.position,
        results: sameTrigger && sameQuery ? current.results : [],
        loading: match.query ? current.loading : false,
        activeIndex: sameTrigger && sameQuery ? current.activeIndex : 0
      };
    });
  };

  useEffect(() => {
    if (!mentionState.open || !mentionSearch || mentionState.query.length < MENTION_MIN_QUERY_LENGTH) {
      if (mentionState.open && mentionState.results.length) {
        setMentionState((current) => ({ ...current, results: [], loading: false, activeIndex: 0 }));
      }
      return undefined;
    }

    let cancelled = false;
    const timer = window.setTimeout(() => {
      setMentionState((current) => current.open ? { ...current, loading: true } : current);
      mentionSearch(mentionState.query)
        .then((users) => {
          if (cancelled) return;
          const results = Array.isArray(users) ? users : [];
          setMentionState((current) => current.open && current.query === mentionState.query
            ? { ...current, results, loading: false, activeIndex: 0 }
            : current
          );
        })
        .catch(() => {
          if (cancelled) return;
          setMentionState((current) => current.open && current.query === mentionState.query
            ? { ...current, results: [], loading: false, activeIndex: 0 }
            : current
          );
        });
    }, 180);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [mentionSearch, mentionState.open, mentionState.query]);

  const insertMention = (user) => {
    const quill = quillRef.current;
    const trigger = mentionState.trigger;
    const username = user?.username;
    if (!quill || !trigger || !username) return;

    quill.focus();
    quill.deleteText(trigger.start, Math.max(0, trigger.end - trigger.start), Quill.sources.USER);
    const text = `@${username} `;
    quill.insertText(trigger.start, text, Quill.sources.USER);
    quill.setSelection(trigger.start + text.length, 0, Quill.sources.SILENT);
    closeMentionMenu();
  };

  const handleMentionKeyDown = (event) => {
    if (!mentionState.open) return;
    if (event.key === "Escape") {
      event.preventDefault();
      closeMentionMenu();
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const count = mentionState.results.length;
      if (!count) return;
      const direction = event.key === "ArrowDown" ? 1 : -1;
      setMentionState((current) => ({
        ...current,
        activeIndex: (current.activeIndex + direction + count) % count
      }));
      return;
    }
    if (event.key === "Enter" || event.key === "Tab") {
      if (!mentionState.results.length) return;
      event.preventDefault();
      insertMention(mentionState.results[mentionState.activeIndex] || mentionState.results[0]);
    }
  };

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
      syncMentionMenu(quill);
    };

    const handleSelectionChange = () => {
      syncMentionMenu(quill);
    };

    const handlePaste = (event) => {
      if (pasteCleanup !== "post" || disabledRef.current) return;
      const clipboard = event.clipboardData;
      if (!clipboard) return;

      const cleaned = cleanPostEditorContent({
        html: clipboard.getData("text/html"),
        text: clipboard.getData("text/plain"),
        category: cleanupCategoryRef.current
      });
      if (!cleaned) return;

      event.preventDefault();
      insertHtmlAtSelection(quill, cleaned);
    };

    quill.on("text-change", handleTextChange);
    quill.on("selection-change", handleSelectionChange);
    quill.root.addEventListener("paste", handlePaste);
    quill.enable(!disabled);

    return () => {
      quill.off("text-change", handleTextChange);
      quill.off("selection-change", handleSelectionChange);
      quill.root.removeEventListener("paste", handlePaste);
      quillRef.current = null;
      mount.innerHTML = "";
    };
  }, [id, maxLength, enterMode, pasteCleanup]);

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
    if (disabled) closeMentionMenu();
  }, [disabled]);

  const cleanCurrentFormatting = () => {
    const quill = quillRef.current;
    if (!quill || disabled) return;

    const cleaned = cleanPostEditorContent({
      html: readEditorHtml(quill),
      text: quill.getText(),
      category: cleanupCategoryRef.current
    });
    if (!cleaned) return;

    writeEditorHtml(quill, cleaned, enterMode);
    const nextValue = readEditorHtml(quill);
    valueRef.current = nextValue;
    setEmpty(!nextValue);
    onChangeRef.current?.(nextValue);
  };

  const handleFormatCleanup = () => {
    if (onFormatCleanup) {
      onFormatCleanup();
      return;
    }
    cleanCurrentFormatting();
  };

  return (
    <div
      className={`rich-text-editor ${className}`.trim()}
      data-empty={empty ? "true" : "false"}
      data-disabled={disabled ? "true" : "false"}
      onKeyDown={handleMentionKeyDown}
    >
      <div ref={mountRef} />
      {showFormatCleanup ? (
        <div className="rich-text-editor-actions">
          <button className="cal-btn subtle icon-text" type="button" onClick={handleFormatCleanup} disabled={disabled || formatCleanupBusy}>
            <FiRefreshCcw aria-hidden="true" />
            {formatCleanupBusy ? "Se curăță cu AI..." : formatCleanupLabel}
          </button>
        </div>
      ) : null}
      {mentionState.open && mentionSearch ? (
        <div
          className="mention-menu"
          style={mentionState.position ? { left: mentionState.position.left, top: mentionState.position.top } : undefined}
          onMouseDown={(event) => event.preventDefault()}
        >
          {mentionState.query.length < MENTION_MIN_QUERY_LENGTH ? (
            <div className="mention-menu-empty">Scrie cel puțin 3 litere</div>
          ) : mentionState.loading ? (
            <div className="mention-menu-empty">Se caută...</div>
          ) : mentionState.results.length ? (
            mentionState.results.map((user, index) => (
              <button
                key={user.id ?? user.username}
                className={`mention-option ${index === mentionState.activeIndex ? "active" : ""}`}
                type="button"
                onMouseEnter={() => setMentionState((current) => ({ ...current, activeIndex: index }))}
                onClick={() => insertMention(user)}
              >
                <img className="mention-avatar" src={avatarPreviewUrl(user.avatar_seed || `${user.username}-shapes`, 32)} alt="" />
                <span className="mention-name">@{user.username}</span>
              </button>
            ))
          ) : (
            <div className="mention-menu-empty">Niciun utilizator</div>
          )}
        </div>
      ) : null}
    </div>
  );
}
