import type { Card, Track } from "./types";

export interface ExampleTemplate {
  key: string;
  label: string;
  title: string;
  tracks: Track[];
  cards: Card[];
}

/** 与仓库 examples/*.json 内容一致的内置模板（新建证明时可选）。 */
export const EXAMPLES: ExampleTemplate[] = [
  {
    key: "blank",
    label: "空白证明",
    title: "未命名证明",
    tracks: [],
    cards: [],
  },
  {
    key: "compatible",
    label: "兼容示例：第 9 帧首次同帧",
    title: "兼容示例：第 9 帧首次同帧",
    tracks: [
      { id: "翅膀", period: "4", phase: "1" },
      { id: "尾巴", period: "6", phase: "3" },
    ],
    cards: [
      { type: "source", track: "翅膀" },
      { type: "source", track: "尾巴" },
      { type: "combine", left: 0, right: 1, witness: { u: "-1", v: "1" } },
      { type: "normalize", card: 2 },
    ],
  },
  {
    key: "conflict",
    label: "冲突示例：奇偶永远错开",
    title: "冲突示例：奇偶永远错开",
    tracks: [
      { id: "左手", period: "4", phase: "0" },
      { id: "右手", period: "6", phase: "1" },
    ],
    cards: [
      { type: "source", track: "左手" },
      { type: "source", track: "右手" },
      { type: "contradiction", left: 0, right: 1 },
    ],
  },
  {
    key: "bigint",
    label: "大整数示例：40 位天文周期",
    title: "大整数示例：40 位天文周期精确核验",
    tracks: [
      {
        id: "彗星级",
        period: "10000000000000000000000000000000000000001",
        phase: "123456789012345678901234567890",
      },
      {
        id: "行星级",
        period: "10000000000000000000000000000000000000003",
        phase: "987654321098765432109876543210",
      },
    ],
    cards: [
      { type: "source", track: "彗星级" },
      { type: "source", track: "行星级" },
      {
        type: "combine",
        left: 0,
        right: 1,
        witness: {
          u: "5000000000000000000000000000000000000001",
          v: "-5000000000000000000000000000000000000000",
        },
      },
      { type: "normalize", card: 2 },
    ],
  },
  {
    key: "merge_a",
    label: "合并顺序甲：翅膀→尾巴→铃铛",
    title: "合并顺序甲：翅膀→尾巴→铃铛",
    tracks: [
      { id: "翅膀", period: "4", phase: "1" },
      { id: "尾巴", period: "6", phase: "3" },
      { id: "铃铛", period: "5", phase: "2" },
    ],
    cards: [
      { type: "source", track: "翅膀" },
      { type: "source", track: "尾巴" },
      { type: "source", track: "铃铛" },
      { type: "combine", left: 0, right: 1, witness: { u: "-1", v: "1" } },
      { type: "combine", left: 3, right: 2, witness: { u: "-2", v: "5" } },
      { type: "normalize", card: 4 },
    ],
  },
  {
    key: "merge_b",
    label: "合并顺序乙：铃铛→尾巴→翅膀",
    title: "合并顺序乙：铃铛→尾巴→翅膀",
    tracks: [
      { id: "翅膀", period: "4", phase: "1" },
      { id: "尾巴", period: "6", phase: "3" },
      { id: "铃铛", period: "5", phase: "2" },
    ],
    cards: [
      { type: "source", track: "翅膀" },
      { type: "source", track: "尾巴" },
      { type: "source", track: "铃铛" },
      { type: "combine", left: 2, right: 1, witness: { u: "-1", v: "1" } },
      { type: "combine", left: 3, right: 0, witness: { u: "1", v: "-7" } },
      { type: "normalize", card: 4 },
    ],
  },
];
