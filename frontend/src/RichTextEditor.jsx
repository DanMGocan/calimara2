import { useEffect, useRef, useState } from "react";
import Quill from "quill";
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
}) {
  const mountRef = useRef(null);
  const quillRef = useRef(null);
  const valueRef = useRef(value || "");
  const onChangeRef = useRef(onChange);
  const mentionSearchRef = useRef(mentionSearch);
  const disabledRef = useRef(disabled);
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

    quill.on("text-change", handleTextChange);
    quill.on("selection-change", handleSelectionChange);
    quill.enable(!disabled);

    return () => {
      quill.off("text-change", handleTextChange);
      quill.off("selection-change", handleSelectionChange);
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
    if (disabled) closeMentionMenu();
  }, [disabled]);

  return (
    <div
      className={`rich-text-editor ${className}`.trim()}
      data-empty={empty ? "true" : "false"}
      data-disabled={disabled ? "true" : "false"}
      onKeyDown={handleMentionKeyDown}
    >
      <div ref={mountRef} />
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
