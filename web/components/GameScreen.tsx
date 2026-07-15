"use client";

import { useCallback, useState } from "react";
import type { Direction, GameState } from "@/lib/game/types";
import { DirectionPad } from "./DirectionPad";
import { MapPanel } from "./MapPanel";
import { NarrativePanel } from "./NarrativePanel";
import { StatusHeader } from "./StatusHeader";

interface GameScreenProps {
  game: GameState;
  onMove: (direction: Direction) => void;
  onAction: (index: number) => void;
  onClimaxAction: (index: number) => void;
  onClearNotice: () => void;
  onRestart: () => void;
}

export function GameScreen({
  game,
  onMove,
  onAction,
  onClimaxAction,
  onClearNotice,
  onRestart,
}: GameScreenProps) {
  const narrativeKey = `${game.phase}-${game.turn}-${game.player.x}:${game.player.y}-${game.narration}`;
  const [completedNarrativeKey, setCompletedNarrativeKey] = useState<string | null>(null);
  const narrationInProgress = completedNarrativeKey !== narrativeKey;
  const handleNarrationComplete = useCallback(
    () => setCompletedNarrativeKey(narrativeKey),
    [narrativeKey],
  );

  return (
    <main
      className={`game-shell phase-${game.phase}`}
      data-narrative-typing={narrationInProgress}
    >
      <div className="game-noise" aria-hidden="true" />
      <StatusHeader game={game} onRestart={onRestart} />
      <div className="game-content">
        <NarrativePanel
          game={game}
          interactionLocked={narrationInProgress}
          narrativeKey={narrativeKey}
          onNarrationComplete={handleNarrationComplete}
          onAction={onAction}
          onClimaxAction={onClimaxAction}
        />
        <div className="game-utility">
          <MapPanel game={game} interactionLocked={narrationInProgress} onMove={onMove} />
          <DirectionPad
            game={game}
            interactionLocked={narrationInProgress}
            onMove={onMove}
          />
        </div>
      </div>
      <footer className="game-footer">
        <span>GREYSTONE MANOR · LOCAL NARRATIVE FALLBACK ACTIVE</span>
        <span>进度自动保存 · D20 检定结果隐藏</span>
      </footer>
      {game.notice && (
        <button className="notice-toast" type="button" onClick={onClearNotice}>
          <span>!</span>{game.notice}<small>点击关闭</small>
        </button>
      )}
    </main>
  );
}
