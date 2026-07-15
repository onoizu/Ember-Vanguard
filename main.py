"""
Ember Vanguard — Milestone 3 战斗与检定
GDD: AI 驱动的终端诡宅冒险 (克苏鲁风格)

架构：节点图 (Node Graph) + 纯选项驱动
玩家所有移动和探索均通过输入数字选项完成。
"""

import json
import os
import random
import re
import sys
import time
from typing import Dict, List, Optional, Tuple

try:
    import ollama
    _OLLAMA_AVAILABLE = True
except ImportError:
    _OLLAMA_AVAILABLE = False

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
    # ── 一楼中央 ─────────────────────────────────────────────
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
            {"room_id": "library",        "direction": "向北 → 腐烂的图书室",   "key": "w"},
            {"room_id": "dining_room",    "direction": "向东 → 阴暗的餐厅",     "key": "d"},
            {"room_id": "cellar_door",    "direction": "向下 → 地窖入口",       "key": "s"},
            {"room_id": "servants_hall",  "direction": "向西 → 仆人通道",       "key": "a"},
        ],
    },
    # ── 一楼北翼 ─────────────────────────────────────────────
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
            {"room_id": "entrance_hall",  "direction": "向南 → 返回入口大厅",   "key": "s"},
            {"room_id": "study",          "direction": "向东 → 密闭的书房",     "key": "d"},
            {"room_id": "greenhouse",     "direction": "向北 → 破碎的温室",     "key": "w"},
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
            {"room_id": "library",        "direction": "向南 → 返回图书室",     "key": "s"},
            {"room_id": "garden_ruins",   "direction": "向北 → 荒芜的花园",     "key": "w"},
            {"room_id": "observatory",    "direction": "向东 → 废弃的观测台",   "key": "d"},
        ],
    },
    "garden_ruins": {
        "name": "荒芜的花园",
        "description": (
            "铁锈斑斑的栅栏将花园封闭，杂草已长至膝盖。\n"
            "中央的喷水池早已干涸，池底刻满了看不懂的符文。\n"
            "月光照在枯枝上，投下人形的影子。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "greenhouse",     "direction": "向南 → 返回温室",       "key": "s"},
            {"room_id": "chapel",         "direction": "向西 → 破败的礼拜堂",   "key": "a"},
        ],
    },
    "observatory": {
        "name": "废弃的观测台",
        "description": (
            "铜制的望远镜依然对准天空，镜头蒙着厚厚的灰尘。\n"
            "墙上挂满了星象图，其中一幅被人用红墨水\n"
            "画出了某个特定的星座，并在旁边潦草写道：\n"
            "「它从那里来。」"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "greenhouse",     "direction": "向西 → 返回温室",       "key": "a"},
        ],
    },
    "chapel": {
        "name": "破败的礼拜堂",
        "description": (
            "长椅被推倒，碎裂的彩窗玻璃散落满地。\n"
            "祭坛上的圣像被凿去了面孔，只剩空洞的轮廓。\n"
            "空气异常寒冷，每次呼吸都能看见白雾，\n"
            "即便今晚并不算冷。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "garden_ruins",   "direction": "向东 → 返回花园",       "key": "d"},
            {"room_id": "crypt",          "direction": "向下 → 地下墓室",       "key": "s"},
        ],
    },
    # ── 一楼东翼 ─────────────────────────────────────────────
    "dining_room": {
        "name": "阴暗的餐厅",
        "description": (
            "长餐桌上摆着已经腐烂的食物，好像一场宴席\n"
            "在中途戛然而止。椅子被推倒，有几把被扯碎了。\n"
            "墙角有一个翻倒的烛台，蜡泪凝固成了人脸的形状。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "entrance_hall",  "direction": "向西 → 返回大厅",       "key": "a"},
            {"room_id": "kitchen",        "direction": "向北 → 腐败的厨房",     "key": "w"},
            {"room_id": "portrait_room",  "direction": "向东 → 肖像画廊",       "key": "d"},
        ],
    },
    "kitchen": {
        "name": "腐败的厨房",
        "description": (
            "铁锅里还剩着黑色的残渣，烟囱口结了厚厚的蜘蛛网。\n"
            "料理台上有一把菜刀，刀刃上的锈迹形状不像锈，\n"
            "更像是干涸的血。\n"
            "水槽里一直在滴水，节奏规律得像心跳。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "dining_room",    "direction": "向南 → 返回餐厅",       "key": "s"},
            {"room_id": "pantry",         "direction": "向东 → 储藏室",         "key": "d"},
        ],
    },
    "portrait_room": {
        "name": "肖像画廊",
        "description": (
            "走廊两侧挂满了家族肖像，画中人物皆着维多利亚风格礼服。\n"
            "所有人的眼睛都被涂黑，唯独最末端那幅没有——\n"
            "那幅画像的人脸与你相似得令人不寒而栗。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "dining_room",    "direction": "向西 → 返回餐厅",       "key": "a"},
            {"room_id": "music_room",     "direction": "向北 → 封尘的音乐室",   "key": "w"},
        ],
    },
    "music_room": {
        "name": "封尘的音乐室",
        "description": (
            "一架竖式钢琴立在窗边，琴盖半开，\n"
            "你进来的时候它自行弹奏了一个音符——然后停止了。\n"
            "地板上的灰尘中有脚印，通向钢琴，但没有返回的足迹。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "portrait_room",  "direction": "向南 → 返回画廊",       "key": "s"},
            {"room_id": "study",          "direction": "向西 → 密闭的书房",     "key": "a"},
        ],
    },
    "pantry": {
        "name": "储藏室",
        "description": (
            "货架上堆满了多年前的罐头和瓶装食物，大半已经胀裂。\n"
            "角落里有一个被锁住的木箱，表面刻着和祭祀间地板\n"
            "同样样式的符文。箱子在轻微地颤动。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "kitchen",        "direction": "向西 → 返回厨房",       "key": "a"},
        ],
    },
    # ── 一楼西翼 ─────────────────────────────────────────────
    "servants_hall": {
        "name": "仆人通道",
        "description": (
            "狭窄的走廊只允许一人通过，两侧墙壁留有灯架的黑痕。\n"
            "走廊尽头的窗户被木板封死，但缝隙里透进的\n"
            "不是月光，而是一种幽绿色的微光。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "entrance_hall",  "direction": "向东 → 返回大厅",       "key": "d"},
            {"room_id": "laundry_room",   "direction": "向西 → 洗衣间",         "key": "a"},
            {"room_id": "hidden_passage", "direction": "向北 → 隐秘的夹墙通道", "key": "w"},
        ],
    },
    "laundry_room": {
        "name": "洗衣间",
        "description": (
            "几件衣物还晾挂在绳子上，早已发霉变黑。\n"
            "其中一件女式连衣裙的背面有深色的掌印，\n"
            "形状不像人类的手。\n"
            "洗衣桶里的水是黑色的，纹丝不动。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "servants_hall",  "direction": "向东 → 返回仆人通道",   "key": "d"},
        ],
    },
    "hidden_passage": {
        "name": "隐秘的夹墙通道",
        "description": (
            "砖墙后面是一条只有侧身才能通过的夹缝走廊。\n"
            "空气潮湿而发霉，脚踩在地面上发出空洞的回响。\n"
            "墙上有人用手指划出的痕迹，像是某种倒计时。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "servants_hall",  "direction": "向南 → 返回仆人通道",   "key": "s"},
            {"room_id": "study",          "direction": "向东 → 密闭的书房",     "key": "d"},
        ],
    },
    # ── 二楼 ─────────────────────────────────────────────────
    "study": {
        "name": "密闭的书房",
        "description": (
            "书桌上摆着一盏煤油灯，火焰是不自然的蓝色。\n"
            "蜡烛旁放着一封未寄出的信，信封上只写着你的名字。\n"
            "信封没有被拆开过，但墨迹新鲜得令人不安。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "library",        "direction": "向西 → 返回图书室",     "key": "a"},
            {"room_id": "music_room",     "direction": "向东 → 封尘的音乐室",   "key": "d"},
            {"room_id": "attic",          "direction": "向上 → 倾斜的阁楼",     "key": "w"},
            {"room_id": "master_bedroom", "direction": "向北 → 主人卧室",       "key": "s"},
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
            {"room_id": "study",          "direction": "向下 → 返回书房",       "key": "s"},
            {"room_id": "water_tower",    "direction": "向上 → 庄园水塔",       "key": "w"},
        ],
    },
    "master_bedroom": {
        "name": "主人卧室",
        "description": (
            "巨大的四柱床立在房间正中，帷幔垂落，\n"
            "床铺上的皱褶显示有人曾经在此辗转反侧。\n"
            "床头柜上的镜子被黑布遮住，但黑布在轻微颤动，\n"
            "好像有什么东西卡在后面想出来。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "study",          "direction": "向上 → 返回书房",       "key": "w"},
            {"room_id": "guest_room",     "direction": "向东 → 客卧",           "key": "d"},
            {"room_id": "nursery",        "direction": "向西 → 儿童房",         "key": "a"},
        ],
    },
    "guest_room": {
        "name": "客卧",
        "description": (
            "房间整洁，像是从未被人住过，却有一股浓烈的香水味。\n"
            "枕头上有一个头发留下的压痕，头发还在。\n"
            "壁橱门虚掩，里面挂着一件不属于这个年代的外套。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "master_bedroom", "direction": "向西 → 返回主卧",       "key": "a"},
        ],
    },
    "nursery": {
        "name": "儿童房",
        "description": (
            "玩具散落在地板上，一辆发条小车还在缓慢地转动，\n"
            "但没有人给它上发条。\n"
            "摇篮挂在角落，随着不存在的风轻轻摇摆，\n"
            "里面有什么东西在低声哼唱。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "master_bedroom", "direction": "向东 → 返回主卧",       "key": "d"},
        ],
    },
    "water_tower": {
        "name": "庄园水塔",
        "description": (
            "锈铁楼梯通向高处的蓄水槽，水槽早已干涸。\n"
            "站在高处可以俯瞰整个庄园，但此刻你注意到——\n"
            "庄园的平面布局从上往下看，\n"
            "与那本书里记载的某个古老符文完全一致。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "attic",          "direction": "向下 → 返回阁楼",       "key": "s"},
        ],
    },
    # ── 地下层 ───────────────────────────────────────────────
    "cellar_door": {
        "name": "地窖入口",
        "description": (
            "一扇向下倾斜的木门，门缝里透出蓝白色的微光。\n"
            "踏上台阶的瞬间，木板发出令人不安的呻吟声。\n"
            "黑暗从下方涌上来，像是有什么东西在屏住呼吸。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "entrance_hall",  "direction": "向上 → 返回入口大厅",   "key": "w"},
            {"room_id": "wine_cellar",    "direction": "向下 → 酒窖",           "key": "s"},
            {"room_id": "ritual_room",    "direction": "向西 → 祭祀间",         "key": "a"},
        ],
    },
    "wine_cellar": {
        "name": "酒窖",
        "description": (
            "拱形砖顶，两侧整齐堆放着积灰的酒瓶。\n"
            "大多数酒已经挥发，只剩奇异的沉淀物附着在瓶底。\n"
            "其中一瓶的标签上写着一个日期——是明天。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "cellar_door",    "direction": "向上 → 返回地窖入口",   "key": "w"},
            {"room_id": "underground_lab","direction": "向西 → 隐秘的地下实验室","key": "a"},
        ],
    },
    "ritual_room": {
        "name": "祭祀间",
        "description": (
            "地面刻着巨大的符文圆阵，颜色介于锈红与黑色之间。\n"
            "圆阵的中心放着一个密封的金属盒，盒子表面温热，\n"
            "像是内部藏着某个还活着的东西。\n"
            "空气在这里变得极为沉重，每一次呼吸都像是在挣扎。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "cellar_door",    "direction": "向东 → 返回地窖入口",   "key": "d"},
            {"room_id": "underground_lab","direction": "向南 → 地下实验室",     "key": "s"},
        ],
    },
    "underground_lab": {
        "name": "地下实验室",
        "description": (
            "金属工作台上摆满了玻璃仪器，内装暗红色的液体，\n"
            "部分仍在以极缓慢的速度冒泡。\n"
            "黑板上写满了公式，但推导到最后一步被擦去了，\n"
            "只留下一个问号，和一行字：「它同意了。」"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "wine_cellar",    "direction": "向东 → 返回酒窖",       "key": "d"},
            {"room_id": "ritual_room",    "direction": "向北 → 返回祭祀间",     "key": "w"},
            {"room_id": "crypt",          "direction": "向下 → 地下墓室",       "key": "s"},
        ],
    },
    "crypt": {
        "name": "地下墓室",
        "description": (
            "石棺并排放置，棺盖雕刻着同一张脸。\n"
            "最中央的石棺缺少了棺盖，里面是空的——\n"
            "但石棺内壁留有爪痕，是从里面刮出来的。\n"
            "这里有某种东西曾经被关着，而现在它自由了。"
        ),
        "visited": False,
        "connected_rooms": [
            {"room_id": "underground_lab","direction": "向上 → 返回地下实验室", "key": "w"},
            {"room_id": "chapel",         "direction": "向东 → 礼拜堂",         "key": "d"},
        ],
    },
}


class MapEngine:
    """
    节点图地图引擎。
    键: room_id (str)；值: 房间数据字典。
    支持动态注册 AI 随机生成的新房间节点。
    """

    def __init__(self, rooms: Dict[str, dict]) -> None:
        self._rooms: Dict[str, dict] = rooms
        # 记录 AI 生成房间的计数，用于生成唯一 room_id
        self._ai_room_counter: int = 0

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

    def add_ai_room(self, room_data: dict, from_room_id: str, key: str) -> str:
        """
        注册一个由 AI 生成的新房间，并在来源房间中添加通道连接。
        返回新房间的 room_id。
        key: 到达新房间所使用的方向键（w/a/s/d）。
        """
        self._ai_room_counter += 1
        new_id = f"ai_room_{self._ai_room_counter}"
        room_data["visited"]  = False
        room_data["is_ai_generated"] = True
        self._rooms[new_id] = room_data

        # 在来源房间中添加通向新房间的连接
        if from_room_id in self._rooms:
            conn_entry = {
                "room_id":   new_id,
                "direction": f"{_KEY_TO_DIRECTION.get(key, key)} → {room_data['name']}",
                "key":       key,
            }
            self._rooms[from_room_id]["connected_rooms"].append(conn_entry)

        return new_id

    def add_connection(self, room_id: str, conn: dict) -> None:
        """向指定房间追加一个连接条目。"""
        if room_id in self._rooms:
            self._rooms[room_id]["connected_rooms"].append(conn)

    def get_all_room_ids(self) -> List[str]:
        return list(self._rooms.keys())

    def get_ai_room_count(self) -> int:
        return self._ai_room_counter


# 方向键 → 中文标签（供 add_ai_room 使用）
_KEY_TO_DIRECTION = {"w": "向北", "s": "向南", "a": "向西", "d": "向东"}


# ─────────────────────────────────────────────
# Fallback Mock 事件（AI 不可用时的保底）
# ─────────────────────────────────────────────

_MOCK_EVENTS: List[dict] = [
    {
        "narration": (
            "DM 的意志被某种力量干扰了——\n"
            "画像中的人突然发出一声无声的尖叫，\n"
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
            "DM 的意志被某种力量干扰了——\n"
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
            "DM 的意志被某种力量干扰了——\n"
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
            "DM 的意志被某种力量干扰了——\n"
            "墙角的镜子映出了你的倒影，\n"
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
            "DM 的意志被某种力量干扰了——\n"
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


def _fallback_event(room_id: str) -> dict:
    """根据 room_id 哈希选取 Fallback 事件。"""
    idx = abs(hash(room_id)) % len(_MOCK_EVENTS)
    return _MOCK_EVENTS[idx]


# ─────────────────────────────────────────────
# 检定系统 (Check System) — GDD §7 模块四
# ─────────────────────────────────────────────

def skill_check(stat_value: int, difficulty: int = 10) -> Tuple[bool, int]:
    """
    隐藏 D20 检定。
    roll: 1-20 随机数；修正值 = stat_value // 3。
    最终值 >= difficulty 即为成功。
    返回 (是否成功, 最终值)。
    """
    roll      = random.randint(1, 20)
    modified  = roll + (stat_value // 3)
    return modified >= difficulty, modified


# ─────────────────────────────────────────────
# AI Pipeline (Milestone 2 / 3)
# ─────────────────────────────────────────────

class AIPipeline:
    """
    封装 Ollama 调用，负责根据房间数据和玩家状态生成动态遭遇叙事。
    对应 GDD §7 模块三：AI 管道与遭遇生成器。
    """

    SYSTEM_PROMPT = """You are the Dungeon Master of a Cthulhu Mythos tabletop RPG set in 1923 Arkham, New England.
Your tone is horrifying, restrained, and oppressive — like Lovecraft's prose. Describe the uncanny with clinical detachment.
Never be explicit about the supernatural; let dread build through implication and wrongness.

The player is an investigator exploring a cursed manor. Each room hides secrets and sanity-eroding events.

You MUST respond with valid JSON only. No markdown. No code blocks. No explanation. Only the JSON object.

Required JSON format:
{
  "narration": "<2-4 sentences of atmospheric horror narration in Chinese, describing what the investigator encounters>",
  "hp_delta": <integer, usually 0 or negative, max -3>,
  "san_delta": <integer, usually 0 or negative, range -3 to 0>,
  "new_item": <string item name in Chinese, or null>,
  "is_cursed": <true if new_item is a cursed artifact, false otherwise>,
  "options": [
    {"key": "1", "text": "<action option in Chinese>"},
    {"key": "2", "text": "<action option in Chinese>"},
    {"key": "3", "text": "<action option in Chinese>"}
  ]
}

Rules:
- narration must be in Chinese (Simplified)
- options must contain exactly 3 choices in Chinese
- hp_delta and san_delta must be integers
- new_item is null if no item is found
- is_cursed is false if new_item is null"""

    def generate_room(self, room_data: dict, player_summary: dict) -> dict:
        """
        调用 Ollama 生成房间动态叙事事件。
        
        Args:
            room_data: 当前房间的基础数据（name, description 等）
            player_summary: 玩家状态摘要（来自 player.to_summary()）
        
        Returns:
            符合 GDD §5.2 格式的遭遇事件字典。
            若 AI 调用失败，返回 Fallback 字典。
        """
        if not _OLLAMA_AVAILABLE:
            return _fallback_event(room_data.get("name", ""))

        user_context = (
            f"Current room: {room_data.get('name', '未知房间')}\n"
            f"Room description: {room_data.get('description', '')}\n\n"
            f"Player status:\n"
            f"- Name: {player_summary['name']} ({player_summary['background']})\n"
            f"- HP: {player_summary['hp']}/{player_summary['max_hp']}\n"
            f"- Sanity: {player_summary['san']}/{player_summary['max_san']}\n"
            f"- Inventory: {', '.join(player_summary['inventory']) if player_summary['inventory'] else 'empty'}\n"
            f"- Curse level: {player_summary['curse_level']}\n"
            f"- Rooms visited: {player_summary['rooms_visited']}\n"
            f"- Recent events: {'; '.join(player_summary['key_events']) if player_summary['key_events'] else 'none'}\n\n"
            "Generate a room encounter event for this room. "
            "The horror level should scale with the player's curse level and sanity loss. "
            "Return JSON only."
        )

        try:
            response = ollama.chat(
                model="llama3.1:8b",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user",   "content": user_context},
                ],
                format="json",
            )
            raw_text = response["message"]["content"]
            return self._parse_response(raw_text, room_data.get("name", ""))

        except Exception:
            return _fallback_event(room_data.get("name", ""))

    def _parse_response(self, raw_text: str, room_id: str) -> dict:
        """
        解析 AI 返回文本为标准事件字典。
        剥离可能包裹的 Markdown 代码块，确保 json.loads() 成功。
        解析彻底失败时返回 Fallback。
        """
        # 剥离 ```json ... ``` 或 ``` ... ``` 包裹
        text = raw_text.strip()
        md_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if md_match:
            text = md_match.group(1).strip()

        # 若未被代码块包裹，尝试提取第一个 { ... } 块
        if not text.startswith("{"):
            brace_match = re.search(r"\{[\s\S]*\}", text)
            if brace_match:
                text = brace_match.group(0)

        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return _fallback_event(room_id)

        # 校验并补全必要字段，防止主循环 KeyError
        return self._validate_and_fill(data, room_id)

    def _validate_and_fill(self, data: dict, room_id: str) -> dict:
        """校验 AI 返回的字典，补全缺失字段，类型强制转换。"""
        fallback = _fallback_event(room_id)

        narration = data.get("narration")
        if not isinstance(narration, str) or not narration.strip():
            narration = fallback["narration"]

        try:
            hp_delta = int(data.get("hp_delta", 0))
        except (TypeError, ValueError):
            hp_delta = 0

        try:
            san_delta = int(data.get("san_delta", 0))
        except (TypeError, ValueError):
            san_delta = 0

        new_item  = data.get("new_item")
        if not isinstance(new_item, str) or not new_item.strip():
            new_item = None

        is_cursed = bool(data.get("is_cursed", False))
        if new_item is None:
            is_cursed = False

        raw_opts = data.get("options", [])
        options: List[dict] = []
        if isinstance(raw_opts, list):
            for i, opt in enumerate(raw_opts[:3]):
                if isinstance(opt, dict) and isinstance(opt.get("text"), str):
                    options.append({"key": str(i + 1), "text": opt["text"]})

        if not options:
            options = fallback["options"]

        return {
            "narration": narration,
            "hp_delta":  hp_delta,
            "san_delta": san_delta,
            "new_item":  new_item,
            "is_cursed": is_cursed,
            "options":   options,
        }

    # ── 行动结算 (Milestone 3) ────────────────────────────────

    ACTION_SYSTEM_PROMPT = (
        "You are the Dungeon Master of a Cthulhu Mythos tabletop RPG set in 1923 Arkham, New England.\n"
        "Your tone is horrifying, restrained, and oppressive — like Lovecraft's prose.\n"
        "The player has just taken an action. Based on their choice and the D20 roll result, determine the outcome.\n"
        "\n"
        "roll_result >= 10 means partial or full success (the action works, reduced harm).\n"
        "roll_result < 10 means failure or backfire (the action worsens the situation, increases terror).\n"
        "The lower the roll, the worse the consequence. A roll of 1-3 is catastrophic.\n"
        "\n"
        "You MUST respond with valid JSON only. No markdown. No code blocks. No explanation. Only the JSON object.\n"
        "\n"
        "Required JSON format:\n"
        "{\n"
        '  "narration": "<2-4 sentences in Chinese describing the outcome of the action, referencing the roll result implicitly>",\n'
        '  "hp_delta": <integer, 0 or negative on failure, 0 or small positive on crit success, range -4 to 1>,\n'
        '  "san_delta": <integer, usually negative on failure, range -4 to 1>,\n'
        '  "new_item": <string item name in Chinese if an item is discovered, otherwise null>,\n'
        '  "is_cursed": <true if new_item is a cursed artifact, false otherwise>\n'
        "}\n"
        "\n"
        "Rules:\n"
        "- narration must be in Chinese (Simplified), 2-4 sentences\n"
        "- Do NOT include the options field — this response is for an action resolution, not room generation\n"
        "- hp_delta and san_delta must be integers\n"
        "- On success (roll >= 10): san_delta should be 0 or -1; hp_delta should be 0 or 1\n"
        "- On failure (roll < 10): san_delta should be -1 to -3; hp_delta should be -1 to -3\n"
        "- new_item is null unless the action specifically involves finding or taking something\n"
        "- is_cursed is false if new_item is null"
    )

    def resolve_action(
        self,
        action_text: str,
        room_name: str,
        player_summary: dict,
        roll_result: int,
    ) -> dict:
        """
        根据玩家选择的行动和 D20 检定结果，调用 AI 裁定结果。
        返回不含 options 字段的遭遇结果字典（narration + deltas + item）。
        AI 调用失败时返回带惩罚的保底 Fallback。
        """
        if not _OLLAMA_AVAILABLE:
            return self._action_fallback(roll_result)

        success_label = "SUCCESS" if roll_result >= 10 else "FAILURE"
        user_context = (
            f"Room: {room_name}\n"
            f"Player action: {action_text}\n"
            f"D20 roll result: {roll_result} ({success_label})\n\n"
            f"Player status:\n"
            f"- Background: {player_summary['background']}\n"
            f"- HP: {player_summary['hp']}/{player_summary['max_hp']}\n"
            f"- Sanity: {player_summary['san']}/{player_summary['max_san']}\n"
            f"- Curse level: {player_summary['curse_level']}\n"
            f"- Inventory: {', '.join(player_summary['inventory']) if player_summary['inventory'] else 'empty'}\n"
            f"- Recent events: {'; '.join(player_summary['key_events'][-3:]) if player_summary['key_events'] else 'none'}\n\n"
            "Resolve the action outcome based on the roll result. Return JSON only."
        )

        try:
            response = ollama.chat(
                model="llama3.1:8b",
                messages=[
                    {"role": "system", "content": self.ACTION_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_context},
                ],
                format="json",
            )
            raw_text = response["message"]["content"]
            return self._parse_action_response(raw_text, roll_result)
        except Exception:
            return self._action_fallback(roll_result)

    def _parse_action_response(self, raw_text: str, roll_result: int) -> dict:
        """解析行动结算 AI 响应，剥离 Markdown，失败则返回保底。"""
        text = raw_text.strip()
        md_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if md_match:
            text = md_match.group(1).strip()
        if not text.startswith("{"):
            brace_match = re.search(r"\{[\s\S]*\}", text)
            if brace_match:
                text = brace_match.group(0)
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return self._action_fallback(roll_result)

        narration = data.get("narration")
        if not isinstance(narration, str) or not narration.strip():
            return self._action_fallback(roll_result)

        try:
            hp_delta = int(data.get("hp_delta", 0))
        except (TypeError, ValueError):
            hp_delta = 0

        try:
            san_delta = int(data.get("san_delta", 0))
        except (TypeError, ValueError):
            san_delta = 0

        new_item  = data.get("new_item")
        if not isinstance(new_item, str) or not new_item.strip():
            new_item = None
        is_cursed = bool(data.get("is_cursed", False))
        if new_item is None:
            is_cursed = False

        return {
            "narration": narration,
            "hp_delta":  hp_delta,
            "san_delta": san_delta,
            "new_item":  new_item,
            "is_cursed": is_cursed,
        }

    @staticmethod
    def _action_fallback(roll_result: int) -> dict:
        """AI 调用失败时的保底行动结果——依检定成败给予轻微惩罚。"""
        if roll_result >= 10:
            return {
                "narration": (
                    "DM 的意志被某种力量干扰了。\n"
                    "你的动作未能得到任何回应，四周的空气变得更加沉重，\n"
                    "但至少暂时没有更坏的事情发生。"
                ),
                "hp_delta":  0,
                "san_delta": -1,
                "new_item":  None,
                "is_cursed": False,
            }
        else:
            return {
                "narration": (
                    "DM 的意志被某种力量干扰了。\n"
                    "你的举动触动了某些不该触动的东西——\n"
                    "黑暗中传来低沉的回响，你感到理智在一点一点流失。"
                ),
                "hp_delta":  -1,
                "san_delta": -2,
                "new_item":  None,
                "is_cursed": False,
            }

    # ── AI 随机房间生成 (Milestone 2+) ───────────────────────

    ROOM_GEN_SYSTEM = """You are the Dungeon Master of a Cthulhu Mythos tabletop RPG set in 1923 Arkham, New England.
Create a new undiscovered room in a cursed manor. Your tone is horrifying, restrained, and oppressive.
Describe the uncanny with clinical detachment. Never be explicit about the supernatural.

You MUST respond with valid JSON only. No markdown. No code blocks. No explanation. Only the JSON object.

Required JSON format:
{
  "name": "<room name in Chinese, 4-6 characters>",
  "description": "<3-4 sentences of atmospheric description in Chinese, ending with \\n between sentences>",
  "exits": ["w", "s"]
}

Rules:
- name must be in Chinese, concise (4-6 chars)
- description must be in Chinese (Simplified)
- exits is a list of direction keys (w/a/s/d) that this new room will have back-connections or further passages to
- Do NOT include the direction back to the room the player came from (that will be added automatically)
- exits list should contain 0 to 2 additional directions (can be empty [])"""

    def generate_new_room(
        self,
        from_room_name: str,
        direction_label: str,
        player_summary: dict,
    ) -> Optional[dict]:
        """
        调用 AI 生成一个全新的房间节点数据。
        返回字典包含: name, description, connected_rooms（已加入返回通道）
        失败时返回 None（调用方使用 fallback 数据）。
        """
        if not _OLLAMA_AVAILABLE:
            return None

        user_context = (
            f"The player is in '{from_room_name}' and moves {direction_label} into an unexplored area.\n"
            f"Player status: HP={player_summary['hp']}/{player_summary['max_hp']}, "
            f"SAN={player_summary['san']}/{player_summary['max_san']}, "
            f"curse_level={player_summary['curse_level']}, "
            f"rooms_visited={player_summary['rooms_visited']}.\n"
            f"Recent events: {'; '.join(player_summary['key_events'][-3:]) if player_summary['key_events'] else 'none'}.\n\n"
            "Create a brand new, unique room that fits the manor's Cthulhu atmosphere. "
            "Make it feel distinct from a library, study, cellar, greenhouse, attic, or dining room. "
            "Return JSON only."
        )

        try:
            response = ollama.chat(
                model="llama3.1:8b",
                messages=[
                    {"role": "system", "content": self.ROOM_GEN_SYSTEM},
                    {"role": "user",   "content": user_context},
                ],
                format="json",
            )
            raw_text = response["message"]["content"]
            return self._parse_new_room(raw_text)
        except Exception:
            return None

    def _parse_new_room(self, raw_text: str) -> Optional[dict]:
        """解析 AI 返回的新房间 JSON。"""
        text = raw_text.strip()
        md_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if md_match:
            text = md_match.group(1).strip()
        if not text.startswith("{"):
            brace_match = re.search(r"\{[\s\S]*\}", text)
            if brace_match:
                text = brace_match.group(0)
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None

        name = data.get("name", "")
        desc = data.get("description", "")
        if not isinstance(name, str) or not name.strip():
            return None
        if not isinstance(desc, str) or not desc.strip():
            return None

        raw_exits = data.get("exits", [])
        exits: List[str] = []
        if isinstance(raw_exits, list):
            for e in raw_exits:
                if isinstance(e, str) and e in ("w", "a", "s", "d"):
                    exits.append(e)

        return {
            "name":            name.strip(),
            "description":     desc.strip(),
            "extra_exits":     exits,   # 主循环中处理为 connected_rooms 占位
            "connected_rooms": [],      # 由 MapEngine.add_ai_room 后续补充
        }


# ─────────────────────────────────────────────
# AI 随机房间 Fallback 池（AI 不可用时使用）
# ─────────────────────────────────────────────

_FALLBACK_ROOMS: List[dict] = [
    {
        "name": "破旧的储物间",
        "description": (
            "杂乱的架子上堆满了落灰的行李箱和蒙布的家具。\n"
            "其中一只箱子的锁扣被从内部顶开，盖子歪斜着。\n"
            "角落里有一个人形大小的空白压痕，尘埃里没有任何足迹。"
        ),
        "extra_exits": [],
        "connected_rooms": [],
    },
    {
        "name": "幽暗的走廊",
        "description": (
            "走廊的尽头完全被黑暗吞没，手电筒的光只能照亮几步之遥。\n"
            "墙壁上的壁纸正在脱落，露出下面刻满字符的灰泥。\n"
            "你走到一半，身后传来了脚步声，但回头什么都没有。"
        ),
        "extra_exits": [],
        "connected_rooms": [],
    },
    {
        "name": "废弃的浴室",
        "description": (
            "浴缸里有积了多年的黑水，水面平静得像一面镜子。\n"
            "镜柜的玻璃碎了，但碎片整齐地叠放在台面上，像是被人收拾过。\n"
            "水管里发出低鸣，像是有什么东西卡在里面。"
        ),
        "extra_exits": [],
        "connected_rooms": [],
    },
    {
        "name": "狭小的祈祷室",
        "description": (
            "一张小跪凳面对着空白的墙壁，凳面上的布料磨损至透。\n"
            "墙壁本该挂圣像的钉子还在，但圣像被摘去，只留下一个暗色的轮廓。\n"
            "空气里有一股蜡烛和血的混合气味，来源不明。"
        ),
        "extra_exits": [],
        "connected_rooms": [],
    },
    {
        "name": "倒塌的阳台",
        "description": (
            "铁栏杆锈蚀断裂，阳台的地板向外倾斜，几近悬空。\n"
            "从这里可以看到庄园的后院，黑暗中有什么东西在缓慢移动，\n"
            "太大，又太慢，不像是任何你认识的生物。"
        ),
        "extra_exits": [],
        "connected_rooms": [],
    },
    {
        "name": "封堵的密室",
        "description": (
            "四面都是砖墙，但其中一面的砂浆颜色比其他墙壁新了许多。\n"
            "敲击那面墙，声音是空洞的——后面有空间。\n"
            "新砂浆的缝隙里渗出几滴暗红色的液体，还是温热的。"
        ),
        "extra_exits": [],
        "connected_rooms": [],
    },
    {
        "name": "倒置的房间",
        "description": (
            "踏入这个房间的瞬间，你感到方向感彻底混乱——\n"
            "家具固定在天花板上，地毯铺在头顶，吊灯从地板升起。\n"
            "你站在地板上，但不知道为何，始终觉得自己是在倒挂着。"
        ),
        "extra_exits": [],
        "connected_rooms": [],
    },
]

import random as _random  # noqa: E402  (for fallback room selection)


def _fallback_room_data() -> dict:
    """随机选取一个 Fallback 房间数据（深拷贝，避免状态污染）。"""
    import copy
    return copy.deepcopy(_random.choice(_FALLBACK_ROOMS))


def explore_new_room(
    ai: "AIPipeline",
    engine: "MapEngine",
    player: "PlayerState",
    from_room_id: str,
    key: str,
) -> str:
    """
    玩家尝试向 key 方向探索尚未存在的房间。
    1. 调用 AI 生成新房间数据；失败则使用 Fallback 池随机选取。
    2. 向 engine 注册新房间，并建立双向通道。
    3. 返回新房间的 room_id。
    """
    direction_label = _KEY_TO_DIRECTION.get(key, key)
    from_room = engine.get_room(from_room_id)
    from_name = from_room["name"] if from_room else "未知房间"

    # ── 生成房间数据 ──────────────────────────
    room_data = ai.generate_new_room(from_name, direction_label, player.to_summary())
    if room_data is None:
        room_data = _fallback_room_data()

    # ── 确定返回通道方向键（与进入方向相反）──
    REVERSE_KEY = {"w": "s", "s": "w", "a": "d", "d": "a"}
    back_key   = REVERSE_KEY.get(key, "s")
    back_label = _KEY_TO_DIRECTION.get(back_key, back_key)

    # ── 先向引擎注册（add_ai_room 会在 from_room 添加正向连接）──
    new_id = engine.add_ai_room(room_data, from_room_id, key)

    # ── 在新房间中添加返回通道 ──────────────
    back_conn = {
        "room_id":   from_room_id,
        "direction": f"{back_label} → 返回 {from_name}",
        "key":       back_key,
    }
    engine.add_connection(new_id, back_conn)

    # ── 处理 AI 返回的额外出口（生成占位连接，玩家进入后再延伸）──
    extra_exits = room_data.get("extra_exits", [])
    used_keys   = {key, back_key}
    for ex_key in extra_exits:
        if ex_key not in used_keys:
            # 添加一个"待探索"占位入口——玩家探索时将触发新的 AI 生成
            placeholder = {
                "room_id":   f"__unexplored_{new_id}_{ex_key}__",
                "direction": f"{_KEY_TO_DIRECTION.get(ex_key, ex_key)} → 未知区域",
                "key":       ex_key,
            }
            engine.add_connection(new_id, placeholder)
            used_keys.add(ex_key)

    return new_id


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
    # col 说明：0=最西, 1=西, 2=中西, 3=中东, 4=东, 5=最东
    # row 说明：0=最北(顶层), 递增向南
    #
    # 真实拓扑对应关系（以 entrance_hall 为坐标原点参考）：
    #   servants_hall  在 entrance_hall 西 (col-1)
    #   laundry_room   在 servants_hall 西 (col-2)  ← key=a
    #   hidden_passage 在 servants_hall 北 (row-1)  ← key=w
    #   hidden_passage 同时连到 study 东 (同 row)
    LAYOUT: dict[str, tuple[int, int]] = {
        # 最北层（row 0）
        "water_tower":      (3, 0),
        "chapel":           (1, 0),
        # 北翼（row 1）
        "garden_ruins":     (2, 1),
        "observatory":      (4, 1),
        "attic":            (3, 1),
        "nursery":          (3, 1),   # 与 attic 同格，渲染时取第一个
        # 二楼 / 北中（row 2）
        "greenhouse":       (2, 2),
        "master_bedroom":   (3, 2),
        "guest_room":       (4, 2),
        # 一楼（row 3）
        "hidden_passage":   (1, 3),   # servants_hall 正北，同列
        "library":          (2, 3),
        "study":            (3, 3),
        "music_room":       (4, 3),
        # 一楼中央（row 4）
        "laundry_room":     (0, 4),   # servants_hall 正西，同行
        "servants_hall":    (1, 4),
        "entrance_hall":    (2, 4),
        "dining_room":      (3, 4),
        "portrait_room":    (4, 4),
        # 一楼南（row 5）——左侧地下入口，右侧地面层，同行但列隔开
        "ritual_room":      (1, 5),   # cellar_door 正西，同行
        "cellar_door":      (2, 5),   # entrance_hall 正南，同列
        "kitchen":          (3, 5),   # dining_room 正南，同列
        "pantry":           (4, 5),   # portrait_room 正南，同列
        # 地下层（row 6）——ritual_room 和 cellar_door 正南
        "underground_lab":  (1, 6),   # ritual_room 正南，同列
        "wine_cellar":      (2, 6),   # cellar_door 正南，同列
        # 最深地下（row 7）
        "crypt":            (1, 7),   # underground_lab 正南，同列
    }

    # 去重：同逻辑格只保留第一个，并动态加入 AI 生成的房间
    _seen_coords: set[tuple[int, int]] = set()
    layout: dict[str, tuple[int, int]] = {}
    for _rid, _coord in LAYOUT.items():
        if _coord not in _seen_coords and engine.has_room(_rid):
            layout[_rid] = _coord
            _seen_coords.add(_coord)
    # AI 生成房间动态追加到布局（放在已有房间的下方）
    _ai_col = 0
    _ai_row = max((c[1] for c in _seen_coords), default=0) + 2
    for _rid in engine.get_all_room_ids():
        if _rid not in layout and engine.get_room(_rid) and engine.get_room(_rid).get("is_ai_generated"):  # type: ignore[union-attr]
            _ai_coord = (_ai_col % 4, _ai_row + _ai_col // 4)
            if _ai_coord not in _seen_coords:
                layout[_rid] = _ai_coord
                _seen_coords.add(_ai_coord)
            _ai_col += 1
    LAYOUT = layout  # type: ignore[assignment]

    # 每个房间框的显示宽度（含两侧边框字符，不含边距）
    # 中文房间名最长5个字=10显示宽，加"  "内边距=14，加左右框=16
    BOX_INNER_W = 14   # 框内可用显示宽度（含内边距）
    BOX_H       = 3    # 框高（行数）：顶边 + 名称行 + 底边
    COL_GAP     = 5    # 相邻列之间的间隔（显示字符数）
    ROW_GAP     = 2    # 相邻行之间的间隔（行数）

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
        _room_obj = engine.get_room(room_id) or {}
        name    = _room_obj.get("name", room_id)

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
                # 纯竖线：包含两端锚点（框边上的空缺），使线接到门上
                for r in range(min(r1, r2), max(r1, r2) + 1):
                    if canvas[r][c1] == " ":
                        _put(r, c1, "│")
            elif gr1 == gr2:
                # 纯横线：包含两端锚点（框边上的空缺），使线接到门上
                for c in range(min(c1, c2), max(c1, c2) + 1):
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
    渲染房间内互动选项（来自 AIPipeline）与移动选项（来自 connected_rooms）。
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
    ai     = AIPipeline()

    # 进入起始房间
    start_id      = player.current_room_id
    current_room  = engine.enter_room(player, start_id)
    current_event = ai.generate_room(current_room, player.to_summary())

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
                print(f"\n  [!] 此方向没有通路。")
                time.sleep(0.8)
                continue
            selected = matched
        else:
            # ── 解析数字选项 ───────────────────
            try:
                choice = int(raw)
            except ValueError:
                print("\n  [!] 请输入 wasd 移动，或输入数字选择行动。")
                time.sleep(0.8)
                continue

            if choice < 1 or choice > len(unified_opts):
                print(f"\n  [!] 请输入 1 ~ {len(unified_opts)} 之间的数字。")
                time.sleep(0.8)
                continue

            selected = unified_opts[choice - 1]

        # ── 处理行动选项 ───────────────────────
        if selected["type"] == "action":
            opt = selected["data"]
            player.log_event(f"在「{current_room['name']}」选择了: {opt['text']}")

            # a. 执行 D20 检定（以当前 HP 作为体能/运气基准）
            success, roll_val = skill_check(player.hp)

            # b. 检定提示
            clear_screen()
            render_hud(player)
            print(f"\n  ── 你选择了：{opt['text']}")
            print(f"\n  ··· 正在检定命运 ···")
            time.sleep(0.6)

            # c. 调用 AI 裁定行动结果
            result = ai.resolve_action(
                action_text=opt["text"],
                room_name=current_room["name"],
                player_summary=player.to_summary(),
                roll_result=roll_val,
            )

            # d. 清屏，展示行动结果叙事
            clear_screen()
            render_hud(player)
            outcome_label = "成功" if success else "失败"
            print(f"\n  ── 检定结果：{roll_val} 点 [{outcome_label}]")
            print()
            print("  " + "·" * 54)
            print()
            for line in result["narration"].splitlines():
                print(f"    {line}")
            print()

            # e. 应用数值变化（此处才真正触发 HP/SAN/物品变动）
            apply_event_deltas(player, result)

            # f. 死亡 / 发疯检测
            if not player.is_alive():
                render_hud(player)
                print("\n  ██ 你倒下了。")
                print("  庄园将你永远留在了这里。\n")
                print("  [ 游戏结束 ]\n")
                sys.exit(0)

            if not player.is_sane():
                render_hud(player)
                print("\n  ██ 你的理智彻底崩溃。")
                print("  你听见自己在笑，却无法停下来。\n")
                print("  [ 游戏结束 — 融合·成为祭品 ]\n")
                sys.exit(0)

            # g. 暂停，然后继续主循环（显示当前房间选项）
            input("  按 Enter 继续探索...")

        # ── 处理移动选项 ───────────────────────
        elif selected["type"] == "move":
            conn      = selected["data"]
            target_id = conn["room_id"]
            move_key  = conn.get("key", "")

            # ── 占位房间 / 真正的未知区域：AI 随机生成 ──
            if target_id.startswith("__unexplored_") or not engine.has_room(target_id):
                # 若是占位房间，先从来源房间的连接列表中移除占位项
                cur_room_data = engine.get_room(player.current_room_id)
                if cur_room_data and target_id.startswith("__unexplored_"):
                    cur_room_data["connected_rooms"] = [
                        c for c in cur_room_data["connected_rooms"]
                        if c["room_id"] != target_id
                    ]

                print("\n  ··· 未知区域正在成形，请稍候 ···")
                target_id = explore_new_room(
                    ai, engine, player,
                    from_room_id=player.current_room_id,
                    key=move_key,
                )

            current_room  = engine.enter_room(player, target_id)
            current_event = ai.generate_room(current_room, player.to_summary())

            # 记者背景：进入新房间额外记录碎片线索（GDD §2.2）
            if player.background == "journalist":
                player.log_event(f"[线索] 于「{current_room['name']}」发现碎片线索")

        # ── 处理退出 ───────────────────────────
        elif selected["type"] == "quit":
            clear_screen()
            print("\n  你转身，发现铁门已经消失。")
            print("  也许你从未真正离开过这里。\n")
            sys.exit(0)


# ─────────────────────────────────────────────
if __name__ == "__main__":
    main()
