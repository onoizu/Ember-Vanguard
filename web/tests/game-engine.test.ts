import assert from "node:assert/strict";
import test from "node:test";
import {
  createGame,
  enterManor,
  getCurrentRoom,
  movePlayer,
  resolveClimaxAction,
  resolveExplorationAction,
} from "../lib/game/engine";

test("journalist exploration uses coordinate rooms and reaches the forced climax", () => {
  const originalRandom = Math.random;
  Math.random = () => 0.99;
  try {
    let game = enterManor(createGame("艾琳", "journalist"));
    assert.equal(game.phase, "exploration");
    assert.equal(game.player.roomsVisited, 1);
    assert.ok(game.player.keyEvents.some((entry) => entry.includes("碎片线索")));

    game = resolveExplorationAction(game, 0);
    assert.equal(getCurrentRoom(game).eventResolved, true);
    assert.ok(game.narration.length > 120);
    assert.match(game.narration, /检查铁门与锁舌/);
    assert.ok(game.effects.includes("行动检定：成功"));
    game.player.roomsVisited = 19;
    game = movePlayer(game, "w");
    assert.deepEqual([game.player.x, game.player.y], [0, 1]);
    assert.equal(game.player.roomsVisited, 20);
    assert.equal(game.phase, "climax");
    assert.ok(game.narration.length > 120);

    for (let round = 0; round < 3 && game.phase === "climax"; round += 1) {
      game = resolveClimaxAction(game, 0);
    }
    assert.equal(game.phase, "ending");
    assert.equal(game.ending, "逃脱·理智尚存");
  } finally {
    Math.random = originalRandom;
  }
});

test("doctor's first zero-SAN event triggers rational resistance", () => {
  const game = createGame("林医生", "doctor");
  game.rooms["0,0"].event.san_delta = -99;
  const entered = enterManor(game);
  assert.equal(entered.player.san, 1);
  assert.equal(entered.player.doctorResistanceUsed, true);
  assert.ok(entered.effects.some((effect) => effect.includes("理性抵抗")));
});
