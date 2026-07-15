"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createGame,
  dismissNotice,
  enterManor,
  getCurrentRoom,
  movePlayer,
  resolveClimaxAction,
  resolveExplorationAction,
} from "@/lib/game/engine";
import type { BackgroundId, Direction, GameState } from "@/lib/game/types";

const STORAGE_KEY = "ember-vanguard-save-v2";

const MOVEMENT_KEYS: Record<string, Direction> = {
  w: "w",
  arrowup: "w",
  a: "a",
  arrowleft: "a",
  s: "s",
  arrowdown: "s",
  d: "d",
  arrowright: "d",
};

export function useGame() {
  const [game, setGame] = useState<GameState | null>(null);
  const [savedGame, setSavedGame] = useState<GameState | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      try {
        const stored = window.localStorage.getItem(STORAGE_KEY);
        if (stored) setSavedGame(JSON.parse(stored) as GameState);
      } catch {
        window.localStorage.removeItem(STORAGE_KEY);
        setSavedGame(null);
      }
      setHydrated(true);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (game) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(game));
    }
  }, [game, hydrated]);

  const start = useCallback((name: string, background: BackgroundId) => {
    const nextGame = createGame(name, background);
    setSavedGame(nextGame);
    setGame(nextGame);
  }, []);
  const resume = useCallback(() => {
    if (savedGame) setGame(savedGame);
  }, [savedGame]);

  const enter = useCallback(() => setGame((value) => (value ? enterManor(value) : value)), []);
  const move = useCallback(
    (direction: Direction) => setGame((value) => (value ? movePlayer(value, direction) : value)),
    [],
  );
  const act = useCallback(
    (index: number) =>
      setGame((value) => (value ? resolveExplorationAction(value, index) : value)),
    [],
  );
  const climaxAct = useCallback(
    (index: number) => setGame((value) => (value ? resolveClimaxAction(value, index) : value)),
    [],
  );
  const clearNotice = useCallback(
    () => setGame((value) => (value ? dismissNotice(value) : value)),
    [],
  );
  const restart = useCallback(() => {
    window.localStorage.removeItem(STORAGE_KEY);
    setSavedGame(null);
    setGame(null);
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!game || event.metaKey || event.ctrlKey || event.altKey) return;
      if (document.querySelector('[data-narrative-typing="true"]')) return;
      const target = event.target as HTMLElement | null;
      if (target?.tagName === "INPUT" || target?.tagName === "TEXTAREA") return;
      const key = event.key.toLowerCase();
      const movementDirection = MOVEMENT_KEYS[key];
      if (game.phase === "exploration") {
        const room = getCurrentRoom(game);
        if (!room.eventResolved && ["1", "2", "3"].includes(key)) {
          event.preventDefault();
          act(Number(key) - 1);
        } else if (room.eventResolved && movementDirection) {
          event.preventDefault();
          move(movementDirection);
        }
      } else if (game.phase === "climax" && ["1", "2", "3"].includes(key)) {
        event.preventDefault();
        climaxAct(Number(key) - 1);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [act, climaxAct, game, move]);

  return {
    game,
    savedGame,
    hydrated,
    start,
    resume,
    enter,
    move,
    act,
    climaxAct,
    clearNotice,
    restart,
  };
}
