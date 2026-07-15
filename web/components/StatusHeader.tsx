import { BACKGROUNDS } from "@/lib/game/content";
import type { GameState } from "@/lib/game/types";

function Meter({ value, max, tone }: { value: number; max: number; tone: "hp" | "san" }) {
  const percent = max ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <div className={`status-meter ${tone}`}>
      <div className="meter-label">
        <span>{tone.toUpperCase()}</span>
        <strong>
          {value}<small>/{max}</small>
        </strong>
      </div>
      <div className="meter-track" aria-label={`${tone} ${value}/${max}`}>
        <span style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

export function StatusHeader({ game, onRestart }: { game: GameState; onRestart: () => void }) {
  const { player } = game;
  const background = BACKGROUNDS[player.background];
  return (
    <header className="game-header">
      <div className="game-brand">
        <span className="brand-monogram">EV</span>
        <div>
          <strong>EMBER VANGUARD</strong>
          <span>灰石庄园调查档案</span>
        </div>
      </div>

      <div className="investigator-id">
        <span className="eyebrow">INVESTIGATOR</span>
        <strong>{player.name}</strong>
        <span>{background.label} / {background.english}</span>
      </div>

      <div className="header-meters">
        <Meter value={player.hp} max={player.hpMax} tone="hp" />
        <Meter value={player.san} max={player.sanMax} tone="san" />
      </div>

      <div className="header-facts">
        <div>
          <span>诅咒</span>
          <strong className={player.curseLevel ? "is-cursed" : ""}>
            {player.curseLevel ? "◆".repeat(Math.min(4, player.curseLevel)) : "—"}
          </strong>
        </div>
        <div>
          <span>探索</span>
          <strong>{String(player.roomsVisited).padStart(2, "0")}<small>/20</small></strong>
        </div>
      </div>

      <button className="icon-action" type="button" onClick={onRestart} aria-label="重新开始游戏">
        ↺
      </button>
    </header>
  );
}
