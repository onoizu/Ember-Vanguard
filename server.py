"""
Ember Vanguard — FastAPI 后端服务器
Client-Server 架构：Web 层，不含任何终端 UI 代码。
"""

import copy
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine import (
    BACKGROUND_STATS,
    INITIAL_ROOMS,
    AIPipeline,
    MapEngine,
    PlayerState,
    explore_new_room,
    skill_check,
)

# ─────────────────────────────────────────────
# FastAPI 应用初始化
# ─────────────────────────────────────────────

app = FastAPI(title="Ember Vanguard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# 全局单例游戏状态（MVP：不考虑多用户并发）
# ─────────────────────────────────────────────

player:        Optional[PlayerState] = None
engine:        Optional[MapEngine]   = None
ai:            AIPipeline            = AIPipeline()
current_room:  Optional[dict]        = None
current_event: Optional[dict]        = None


# ─────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────

def _apply_event_deltas(p: PlayerState, event: dict) -> None:
    """将遭遇 JSON 中的 hp_delta / san_delta / new_item 应用到玩家状态。"""
    hp_delta  = event.get("hp_delta",  0)
    san_delta = event.get("san_delta", 0)
    new_item  = event.get("new_item",  None)
    is_cursed = event.get("is_cursed", False)

    if hp_delta < 0:
        p.apply_damage(-hp_delta)
    elif hp_delta > 0:
        p.apply_heal(hp_delta)

    if san_delta < 0:
        p.apply_san_loss(-san_delta)
    elif san_delta > 0:
        p.apply_san_gain(san_delta)

    if new_item:
        p.add_item(new_item, cursed=is_cursed)


def _build_state_snapshot() -> Dict[str, Any]:
    """
    构建当前游戏完整快照，供所有接口返回。
    结构：
    {
      "player":   { ...玩家状态摘要... },
      "room":     { name, description },
      "narration": str,
      "options":  [ { "index": int, "type": "action"|"move", "text": str,
                      "key": str|null, "room_id": str|null } ],
      "game_over": { "dead": bool, "insane": bool }
    }
    """
    assert player and engine and current_room and current_event

    # ── 玩家摘要 ──────────────────────────────
    bg_label = BACKGROUND_STATS[player.background]["label"]
    player_snapshot = {
        **player.to_summary(),
        "background_label": bg_label,
        "current_room_id":  player.current_room_id,
    }

    # ── 房间基础信息 ──────────────────────────
    room_snapshot = {
        "name":        current_room.get("name", ""),
        "description": current_room.get("description", ""),
    }

    # ── 统一选项列表（行动 + 移动）────────────
    options: List[Dict[str, Any]] = []
    idx = 1

    # 行动选项（来自 current_event）
    for opt in current_event.get("options", []):
        options.append({
            "index":   idx,
            "type":    "action",
            "text":    opt["text"],
            "key":     None,
            "room_id": None,
        })
        idx += 1

    # 移动选项（来自 connected_rooms）
    KEY_ORDER = ["w", "a", "s", "d"]
    connections = engine.get_connections(player.current_room_id)
    sorted_conns = sorted(
        connections,
        key=lambda c: KEY_ORDER.index(c.get("key", "")) if c.get("key", "") in KEY_ORDER else 99,
    )
    for conn in sorted_conns:
        target_id  = conn["room_id"]
        key        = conn.get("key", "")
        is_visited = engine.is_visited(target_id)
        direction  = conn.get("direction", "")

        if is_visited:
            dest_text = direction.split("→")[-1].strip() if "→" in direction else direction
        else:
            dir_only  = direction.split("→")[0].strip() if "→" in direction else direction
            dest_text = f"{dir_only}  ···"

        options.append({
            "index":   idx,
            "type":    "move",
            "text":    dest_text,
            "key":     key,
            "room_id": target_id,
        })
        idx += 1

    # 退出选项
    options.append({
        "index":   idx,
        "type":    "quit",
        "text":    "放弃探索，离开游戏",
        "key":     None,
        "room_id": None,
    })

    return {
        "player":    player_snapshot,
        "room":      room_snapshot,
        "narration": current_event.get("narration", ""),
        "options":   options,
        "game_over": {
            "dead":   not player.is_alive(),
            "insane": not player.is_sane(),
        },
    }


def _ensure_started() -> None:
    """确保游戏已初始化，否则抛出 400。"""
    if player is None or engine is None:
        raise HTTPException(status_code=400, detail="游戏尚未初始化，请先调用 POST /api/start")


# ─────────────────────────────────────────────
# Pydantic 请求体模型
# ─────────────────────────────────────────────

class StartRequest(BaseModel):
    name:       str = "调查者"
    background: str = "journalist"


class ActionRequest(BaseModel):
    action_index: int   # 对应 options 列表中 type=="action" 的 index


class MoveRequest(BaseModel):
    direction_key: str  # w / a / s / d


# ─────────────────────────────────────────────
# 接口实现
# ─────────────────────────────────────────────

@app.get("/api/state")
async def get_state() -> Dict[str, Any]:
    """返回当前完整的游戏快照。"""
    _ensure_started()
    return _build_state_snapshot()


@app.post("/api/start")
async def start_game(req: StartRequest = StartRequest()) -> Dict[str, Any]:
    """
    初始化 / 重置游戏。
    接受可选的 name 和 background，返回初始游戏状态快照。
    """
    global player, engine, current_room, current_event

    # 深拷贝初始房间数据，防止多次 /start 时互相污染
    player        = PlayerState(name=req.name, background=req.background)
    engine        = MapEngine(rooms=copy.deepcopy(INITIAL_ROOMS))

    start_id      = player.current_room_id
    current_room  = engine.enter_room(player, start_id)
    current_event = ai.generate_room(current_room, player.to_summary())

    return _build_state_snapshot()


@app.post("/api/action")
async def do_action(req: ActionRequest) -> Dict[str, Any]:
    """
    执行行动选项。
    流程：D20 检定 → AI 裁定结果 → 应用 delta → 返回最新状态。
    """
    global current_event
    _ensure_started()

    # 从快照中取出当前行动选项列表
    snapshot     = _build_state_snapshot()
    action_opts  = [o for o in snapshot["options"] if o["type"] == "action"]

    # 将 action_index 映射到行动选项（允许传 1-based index 或绝对 index）
    target = next((o for o in action_opts if o["index"] == req.action_index), None)
    if target is None:
        raise HTTPException(
            status_code=422,
            detail=f"无效的 action_index: {req.action_index}，当前行动选项 index 为 "
                   f"{[o['index'] for o in action_opts]}",
        )

    opt_text = target["text"]
    player.log_event(f"在「{current_room['name']}」选择了: {opt_text}")

    # D20 检定（以当前 HP 作为基准，与终端版一致）
    success, roll_val = skill_check(player.hp)

    # AI 裁定行动结果
    result = ai.resolve_action(
        action_text=opt_text,
        room_name=current_room["name"],
        player_summary=player.to_summary(),
        roll_result=roll_val,
    )

    # 应用数值变化
    _apply_event_deltas(player, result)

    # 将本次行动结果叙事注入 current_event，前端可直接展示
    current_event = {
        **current_event,
        "narration": result["narration"],
        "roll_result": roll_val,
        "roll_success": success,
    }

    state = _build_state_snapshot()
    state["action_result"] = {
        "roll_result":  roll_val,
        "roll_success": success,
        "narration":    result["narration"],
        "hp_delta":     result.get("hp_delta", 0),
        "san_delta":    result.get("san_delta", 0),
        "new_item":     result.get("new_item"),
    }
    return state


@app.post("/api/move")
async def do_move(req: MoveRequest) -> Dict[str, Any]:
    """
    执行移动。
    流程：查找目标房间 → 若未知则 explore_new_room → enter_room → 生成新遭遇 → 返回最新状态。
    """
    global current_room, current_event
    _ensure_started()

    key = req.direction_key.lower()
    if key not in ("w", "a", "s", "d"):
        raise HTTPException(status_code=422, detail="direction_key 必须为 w / a / s / d")

    # 在当前房间的连接中找到对应方向
    connections = engine.get_connections(player.current_room_id)
    conn = next((c for c in connections if c.get("key") == key), None)

    if conn is None:
        raise HTTPException(status_code=422, detail=f"当前房间没有方向 '{key}' 的通路")

    target_id = conn["room_id"]

    # 占位房间 / 未知区域：调用 AI 生成新房间
    if target_id.startswith("__unexplored_") or not engine.has_room(target_id):
        # 移除占位连接条目
        cur_room_data = engine.get_room(player.current_room_id)
        if cur_room_data and target_id.startswith("__unexplored_"):
            cur_room_data["connected_rooms"] = [
                c for c in cur_room_data["connected_rooms"]
                if c["room_id"] != target_id
            ]

        target_id = explore_new_room(
            ai, engine, player,
            from_room_id=player.current_room_id,
            key=key,
        )

    current_room  = engine.enter_room(player, target_id)
    current_event = ai.generate_room(current_room, player.to_summary())

    # 记者背景：进入新房间额外记录碎片线索（GDD §2.2）
    if player.background == "journalist":
        player.log_event(f"[线索] 于「{current_room['name']}」发现碎片线索")

    return _build_state_snapshot()


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
