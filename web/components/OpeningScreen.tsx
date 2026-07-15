"use client";

import { OPENING_LINES } from "@/lib/game/content";
import type { PlayerState } from "@/lib/game/types";

interface OpeningScreenProps {
  player: PlayerState;
  onEnter: () => void;
  onRestart: () => void;
}

export function OpeningScreen({ player, onEnter, onRestart }: OpeningScreenProps) {
  return (
    <main className="opening-screen">
      <div className="opening-frame">
        <header>
          <span>GREYSTONE MANOR</span>
          <span>00 : 13 AM</span>
        </header>
        <div className="opening-body">
          <div className="door-sigil" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <p className="eyebrow">调查者 / {player.name}</p>
          <div className="opening-copy">
            {OPENING_LINES.map((line, index) => (
              <p key={line} style={{ animationDelay: `${index * 180}ms` }}>
                {line}
              </p>
            ))}
          </div>
          <button className="primary-action opening-action" type="button" onClick={onEnter}>
            <span>向前走去</span>
            <kbd>ENTER</kbd>
          </button>
          <button className="text-action" type="button" onClick={onRestart}>
            返回调查者档案
          </button>
        </div>
        <footer>THE DOOR REMEMBERS · THE HOUSE WAITS</footer>
      </div>
    </main>
  );
}
