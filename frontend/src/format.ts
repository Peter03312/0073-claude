import type { Card, CardType, Judgment, VerifyStatus } from "./types";

/** 大整数缩写显示：中间省略，标注位数；完整值放 title。 */
export function shortNum(s: string | undefined, max = 14): string {
  if (s === undefined || s === null) return "";
  const neg = s.startsWith("-");
  const digits = neg ? s.slice(1) : s;
  if (digits.length <= max) return s;
  return `${neg ? "-" : ""}${digits.slice(0, 6)}…${digits.slice(-4)}（${digits.length}位）`;
}

export function judgmentText(j: Judgment | undefined): string {
  if (!j) return "";
  if (j.kind === "contradiction") return "冲突：无解";
  return `x ≡ ${shortNum(j.canonical_residue)} (mod ${shortNum(j.modulus)})`;
}

export const CARD_TYPE_LABEL: Record<CardType, string> = {
  source: "来源",
  combine: "合并",
  normalize: "规范化",
  contradiction: "冲突",
};

export const STATUS_LABEL: Record<VerifyStatus, string> = {
  solvable: "已证明可解",
  unsolvable: "已证明无解",
  incomplete: "证明未完成",
  invalid: "证明非法",
  empty: "空证明",
};

export function cardRefs(card: Card): number[] {
  switch (card.type) {
    case "combine":
    case "contradiction":
      return [card.left, card.right];
    case "normalize":
      return [card.card];
    default:
      return [];
  }
}

/** 扩展欧几里得（BigInt 任意精度）：返回 [g, u, v]，u·a + v·b = g = gcd(a,b) ≥ 0。 */
export function egcd(a: bigint, b: bigint): [bigint, bigint, bigint] {
  let [oldR, r] = [a, b];
  let [oldS, s] = [1n, 0n];
  let [oldT, t] = [0n, 1n];
  while (r !== 0n) {
    const q = oldR / r;
    [oldR, r] = [r, oldR - q * r];
    [oldS, s] = [s, oldS - q * s];
    [oldT, t] = [t, oldT - q * t];
  }
  if (oldR < 0n) return [-oldR, -oldS, -oldT];
  return [oldR, oldS, oldT];
}

const INT_RE = /^[+-]?\d+$/;
export function isIntText(s: string): boolean {
  return INT_RE.test(s.trim());
}
export function isPosIntText(s: string): boolean {
  return isIntText(s) && BigInt(s.trim()) > 0n;
}
export function isNonNegIntText(s: string): boolean {
  return isIntText(s) && BigInt(s.trim()) >= 0n;
}
