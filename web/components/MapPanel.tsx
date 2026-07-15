import { DIRECTION_META, getCurrentRoom, roomKey } from "@/lib/game/engine";
import type { Direction, GameState, Room } from "@/lib/game/types";

const VIEW_RADIUS = 3;

function directionFromDelta(dx: number, dy: number): Direction | null {
  if (dx === 0 && dy === 1) return "w";
  if (dx === -1 && dy === 0) return "a";
  if (dx === 0 && dy === -1) return "s";
  if (dx === 1 && dy === 0) return "d";
  return null;
}

function RoomNode({ room, current }: { room: Room; current: boolean }) {
  return (
    <div className={`map-node ${current ? "is-current" : "is-visited"}`}>
      {room.exits.map((exit) => <span className={`map-link link-${exit}`} key={exit} />)}
      <span className="node-code">{current ? "YOU" : `${room.x}:${room.y}`}</span>
      <strong>{room.name}</strong>
      <span className="node-mark">{current ? "◎" : "•"}</span>
    </div>
  );
}

export function MapPanel({
  game,
  interactionLocked,
  onMove,
}: {
  game: GameState;
  interactionLocked: boolean;
  onMove: (direction: Direction) => void;
}) {
  const { player } = game;
  const current = getCurrentRoom(game);
  const movementLocked =
    interactionLocked || game.phase !== "exploration" || !current.eventResolved;
  const cells: React.ReactNode[] = [];

  for (let dy = VIEW_RADIUS; dy >= -VIEW_RADIUS; dy -= 1) {
    for (let dx = -VIEW_RADIUS; dx <= VIEW_RADIUS; dx += 1) {
      const x = player.x + dx;
      const y = player.y + dy;
      const room = game.rooms[roomKey(x, y)];
      const direction = directionFromDelta(dx, dy);
      const reachable = Boolean(direction && current.exits.includes(direction));
      const canMove = Boolean(direction && reachable && !movementLocked);
      const key = roomKey(x, y);

      if (room?.visited) {
        cells.push(
          <button
            className={`map-cell has-room ${canMove ? "is-reachable" : ""}`}
            type="button"
            key={key}
            onClick={() => direction && canMove && onMove(direction)}
            disabled={!canMove}
            aria-label={canMove ? `移动到${room.name}` : room.name}
          >
            <RoomNode room={room} current={dx === 0 && dy === 0} />
          </button>,
        );
      } else if (reachable) {
        cells.push(
          <button
            className={`map-cell unknown-room ${canMove ? "is-reachable" : "is-locked"}`}
            type="button"
            key={key}
            onClick={() => direction && canMove && onMove(direction)}
            disabled={!canMove}
            aria-label={direction ? `${DIRECTION_META[direction].long}探索未知区域` : "未知区域"}
          >
            <span>?</span>
            <small>{direction ? DIRECTION_META[direction].label : ""}</small>
          </button>,
        );
      } else {
        cells.push(<div className="map-cell map-void" key={key}><span>·</span></div>);
      }
    }
  }

  return (
    <section className={`map-panel ${game.phase === "climax" ? "is-anomaly" : ""}`}>
      <header className="panel-heading map-heading">
        <div>
          <span className="eyebrow">MANOR CARTOGRAPHY / LIVE</span>
          <h2>庄园探索图</h2>
        </div>
        <div className="coordinate-readout">
          <span>当前位置</span>
          <strong>{player.x >= 0 ? "+" : ""}{player.x} / {player.y >= 0 ? "+" : ""}{player.y}</strong>
        </div>
      </header>

      <div className="map-stage">
        <div className="map-axis axis-y" aria-hidden="true">N<br />↑</div>
        <div className="map-grid" role="group" aria-label="已探索庄园地图">
          {cells}
        </div>
        {game.phase === "climax" && (
          <div className="anomaly-stamp" aria-hidden="true">
            <span>ANOMALY</span>
            <strong>地图已失效</strong>
          </div>
        )}
      </div>

      <footer className="map-footer">
        <div className="map-legend">
          <span><i className="legend-current" />当前位置</span>
          <span><i className="legend-visited" />已探索</span>
          <span><i className="legend-unknown" />可探索</span>
        </div>
        <span className="map-scale">局部视野 7 × 7 · 坐标哈希地图</span>
      </footer>
    </section>
  );
}
