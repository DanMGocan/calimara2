import { Suspense, lazy } from "react";

const RichTextEditorImpl = lazy(() => import("../RichTextEditor.jsx").then((module) => ({ default: module.RichTextEditor })));

export function RichTextEditor(props) {
  return (
    <Suspense fallback={<div className="editor-fallback" aria-hidden="true" />}>
      <RichTextEditorImpl {...props} />
    </Suspense>
  );
}
