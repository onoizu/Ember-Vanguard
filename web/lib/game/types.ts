export type BackgroundId = "journalist" | "doctor" | "looter";
export type Direction = "w" | "a" | "s" | "d";
export type GamePhase = "opening" | "exploration" | "climax" | "ending";

export type EndingType =
  | "逃脱·理智尚存"
  | "逃脱·精神破碎"
  | "融合·成为祭品"
  | "战死·无名英雄"
  | "湮灭·彻底消失";

export interface BackgroundSpec {
  id: BackgroundId;
  label: string;
  english: string;
  hp: number;
  san: number;
  description: string;
  ability: string;
}

export interface EventOption {
  key: "1" | "2" | "3";
  text: string;
}

/** The exact six-field event contract defined by GDD section 5.2. */
export interface GameEvent {
  narration: string;
  hp_delta: number;
  san_delta: number;
  new_item: string | null;
  is_cursed: boolean;
  options: [EventOption, EventOption, EventOption];
}

export interface Room {
  x: number;
  y: number;
  name: string;
  description: string;
  exits: Direction[];
  visited: boolean;
  eventTriggered: boolean;
  eventResolved: boolean;
  event: GameEvent;
  clue: string;
}

export interface PlayerState {
  name: string;
  background: BackgroundId;
  hp: number;
  hpMax: number;
  san: number;
  sanMax: number;
  inventory: string[];
  curseLevel: number;
  roomsVisited: number;
  keyEvents: string[];
  x: number;
  y: number;
  doctorResistanceUsed: boolean;
}

export interface ClimaxState {
  title: string;
  progress: number;
  danger: number;
  rounds: number;
  options: [EventOption, EventOption, EventOption];
}

export interface GameState {
  phase: GamePhase;
  player: PlayerState;
  rooms: Record<string, Room>;
  narration: string;
  effects: string[];
  keyEvents: string[];
  climax: ClimaxState | null;
  ending: EndingType | null;
  endingText: string | null;
  turn: number;
  notice: string | null;
}

export interface RoomTemplate {
  name: string;
  description: string;
  clue: string;
}
