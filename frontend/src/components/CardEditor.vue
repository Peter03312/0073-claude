<script setup lang="ts">
import { computed } from "vue";
import type { Card, CardType, Track, VerifyResult } from "../types";
import { CARD_TYPE_LABEL, cardRefs, egcd, isIntText } from "../format";

const props = defineProps<{
  card: Card;
  index: number;
  cards: Card[];
  tracks: Track[];
  result: VerifyResult | null;
  selected: boolean;
}>();
const emit = defineEmits<{
  update: [card: Card];
  remove: [];
  select: [];
}>();

const asCombine = computed(() => (props.card.type === "combine" ? props.card : null));
const asNormalize = computed(() => (props.card.type === "normalize" ? props.card : null));
const asContradiction = computed(() =>
  props.card.type === "contradiction" ? props.card : null,
);
const asSource = computed(() => (props.card.type === "source" ? props.card : null));

/** 引用该卡的后续卡（删除前必须没有）。 */
const referrers = computed(() =>
  props.cards
    .map((c, i) => ({ c, i }))
    .filter(({ c, i }) => i > props.index && cardRefs(c).includes(props.index))
    .map(({ i }) => i),
);

function clone(): Card {
  return JSON.parse(JSON.stringify(props.card)) as Card;
}
function patch(fn: (c: Card) => void) {
  const c = clone();
  fn(c);
  emit("update", c);
}

function changeType(e: Event) {
  const t = (e.target as HTMLSelectElement).value as CardType;
  const last = Math.max(0, props.index - 1);
  const prev = Math.max(0, props.index - 2);
  let next: Card;
  switch (t) {
    case "source":
      next = { type: "source", track: props.tracks[0]?.id ?? "" };
      break;
    case "combine":
      next = { type: "combine", left: prev, right: last, witness: { u: "0", v: "0" } };
      break;
    case "normalize":
      next = { type: "normalize", card: last };
      break;
    case "contradiction":
      next = { type: "contradiction", left: prev, right: last };
      break;
  }
  emit("update", next);
}

/** 用已核验结论里的模数，以前端 BigInt 扩展欧几里得自动填 Bézout 见证。 */
const canAutoWitness = computed(() => {
  if (!asCombine.value || !props.result) return false;
  const { left, right } = asCombine.value;
  const jl = props.result.steps[left]?.judgment;
  const jr = props.result.steps[right]?.judgment;
  return jl?.kind === "congruence" && jr?.kind === "congruence";
});
function autoWitness() {
  const c = asCombine.value;
  if (!c || !props.result) return;
  const ml = props.result.steps[c.left]?.judgment?.modulus;
  const mr = props.result.steps[c.right]?.judgment?.modulus;
  if (!ml || !mr) return;
  const [, u, v] = egcd(BigInt(ml), BigInt(mr));
  patch((card) => {
    if (card.type === "combine") {
      card.witness.u = u.toString();
      card.witness.v = v.toString();
    }
  });
}

const step = computed(() => props.result?.steps[props.index]);
const witnessBad = computed(() => {
  const c = asCombine.value;
  if (!c) return false;
  return !isIntText(c.witness.u) || !isIntText(c.witness.v);
});
</script>

<template>
  <div
    class="card-row"
    :class="{ selected, error: step && !step.ok, ok: step?.ok }"
    @click="emit('select')"
  >
    <span class="idx mono">#{{ index }}</span>
    <select :value="card.type" @change="changeType" @click.stop>
      <option v-for="(label, t) in CARD_TYPE_LABEL" :key="t" :value="t">{{ label }}</option>
    </select>

    <template v-if="asSource">
      <label>
        轨道
        <select
          :value="asSource.track"
          @change="patch((c) => { if (c.type === 'source') c.track = ($event.target as HTMLSelectElement).value; })"
          @click.stop
        >
          <option v-for="t in tracks" :key="t.id" :value="t.id">{{ t.id }}</option>
          <option v-if="!tracks.some((t) => t.id === asSource!.track)" :value="asSource.track">
            {{ asSource.track }}（未定义）
          </option>
        </select>
      </label>
    </template>

    <template v-if="asCombine">
      <label>
        左
        <select
          :value="asCombine.left"
          @change="patch((c) => { if (c.type === 'combine') c.left = Number(($event.target as HTMLSelectElement).value); })"
          @click.stop
        >
          <option v-for="j in index" :key="j - 1" :value="j - 1">#{{ j - 1 }}</option>
        </select>
      </label>
      <label>
        右
        <select
          :value="asCombine.right"
          @change="patch((c) => { if (c.type === 'combine') c.right = Number(($event.target as HTMLSelectElement).value); })"
          @click.stop
        >
          <option v-for="j in index" :key="j - 1" :value="j - 1">#{{ j - 1 }}</option>
        </select>
      </label>
      <label class="grow">
        见证 u
        <input
          class="mono"
          :class="{ invalid: !isIntText(asCombine.witness.u) }"
          :value="asCombine.witness.u"
          placeholder="u·m₁+v·m₂=gcd"
          @input="patch((c) => { if (c.type === 'combine') c.witness.u = ($event.target as HTMLInputElement).value; })"
          @click.stop
        />
      </label>
      <label class="grow">
        见证 v
        <input
          class="mono"
          :class="{ invalid: !isIntText(asCombine.witness.v) }"
          :value="asCombine.witness.v"
          @input="patch((c) => { if (c.type === 'combine') c.witness.v = ($event.target as HTMLInputElement).value; })"
          @click.stop
        />
      </label>
      <button type="button" :disabled="!canAutoWitness" title="用左右两卡的模数自动求 Bézout 见证" @click.stop="autoWitness">
        自动填见证
      </button>
    </template>

    <template v-if="asNormalize">
      <label>
        目标卡
        <select
          :value="asNormalize.card"
          @change="patch((c) => { if (c.type === 'normalize') c.card = Number(($event.target as HTMLSelectElement).value); })"
          @click.stop
        >
          <option v-for="j in index" :key="j - 1" :value="j - 1">#{{ j - 1 }}</option>
        </select>
      </label>
      <span class="muted">只化为最小非负剩余</span>
    </template>

    <template v-if="asContradiction">
      <label>
        左
        <select
          :value="asContradiction.left"
          @change="patch((c) => { if (c.type === 'contradiction') c.left = Number(($event.target as HTMLSelectElement).value); })"
          @click.stop
        >
          <option v-for="j in index" :key="j - 1" :value="j - 1">#{{ j - 1 }}</option>
        </select>
      </label>
      <label>
        右
        <select
          :value="asContradiction.right"
          @change="patch((c) => { if (c.type === 'contradiction') c.right = Number(($event.target as HTMLSelectElement).value); })"
          @click.stop
        >
          <option v-for="j in index" :key="j - 1" :value="j - 1">#{{ j - 1 }}</option>
        </select>
      </label>
      <span class="muted">仅当相位差不能被 gcd 整除时合法</span>
    </template>

    <span v-if="step && !step.ok" class="err" :title="step.message">✗ {{ step.code }}</span>
    <span v-else-if="step?.ok" class="okmark">✓</span>

    <button
      type="button"
      class="danger del"
      :disabled="referrers.length > 0"
      :title="referrers.length ? `被卡 ${referrers.map((r) => '#' + r).join('、')} 引用，不能删除` : '删除此卡'"
      @click.stop="emit('remove')"
    >
      ✕
    </button>
    <span v-if="witnessBad" class="muted">见证需为整数十进制</span>
  </div>
</template>

<style scoped>
.card-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 7px 10px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  font-size: 13.5px;
}
.card-row.selected {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-soft);
}
.card-row.error {
  border-color: var(--bad);
  background: var(--bad-soft);
}
.card-row.ok {
  background: #fbfefc;
}
.idx {
  color: var(--ink-soft);
  min-width: 28px;
}
label {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--ink-soft);
  font-size: 12.5px;
}
label.grow {
  flex: 1;
  min-width: 120px;
}
label.grow input {
  width: 100%;
}
select {
  padding: 4px 6px;
  font-size: 13px;
}
input {
  padding: 4px 8px;
  font-size: 13px;
}
.err {
  color: var(--bad);
  font-size: 12.5px;
  font-weight: 600;
}
.okmark {
  color: var(--ok);
  font-weight: 700;
}
.del {
  margin-left: auto;
  padding: 2px 9px;
}
</style>
