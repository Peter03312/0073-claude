<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { api } from "../api";
import type {
  Card,
  CompareResponse,
  ProofDraft,
  ProofPayload,
  Track,
  VersionInfo,
} from "../types";
import ProofGraph from "../components/ProofGraph.vue";
import ResultView from "../components/ResultView.vue";

interface Side {
  proofId: string | null;
  source: string; // "draft" 或 "v3"
  versions: VersionInfo[];
  payload: ProofPayload | null;
  label: string;
}

const route = useRoute();
const proofs = ref<ProofDraft[]>([]);
const left = reactive<Side>({ proofId: null, source: "draft", versions: [], payload: null, label: "" });
const right = reactive<Side>({ proofId: null, source: "draft", versions: [], payload: null, label: "" });
const response = ref<CompareResponse | null>(null);
const error = ref("");
const leftSel = ref<number | null>(null);
const rightSel = ref<number | null>(null);
const leftHov = ref<number | null>(null);
const rightHov = ref<number | null>(null);

let seq = 0;

function parsePreset(key: string): { proofId: string; source: string } | null {
  const q = route.query[key];
  if (typeof q !== "string" || !q.includes(":")) return null;
  const [proofId, source] = q.split(":");
  return { proofId, source };
}

async function loadVersions(side: Side) {
  side.versions = side.proofId ? await api.listVersions(side.proofId) : [];
}

async function loadPayload(side: Side) {
  side.payload = null;
  if (!side.proofId) return;
  if (side.source === "draft") {
    const p = await api.getProof(side.proofId);
    side.payload = { tracks: p.tracks, cards: p.cards };
    side.label = `${p.title} · 草稿 r${p.revision}`;
  } else {
    const no = Number(side.source.slice(1));
    const v = await api.getVersion(side.proofId, no);
    side.payload = { tracks: v.tracks, cards: v.cards };
    side.label = `${v.title} · v${v.version_no}`;
  }
}

async function refresh(side: Side) {
  await loadVersions(side);
  await loadPayload(side);
  await runCompare();
}

async function runCompare() {
  if (!left.payload || !right.payload) return;
  const mySeq = ++seq;
  error.value = "";
  try {
    const resp = await api.compare(left.payload, right.payload);
    if (mySeq !== seq) return; // 迟到响应不得覆盖新选择
    response.value = resp;
  } catch {
    if (mySeq !== seq) return;
    error.value = "对照请求失败";
  }
}

const verdictClass = computed(() => {
  const c = response.value?.comparison;
  if (!c) return "info";
  if (c.kind === "congruences") return c.equal ? "ok" : c.consistent ? "warn" : "bad";
  if (c.kind === "both_unsolvable") return "ok";
  if (c.kind === "mixed") return "bad";
  return "warn";
});

onMounted(async () => {
  proofs.value = await api.listProofs();
  const lp = parsePreset("left");
  const rp = parsePreset("right");
  if (lp && proofs.value.some((p) => p.id === lp.proofId)) {
    left.proofId = lp.proofId;
    left.source = lp.source;
  }
  if (rp && proofs.value.some((p) => p.id === rp.proofId)) {
    right.proofId = rp.proofId;
    right.source = rp.source;
  }
  if (left.proofId) await refresh(left);
  if (right.proofId) await refresh(right);
});

watch(
  () => [left.proofId, left.source],
  () => refresh(left),
);
watch(
  () => [right.proofId, right.source],
  () => refresh(right),
);

function tracksOf(side: Side): Track[] {
  return side.payload?.tracks ?? [];
}
function cardsOf(side: Side): Card[] {
  return side.payload?.cards ?? [];
}
</script>

<template>
  <div class="compare">
    <section class="panel">
      <h3>对照两份证明</h3>
      <p class="muted">
        同一组轨道可以有多种合并顺序。若两种顺序都覆盖全部轨道，
        它们的模数都是全部周期的最小公倍数，规范余数必须相同——这就是“殊途同归”的机器检查。
      </p>
      <div class="pickers">
        <div class="picker">
          <label>左</label>
          <select v-model="left.proofId">
            <option :value="null" disabled>选择证明</option>
            <option v-for="p in proofs" :key="p.id" :value="p.id">{{ p.title }}</option>
          </select>
          <select v-model="left.source">
            <option value="draft">当前草稿</option>
            <option v-for="v in left.versions" :key="v.version_no" :value="`v${v.version_no}`">
              版本 v{{ v.version_no }}
            </option>
          </select>
        </div>
        <div class="picker">
          <label>右</label>
          <select v-model="right.proofId">
            <option :value="null" disabled>选择证明</option>
            <option v-for="p in proofs" :key="p.id" :value="p.id">{{ p.title }}</option>
          </select>
          <select v-model="right.source">
            <option value="draft">当前草稿</option>
            <option v-for="v in right.versions" :key="v.version_no" :value="`v${v.version_no}`">
              版本 v{{ v.version_no }}
            </option>
          </select>
        </div>
      </div>
      <div v-if="error" class="banner bad">{{ error }}</div>
      <div v-if="response" class="banner" :class="verdictClass">
        {{ response.comparison.message }}
      </div>
    </section>

    <div class="panes">
      <section class="panel">
        <h4>{{ left.label || "左侧证明" }}</h4>
        <template v-if="response">
          <ResultView
            v-model:selected="leftSel"
            v-model:hovered="leftHov"
            :result="response.left"
            :loading="false"
            compact
          />
          <ProofGraph
            v-model:selected="leftSel"
            v-model:hovered="leftHov"
            :cards="cardsOf(left)"
            :result="response.left"
          />
        </template>
        <p v-else class="muted">选择左侧证明。</p>
        <p class="muted">{{ tracksOf(left).length }} 条轨道 · {{ cardsOf(left).length }} 张卡</p>
      </section>

      <section class="panel">
        <h4>{{ right.label || "右侧证明" }}</h4>
        <template v-if="response">
          <ResultView
            v-model:selected="rightSel"
            v-model:hovered="rightHov"
            :result="response.right"
            :loading="false"
            compact
          />
          <ProofGraph
            v-model:selected="rightSel"
            v-model:hovered="rightHov"
            :cards="cardsOf(right)"
            :result="response.right"
          />
        </template>
        <p v-else class="muted">选择右侧证明。</p>
        <p class="muted">{{ tracksOf(right).length }} 条轨道 · {{ cardsOf(right).length }} 张卡</p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.compare {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.pickers {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  margin-top: 10px;
}
.picker {
  display: flex;
  align-items: center;
  gap: 8px;
}
.picker label {
  font-weight: 700;
  color: var(--ink-soft);
}
.panes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  align-items: start;
}
@media (max-width: 1100px) {
  .panes {
    grid-template-columns: 1fr;
  }
}
h4 {
  margin: 0 0 10px;
}
</style>
