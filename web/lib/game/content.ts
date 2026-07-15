import type {
  BackgroundId,
  BackgroundSpec,
  EndingType,
  EventOption,
  GameEvent,
  PlayerState,
  RoomTemplate,
} from "./types";

export const BACKGROUNDS: Record<BackgroundId, BackgroundSpec> = {
  journalist: {
    id: "journalist",
    label: "记者",
    english: "THE JOURNALIST",
    hp: 8,
    san: 7,
    description: "习惯挖掘真相，擅长从残缺记录中找出不该存在的联系。",
    ability: "每次进入新房间，额外记录一条碎片线索。",
  },
  doctor: {
    id: "doctor",
    label: "医生",
    english: "THE PHYSICIAN",
    hp: 7,
    san: 9,
    description: "受过严格理性训练，相信一切异常都有可以被描述的症状。",
    ability: "首次 SAN 归零时发动理性抵抗，保留 1 点理智。",
  },
  looter: {
    id: "looter",
    label: "盗墓者",
    english: "THE TOMB RAIDER",
    hp: 10,
    san: 5,
    description: "见过太多不应重见天日之物，身体比判断更早作出反应。",
    ability: "战斗检定获得 +1 修正，但初始理智较低。",
  },
};

export const OPENING_LINES = [
  "铁门在你身后轰然关闭。",
  "黑暗吞没了来时的路。",
  "空气中有一股腐烂的甜味——",
  "像是某种东西正在等待你。",
  "你握紧手中的手电筒，向前走去。",
] as const;

export const ROOM_TEMPLATES: RoomTemplate[] = [
  {
    name: "腐烂的图书室",
    description:
      "书架上的书籍凝结成黑色砖块，唯有一本无字书仍保持干燥。窗外的灰光照着一页正在自行书写的日记。",
    clue: "日记反复写着同一句话：不要相信朝北的门。",
  },
  {
    name: "破碎的温室",
    description:
      "玻璃穹顶裂成蛛网，黑紫色根茎在无风处追逐你的影子。泥土里埋着一排整齐的人类牙齿。",
    clue: "每颗牙齿上都刻着与庄园房间对应的方位。",
  },
  {
    name: "肖像画廊",
    description:
      "家族肖像的眼睛都被涂黑，最末一幅却长着与你相同的脸。画框背后传来细微的抓挠声。",
    clue: "画像落款日期是明天，画中人的衣袋露出半封匿名信。",
  },
  {
    name: "封尘的音乐室",
    description:
      "钢琴在你踏入时自行落下一个琴键。灰尘里的脚印只通向琴凳，没有任何返回的痕迹。",
    clue: "琴谱的休止符连起来，恰好组成地下祭坛的轮廓。",
  },
  {
    name: "倾斜的阁楼",
    description:
      "地板向西倾斜，白布覆盖的人形物随你的呼吸轻微起伏。梁上挂着一串没有指针的钟表。",
    clue: "所有钟面都停在你收到匿名信的时刻。",
  },
  {
    name: "儿童房",
    description:
      "发条小车绕着空摇篮缓慢转圈。墙上的身高刻度最高处写着你的名字，而墨迹还很新。",
    clue: "摇篮底部刻着灰石庄园上一任调查者的失踪日期。",
  },
  {
    name: "腐败的厨房",
    description:
      "铁锅中的黑色残渣仍有余温，水槽滴水的节奏与心跳完全一致。锈刀映不出你的脸。",
    clue: "刀柄内藏着半张地图，出口位置被人故意撕去。",
  },
  {
    name: "仆人夹道",
    description:
      "狭道只容侧身通过，墙上布满指甲划出的倒计时。数字在你回头后悄悄减少了一位。",
    clue: "划痕旁有一句祷词：第二十扇门打开时，不要回答。",
  },
  {
    name: "地下酒窖",
    description:
      "拱顶下堆着积灰酒瓶，其中一瓶的标签写着明天的日期。瓶中沉淀物正缓慢拼成字母。",
    clue: "瓶底字母拼出匿名信寄件人的姓氏，却与你相同。",
  },
  {
    name: "无面礼拜堂",
    description:
      "圣像的脸被彻底凿去，碎彩窗在地面投出不属于任何人的影子。祭坛后传来潮汐声。",
    clue: "祭坛夹层里藏着记载五种命运的残页。",
  },
  {
    name: "废弃观测台",
    description:
      "铜望远镜指向没有星星的天空。镜筒内侧沾着新鲜海盐，星图上多出一个正在移动的黑点。",
    clue: "星图标注的并非天空，而是庄园地下的房间分布。",
  },
  {
    name: "倒置的客房",
    description:
      "家具固定在天花板，吊灯从地板向上生长。你明明站得笔直，血液却像倒挂般涌向头顶。",
    clue: "床底写着：重力只是它尚未醒来时的习惯。",
  },
  {
    name: "积水浴室",
    description:
      "浴缸盛着纹丝不动的黑水，碎镜片被人整齐叠好。水下的倒影比你多出一只手。",
    clue: "镜背贴着失踪者名单，最后一行留给了你。",
  },
  {
    name: "潮湿标本室",
    description:
      "玻璃罐排列到视野尽头，标签只有日期而没有名称。最近的罐子贴着今天，内部还是空的。",
    clue: "旧标签说明所有标本都来自主动走进庄园的人。",
  },
];

const commonOptions = (one: string, two: string, three: string): GameEvent["options"] => [
  { key: "1", text: one },
  { key: "2", text: two },
  { key: "3", text: three },
];

export const COMMON_EVENTS: GameEvent[] = [
  {
    narration:
      "墙纸后传来指尖划过石灰的声音。它停在与你胸口齐平的位置，随后敲了三下。",
    hp_delta: 0,
    san_delta: -1,
    new_item: null,
    is_cursed: false,
    options: commonOptions("撕开墙纸，追查声音来源", "以同样节奏敲击回应", "保持沉默并检查周围退路"),
  },
  {
    narration:
      "一团过于瘦长的影子从门缝滑过，却没有任何实体经过。你的手电光开始不规律地闪烁。",
    hp_delta: 0,
    san_delta: -1,
    new_item: null,
    is_cursed: false,
    options: commonOptions("追上那团影子", "关掉手电，凭听觉判断位置", "背靠墙壁稳步后退"),
  },
  {
    narration:
      "腐朽地板骤然下陷，黑暗中有什么东西抓住了你的鞋跟。木板裂口正缓慢扩大。",
    hp_delta: 0,
    san_delta: 0,
    new_item: null,
    is_cursed: false,
    options: commonOptions("用力挣脱并跃过裂口", "俯身攻击抓住鞋跟的东西", "放弃鞋子，贴地爬向稳固处"),
  },
];

export const ITEM_EVENTS: GameEvent[] = [
  {
    narration:
      "倒塌柜门后露出一只仍可使用的医药盒，封条上印着阿卡姆医院的旧徽记。",
    hp_delta: 1,
    san_delta: 0,
    new_item: "旧医药盒",
    is_cursed: false,
    options: commonOptions("检查药品的生产日期", "立刻处理身上的伤口", "收好药盒，避免久留"),
  },
  {
    narration:
      "桌下压着一盏备用煤油灯，火芯干燥，灯油却散发出微弱海腥味。",
    hp_delta: 0,
    san_delta: 0,
    new_item: "备用煤油灯",
    is_cursed: false,
    options: commonOptions("点亮煤油灯检查暗角", "闻一闻灯油，辨认其成分", "包好煤油灯继续前进"),
  },
];

export const CURSED_EVENTS: GameEvent[] = [
  {
    narration:
      "金属圆盒静置在地面中央，盒盖下传来与脉搏同步的轻响。它在你靠近前便自行落入口袋。",
    hp_delta: 0,
    san_delta: -1,
    new_item: "搏动的封印圆盒",
    is_cursed: true,
    options: commonOptions("试着撬开圆盒", "隔着衣料聆听盒内声响", "将圆盒层层包裹"),
  },
  {
    narration:
      "一枚黑曜石眼球躺在壁龛中，瞳孔映出的不是你，而是某个站在你身后的轮廓。",
    hp_delta: 0,
    san_delta: -1,
    new_item: "注视者之眼",
    is_cursed: true,
    options: commonOptions("借它观察身后的轮廓", "将眼球按回壁龛", "遮住瞳孔并寻找铭文"),
  },
];

export const ESCAPE_EVENT: GameEvent = {
  narration:
    "壁板后吹来真正属于室外的冷风。一张泛白的建筑图标出了尚未被庄园吞没的侧门。",
  hp_delta: 0,
  san_delta: 0,
  new_item: "逃脱出口·西侧铁门",
  is_cursed: false,
  options: commonOptions("沿图纸标记寻找侧门", "核对图纸与当前方位", "记下路线并搜查暗格"),
};

export const CLIMAX_OPTIONS: [EventOption, EventOption, EventOption] = [
  { key: "1", text: "利用收集的线索寻找封印缺口" },
  { key: "2", text: "以随身物品布置临时防线" },
  { key: "3", text: "冲向意识核心，强行打断仪式" },
];

const ENDING_BASE: Record<EndingType, string> = {
  "逃脱·理智尚存":
    "侧门在黎明前最后一刻打开。你跌进潮湿草地，身后的灰石庄园没有追来，只是每一扇窗都同时亮起幽光。你把线索锁进阿卡姆银行的保险柜，并发誓不再提起那一夜。",
  "逃脱·精神破碎":
    "你从侧门爬出时还活着，也认得清晨与海风。镇民找到你后，你只反复说庄园没有房间，所有门都通向同一个地方。第七天，你的病房墙内开始传出三次规律敲击。",
  "融合·成为祭品":
    "当最后一点理性熄灭，你终于明白匿名信为何熟悉：那是你在未来写给自己的邀请。你亲手补全封印缺失的线条，庄园以温柔得近乎慈悲的方式接纳了你。",
  "战死·无名英雄":
    "伤势夺走最后一口气，你却在倒下前毁掉了最接近封印的通路。官方记录只写着又一名调查者失踪，无人知道你曾让阿卡姆多得到数十年的安宁。",
  "湮灭·彻底消失":
    "异变越过最后一道防线。你的身体、脚印与名字同时从庄园中褪去，仿佛从未存在。认识你的人开始记不起你的面容，档案里的照片只剩一块灰斑。",
};

export function buildEndingText(type: EndingType, player: PlayerState): string {
  const items = player.inventory.slice(-3).join("、") || "一无所有";
  const memory = player.keyEvents.slice(-2).join("；") || "铁门在身后合拢";
  return `${ENDING_BASE[type]}你以${BACKGROUNDS[player.background].label}的身份进入庄园，最终带着${items}走到这里。残存记忆里最清晰的是：${memory}。这一夜你共踏入${player.roomsVisited}间房，体力停在${player.hp}，理智停在${player.san}；然而数字无法说明门后究竟发生了什么。后来每当阿卡姆海雾升起，总有人听见灰石深处传来一声迟到的关门声。`;
}
