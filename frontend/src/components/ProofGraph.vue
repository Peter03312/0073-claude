<script setup lang="ts">
import { computed } from "vue";
import type { Card, VerifyResult } from "../types";
import { CARD_TYPE_LABEL, cardRefs, judgmentText } from "../format";

const props = defineProps<{
  cards: Card[];
  result: VerifyResult | null;
  selected: number | null;
  hovered: number | null;
}>();
const emit = defineEmits<{
  "update:selected": [index: number | null];
  "update:hovered": [index: number | null];
}>();

const NODE_W = 208;
const NODE_H = 68;
const GAP_X = 64;
const GAP_Y = 18;
const PAD = 20;

interface NodeBox {
  i: number;
  x: number;
  y: number;
}
interface Edge {
  key: string;
  d: string;
  to: number;
}

/** 按“最长依赖链”分层布局：来源卡在第 0 列，其余卡在其依赖之后。 */
const layout = computed(() => {
  const depths: number[] = [];
  props.cards.forEach((card, i) => {
    const refs = cardRefs(card).filter((r) => r >= 0 && r < i);
    depths[i] = refs.length ? 1 + Math.max(...refs.map((r) => depths[r])) : 0;
  });
  const rows = new Map<number, number>();
  const nodes: NodeBox[] = props.cards.map((_, i) => {
    const d = depths[i];
    const row = rows.get(d) ?? 0;
    rows.set(d, row + 1);
    return { i, x: PAD + d * (NODE_W + GAP_X), y: PAD + row * (NODE_H + GAP_Y) };
  });
  const edges: Edge[] = [];
  props.cards.forEach((card, i) => {
    for (const r of cardRefs(card)) {
      if (r < 0 || r >= props.cards.length) continue;
      const a = nodes[r];
      const b = nodes[i];
      const x1 = a.x + NODE_W;
      const y1 = a.y + NODE_H / 2;
      const x2 = b.x;
      const y2 = b.y + NODE_H / 2;
      const dx = Math.max(28, (x2 - x1) * 0.45);
      edges.push({
        key: `${r}->${i}`,
        d: `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`,
        to: i,
      });
    }
  });
  const width = nodes.length
    ? Math.max(...nodes.map((n) => n.x + NODE_W)) + PAD
    : 120;
  const height = nodes.length
    ? Math.max(...nodes.map((n) => n.y + NODE_H)) + PAD
    : 60;
  return { nodes, edges, width, height };
});

function stepOf(i: number) {
  return props.result?.steps[i];
}
function nodeState(i: number): string {
  const step = stepOf(i);
  if (!step) return "pending";
  return step.ok ? "ok" : "error";
}
function isFinal(i: number): boolean {
  if (!props.result || props.result.steps.length === 0) return false;
  const last = props.result.steps[props.result.steps.length - 1];
  return last.ok && i === last.index && props.result.status !== "invalid";
}
function line2(i: number): string {
  const step = stepOf(i);
  if (!step) return "待核验";
  if (!step.ok) return `✗ ${step.code ?? "ERROR"}`;
  return judgmentText(step.judgment);
}
function line3(i: number): string {
  const j = stepOf(i)?.judgment;
  if (!j) return "";
  const src = j.sources;
  const shown = src.slice(0, 3).join("、") + (src.length > 3 ? `…共${src.length}条` : "");
  return `来源：${shown}`;
}
function fullTitle(i: number): string {
  const step = stepOf(i);
  const j = step?.judgment;
  const parts = [`#${i} ${CARD_TYPE_LABEL[props.cards[i].type]}`];
  if (step && !step.ok) parts.push(`错误 ${step.code}：${step.message}`);
  if (j?.kind === "congruence")
    parts.push(`x ≡ ${j.residue} (mod ${j.modulus})，规范余数 ${j.canonical_residue}`);
  if (j?.kind === "contradiction") parts.push("冲突结论");
  if (j) parts.push(`来源：${j.sources.join("、")}`);
  return parts.join("\n");
}
</script>

<template>
  <div class="graph-wrap">
    <svg
      v-if="cards.length"
      :viewBox="`0 0 ${layout.width} ${layout.height}`"
      :width="layout.width"
      :height="layout.height"
      class="graph"
      role="img"
    >
      <defs>
        <marker
          id="arrow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M 0 1 L 9 5 L 0 9 z" fill="#b3a8d9" />
        </marker>
      </defs>
      <path
        v-for="e in layout.edges"
        :key="e.key"
        :d="e.d"
        class="edge"
        :class="{ dim: hovered !== null && hovered !== e.to }"
        marker-end="url(#arrow)"
      />
      <g
        v-for="n in layout.nodes"
        :key="n.i"
        class="node"
        :class="[
          `t-${cards[n.i].type}`,
          `s-${nodeState(n.i)}`,
          {
            final: isFinal(n.i),
            selected: selected === n.i,
            hovered: hovered === n.i,
          },
        ]"
        :transform="`translate(${n.x}, ${n.y})`"
        @click="emit('update:selected', selected === n.i ? null : n.i)"
        @mouseenter="emit('update:hovered', n.i)"
        @mouseleave="emit('update:hovered', null)"
      >
        <title>{{ fullTitle(n.i) }}</title>
        <rect :width="NODE_W" :height="NODE_H" rx="11" />
        <text class="t1" x="12" y="21">
          #{{ n.i }} {{ CARD_TYPE_LABEL[cards[n.i].type] }}
          <tspan v-if="isFinal(n.i)" class="final-mark">★ 结论</tspan>
        </text>
        <text class="t2 mono" x="12" y="41">{{ line2(n.i) }}</text>
        <text class="t3" x="12" y="59">{{ line3(n.i) }}</text>
      </g>
    </svg>
    <p v-else class="muted">还没有证明卡。在下方添加第一张「来源」卡吧。</p>
    <div class="legend muted">
      <span><i class="sw t-source"></i>来源</span>
      <span><i class="sw t-combine"></i>合并</span>
      <span><i class="sw t-normalize"></i>规范化</span>
      <span><i class="sw t-contradiction"></i>冲突</span>
      <span><i class="sw s-error"></i>首个错误</span>
      <span><i class="sw s-final"></i>最终结论</span>
    </div>
  </div>
</template>

<style scoped>
.graph-wrap {
  overflow-x: auto;
}
.graph {
  display: block;
  max-width: none;
}
.edge {
  fill: none;
  stroke: #b3a8d9;
  stroke-width: 1.6;
  transition: opacity 0.15s;
}
.edge.dim {
  opacity: 0.25;
}
.node {
  cursor: pointer;
}
.node rect {
  fill: #fff;
  stroke: var(--line);
  stroke-width: 1.4;
  transition:
    stroke 0.15s,
    stroke-width 0.15s;
}
.node.t-source rect {
  fill: #eef4ff;
}
.node.t-combine rect {
  fill: #ecf9f0;
}
.node.t-normalize rect {
  fill: #fff6e6;
}
.node.t-contradiction rect {
  fill: #fdeeee;
}
.node.s-error rect {
  stroke: var(--bad);
  stroke-width: 3;
}
.node.final rect {
  stroke: var(--ok);
  stroke-width: 3;
}
.node.selected rect,
.node.hovered rect {
  stroke: var(--accent);
  stroke-width: 3;
}
.node.s-pending {
  opacity: 0.55;
}
.t1 {
  font-size: 12.5px;
  font-weight: 700;
  fill: var(--ink);
}
.final-mark {
  fill: var(--ok);
  font-weight: 700;
}
.t2 {
  font-size: 12px;
  fill: var(--ink);
}
.t3 {
  font-size: 11px;
  fill: var(--ink-soft);
}
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 8px;
  font-size: 12px;
}
.sw {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 4px;
  margin-right: 4px;
  vertical-align: -1px;
}
.sw.t-source {
  background: #eef4ff;
  border: 1px solid #b9ccf0;
}
.sw.t-combine {
  background: #ecf9f0;
  border: 1px solid #a9dcc0;
}
.sw.t-normalize {
  background: #fff6e6;
  border: 1px solid #ecd9a8;
}
.sw.t-contradiction {
  background: #fdeeee;
  border: 1px solid #f0b9b9;
}
.sw.s-error {
  background: #fff;
  border: 2px solid var(--bad);
}
.sw.s-final {
  background: #fff;
  border: 2px solid var(--ok);
}
</style>
