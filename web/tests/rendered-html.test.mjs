import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server renders the Ember Vanguard game shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /<title>Ember Vanguard｜灰石庄园<\/title>/i);
  assert.match(html, /正在调取灰石庄园档案/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton|Your site is taking shape/i);
});

test("homepage presents the illustrated loading cover before investigator selection", async () => {
  const source = await readFile(new URL("../components/StartScreen.tsx", import.meta.url), "utf8");
  assert.match(source, /src="\/og\.png"/);
  assert.match(source, /正在调取灰石庄园档案/);
  assert.match(source, /&gt;&gt;&gt;/);
  assert.match(source, /introPhase !== "ready"/);
  assert.match(source, /选择调查者背景/);
  assert.match(source, /继续上次档案/);
});

test("action narration is revealed with a cancellable typewriter", async () => {
  const source = await readFile(
    new URL("../components/TypewriterNarration.tsx", import.meta.url),
    "utf8",
  );
  assert.match(source, /delayForCharacter/);
  assert.match(source, /setVisibleLength/);
  assert.match(source, /viewport\.scrollTop = viewport\.scrollHeight/);
  assert.match(source, /显示全文/);
  assert.match(source, /complete \? "is-resting"/);
  assert.doesNotMatch(source, /className="sr-only"/);
});

test("game layout prioritizes the transcript and docks movement controls", async () => {
  const gameScreen = await readFile(new URL("../components/GameScreen.tsx", import.meta.url), "utf8");
  const directionPad = await readFile(new URL("../components/DirectionPad.tsx", import.meta.url), "utf8");
  const narrativePanel = await readFile(new URL("../components/NarrativePanel.tsx", import.meta.url), "utf8");
  assert.ok(gameScreen.indexOf("<NarrativePanel") < gameScreen.indexOf("<MapPanel"));
  assert.match(gameScreen, /className="game-utility"/);
  assert.match(directionPad, /className="direction-grid"/);
  assert.match(directionPad, /\["w", "a", "s", "d"\]/);
  assert.match(narrativePanel, /className="room-context"/);
  assert.match(narrativePanel, /className="narration-viewport"/);
});

test("game viewport is fixed and movement supports arrows plus WASD", async () => {
  const styles = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");
  const gameHook = await readFile(new URL("../hooks/useGame.ts", import.meta.url), "utf8");
  assert.match(styles, /\.game-shell\s*\{[\s\S]*?height: 100dvh;[\s\S]*?overflow: hidden;/);
  assert.match(styles, /\.narrative-panel\s*\{[\s\S]*?overflow: hidden;/);
  assert.match(styles, /grid-template-rows: auto minmax\(0, 1fr\) auto auto auto auto;/);
  assert.match(styles, /grid-template-columns: repeat\(3, minmax\(0, 1fr\)\);/);
  assert.match(styles, /\.typewriter-narration\.is-complete\s*\{\s*padding-bottom: 4px;/);
  for (const key of ["arrowup", "arrowleft", "arrowdown", "arrowright"]) {
    assert.match(gameHook, new RegExp(`${key}:`));
  }
});
