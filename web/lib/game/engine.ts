import {
  BACKGROUNDS,
  CLIMAX_OPTIONS,
  COMMON_EVENTS,
  CURSED_EVENTS,
  ESCAPE_EVENT,
  ITEM_EVENTS,
  ROOM_TEMPLATES,
  buildEndingText,
} from "./content";
import type {
  BackgroundId,
  Direction,
  EndingType,
  GameEvent,
  GameState,
  PlayerState,
  Room,
} from "./types";

export const DIRECTION_META: Record<
  Direction,
  { dx: number; dy: number; label: string; long: string; opposite: Direction }
> = {
  w: { dx: 0, dy: 1, label: "北", long: "向北", opposite: "s" },
  a: { dx: -1, dy: 0, label: "西", long: "向西", opposite: "d" },
  s: { dx: 0, dy: -1, label: "南", long: "向南", opposite: "w" },
  d: { dx: 1, dy: 0, label: "东", long: "向东", opposite: "a" },
};

const DIRECTIONS = Object.keys(DIRECTION_META) as Direction[];

function eventOptions(one: string, two: string, three: string): GameEvent["options"] {
  return [
    { key: "1", text: one },
    { key: "2", text: two },
    { key: "3", text: three },
  ];
}

function entryRoom(): Room {
  return {
    x: 0,
    y: 0,
    name: "入口大厅",
    description:
      "铁制枝形吊灯悬在头顶，蜡烛早已熄灭，烛泪却依然新鲜。四壁油画无一例外地把目光投向北方，空气里浮着腐烂的甜味。",
    exits: ["w", "d"],
    visited: true,
    eventTriggered: false,
    eventResolved: false,
    clue: "大厅地砖下刻着数字二十，其中最后一笔尚未干透。",
    event: {
      narration: "铁门的锁舌自行滑落。画像中的人似乎同时屏住了呼吸。",
      hp_delta: 0,
      san_delta: 0,
      new_item: null,
      is_cursed: false,
      options: eventOptions(
        "检查铁门与锁舌",
        "观察所有画像注视的方向",
        "熄灭手电，倾听黑暗中的动静",
      ),
    },
  };
}

export function roomKey(x: number, y: number): string {
  return `${x},${y}`;
}

export function getCurrentRoom(state: GameState): Room {
  return state.rooms[roomKey(state.player.x, state.player.y)];
}

export function createGame(name: string, background: BackgroundId): GameState {
  const spec = BACKGROUNDS[background];
  const player: PlayerState = {
    name: name.trim().slice(0, 24) || "调查者",
    background,
    hp: spec.hp,
    hpMax: spec.hp,
    san: spec.san,
    sanMax: spec.san,
    inventory: [],
    curseLevel: 0,
    roomsVisited: 1,
    keyEvents: ["推开灰石庄园的腐朽铁门"],
    x: 0,
    y: 0,
    doctorResistanceUsed: false,
  };
  const room = entryRoom();
  return {
    phase: "opening",
    player,
    rooms: { [roomKey(0, 0)]: room },
    narration: room.event.narration,
    effects: [],
    keyEvents: [...player.keyEvents],
    climax: null,
    ending: null,
    endingText: null,
    turn: 0,
    notice: null,
  };
}

export function enterManor(previous: GameState): GameState {
  const state = clone(previous);
  state.phase = "exploration";
  const room = getCurrentRoom(state);
  room.eventTriggered = true;
  const effects: string[] = [];
  if (state.player.background === "journalist") {
    const clue = `碎片线索：${room.clue}`;
    state.player.keyEvents.push(clue);
    state.keyEvents.push(clue);
    effects.push(clue);
  }
  applyEvent(state, room.event, effects);
  state.narration = `你跨过铁门留下的阴影，鞋底在大厅地砖上发出过分清晰的回声。${room.event.narration}头顶的吊灯轻轻晃动，画像的视线也随之偏转；从这一刻起，庄园开始记录你的每一次呼吸。`;
  state.effects = effects;
  return state;
}

export function movePlayer(previous: GameState, direction: Direction): GameState {
  if (previous.phase !== "exploration") return previous;
  const current = getCurrentRoom(previous);
  if (!current.eventResolved) {
    return withNotice(previous, "必须先处理当前房间的遭遇。");
  }
  if (!current.exits.includes(direction)) {
    return withNotice(previous, `通往${DIRECTION_META[direction].label}方的道路被封死了。`);
  }

  const state = clone(previous);
  state.notice = null;
  state.turn += 1;
  const { dx, dy, opposite } = DIRECTION_META[direction];
  const targetX = state.player.x + dx;
  const targetY = state.player.y + dy;
  const targetKey = roomKey(targetX, targetY);
  let target = state.rooms[targetKey];
  if (!target) {
    target = generateRoom(targetX, targetY, opposite, state.player.roomsVisited);
    state.rooms[targetKey] = target;
  } else if (!target.exits.includes(opposite)) {
    target.exits.push(opposite);
  }

  state.player.x = targetX;
  state.player.y = targetY;
  const firstVisit = !target.visited;
  const effects: string[] = [];
  if (firstVisit) {
    target.visited = true;
    state.player.roomsVisited += 1;
    logEvent(state, `首次进入「${target.name}」`);
    if (state.player.background === "journalist") {
      const clue = `碎片线索：${target.clue}`;
      logEvent(state, clue);
      effects.push(clue);
    }
  }

  const newEncounter = !target.eventTriggered;
  const passage = movementPassage(direction, current.name, target.name, state.turn);
  state.narration = newEncounter
    ? `${passage}${target.event.narration}你停在门内，没有立刻回头——身后的走廊已经比来时狭窄了一些。`
    : `${passage}这里的异象暂时沉寂，只剩旧木、冷灰与某种潮湿呼吸混在一起。你曾留下的痕迹还在，却被挪到了不可能的位置。`;
  let cursedAdded = false;
  if (newEncounter) {
    target.eventTriggered = true;
    cursedAdded = applyEvent(state, target.event, effects);
  }
  state.effects = effects;

  const terminal = evaluateTerminal(state);
  if (terminal) return terminal;
  if (cursedAdded && curseCheck(state.player.curseLevel)) {
    return beginClimax(state, "受诅物在衣袋中发出一声清晰的心跳。地图边界开始从现实中脱落。");
  }
  if (state.player.roomsVisited >= 20) {
    return beginClimax(state, "第二十个房间在身后闭合。庄园终于完成了自己的形状。");
  }
  return state;
}

export function resolveExplorationAction(
  previous: GameState,
  choiceIndex: number,
): GameState {
  if (previous.phase !== "exploration") return previous;
  const current = getCurrentRoom(previous);
  if (current.eventResolved) {
    return withNotice(previous, "这个房间的异象已经沉寂。选择一个方向继续探索。");
  }
  const option = current.event.options[choiceIndex];
  if (!option) return withNotice(previous, "无效的行动选项。");

  const state = clone(previous);
  const room = getCurrentRoom(state);
  const action = room.event.options[choiceIndex].text;
  const kind = inferCheckKind(action);
  const stat = kind === "mental" ? state.player.san : state.player.hp;
  const roll = randomInt(1, 20);
  const looterBonus = state.player.background === "looter" && kind === "combat" ? 1 : 0;
  const modified = roll + Math.floor(stat / 3) + looterBonus;
  const difficulty = 10 + choiceIndex;
  const success = modified >= difficulty;
  const effects: string[] = [];

  room.eventResolved = true;
  state.turn += 1;
  state.notice = null;
  if (success) {
    state.narration = buildExplorationOutcome(
      room,
      action,
      true,
      kind,
      choiceIndex,
      state.player.background,
      state.turn,
    );
    effects.push("行动检定：成功");
    if (choiceIndex === 2 && Math.random() < 0.3) {
      state.player.san = Math.max(0, state.player.san - 1);
      effects.push("SAN −1");
    }
  } else {
    state.narration = buildExplorationOutcome(
      room,
      action,
      false,
      kind,
      choiceIndex,
      state.player.background,
      state.turn,
    );
    effects.push("行动检定：失败");
    if (kind === "mental" || Math.random() < 0.5) {
      applySanLoss(state, 1, effects);
    } else {
      state.player.hp = Math.max(0, state.player.hp - 1);
      effects.push("HP −1");
    }
  }
  state.effects = effects;
  logEvent(state, `在「${room.name}」${action}：${success ? "成功" : "失败"}`);
  return evaluateTerminal(state) ?? state;
}

export function resolveClimaxAction(previous: GameState, choiceIndex: number): GameState {
  if (previous.phase !== "climax" || !previous.climax) return previous;
  const option = previous.climax.options[choiceIndex];
  if (!option) return withNotice(previous, "无效的终局行动。");

  const state = clone(previous);
  const climax = state.climax!;
  const action = climax.options[choiceIndex].text;
  const kind = inferCheckKind(action);
  const stat = kind === "mental" ? state.player.san : state.player.hp;
  const roll = randomInt(1, 20);
  const bonus = state.player.background === "looter" && kind === "combat" ? 1 : 0;
  const difficulty = 9 + climax.danger + choiceIndex * 2;
  const success = roll + Math.floor(stat / 3) + bonus >= difficulty;
  const effects: string[] = [];

  climax.rounds += 1;
  state.turn += 1;
  if (success) {
    climax.progress += choiceIndex === 2 ? 2 : 1;
    state.narration = buildClimaxOutcome(action, true, choiceIndex, climax.rounds);
    effects.push("终局检定：成功");
    effects.push(`封印突破 +${choiceIndex === 2 ? 2 : 1}`);
  } else {
    const dangerGain = choiceIndex === 2 ? 2 : 1;
    climax.danger += dangerGain;
    state.narration = buildClimaxOutcome(action, false, choiceIndex, climax.rounds);
    effects.push("终局检定：失败");
    effects.push(`危机 +${dangerGain}`);
    if (choiceIndex === 0) applySanLoss(state, 1, effects);
    else {
      state.player.hp = Math.max(0, state.player.hp - 1);
      effects.push("HP −1");
    }
  }
  state.effects = effects;
  logEvent(state, `异变期行动“${action}”：${success ? "成功" : "失败"}`);

  if (state.player.hp <= 0 || climax.danger >= 3) {
    return setEnding(state, "湮灭·彻底消失");
  }
  if (state.player.san <= 0) return setEnding(state, "融合·成为祭品");
  if (climax.progress >= 3) {
    state.player.inventory.push("逃脱出口·异变裂隙");
    const ending: EndingType = state.player.san > 3 ? "逃脱·理智尚存" : "逃脱·精神破碎";
    return setEnding(state, ending);
  }
  return state;
}

export function dismissNotice(previous: GameState): GameState {
  if (!previous.notice) return previous;
  return { ...previous, notice: null };
}

function generateRoom(x: number, y: number, requiredExit: Direction, visited: number): Room {
  const hash = coordinateHash(x, y, visited);
  const template = ROOM_TEMPLATES[hash % ROOM_TEMPLATES.length];
  const candidates = DIRECTIONS.filter((direction) => direction !== requiredExit);
  candidates.sort((a, b) =>
    coordinateHash(x + DIRECTION_META[a].dx, y + DIRECTION_META[a].dy, hash) -
    coordinateHash(x + DIRECTION_META[b].dx, y + DIRECTION_META[b].dy, hash),
  );
  const exits: Direction[] = [requiredExit, ...candidates.slice(0, 1 + (hash % 2))];
  const chance = Math.random();
  let event: GameEvent;
  if (visited >= 6 && chance < 0.035) event = clone(ESCAPE_EVENT);
  else if (chance < 0.18) event = clone(CURSED_EVENTS[hash % CURSED_EVENTS.length]);
  else if (chance < 0.4) event = clone(ITEM_EVENTS[hash % ITEM_EVENTS.length]);
  else event = clone(COMMON_EVENTS[hash % COMMON_EVENTS.length]);

  return {
    x,
    y,
    name: template.name,
    description: template.description,
    exits: [...new Set(exits)],
    visited: false,
    eventTriggered: false,
    eventResolved: false,
    event,
    clue: template.clue,
  };
}

function applyEvent(state: GameState, event: GameEvent, effects: string[]): boolean {
  if (event.hp_delta) {
    state.player.hp = clamp(state.player.hp + event.hp_delta, 0, state.player.hpMax);
    effects.push(`HP ${signed(event.hp_delta)}`);
  }
  if (event.san_delta) applySanDelta(state, event.san_delta, effects);
  if (!event.new_item) return false;
  state.player.inventory.push(event.new_item);
  effects.push(`获得：${event.new_item}`);
  logEvent(state, `获得${event.is_cursed ? "受诅物" : "物品"}：${event.new_item}`);
  if (event.is_cursed) state.player.curseLevel += 1;
  return event.is_cursed;
}

function applySanLoss(state: GameState, amount: number, effects: string[]): void {
  applySanDelta(state, -Math.abs(amount), effects);
}

function applySanDelta(state: GameState, delta: number, effects: string[]): void {
  state.player.san = clamp(state.player.san + delta, 0, state.player.sanMax);
  effects.push(`SAN ${signed(delta)}`);
  if (
    state.player.san === 0 &&
    state.player.background === "doctor" &&
    !state.player.doctorResistanceUsed
  ) {
    state.player.doctorResistanceUsed = true;
    state.player.san = 1;
    effects.push("理性抵抗：SAN 保留为 1");
    logEvent(state, "理性抵抗：在精神崩溃边缘重新抓住现实");
  }
}

function evaluateTerminal(state: GameState): GameState | null {
  if (state.player.hp <= 0) {
    const type: EndingType =
      state.phase === "climax" || state.player.curseLevel >= 3
        ? "湮灭·彻底消失"
        : "战死·无名英雄";
    return setEnding(state, type);
  }
  if (state.player.san <= 0) return setEnding(state, "融合·成为祭品");
  if (state.player.inventory.some((item) => item.includes("逃脱出口"))) {
    return setEnding(state, state.player.san > 3 ? "逃脱·理智尚存" : "逃脱·精神破碎");
  }
  return null;
}

function beginClimax(previous: GameState, trigger: string): GameState {
  const state = clone(previous);
  state.phase = "climax";
  state.climax = {
    title: "灰石庄园的心跳",
    progress: 0,
    danger: 0,
    rounds: 0,
    options: clone(CLIMAX_OPTIONS),
  };
  state.narration = `${trigger}所有门同时在身后闭合，你经历过的房间被拼成一张巨大的脸。不同方向传来你此前做过的每一个选择，却都被换成了同一种陌生嗓音。地板下的远古碎片意识已经醒来，正等待你替它完成最后一步；而那些被你收集的线索，此刻正从口袋里透出微弱热度，像在提醒你仍有一次拒绝的机会。`;
  state.effects = ["地图探索已挂起", "异变期开始"];
  logEvent(state, "灰石庄园进入异变期");
  return state;
}

function setEnding(previous: GameState, type: EndingType): GameState {
  const state = clone(previous);
  state.phase = "ending";
  state.ending = type;
  logEvent(state, `结局：${type}`);
  state.endingText = buildEndingText(type, state.player);
  state.effects = [];
  return state;
}

function logEvent(state: GameState, event: string): void {
  state.player.keyEvents.push(event);
  state.keyEvents.push(event);
  state.player.keyEvents = state.player.keyEvents.slice(-50);
  state.keyEvents = state.keyEvents.slice(-50);
}

function inferCheckKind(action: string): "combat" | "mental" | "general" {
  const combat = ["攻击", "砸", "踢", "挣脱", "撬", "跃", "冲向", "打断"];
  const mental = ["观察", "阅读", "聆听", "辨认", "回忆", "线索", "祷", "凝视"];
  if (combat.some((word) => action.includes(word))) return "combat";
  if (mental.some((word) => action.includes(word))) return "mental";
  return "general";
}

function movementPassage(
  direction: Direction,
  fromRoom: string,
  toRoom: string,
  turn: number,
): string {
  const textures = [
    "墙内传来与脚步不同步的摩擦声，每当你停下，它就多走一步。",
    "手电光在拐角处被黑暗折断，几秒后才从另一面墙上重新出现。",
    "过道比记忆中多出七块地板，最后一块木板还残留着陌生人的体温。",
    "门框在你经过时轻轻收紧，像庄园用木头与石灰测量了你的肩宽。",
  ];
  const texture = textures[Math.abs(turn + direction.charCodeAt(0)) % textures.length];
  return `你${DIRECTION_META[direction].long}离开「${fromRoom}」。${texture}当「${toRoom}」的门在面前开启时，身后的回声才终于停止。`;
}

function buildExplorationOutcome(
  room: Room,
  action: string,
  success: boolean,
  kind: "combat" | "mental" | "general",
  choiceIndex: number,
  background: BackgroundId,
  turn: number,
): string {
  const approach = success
    ? {
        combat: "你抢在阴影重新聚拢前发力，动作干脆得没有给恐惧留下名字。",
        mental: "你强迫自己把每一处异常拆成可以观察、记录与验证的细节。",
        general: "你压低呼吸，先确认退路，再把手伸向最不愿触碰的那一点。",
      }[kind]
    : {
        combat: "你用力过猛，声音沿着墙体传开，像敲响了一口埋在地下的钟。",
        mental: "你试图维持理性，可某个细节在脑中反复放大，直到它取代了房间本身。",
        general: "你刚迈出第一步，脚下的阴影便先一步模仿了完整动作。",
      }[kind];
  const successTextures = [
    "手电光恢复稳定，墙纸后的抓挠声一层层退远，最终沉到地板下面。",
    "空气短暂变暖，尘埃从地面升起又落回原位，仿佛时间被纠正了一次。",
    "房间深处响起一声不甘的关门声，紧绷的木梁随后慢慢松开。",
  ];
  const failureTextures = [
    "庄园却像早已读过这段行动，黑暗从错误的方向压来，冰冷触感贴着皮肤划过。",
    "四周先是绝对安静，随后每件家具都用你的声音重复了一遍刚才的决定。",
    "门缝里涌出潮湿冷气，视野边缘多出一个始终与你保持半步距离的轮廓。",
  ];
  const textureIndex = coordinateHash(room.x, room.y, turn + choiceIndex) % 3;
  const texture = success ? successTextures[textureIndex] : failureTextures[textureIndex];
  const backgroundBeat = {
    journalist: "你仍把最反常的细节记进档案边缘，墨迹落下时，墙内也响起相同的书写声。",
    doctor: "你默数自己的脉搏，确认身体仍属于现实；第四次计数时，房间里却传来第五次心跳。",
    looter: "你凭经验护住要害并记住出口，口袋里的旧物却自行换了位置，像在躲避什么。",
  }[background];
  const conclusion = success
    ? `${room.name}里的异常终于退回阴影，你暂时夺回了行动的节奏，但这并不意味着它已经离开。`
    : "直到异响停下，你才发现自己的呼吸一直配合着另一个不存在的人；代价已经发生，只是伤口尚未决定出现在哪里。";

  return `你决定“${action}”。${approach}${texture}${backgroundBeat}${conclusion}`;
}

function buildClimaxOutcome(
  action: string,
  success: boolean,
  choiceIndex: number,
  round: number,
): string {
  const successTextures = [
    "你把散落线索按记忆中的顺序重新排列，错误的墙面随之裂开一道苍白缝隙。",
    "临时防线在最后一刻咬住地板，翻涌的黑暗被迫显露出真正的边界。",
    "你迎着那股意志向前冲去，耳边所有低语在同一瞬间变成尖锐静默。",
  ];
  const failureTextures = [
    "线索在手中变成陌生文字，每一行都开始描述你下一秒的失败。",
    "防线刚刚闭合，墙壁便从内部伸出更多房间，把退路折进无法抵达的角度。",
    "你的冲击穿过一层虚假的躯壳，那股意志反而借着恐惧触到了更深的记忆。",
  ];
  const texture = success ? successTextures[choiceIndex] : failureTextures[choiceIndex];
  const ending = success
    ? "封印纹路逐段亮起，庞大意识发出无声震颤；它对现实的抓握松动了一层，一条此前不存在的通道在远处显现。"
    : "房间向内收拢，记忆中最安全的地方也被改写成庄园的一部分。你听见它在地板下学习你的名字，下一轮回应只会更加准确。";
  return `第${round}轮异变中，你选择“${action}”。${texture}${ending}`;
}

function curseCheck(level: number): boolean {
  const threshold = Math.min(level * level * 5, 80);
  return randomInt(1, 100) <= threshold;
}

function coordinateHash(x: number, y: number, salt: number): number {
  let value = Math.imul(x + 101, 73856093) ^ Math.imul(y + 307, 19349663) ^ salt;
  value ^= value >>> 13;
  return Math.abs(value);
}

function withNotice(previous: GameState, notice: string): GameState {
  return { ...previous, notice };
}

function randomInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function signed(value: number): string {
  return value > 0 ? `+${value}` : `${value}`;
}

function clone<T>(value: T): T {
  return structuredClone(value);
}
