import { useEffect, useMemo, useRef, useState } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import CharacterCount from "@tiptap/extension-character-count";
import Underline from "@tiptap/extension-underline";
import { FiBold, FiItalic, FiList, FiRefreshCcw, FiUnderline } from "react-icons/fi";
import { avatarPreviewUrl } from "./app/paths.js";
import { cssZoomOf } from "./app/zoom.js";

const HTML_RE = /<[a-zA-Z][^>]*>/;
const MENTION_CONTEXT_RE = /(^|[\s([{])@([A-Za-z0-9]{0,40})$/;
const MENTION_MIN_QUERY_LENGTH = 3;
const INVISIBLE_TEXT_RE = /[\u200B-\u200D\uFEFF]/g;
const SOFT_HYPHEN_RE = /\u00ad/g;
const SKIPPED_PASTE_TAGS = new Set(["script", "style", "meta", "link", "img", "svg", "iframe"]);
const SAFE_INLINE_MARK_TAGS = new Map([
  ["strong", "strong"],
  ["b", "strong"],
  ["em", "em"],
  ["i", "em"],
  ["u", "u"]
]);
const PASTE_MARK_ORDER = ["strong", "em", "u"];
const BLOCKISH_TAGS = new Set([
  "address", "article", "aside", "blockquote", "div", "figcaption", "figure", "footer", "h1", "h2", "h3",
  "h4", "h5", "h6", "header", "li", "main", "ol", "p", "pre", "section", "ul"
]);

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
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

function plainTextToParagraphHtml(value) {
  const blocks = blockLines(value);
  if (!blocks.length) return "";

  return blocks
    .map((lines) => `<p>${lines.map((line) => escapeHtml(line)).join("<br>")}</p>`)
    .join("");
}

function pasteHtmlNodeToText(node) {
  if (node.nodeType === Node.TEXT_NODE) {
    return normalizePastedTextFragment(node.nodeValue);
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return "";

  const tag = node.tagName.toLowerCase();
  if (SKIPPED_PASTE_TAGS.has(tag)) return "";
  if (tag === "br") return "\n";

  const children = Array.from(node.childNodes).map(pasteHtmlNodeToText).join("");
  if (!children.trim()) return "";

  if (BLOCKISH_TAGS.has(tag)) {
    return `${children}\n\n`;
  }

  return children;
}

function textFromPastedHtml(html) {
  if (!html || typeof document === "undefined") return "";
  const doc = document.implementation.createHTMLDocument("");
  doc.body.innerHTML = String(html || "")
    .replace(INVISIBLE_TEXT_RE, "")
    .replace(SOFT_HYPHEN_RE, "")
    .replace(/\u00a0/g, " ")
    .replace(/&nbsp;/gi, " ");

  return normalizePastedText(Array.from(doc.body.childNodes).map(pasteHtmlNodeToText).join(""));
}

function pushPasteSegment(segments, text, marks) {
  if (!text) return;
  const key = PASTE_MARK_ORDER.filter((mark) => marks.has(mark)).join(",");
  const previous = segments[segments.length - 1];
  if (previous?.key === key) {
    previous.text += text;
    return;
  }
  segments.push({
    key,
    text,
    marks: new Set(marks)
  });
}

function collectPasteSegments(node, activeMarks = new Set(), segments = []) {
  if (node.nodeType === Node.TEXT_NODE) {
    pushPasteSegment(segments, normalizePastedTextFragment(node.nodeValue), activeMarks);
    return segments;
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return segments;

  const tag = node.tagName.toLowerCase();
  if (SKIPPED_PASTE_TAGS.has(tag)) return segments;
  if (tag === "br") {
    pushPasteSegment(segments, "\n", activeMarks);
    return segments;
  }

  const nextMarks = new Set(activeMarks);
  const mark = SAFE_INLINE_MARK_TAGS.get(tag);
  if (mark) nextMarks.add(mark);

  Array.from(node.childNodes).forEach((child) => collectPasteSegments(child, nextMarks, segments));
  if (BLOCKISH_TAGS.has(tag)) {
    pushPasteSegment(segments, "\n\n", activeMarks);
  }
  return segments;
}

function canonicalTextMap(value) {
  const canonical = [];
  const indexMap = [];
  let pendingWhitespace = null;
  const text = String(value || "");

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (/\s/.test(char)) {
      if (canonical.length && pendingWhitespace === null) {
        pendingWhitespace = index;
      }
      continue;
    }
    if (pendingWhitespace !== null) {
      canonical.push(" ");
      indexMap.push(pendingWhitespace);
      pendingWhitespace = null;
    }
    canonical.push(char);
    indexMap.push(index);
  }

  return {
    text: canonical.join(""),
    indexMap
  };
}

function inlineMarkRangesFromHtml(html, plainText) {
  if (!html || !plainText || typeof document === "undefined") return [];
  const doc = document.implementation.createHTMLDocument("");
  doc.body.innerHTML = String(html || "")
    .replace(INVISIBLE_TEXT_RE, "")
    .replace(SOFT_HYPHEN_RE, "")
    .replace(/\u00a0/g, " ")
    .replace(/&nbsp;/gi, " ");

  const reference = canonicalTextMap(plainText);
  if (!reference.text) return [];

  const segments = collectPasteSegments(doc.body);
  const ranges = [];
  let cursor = 0;

  segments.forEach((segment) => {
    const needle = canonicalTextMap(segment.text);
    if (!needle.text) return;

    const found = reference.text.indexOf(needle.text, cursor);
    if (found === -1) return;

    if (segment.marks.size) {
      const start = reference.indexMap[found];
      const end = reference.indexMap[found + needle.text.length - 1] + 1;
      ranges.push({
        start,
        end,
        marks: PASTE_MARK_ORDER.filter((mark) => segment.marks.has(mark))
      });
    }
    cursor = found + needle.text.length;
  });

  return ranges;
}

function activePasteMarksAt(index, ranges) {
  const marks = new Set();
  ranges.forEach((range) => {
    if (index >= range.start && index < range.end) {
      range.marks.forEach((mark) => marks.add(mark));
    }
  });
  return PASTE_MARK_ORDER.filter((mark) => marks.has(mark));
}

function wrapMarkedText(text, marks) {
  return marks.reduceRight((content, mark) => `<${mark}>${content}</${mark}>`, escapeHtml(text));
}

function markedTextSliceToHtml(text, start, end, ranges) {
  let output = "";
  let index = start;

  while (index < end) {
    const marks = activePasteMarksAt(index, ranges);
    const key = marks.join(",");
    let runEnd = index + 1;
    while (runEnd < end && activePasteMarksAt(runEnd, ranges).join(",") === key) {
      runEnd += 1;
    }
    output += wrapMarkedText(text.slice(index, runEnd), marks);
    index = runEnd;
  }

  return output;
}

function trimTextRange(text, start, end) {
  let nextStart = start;
  let nextEnd = end;
  while (nextStart < nextEnd && /\s/.test(text[nextStart])) nextStart += 1;
  while (nextEnd > nextStart && /\s/.test(text[nextEnd - 1])) nextEnd -= 1;
  return { start: nextStart, end: nextEnd };
}

function splitLinesWithOffsets(text, start, end) {
  const lines = [];
  let lineStart = start;

  for (let index = start; index <= end; index += 1) {
    if (index !== end && text[index] !== "\n") continue;
    const range = trimTextRange(text, lineStart, index);
    if (range.end > range.start) {
      lines.push(range);
    }
    lineStart = index + 1;
  }

  return lines;
}

function splitBlocksWithOffsets(text) {
  const blocks = [];
  let index = 0;

  while (index < text.length) {
    while (text[index] === "\n") index += 1;
    const start = index;
    while (index < text.length && !(text[index] === "\n" && text[index + 1] === "\n")) {
      index += 1;
    }
    const range = trimTextRange(text, start, index);
    if (range.end > range.start) {
      blocks.push({
        start: range.start,
        end: range.end,
        lines: splitLinesWithOffsets(text, range.start, range.end)
      });
    }
    while (text[index] === "\n") index += 1;
  }

  return blocks;
}

function canonicalPasteHtmlFromText(text, mode = "prose", markRanges = []) {
  const normalized = normalizePastedText(text);
  if (!normalized) return "";

  const blocks = splitBlocksWithOffsets(normalized);
  if (!blocks.length) return "";

  return blocks.map((block) => {
    if (mode === "poetry") {
      const lines = block.lines.map((line) => markedTextSliceToHtml(normalized, line.start, line.end, markRanges));
      return `<p>${lines.join("<br>")}</p>`;
    }

    const lines = block.lines.map((line) => markedTextSliceToHtml(normalized, line.start, line.end, markRanges));
    return `<p>${lines.join(" ")}</p>`;
  }).join("");
}

function normalizePasteMode(mode) {
  return mode === "poetry" ? "poetry" : "prose";
}

function cleanEditorContent({ html = "", text = "", pasteMode = "prose" } = {}) {
  const normalizedText = normalizePastedText(text) || textFromPastedHtml(html);
  if (!normalizedText) return "";

  const mode = normalizePasteMode(pasteMode);
  const markRanges = inlineMarkRangesFromHtml(html, normalizedText);
  return canonicalPasteHtmlFromText(normalizedText, mode, markRanges);
}

function valueToEditorHtml(value) {
  const nextValue = (value || "").trim();
  if (!nextValue) return "";
  return HTML_RE.test(nextValue) ? nextValue : plainTextToParagraphHtml(nextValue);
}

function readEditorText(editor) {
  if (!editor || editor.isDestroyed || !editor.schema) return "";
  return editor.getText({ blockSeparator: "\n\n" }).replace(/\u00a0/g, " ").trim();
}

function readEditorHtml(editor) {
  if (!editor || editor.isDestroyed || !editor.schema) return "";
  const plainText = readEditorText(editor);
  if (!plainText) return "";
  return editor.getHTML().replace(/\u00a0/g, " ").trim();
}

function detectMention(editor, wrapper) {
  if (!editor || editor.isDestroyed || !editor.schema) return null;
  const { selection, doc } = editor.state;
  if (!selection.empty) return null;

  const end = selection.from;
  const lookBehindStart = Math.max(0, end - 80);
  const beforeCursor = doc.textBetween(lookBehindStart, end, "\n", "\n");
  const match = beforeCursor.match(MENTION_CONTEXT_RE);
  if (!match) return null;

  const query = match[2] || "";
  const start = end - query.length - 1;
  let position = null;

  try {
    const coords = editor.view.coordsAtPos(end);
    const wrapperRect = wrapper?.getBoundingClientRect?.();
    // Rects are in window px; the menu's left/top are in the page's (possibly zoomed) CSS px.
    const zoom = cssZoomOf(wrapper || editor.view.dom);
    const viewportWidth = (window.innerWidth || 360) / zoom;
    const editorWidth = (wrapperRect?.width || window.innerWidth || 360) / zoom;
    const menuWidth = Math.min(280, Math.max(180, editorWidth - 16), Math.max(180, viewportWidth - 32));
    const rawLeft = (wrapperRect ? coords.left - wrapperRect.left : coords.left) / zoom;
    const rawTop = (wrapperRect ? coords.bottom - wrapperRect.top : coords.bottom) / zoom + 8;
    position = {
      left: Math.max(8, Math.min(rawLeft, Math.max(8, editorWidth - menuWidth - 8))),
      top: Math.max(8, rawTop)
    };
  } catch {
    position = null;
  }

  return {
    query,
    start,
    end,
    position
  };
}

function isAfterHardBreak(editor) {
  const { selection } = editor.state;
  if (!selection.empty) return false;
  return selection.$from.nodeBefore?.type?.name === "hardBreak";
}

function ToolbarButton({ active = false, disabled = false, label, onClick, children }) {
  return (
    <button
      className={`rich-text-editor-tool ${active ? "active" : ""}`}
      type="button"
      aria-label={label}
      aria-pressed={active}
      title={label}
      disabled={disabled}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
    >
      {children}
    </button>
  );
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
  pasteMode = "prose",
  showFormatCleanup = false,
  formatCleanupLabel = "Curăță formatarea",
  formatCleanupBusy = false,
  onFormatCleanup,
}) {
  const wrapperRef = useRef(null);
  const editorRef = useRef(null);
  const valueRef = useRef(value || "");
  const onChangeRef = useRef(onChange);
  const mentionSearchRef = useRef(mentionSearch);
  const disabledRef = useRef(disabled);
  const pasteModeRef = useRef(pasteMode);
  const enterModeRef = useRef(enterMode);
  const mentionStateRef = useRef(null);
  const [empty, setEmpty] = useState(!value);
  const [, setEditorVersion] = useState(0);
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
    pasteModeRef.current = pasteMode;
  }, [pasteMode]);

  useEffect(() => {
    enterModeRef.current = enterMode;
  }, [enterMode]);

  useEffect(() => {
    mentionStateRef.current = mentionState;
  }, [mentionState]);

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

  const insertMention = (user, triggerOverride) => {
    const editor = editorRef.current;
    const trigger = triggerOverride || mentionStateRef.current?.trigger;
    const username = user?.username;
    if (!editor || editor.isDestroyed || !trigger || !username) return;

    editor
      .chain()
      .focus()
      .deleteRange({ from: trigger.start, to: trigger.end })
      .insertContent(`@${username} `)
      .run();
    closeMentionMenu();
  };

  const handleMentionNavigation = (event) => {
    const current = mentionStateRef.current;
    if (!current?.open) return false;

    if (event.key === "Escape") {
      event.preventDefault();
      closeMentionMenu();
      return true;
    }

    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const count = current.results.length;
      if (!count) return true;
      const direction = event.key === "ArrowDown" ? 1 : -1;
      setMentionState((state) => ({
        ...state,
        activeIndex: (state.activeIndex + direction + count) % count
      }));
      return true;
    }

    if (event.key === "Enter" || event.key === "Tab") {
      if (!current.results.length) return false;
      event.preventDefault();
      insertMention(current.results[current.activeIndex] || current.results[0], current.trigger);
      return true;
    }

    return false;
  };

  const syncMentionMenu = (editor) => {
    if (!mentionSearchRef.current || disabledRef.current) {
      closeMentionMenu();
      return;
    }

    const match = detectMention(editor, wrapperRef.current);
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

  const extensions = useMemo(() => [
    StarterKit.configure({
      code: false,
      codeBlock: false,
      dropcursor: false,
      gapcursor: false,
      heading: false,
      horizontalRule: false,
      link: false,
      strike: false,
      trailingNode: false,
      underline: false,
      hardBreak: {
        keepMarks: true
      }
    }),
    Underline,
    CharacterCount.configure({
      limit: maxLength || null
    })
  ], [maxLength]);

  const editor = useEditor({
    extensions,
    content: valueToEditorHtml(valueRef.current),
    editable: !disabled,
    immediatelyRender: false,
    editorProps: {
      attributes: {
        id,
        class: "tiptap-editor",
        "aria-multiline": "true",
        role: "textbox"
      },
      handlePaste: (_view, event) => {
        if (disabledRef.current) return false;
        const clipboard = event.clipboardData;
        if (!clipboard) return false;

        const cleaned = cleanEditorContent({
          html: clipboard.getData("text/html"),
          text: clipboard.getData("text/plain"),
          pasteMode: pasteModeRef.current
        });
        if (!cleaned) return false;

        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation?.();
        const currentEditor = editorRef.current;
        if (currentEditor && !currentEditor.isDestroyed) {
          currentEditor.chain().focus().insertContent(cleaned).run();
        }
        return true;
      },
      handleKeyDown: (_view, event) => {
        if (handleMentionNavigation(event)) return true;

        const currentEditor = editorRef.current;
        if (
          !currentEditor
          || currentEditor.isDestroyed
          || disabledRef.current
          || enterModeRef.current !== "soft-break"
          || event.key !== "Enter"
          || event.altKey
          || event.ctrlKey
          || event.metaKey
          || currentEditor.isActive("bulletList")
          || currentEditor.isActive("orderedList")
          || currentEditor.isActive("blockquote")
        ) {
          return false;
        }

        event.preventDefault();
        const { from, empty: selectionEmpty } = currentEditor.state.selection;
        const chain = currentEditor.chain().focus();
        if (!selectionEmpty) {
          chain.deleteSelection();
        }
        if (selectionEmpty && !event.shiftKey && isAfterHardBreak(currentEditor)) {
          chain.deleteRange({ from: Math.max(0, from - 1), to: from }).splitBlock().run();
        } else {
          chain.setHardBreak().run();
        }
        return true;
      }
    },
    onUpdate: ({ editor: currentEditor }) => {
      const nextValue = readEditorHtml(currentEditor);
      valueRef.current = nextValue;
      setEmpty(!nextValue);
      onChangeRef.current?.(nextValue);
      syncMentionMenu(currentEditor);
      setEditorVersion((current) => current + 1);
    },
    onSelectionUpdate: ({ editor: currentEditor }) => {
      syncMentionMenu(currentEditor);
      setEditorVersion((current) => current + 1);
    },
    onBlur: () => {
      closeMentionMenu();
    },
  }, [extensions, id]);

  useEffect(() => {
    editorRef.current = editor;
    if (!editor || editor.isDestroyed) return undefined;
    setEmpty(!readEditorHtml(editor));

    return () => {
      if (editorRef.current === editor) {
        editorRef.current = null;
      }
    };
  }, [editor]);

  useEffect(() => {
    const nextValue = value || "";
    valueRef.current = nextValue;
    if (!editor || editor.isDestroyed) {
      setEmpty(!nextValue);
      return;
    }

    const currentValue = readEditorHtml(editor);
    if (currentValue !== nextValue.trim()) {
      editor.commands.setContent(valueToEditorHtml(nextValue), { emitUpdate: false });
    }
    setEmpty(!readEditorHtml(editor));
  }, [editor, value]);

  useEffect(() => {
    if (editor && !editor.isDestroyed) {
      editor.setEditable(!disabled);
    }
    if (disabled) closeMentionMenu();
  }, [disabled, editor]);

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

  const cleanCurrentFormatting = () => {
    if (!editor || editor.isDestroyed || disabled) return;

    const cleaned = cleanEditorContent({
      html: readEditorHtml(editor),
      text: readEditorText(editor),
      pasteMode: pasteModeRef.current
    });
    if (!cleaned) return;

    editor.commands.setContent(cleaned, { emitUpdate: true });
  };

  const handleFormatCleanup = () => {
    if (onFormatCleanup) {
      onFormatCleanup();
      return;
    }
    cleanCurrentFormatting();
  };

  const runToolbarCommand = (command) => {
    if (!editor || editor.isDestroyed || disabled) return;
    command(editor.chain().focus()).run();
  };

  return (
    <div
      ref={wrapperRef}
      className={`rich-text-editor ${className}`.trim()}
      data-empty={empty ? "true" : "false"}
      data-disabled={disabled ? "true" : "false"}
    >
      <div className="rich-text-editor-toolbar" role="toolbar" aria-label="Formatare text">
        <ToolbarButton
          active={Boolean(editor?.isActive("bold"))}
          disabled={!editor || disabled}
          label="Aldin"
          onClick={() => runToolbarCommand((chain) => chain.toggleBold())}
        >
          <FiBold aria-hidden="true" />
        </ToolbarButton>
        <ToolbarButton
          active={Boolean(editor?.isActive("italic"))}
          disabled={!editor || disabled}
          label="Italic"
          onClick={() => runToolbarCommand((chain) => chain.toggleItalic())}
        >
          <FiItalic aria-hidden="true" />
        </ToolbarButton>
        <ToolbarButton
          active={Boolean(editor?.isActive("underline"))}
          disabled={!editor || disabled}
          label="Subliniat"
          onClick={() => runToolbarCommand((chain) => chain.toggleUnderline())}
        >
          <FiUnderline aria-hidden="true" />
        </ToolbarButton>
        <ToolbarButton
          active={Boolean(editor?.isActive("blockquote"))}
          disabled={!editor || disabled}
          label="Citat"
          onClick={() => runToolbarCommand((chain) => chain.toggleBlockquote())}
        >
          <span aria-hidden="true" className="rich-text-editor-symbol">"</span>
        </ToolbarButton>
        <ToolbarButton
          active={Boolean(editor?.isActive("orderedList"))}
          disabled={!editor || disabled}
          label="Listă numerotată"
          onClick={() => runToolbarCommand((chain) => chain.toggleOrderedList())}
        >
          <span aria-hidden="true" className="rich-text-editor-symbol">1.</span>
        </ToolbarButton>
        <ToolbarButton
          active={Boolean(editor?.isActive("bulletList"))}
          disabled={!editor || disabled}
          label="Listă simplă"
          onClick={() => runToolbarCommand((chain) => chain.toggleBulletList())}
        >
          <FiList aria-hidden="true" />
        </ToolbarButton>
        <ToolbarButton
          disabled={!editor || disabled}
          label="Curăță formatarea"
          onClick={() => runToolbarCommand((chain) => chain.unsetAllMarks().clearNodes())}
        >
          <FiRefreshCcw aria-hidden="true" />
        </ToolbarButton>
      </div>
      <EditorContent editor={editor} />
      {showFormatCleanup ? (
        <div className="rich-text-editor-actions">
          <button className="cal-btn subtle icon-text" type="button" onClick={handleFormatCleanup} disabled={disabled || formatCleanupBusy}>
            <FiRefreshCcw aria-hidden="true" />
            {formatCleanupBusy ? "Se curăță formatarea..." : formatCleanupLabel}
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
