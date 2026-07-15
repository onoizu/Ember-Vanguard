"use client";

import { useGame } from "@/hooks/useGame";
import { EndingScreen } from "./EndingScreen";
import { GameScreen } from "./GameScreen";
import { OpeningScreen } from "./OpeningScreen";
import { StartScreen } from "./StartScreen";

export function GameApp() {
  const {
    game,
    savedGame,
    start,
    resume,
    enter,
    move,
    act,
    climaxAct,
    clearNotice,
    restart,
  } = useGame();

  if (!game) {
    return (
      <StartScreen
        hasSavedGame={Boolean(savedGame)}
        onResume={resume}
        onStart={start}
      />
    );
  }
  if (game.phase === "opening") {
    return <OpeningScreen player={game.player} onEnter={enter} onRestart={restart} />;
  }
  if (game.phase === "ending") return <EndingScreen game={game} onRestart={restart} />;
  return (
    <GameScreen
      game={game}
      onMove={move}
      onAction={act}
      onClimaxAction={climaxAct}
      onClearNotice={clearNotice}
      onRestart={restart}
    />
  );
}
