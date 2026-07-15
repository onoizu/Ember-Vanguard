"use client";

import { getCurrentRoom } from "@/lib/game/engine";
import type { GameState } from "@/lib/game/types";
import { TypewriterNarration } from "./TypewriterNarration";

interface NarrativePanelProps {
  game: GameState;
  interactionLocked: boolean;
  narrativeKey: string;
  onNarrationComplete: () => void;
  onAction: (index: number) => void;
  onClimaxAction: (index: number) => void;
}

export function NarrativePanel({
  game,
  interactionLocked,
  narrativeKey,
  onNarrationComplete,
  onAction,
  onClimaxAction,
}: NarrativePanelProps) {
  const room = getCurrentRoom(game);
  const isClimax = game.phase === "climax";
  const options = isClimax ? game.climax?.options ?? [] : room.event.options;
  const pendingEncounter = !room.eventResolved;

  return (
    <aside className="narrative-panel">
      <header className="narrative-header">
        <span className="eyebrow">FIELD TRANSCRIPT / TURN {String(game.turn).padStart(3, "0")}</span>
        <div className="phase-chip">
          <i />
          {isClimax ? "异变期" : "探索期"}
        </div>
      </header>

      <article className="room-copy">
        <div className="room-context">
          <div className="room-title-row">
            <span className="room-index">ROOM {String(game.player.roomsVisited).padStart(2, "0")}</span>
            <h2>{isClimax ? game.climax?.title : room.name}</h2>
          </div>
          {!isClimax && <p className="room-description">{room.description}</p>}
        </div>
        <div className="narration-rule"><span /></div>
        <div className="narration-viewport">
          <TypewriterNarration
            key={narrativeKey}
            text={game.narration}
            onComplete={onNarrationComplete}
          />
        </div>
      </article>

      {game.effects.length > 0 && (
        <div className="effect-list" aria-label="本轮状态变化">
          {game.effects.map((effect, index) => <span key={`${effect}-${index}`}>{effect}</span>)}
        </div>
      )}

      <div className={`choice-section ${!isClimax && !pendingEncounter ? "is-movement-ready" : ""}`}>
        <div className="choice-heading">
          <span>{isClimax ? "连续检定" : pendingEncounter ? "你的选择" : "选择方向"}</span>
          <small>
            {interactionLocked
              ? "档案记录中…"
              : isClimax || pendingEncounter
                ? "数字键 1—3"
                : "W / A / S / D"}
          </small>
        </div>

        {isClimax || pendingEncounter ? (
          <div className="choice-list">
            {options.map((option, index) => (
              <button
                type="button"
                className="choice-button"
                disabled={interactionLocked}
                onClick={() => isClimax ? onClimaxAction(index) : onAction(index)}
                key={option.key}
              >
                <kbd>{option.key}</kbd>
                <span>{option.text}</span>
                <i aria-hidden="true">↗</i>
              </button>
            ))}
          </div>
        ) : (
          <div className="movement-handoff">
            <span>当前房间的异象已经沉寂。</span>
            <small>使用界面右下角的方向控制继续探索。</small>
          </div>
        )}
      </div>

      <div className="inventory-section">
        <div className="subsection-heading">
          <span>随身物品</span>
          <small>{game.player.inventory.length} / ∞</small>
        </div>
        <div className="inventory-list">
          {game.player.inventory.length ? game.player.inventory.map((item, index) => (
            <span className={item.includes("逃脱出口") ? "is-key-item" : ""} key={`${item}-${index}`}>
              <i>◇</i>{item}
            </span>
          )) : <em>口袋里只有那封匿名信。</em>}
        </div>
      </div>

      <details className="event-log">
        <summary>关键事件记录 <span>{game.keyEvents.length}</span></summary>
        <ol>
          {game.keyEvents.slice(-6).reverse().map((event, index) => <li key={`${event}-${index}`}>{event}</li>)}
        </ol>
      </details>
    </aside>
  );
}
