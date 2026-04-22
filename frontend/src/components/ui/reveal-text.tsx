import { useMemo } from "react";

type RevealTextProps = {
  text: string;
  keySeed?: string | number;
  baseDelay?: number;
  lineStagger?: number;
};

export function RevealText({
  text,
  keySeed,
  baseDelay = 0.08,
  lineStagger = 0.035,
}: RevealTextProps) {
  const lines = useMemo(() => text.split("\n"), [text]);
  return (
    <div className="reveal-text" key={keySeed}>
      {lines.map((line, i) => {
        if (line.trim() === "") {
          return (
            <div key={i} className="reveal-line reveal-blank">
              &nbsp;
            </div>
          );
        }
        const delay = baseDelay + i * lineStagger;
        return (
          <div
            key={i}
            className="reveal-line"
            style={{ animationDelay: `${delay}s` }}
          >
            {line}
          </div>
        );
      })}
    </div>
  );
}
