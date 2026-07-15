"use client";

import { useEffect, useRef, useState } from "react";

interface TypewriterNarrationProps {
  text: string;
  onComplete: () => void;
}

function delayForCharacter(character: string): number {
  if (/[。！？]/.test(character)) return 150;
  if (/[，；：]/.test(character)) return 72;
  if (/\s/.test(character)) return 24;
  return 15;
}

export function TypewriterNarration({ text, onComplete }: TypewriterNarrationProps) {
  const [visibleLength, setVisibleLength] = useState(0);
  const narrationRef = useRef<HTMLDivElement>(null);
  const complete = visibleLength >= text.length;

  useEffect(() => {
    const viewport = narrationRef.current?.closest(".narration-viewport") as HTMLElement | null;
    if (viewport && viewport.scrollHeight > viewport.clientHeight) {
      viewport.scrollTop = viewport.scrollHeight;
    }
  }, [visibleLength]);

  useEffect(() => {
    if (complete) {
      const completionTimer = window.setTimeout(onComplete, 0);
      return () => window.clearTimeout(completionTimer);
    }

    const character = text[visibleLength] ?? "";
    const typingTimer = window.setTimeout(
      () => setVisibleLength((length) => Math.min(length + 1, text.length)),
      delayForCharacter(character),
    );
    return () => window.clearTimeout(typingTimer);
  }, [complete, onComplete, text, visibleLength]);

  return (
    <div
      ref={narrationRef}
      className={`typewriter-narration ${complete ? "is-complete" : "is-typing"}`}
      role="status"
      aria-live="polite"
      aria-atomic="true"
      aria-label={text}
    >
      <p className="current-narration" aria-hidden="true">
        {text.slice(0, visibleLength)}
        <span className={`typing-cursor ${complete ? "is-resting" : ""}`} />
      </p>
      {!complete && (
        <button
          className="typing-skip"
          type="button"
          onClick={() => {
            setVisibleLength(text.length);
            onComplete();
          }}
        >
          显示全文
        </button>
      )}
    </div>
  );
}
