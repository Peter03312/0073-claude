<script setup lang="ts">
import { computed } from "vue";
import type { VerifyResult } from "../types";
import { CARD_TYPE_LABEL, judgmentText, shortNum } from "../format";

const props = defineProps<{
  result: VerifyResult | null;
  loading: boolean;
  selected: number | null;
  hovered: number | null;
  compact?: boolean;
}>();
const emit = defineEmits<{
  "update:selected": [index: number | null];
  "update:hovered": [index: number | null];
}>();

const banner = computed(() => {
  const r = props.result;
  if (!r) return null;
  switch (r.status) {
    case "solvable": {
      const f = r.final!;
      return {
        cls: "ok",
        text: `✔ 已证明可解：第 ${shortNum(f.canonical_residue)} 帧首次同帧，之后每 ${shortNum(
          f.modulus,
        )} 帧循环一次（覆盖全部 ${r.tracks_total} 条轨道）`,
        title: `x ≡ ${f.canonical_residue} (mod ${f.modulus})`,
      };
    }
    case "unsolvable":
      return {
        cls: "bad",
        text: `✖ 已证明无解：冲突子集 { ${r.final!.sources.join("、")} } 永不同帧`,
        title: "",
      };
    case "incomplete": {
      const covered = r.final?.sources.length ?? 0;
      return {
        cls: "warn",
        text: `… 证明未完成：末卡只覆盖 ${covered}/${r.tracks_total} 条轨道，继续合并或声明冲突`,
        title: "",
      };
    }
    case "invalid": {
      const e = r.first_error!;
      const where = e.card_index === null ? "轨道定义" : `第 ${e.card_index} 张卡`;
      return { cls: "bad", text: `✗ 首个错误在${where}：${e.message}`, title: e.code };
    }
    default:
      return { cls: "info", text: "空证明：先添加来源卡引入轨道", title: "" };
  }
});
</script>

<template>
  <div class="result">
    <div v-if="loading" class="muted">核验中…</div>
    <div v-if="banner" class="banner" :class="banner.cls" :title="banner.title">
      {{ banner.text }}
    </div>
    <ol v-if="result && result.steps.length && !compact" class="steps">
      <li
        v-for="s in result.steps"
        :key="s.index"
        :class="{ ok: s.ok, bad: !s.ok, selected: selected === s.index, hovered: hovered === s.index }"
        @click="emit('update:selected', selected === s.index ? null : s.index)"
        @mouseenter="emit('update:hovered', s.index)"
        @mouseleave="emit('update:hovered', null)"
      >
        <span class="idx mono">#{{ s.index }}</span>
        <span class="type">{{ CARD_TYPE_LABEL[s.type as keyof typeof CARD_TYPE_LABEL] ?? s.type }}</span>
        <span v-if="s.ok" class="mono judge">{{ judgmentText(s.judgment) }}</span>
        <span v-else class="err">✗ {{ s.code }}：{{ s.message }}</span>
        <span v-if="s.ok && s.judgment" class="src muted">
          {{ s.judgment.sources.join("、") }}
        </span>
      </li>
    </ol>
    <p v-if="result && result.status === 'empty'" class="muted">
      证明卡列表为空。
    </p>
  </div>
</template>

<style scoped>
.result {
  min-height: 40px;
}
.steps {
  list-style: none;
  margin: 10px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 320px;
  overflow-y: auto;
}
.steps li {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 5px 10px;
  border-radius: 8px;
  border: 1px solid transparent;
  cursor: pointer;
  font-size: 13.5px;
}
.steps li.ok {
  background: #f4fbf7;
}
.steps li.bad {
  background: var(--bad-soft);
}
.steps li.selected,
.steps li.hovered {
  border-color: var(--accent);
}
.idx {
  color: var(--ink-soft);
  min-width: 30px;
}
.type {
  font-weight: 600;
  min-width: 44px;
}
.judge {
  flex: 1;
}
.err {
  color: var(--bad);
  flex: 1;
}
.src {
  font-size: 12px;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
