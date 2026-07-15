import { BACKGROUNDS } from "@/lib/game/content";
import type { GameState } from "@/lib/game/types";

export function EndingScreen({ game, onRestart }: { game: GameState; onRestart: () => void }) {
  const player = game.player;
  const background = BACKGROUNDS[player.background];
  return (
    <main className="ending-screen">
      <div className="ending-vignette" aria-hidden="true" />
      <article className="ending-document">
        <header>
          <span className="eyebrow">ARKHAM COUNTY / CLOSED CASE</span>
          <span>CASE NO. 1923—{String(game.turn).padStart(3, "0")}</span>
        </header>
        <div className="ending-mark" aria-hidden="true">终</div>
        <p className="ending-label">最终记录</p>
        <h1>{game.ending}</h1>
        <div className="ending-rule"><span /></div>
        <p className="ending-copy">{game.endingText}</p>
        <dl className="ending-stats">
          <div><dt>调查者</dt><dd>{player.name} · {background.label}</dd></div>
          <div><dt>最终状态</dt><dd>HP {player.hp}/{player.hpMax} · SAN {player.san}/{player.sanMax}</dd></div>
          <div><dt>庄园深度</dt><dd>{player.roomsVisited} 个房间 · 诅咒 {player.curseLevel}</dd></div>
          <div><dt>带出物品</dt><dd>{player.inventory.join("、") || "无"}</dd></div>
        </dl>
        <button className="primary-action" type="button" onClick={onRestart}>
          <span>建立新档案</span>
          <kbd>RESTART</kbd>
        </button>
      </article>
    </main>
  );
}
