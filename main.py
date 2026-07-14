"""
Ember Vanguard — Milestone 1 骨架
GDD: AI 驱动的终端诡宅冒险 (克苏鲁风格)

架构：节点图 (Node Graph) + 纯选项驱动
玩家所有移动和探索均通过输入数字选项完成。
"""

import os
import sys
from typing import Dict, List, Optional

# ─────────────────────────────────────────────
# 角色背景初始属性
# ─────────────────────────────────────────────

BACKGROUND_STATS: Dict[str, dict] = {
    "journalist": {"hp": 8,  "san": 7,  "label": "记者"},
    "doctor":     {"hp": 7,  "san": 9,  "label": "医生"},
    "looter":     {"hp": 10, "san": 5,  "label": "盗墓者"},
}


# ─────────────────────────────────────────────
# 玩家状态 (PlayerState)
# ─────────────────────────────────────────────

class PlayerState:
    """核心玩家状态，对应 GDD §5.1。使用 current_room_id 替代坐标。"""

    def __init__(self, name: str = "调查者", background: str = "journalist") -> None:
        if background not in BACKGROUND_STATS:
            background = "journalist"
        stats = BACKGROUND_STATS[background]

        self.name: str             = name
        self.background: str       = background
        self.hp: int               = stats["hp"]
        self.max_hp: int           = stats["hp"]
        self.san: int              = stats["san"]
        self.max_san: int          = stats["san"]
        self.inventory: List[str]  = []
        self.curse_level: int      = 0
        self.rooms_visited: int    = 0
        self.key_events: List[str] = []
        self.current_room_id: str  = "entrance_hall"

    # ── 状态修改方法 ──────────────────────────

    def apply_damage(self, amount: int) -> None:
        self.hp = max(0, self.hp - amount)

    def apply_heal(self, amount: int) -> None:
        self.hp = min(self.max_hp, self.hp + amount)

    def apply_san_loss(self, amount: int) -> None:
        self.san = max(0, self.san - amount)

    def apply_san_gain(self, amount: int) -> None:
        self.san = min(self.max_san, self.san + amount)

    def is_alive(self) -> bool:
        return self.hp > 0

    def is_sane(self) -> bool:
        return self.san > 0

    def add_item(self, item: str, cursed: bool = False) -> None:
        self.inventory.append(item)
        if cursed:
            self.curse_level += 1
            self.key_events.append(f"获得受诅物: {item}")

    def log_event(self, event: str) -> None:
        self.key_events.append(event)

    def to_summary(self) -> dict:
        """返回用于 AI Prompt 注入的状态摘要。"""
        return {
            "name":          self.name,
            "background":    self.background,
            "hp":            self.hp,
            "max_hp":        self.max_hp,
            "san":           self.san,
            "max_san":       self.max_san,
            "inventory":     self.inventory,
            "curse_level":   self.curse_level,
            "rooms_visited": self.rooms_visited,
            "key_events":    self.key_events[-5:],
        }


# ─────────────────────────────────────────────
# 地图引擎 (MapEngine) — 节点图
# ─────────────────────────────────────────────

# 房间数据结构：
# {
#   "name":           str,          # 房间名称
#   "description":    str,          # 房间描述
#   "visited":        bool,         # 是否已探索
#   "connected_rooms": [            # 可前往的相邻节点
#       {"room_id": str, "direction": str},  # direction 为方向/描述文字
#       ...
#   ]
# }

INITIAL_ROOMS: Dict[str, dict] = {
    "entrance_hall": {
        "name": "入口大厅",
        "description": (
            "你站在庄园的入口大厅。\n"
            "铁制的枝形吊灯挂在头顶，蜡烛早已熄灭，但烛泪\n"
            "依然新鲜。空气中弥漫着腐烂的甜味，四壁的油画\n"
            "无一例外地将目光投向同一个方向——向北。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "library",     "direction": "向北 → 腐烂的图书室", "key": "w"},
            {"room_id": "cellar_door", "direction": "向下 → 地窖入口",     "key": "s"},
        ],
    },
    "library": {
        "name": "腐烂的图书室",
        "description": (
            "架子上的书籍早已腐烂，纸张凝结成黑色的砖块。\n"
            "但其中一本的封面依然清晰——它的标题用你不认识\n"
            "的文字写就，却莫名令你感到窒息。\n"
            "窗外透进一缕灰白的光，照亮了桌上的日记残页。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "entrance_hall", "direction": "向南 → 返回入口大厅", "key": "s"},
            {"room_id": "study",         "direction": "向东 → 密闭的书房",   "key": "d"},
            {"room_id": "greenhouse",    "direction": "向北 → 破碎的温室",   "key": "w"},
        ],
    },
    "cellar_door": {
        "name": "地窖入口",
        "description": (
            "一扇向下倾斜的木门，门缝里透出蓝白色的微光。\n"
            "踏上台阶的瞬间，木板发出令人不安的呻吟声。\n"
            "黑暗从下方涌上来，像是有什么东西在屏住呼吸。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "entrance_hall", "direction": "向上 → 返回入口大厅", "key": "w"},
            {"room_id": "ritual_room",   "direction": "深入 → 封闭的祭祀间", "key": "s"},
        ],
    },
    "study": {
        "name": "密闭的书房",
        "description": (
            "书桌上摆着一盏煤油灯，火焰是不自然的蓝色。\n"
            "蜡烛旁放着一封未寄出的信，信封上只写着你的名字。\n"
            "信封没有被拆开过，但墨迹新鲜得令人不安。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "library",   "direction": "向西 → 返回图书室", "key": "a"},
            {"room_id": "attic",     "direction": "向上 → 倾斜的阁楼", "key": "w"},
        ],
    },
    "greenhouse": {
        "name": "破碎的温室",
        "description": (
            "玻璃穹顶大半已经碎裂，枯萎的植株盘踞在铁架上。\n"
            "其中一株似乎还活着——它的根茎呈黑紫色，\n"
            "在无风的空气里缓慢地摆动，像是在追踪某种气味。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "library", "direction": "向南 → 返回图书室", "key": "s"},
        ],
    },
    "ritual_room": {
        "name": "封闭的祭祀间",
        "description": (
            "地面刻着巨大的符文圆阵，颜色介于锈红与黑色之间。\n"
            "圆阵的中心放着一个密封的金属盒，盒子表面温热，\n"
            "像是内部藏着某个还活着的东西。\n"
            "空气在这里变得极为沉重，每一次呼吸都像是在挣扎。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "cellar_door", "direction": "向上 → 返回地窖入口", "key": "w"},
        ],
    },
    "attic": {
        "name": "倾斜的阁楼",
        "description": (
            "阁楼的地板向一侧倾斜，你不得不扶着墙才能站稳。\n"
            "角落里堆着数个被白布遮盖的物体，形状各异。\n"
            "其中一个白布覆盖物的高度，与一个蜷缩的人完全相同。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "study", "direction": "向下 → 返回书房", "key": "s"},
        ],
    },
}


class MapEngine:
    """
    节点图地图引擎。
    键: room_id (str)；值: 房间数据字典。
    """

    def __init__(self, rooms: Dict[str, dict]) -> None:
        self._rooms: Dict[str, dict] = rooms

    def get_room(self, room_id: str) -> Optional[dict]:
        return self._rooms.get(room_id)

    def has_room(self, room_id: str) -> bool:
        return room_id in self._rooms

    def mark_visited(self, room_id: str) -> None:
        if room_id in self._rooms:
            self._rooms[room_id]["visited"] = True

    def enter_room(self, player: "PlayerState", room_id: str) -> dict:
        """
        进入指定 room_id 的房间：
        - 若首次进入，rooms_visited +1
        - 标记为已探索
        - 更新 player.current_room_id
        """
        room = self._rooms[room_id]
        if not room["visited"]:
            player.rooms_visited += 1
        self.mark_visited(room_id)
        player.current_room_id = room_id
        return room

    def get_connections(self, room_id: str) -> List[dict]:
        """返回当前房间的 connected_rooms 列表。"""
        room = self._rooms.get(room_id)
        if room is None:
            return []
        return room.get("connected_rooms", [])

    def is_visited(self, room_id: str) -> bool:
        room = self._rooms.get(room_id)
        if room is None:
            return False
        return room.get("visited", False)


# ─────────────────────────────────────────────
# Mock AI 响应  (GDD §5.2 格式)
# ─────────────────────────────────────────────

# Milestone 2 将此函数替换为真实 Ollama 调用。
_MOCK_EVENTS: List[dict] = [
    {
        "narration": (
            "画像中的人突然发出一声无声的尖叫——\n"
            "你的精神受到了剧烈冲击，双手不受控制地颤抖。\n"
            "窗外的风声消失了，整个房间陷入死寂。"
        ),
        "hp_delta":  0,
        "san_delta": -2,
        "new_item":  None,
        "is_cursed": False,
        "options": [
            {"key": "1", "text": "仔细检查画像，寻找隐藏的信息"},
            {"key": "2", "text": "转身离开，不想在此多做停留"},
            {"key": "3", "text": "用手帕遮住眼睛，强迫自己继续前进"},
        ],
    },
    {
        "narration": (
            "地板下传来低沉的摩擦声，\n"
            "像是某种巨大的东西在缓慢移动。\n"
            "你感到脚下的木板微微震颤，尘埃从缝隙中渗出。"
        ),
        "hp_delta":  0,
        "san_delta": -1,
        "new_item":  None,
        "is_cursed": False,
        "options": [
            {"key": "1", "text": "跪下来，把耳朵贴近地板仔细倾听"},
            {"key": "2", "text": "迅速后退，远离震动区域"},
            {"key": "3", "text": "用力跺脚，试图引发回应"},
        ],
    },
    {
        "narration": (
            "桌上有一本打开的日记，最后一行写道：\n"
            "「它已经在里面了，我只是还没意识到。」\n"
            "纸张泛黄，但墨迹新鲜得令人不安。"
        ),
        "hp_delta":  0,
        "san_delta": -1,
        "new_item":  "泛黄的日记残页",
        "is_cursed": False,
        "options": [
            {"key": "1", "text": "翻阅日记，试图找到更多线索"},
            {"key": "2", "text": "将日记带走，留待之后细读"},
            {"key": "3", "text": "放下日记，不想被它的内容侵扰"},
        ],
    },
    {
        "narration": (
            "墙角的镜子映出了你的倒影——\n"
            "但那个倒影比你慢了整整半秒才跟上动作。\n"
            "你盯着它，它也盯着你，嘴角缓缓上扬。"
        ),
        "hp_delta":  0,
        "san_delta": -3,
        "new_item":  None,
        "is_cursed": False,
        "options": [
            {"key": "1", "text": "靠近镜子，看清那张脸究竟是什么"},
            {"key": "2", "text": "砸碎镜子，眼不见为净"},
            {"key": "3", "text": "背对镜子站立，强迫自己无视它"},
        ],
    },
    {
        "narration": (
            "一个小小的金属圆盒出现在地板中央，\n"
            "盒盖雕刻着你从未见过的符文。\n"
            "它的表面微微发热，像是有什么东西在里面搏动。"
        ),
        "hp_delta":  0,
        "san_delta": -1,
        "new_item":  "封印的金属圆盒",
        "is_cursed": True,
        "options": [
            {"key": "1", "text": "拾起圆盒，揣进口袋"},
            {"key": "2", "text": "用布包裹圆盒后小心拾起"},
            {"key": "3", "text": "原地不动，假装没有看见它"},
        ],
    },
]


def mock_ai_response(room_id: str) -> dict:
    """
    返回符合 GDD §5.2 格式的静态 mock 事件字典。
    利用 room_id 哈希选取不同内容，避免所有房间完全相同。
    Milestone 2 替换为真实 Ollama 调用。
    """
    idx = abs(hash(room_id)) % len(_MOCK_EVENTS)
    return _MOCK_EVENTS[idx]


# ─────────────────────────────────────────────
# 终端 UI 工具
# ─────────────────────────────────────────────

def clear_screen() -> None:
    os.system("clear" if os.name != "nt" else "cls")


def _bar(current: int, maximum: int, width: int = 10,
         fill: str = "█", empty: str = "░") -> str:
    if maximum <= 0:
        return empty * width
    filled = round(current / maximum * width)
    return fill * filled + empty * (width - filled)


def render_hud(player: PlayerState) -> None:
    """顶部 HUD：角色信息 / HP / SAN / 物品栏 / 诅咒值"""
    bg_label = BACKGROUND_STATS[player.background]["label"]
    sep = "─" * 58

    hp_bar  = _bar(player.hp,  player.max_hp)
    san_bar = _bar(player.san, player.max_san, fill="▓")

    inv_str      = "、".join(player.inventory) if player.inventory else "（空）"
    curse_stars  = "★" * player.curse_level + "☆" * max(0, 4 - player.curse_level)

    print(sep)
    print(
        f"  {player.name} [{bg_label}]"
        f"   当前房间: {player.current_room_id}"
        f"   已探索: {player.rooms_visited} 间"
    )
    print(
        f"  HP  {hp_bar} {player.hp:2d}/{player.max_hp}"
        f"   SAN {san_bar} {player.san:2d}/{player.max_san}"
        f"   诅咒 {curse_stars}"
    )
    print(f"  物品栏: {inv_str}")
    print(sep)


def _display_width(s: str) -> int:
    """计算字符串的终端显示宽度（中日韩字符占2列，其余占1列）。"""
    width = 0
    for ch in s:
        cp = ord(ch)
        # CJK 统一汉字、全角标点等宽度为 2
        if (
            0x1100 <= cp <= 0x115F or   # Hangul Jamo
            0x2E80 <= cp <= 0x303E or   # CJK Radicals / Kangxi
            0x3040 <= cp <= 0x33FF or   # Hiragana / Katakana / CJK symbols
            0x3400 <= cp <= 0x4DBF or   # CJK Extension A
            0x4E00 <= cp <= 0x9FFF or   # CJK Unified
            0xA000 <= cp <= 0xA4CF or   # Yi
            0xAC00 <= cp <= 0xD7AF or   # Hangul Syllables
            0xF900 <= cp <= 0xFAFF or   # CJK Compatibility
            0xFE10 <= cp <= 0xFE1F or   # Vertical Forms
            0xFE30 <= cp <= 0xFE6F or   # CJK Compatibility Forms
            0xFF01 <= cp <= 0xFF60 or   # Fullwidth Forms
            0x20000 <= cp <= 0x2FFFD or # CJK Extension B-F
            0x30000 <= cp <= 0x3FFFD
        ):
            width += 2
        else:
            width += 1
    return width


def _pad_to_width(s: str, target_w: int, align: str = "center") -> str:
    """将字符串填充至 target_w 显示宽度（按显示宽度居中/左/右对齐）。"""
    cur = _display_width(s)
    total_pad = max(0, target_w - cur)
    if align == "center":
        lpad = total_pad // 2
        rpad = total_pad - lpad
    elif align == "left":
        lpad, rpad = 0, total_pad
    else:
        lpad, rpad = total_pad, 0
    return " " * lpad + s + " " * rpad


def render_full_map(engine: MapEngine, current_room_id: str) -> None:
    """
    渲染已探索房间的全图（未探索房间完全隐藏）。
    用纯字符串行列表构建画布，每列单位 = 1个显示宽度，
    彻底解决中文字符宽度导致的对齐问题。
    """
    # ── 房间布局：(grid_col, grid_row)，逻辑格坐标 ──────────
    LAYOUT: dict[str, tuple[int, int]] = {
        "greenhouse":    (0, 0),
        "attic":         (2, 0),
        "library":       (0, 1),
        "study":         (2, 1),
        "entrance_hall": (0, 2),
        "cellar_door":   (0, 3),
        "ritual_room":   (0, 4),
    }

    # 每个房间框的显示宽度（含两侧边框字符，不含边距）
    # 中文房间名最长5个字=10显示宽，加"  "内边距=14，加左右框=16
    BOX_INNER_W = 14   # 框内可用显示宽度（含内边距）
    BOX_H       = 3    # 框高（行数）：顶边 + 名称行 + 底边
    COL_GAP     = 6    # 相邻列之间的间隔（显示字符数）
    ROW_GAP     = 1    # 相邻行之间的间隔（行数）

    BOX_TOTAL_W = BOX_INNER_W + 2   # 含左右框字符：16

    # ── 仅处理已探索的房间 ──────────────────────────────────
    visible: set[str] = {
        rid for rid in LAYOUT
        if engine.is_visited(rid) or rid == current_room_id
    }

    if not visible:
        return

    # ── 计算每个逻辑格在画布中的像素起点 ───────────────────
    max_gcol = max(LAYOUT[rid][0] for rid in visible)
    max_grow = max(LAYOUT[rid][1] for rid in visible)

    # 逻辑列 → 起始显示列（x）
    col_x: dict[int, int] = {}
    x = 2   # 左边距
    for gc in range(max_gcol + 1):
        col_x[gc] = x
        x += BOX_TOTAL_W + COL_GAP

    # 逻辑行 → 起始画布行（y）
    row_y: dict[int, int] = {}
    y = 0
    for gr in range(max_grow + 1):
        row_y[gr] = y
        y += BOX_H + ROW_GAP

    canvas_h = y + 1
    canvas_w = x + 4

    # ── 画布：每行是一个「显示宽度」列表，初始化为空格 ───────
    # 用列表存储每行字符串，输出时直接 join
    # 为正确处理宽字符，存储为「每个显示列一个格子」
    # 格子内容为单个字符（宽字符存在左格，右格存占位符 "\x00"）
    canvas: list[list[str]] = [[" "] * canvas_w for _ in range(canvas_h)]

    def _put(r: int, c: int, ch: str) -> None:
        """在画布 (r, c) 写入字符，宽字符自动占两列。"""
        if r < 0 or r >= canvas_h or c < 0 or c >= canvas_w:
            return
        w = _display_width(ch)
        canvas[r][c] = ch
        if w == 2 and c + 1 < canvas_w:
            canvas[r][c + 1] = "\x00"   # 右半占位，输出时跳过

    def _put_str(r: int, c: int, s: str) -> None:
        cur_c = c
        for ch in s:
            _put(r, cur_c, ch)
            cur_c += _display_width(ch)

    # ── 记录每个房间框的连接锚点 ────────────────────────────
    # top_anchor:   顶边中心 (row, col)，用于向上的竖线
    # bot_anchor:   底边中心 (row, col)，用于向下的竖线
    # left_anchor:  左边中心 (row, col)，用于向左的横线
    # right_anchor: 右边中心 (row, col)，用于向右的横线
    # mid_row:      内容行行号（同行横线在此行走）
    room_anchors: dict[str, dict[str, tuple[int, int]]] = {}

    # ── 绘制已探索房间的框 ───────────────────────────────────
    for room_id in visible:
        gc, gr = LAYOUT[room_id]
        bx = col_x[gc]   # 框左上角显示列
        by = row_y[gr]   # 框左上角行

        is_here = (room_id == current_room_id)
        name    = engine.get_room(room_id)["name"]   # type: ignore[index]

        # 按显示宽度截断名称
        inner_content_w = BOX_INNER_W - 2   # 去掉左右各1格内边距
        truncated = ""
        tw = 0
        for ch in name:
            cw = _display_width(ch)
            if tw + cw > inner_content_w:
                truncated += "…"
                break
            truncated += ch
            tw += cw

        # 收集该房间的出口方向
        room_data = engine.get_room(room_id)
        exit_keys: set[str] = set()
        if room_data:
            for conn in room_data.get("connected_rooms", []):
                k = conn.get("key", "")
                if k in ("w", "a", "s", "d"):
                    exit_keys.add(k)

        # 框字符
        if is_here:
            tl, tr_, bl, br_, h, v = "╔", "╗", "╚", "╝", "═", "║"
        else:
            tl, tr_, bl, br_, h, v = "┌", "┐", "└", "┘", "─", "│"

        # 顶/底边中间留空缺的列偏移（框内显示宽度中心）
        gap_off = 1 + BOX_INNER_W // 2   # 相对于 bx 的偏移，指向中间格
        GAP_HALF = 1   # 空缺半宽：中心左右各 GAP_HALF 格，共 2*GAP_HALF+1 格

        # ── 顶边（有 w 出口则中心3格留空缺）──
        _put_str(by, bx, tl + h * BOX_INNER_W + tr_)
        if "w" in exit_keys:
            for _g in range(-GAP_HALF, GAP_HALF + 1):
                _put(by, bx + gap_off + _g, " ")

        # ── 名称行（有 a/d 出口则对应竖线留空缺）──
        content = _pad_to_width(truncated, BOX_INNER_W)
        _put(by + 1, bx,                     " " if "a" in exit_keys else v)
        _put_str(by + 1, bx + 1, content)
        _put(by + 1, bx + 1 + BOX_INNER_W,  " " if "d" in exit_keys else v)

        # ── 底边（有 s 出口则中心3格留空缺）──
        _put_str(by + 2, bx, bl + h * BOX_INNER_W + br_)
        if "s" in exit_keys:
            for _g in range(-GAP_HALF, GAP_HALF + 1):
                _put(by + 2, bx + gap_off + _g, " ")

        # 锚点：放在框边线上的空缺处（连线直接从这里延伸出去）
        mid_row = by + 1
        top_col = bx + gap_off
        room_anchors[room_id] = {
            "top":     (by,                      top_col),              # 顶边空缺
            "bot":     (by + 2,                  top_col),              # 底边空缺
            "left":    (mid_row,                 bx),                   # 左侧竖线空缺
            "right":   (mid_row,                 bx + 1 + BOX_INNER_W), # 右侧竖线空缺
            "mid_row": (mid_row,                 top_col),
        }

    # ── 判断两房间相对方向并选择锚点 ─────────────────────────
    def _pick_anchors(
        id1: str, id2: str
    ) -> tuple[tuple[int, int], tuple[int, int]]:
        """返回 (id1 出发锚点, id2 到达锚点)，根据逻辑格位置判断方向。"""
        gc1, gr1 = LAYOUT[id1]
        gc2, gr2 = LAYOUT[id2]
        a1 = room_anchors[id1]
        a2 = room_anchors[id2]

        if gc1 == gc2:
            # 同列：竖向连线
            if gr1 < gr2:
                return a1["bot"], a2["top"]
            else:
                return a1["top"], a2["bot"]
        elif gr1 == gr2:
            # 同行：横向连线
            if gc1 < gc2:
                return a1["right"], a2["left"]
            else:
                return a1["left"], a2["right"]
        else:
            # 不同行不同列：L 形折线，从 id1 的右/左出发，到 id2 的上/下
            if gc1 < gc2:
                return a1["right"], a2["top"]
            else:
                return a1["left"], a2["top"]

    # ── 绘制连线（两端均已探索才画）────────────────────────
    drawn_edges: set[frozenset] = set()

    for room_id in visible:
        room = engine.get_room(room_id)
        if room is None:
            continue
        for conn in room.get("connected_rooms", []):
            target_id = conn["room_id"]
            if target_id not in visible:
                continue
            edge: frozenset = frozenset({room_id, target_id})
            if edge in drawn_edges:
                continue
            drawn_edges.add(edge)

            (r1, c1), (r2, c2) = _pick_anchors(room_id, target_id)
            gc1, gr1 = LAYOUT[room_id]
            gc2, gr2 = LAYOUT[target_id]

            if gc1 == gc2:
                # 纯竖线：只在两框之间的空白行（不含框线本身）画 │
                # 框线上的空缺已留空，视觉上自然形成通道
                for r in range(min(r1, r2) + 1, max(r1, r2)):
                    if canvas[r][c1] == " ":
                        _put(r, c1, "│")
            elif gr1 == gr2:
                # 纯横线：只在两框之间的空白列画 ─（框线上的空缺留空）
                for c in range(min(c1, c2) + 1, max(c1, c2)):
                    if canvas[r1][c] == " ":
                        _put(r1, c, "─")
            else:
                # L 形：横段从 c1 外侧一格走到 c2，再从 r1 竖走到 r2
                step_c = 1 if c2 > c1 else -1
                c = c1 + step_c
                while c != c2:
                    if canvas[r1][c] == " ":
                        _put(r1, c, "─")
                    c += step_c
                # 转角
                _put(r1, c2, "┐" if c2 < c1 else "┌")
                # 竖段（不含转角行，不含目标框边）
                step_r = 1 if r2 > r1 else -1
                r = r1 + step_r
                while r != r2:
                    if canvas[r][c2] == " ":
                        _put(r, c2, "│")
                    r += step_r

    # ── 渲染输出 ─────────────────────────────────────────────
    sep = "─" * 54
    print(f"\n  {sep}")
    print("    灰石庄园 — 全图（仅显示已探索区域）")
    print(f"  {sep}")
    for row_cells in canvas:
        parts = []
        skip = False
        for cell in row_cells:
            if skip:
                skip = False
                continue
            if cell == "\x00":
                continue
            parts.append(cell)
            if _display_width(cell) == 2:
                skip = True
        line = "  " + "".join(parts).rstrip()
        if line.strip():
            print(line)
    print()
    print("    ╔═╗ 当前位置    ┌─┐ 已探索")
    print(f"  {sep}\n")


def render_room(room: dict, event: dict) -> None:
    """渲染当前房间名称、房间描述与遭遇叙事。"""
    print(f"\n  ◆ {room['name']}\n")
    for line in room["description"].splitlines():
        print(f"    {line}")
    print()
    print("  " + "·" * 54)
    print()
    for line in event["narration"].splitlines():
        print(f"    {line}")
    print()


def render_options(event: dict, connections: List[dict],
                   engine: MapEngine) -> List[dict]:
    """
    渲染房间内互动选项（来自 mock_ai_response）与移动选项（来自 connected_rooms）。
    返回一个统一的选项列表，格式: [{"type": "action"|"move", ...}, ...]
    以便主循环根据玩家输入编号定位。
    """
    unified: List[dict] = []

    # ── 房间内行动选项 ────────────────────────
    print("  ── 你的选择 ─────────────────────────────────────")
    for opt in event["options"]:
        n = len(unified) + 1
        print(f"    [{n}] {opt['text']}")
        unified.append({"type": "action", "data": opt})

    print()

    # ── 移动选项（wasd 按键绑定）──────────────
    # key → 显示标签
    KEY_LABEL = {"w": "W ↑", "s": "S ↓", "a": "A ←", "d": "D →"}
    # 按固定顺序排列：w s a d（其余兜底）
    KEY_ORDER = ["w", "a", "s", "d"]
    sorted_conns = sorted(
        connections,
        key=lambda c: KEY_ORDER.index(c.get("key", "")) if c.get("key", "") in KEY_ORDER else 99,
    )

    print("  ── 移动 ─────────────────────────────────────────")
    if not sorted_conns:
        print("    （此处没有通路）")
    else:
        for conn in sorted_conns:
            target_id  = conn["room_id"]
            key        = conn.get("key", "?")
            is_visited = engine.is_visited(target_id)
            key_label  = KEY_LABEL.get(key, f"{key.upper()} ·")

            if is_visited:
                raw = conn["direction"]
                dest = raw.split("→")[-1].strip() if "→" in raw else raw
                print(f"    [{key_label}]  {dest}")
            else:
                raw = conn["direction"]
                dir_only = raw.split("→")[0].strip() if "→" in raw else raw
                print(f"    [{key_label}]  {dir_only}  ···")
            unified.append({"type": "move", "data": conn})

    print()
    print("  ── 其他 ─────────────────────────────────────────")
    quit_n = len(unified) + 1
    print(f"    [{quit_n}] 放弃探索，离开游戏")
    unified.append({"type": "quit", "data": {}})
    print()

    return unified


# ─────────────────────────────────────────────
# 事件效果应用
# ─────────────────────────────────────────────

def apply_event_deltas(player: PlayerState, event: dict) -> None:
    """
    将遭遇 JSON 中的 hp_delta / san_delta / new_item 应用到玩家状态。
    Milestone 1：进入新房间时自动触发一次。
    Milestone 3 起改为选项选择后触发。
    """
    hp_delta  = event.get("hp_delta",  0)
    san_delta = event.get("san_delta", 0)
    new_item  = event.get("new_item",  None)
    is_cursed = event.get("is_cursed", False)

    if hp_delta < 0:
        player.apply_damage(-hp_delta)
    elif hp_delta > 0:
        player.apply_heal(hp_delta)

    if san_delta < 0:
        player.apply_san_loss(-san_delta)
    elif san_delta > 0:
        player.apply_san_gain(san_delta)

    if new_item:
        player.add_item(new_item, cursed=is_cursed)


# ─────────────────────────────────────────────
# 开场文本
# ─────────────────────────────────────────────

OPENING_TEXT = """
  铁门在你身后轰然关闭。
  黑暗吞没了来时的路。
  空气中有一股腐烂的甜味——
  像是某种东西正在等待你。

  你握紧手中的手电筒，向前走去。
"""


# ─────────────────────────────────────────────
# 主循环 (Main Loop)
# ─────────────────────────────────────────────

def main() -> None:
    clear_screen()

    # ── 开场叙事 ──────────────────────────────
    print("=" * 58)
    print("             EMBER VANGUARD — 诡宅冒险")
    print("=" * 58)
    print(OPENING_TEXT)
    input("  按 Enter 键开始探索...")

    # ── 初始化 ────────────────────────────────
    player = PlayerState(name="调查者", background="journalist")
    engine = MapEngine(rooms=INITIAL_ROOMS)

    # 进入起始房间
    start_id      = player.current_room_id
    current_room  = engine.enter_room(player, start_id)
    current_event = mock_ai_response(start_id)

    # ── 主循环 ────────────────────────────────
    while True:
        # 1. 清屏
        clear_screen()

        # 2. 顶部 HUD
        render_hud(player)

        # 3. 全图
        render_full_map(engine, player.current_room_id)

        # 4. 房间描述 + 遭遇叙事
        render_room(current_room, current_event)

        # 5. 渲染选项（行动 + 移动合并编号），获取统一列表
        connections   = engine.get_connections(player.current_room_id)
        unified_opts  = render_options(current_event, connections, engine)

        # 6. 接收输入
        try:
            raw = input("  > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n  游戏中断。愿你安然离开这里。\n")
            sys.exit(0)

        if not raw:
            continue

        # ── 优先解析 wasd 字母移动 ─────────────
        key_input = raw.lower()
        if key_input in ("w", "a", "s", "d"):
            # 在 unified_opts 中找对应 key 的 move 项
            matched = next(
                (opt for opt in unified_opts
                 if opt["type"] == "move" and opt["data"].get("key") == key_input),
                None,
            )
            if matched is None:
                input(f"  [!] 此方向没有通路，按 Enter 继续...")
                continue
            selected = matched
        else:
            # ── 解析数字选项 ───────────────────
            try:
                choice = int(raw)
            except ValueError:
                input("  [!] 请输入 wasd 移动，或输入数字选择行动，按 Enter 继续...")
                continue

            if choice < 1 or choice > len(unified_opts):
                input(f"  [!] 请输入 1 ~ {len(unified_opts)} 之间的数字，按 Enter 继续...")
                continue

            selected = unified_opts[choice - 1]

        # ── 处理行动选项 ───────────────────────
        if selected["type"] == "action":
            opt = selected["data"]
            player.log_event(
                f"在「{current_room['name']}」选择了: {opt['text']}"
            )
            # Milestone 1：仅记录，不触发判定
            # Milestone 3 起：skill_check + AI 意图解析 + apply_event_deltas
            input("  [·] 你做出了选择。（Milestone 3 接入后此处将触发判定）按 Enter 继续...")

        # ── 处理移动选项 ───────────────────────
        elif selected["type"] == "move":
            conn         = selected["data"]
            target_id    = conn["room_id"]
            current_room  = engine.enter_room(player, target_id)
            current_event = mock_ai_response(target_id)

            # 进入新房间自动触发遭遇效果（Milestone 3 前的简化处理）
            apply_event_deltas(player, current_event)

            # 记者背景：进入新房间额外记录碎片线索（GDD §2.2）
            if player.background == "journalist":
                player.log_event(f"[线索] 于「{current_room['name']}」发现碎片线索")

            # 死亡检测（简化版，Milestone 4 完善）
            if not player.is_alive():
                clear_screen()
                render_hud(player)
                print("\n  ██ 你倒下了。")
                print("  庄园将你永远留在了这里。\n")
                print("  [ 游戏结束 ]\n")
                sys.exit(0)

            if not player.is_sane():
                clear_screen()
                render_hud(player)
                print("\n  ██ 你的理智彻底崩溃。")
                print("  你听见自己在笑，却无法停下来。\n")
                print("  [ 游戏结束 — 融合·成为祭品 ]\n")
                sys.exit(0)

        # ── 处理退出 ───────────────────────────
        elif selected["type"] == "quit":
            clear_screen()
            print("\n  你转身，发现铁门已经消失。")
            print("  也许你从未真正离开过这里。\n")
            sys.exit(0)


# ─────────────────────────────────────────────
if __name__ == "__main__":
    main()
