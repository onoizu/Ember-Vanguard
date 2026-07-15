import { DIRECTION_META, getCurrentRoom } from "@/lib/game/engine";
import type { Direction, GameState } from "@/lib/game/types";

const DIRECTION_ARROWS: Record<Direction, string> = {
  w: "▲",
  a: "◀",
  s: "▼",
  d: "▶",
};

interface DirectionPadProps {
  game: GameState;
  interactionLocked: boolean;
  onMove: (direction: Direction) => void;
}

export function DirectionPad({ game, interactionLocked, onMove }: DirectionPadProps) {
  const room = getCurrentRoom(game);
  const movementReady = game.phase === "exploration" && room.eventResolved;

  return (
    <section
      className={`direction-dock ${movementReady ? "is-ready" : "is-waiting"}`}
      aria-label="移动方向"
    >
      <header>
        <span>{"// 选择方向"}</span>
        <small>{movementReady ? "WASD / ↑ ← ↓ →" : "等待行动完成"}</small>
      </header>
      <div className="direction-grid">
        {(["w", "a", "s", "d"] as Direction[]).map((direction) => {
          const open = movementReady && room.exits.includes(direction);
          const disabled = interactionLocked || !open;
          return (
            <button
              className={`direction-key direction-${direction} ${open ? "is-open" : "is-sealed"}`}
              type="button"
              disabled={disabled}
              onClick={() => onMove(direction)}
              aria-label={open ? `${DIRECTION_META[direction].long}移动` : `${DIRECTION_META[direction].label}方封闭`}
              key={direction}
            >
              <span className="direction-arrow" aria-hidden="true">{DIRECTION_ARROWS[direction]}</span>
              <span className="direction-letter">{direction.toUpperCase()}</span>
              <small>{open ? DIRECTION_META[direction].label : "封"}</small>
            </button>
          );
        })}
      </div>
    </section>
  );
}
