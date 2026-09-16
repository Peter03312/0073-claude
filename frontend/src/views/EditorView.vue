<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, ApiError } from "../api";
import type { Card, CardType, Track, VerifyResult, VersionInfo } from "../types";
import { cardRefs, isNonNegIntText, isPosIntText } from "../format";
import ProofGraph from "../components/ProofGraph.vue";
import ResultView from "../components/ResultView.vue";
import CardEditor from "../components/CardEditor.vue";

const route = useRoute();
const router = useRouter();
const proofId = route.params.id as string;

const title = ref("");
const revision = ref(0);
const tracks = ref<Track[]>([]);
const cards = ref<Card[]>([]);
const versions = ref<VersionInfo[]>([]);
const result = ref<VerifyResult | null>(null);
const verifying = ref(false);
const loaded = ref(false);
const loadError = ref("");
const notice = ref("");
const stale = ref<number | null>(null); // 服务器上的当前 revision（本稿已落后）
const selected = ref<number | null>(null);
const hovered = ref<number | null>(null);
const publishNote = ref("");
const versionResult = ref<{ no: number; result: VerifyResult } | null>(null);

// ---- 迟到响应防护：每次请求递增序号，只有最新一次的结果允许落地 ----
let verifySeq = 0;
let saveSeq = 0;
let debounceTimer: ReturnType<typeof setTimeout> | null = null;

async function load() {
  try {
    const proof = await api.getProof(proofId);
    title.value = proof.title;
    revision.value = proof.revision;
    tracks.value = proof.tracks;
    cards.value = proof.cards;
    versions.value = await api.listVersions(proofId);
    stale.value = null;
    loaded.value = true;
    await runVerify();
  } catch (e) {
    loadError.value = e instanceof ApiError ? `加载失败：${e.message}` : "加载失败";
  }
}

async function runVerify() {
  if (!loaded.value) return;
  const seq = ++verifySeq;
  verifying.value = true;
  try {
    const resp = await api.verifyDraft(proofId, revision.value, {
      tracks: tracks.value,
      cards: cards.value,
    });
    if (seq !== verifySeq) return; // 迟到响应，丢弃
    result.value = resp.result;
    stale.value = null;
  } catch (e) {
    if (seq !== verifySeq) return;
    if (e instanceof ApiError && e.status === 409) {
      stale.value = e.body?.current_revision ?? null;
    } else {
      notice.value = "核验请求失败，请检查网络";
    }
  } finally {
    if (seq === verifySeq) verifying.value = false;
  }
}

function scheduleVerify() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(runVerify, 350);
}
watch([tracks, cards], scheduleVerify, { deep: true });

async function save() {
  const seq = ++saveSeq;
  notice.value = "";
  try {
    const updated = await api.updateProof(proofId, revision.value, {
      title: title.value,
      tracks: tracks.value,
      cards: cards.value,
    });
    if (seq !== saveSeq) return; // 更晚的保存已发出，忽略本次迟到响应
    revision.value = updated.revision;
    stale.value = null;
    notice.value = `已保存（revision ${updated.revision}）`;
    runVerify();
  } catch (e) {
    if (seq !== saveSeq) return;
    if (e instanceof ApiError && e.status === 409) {
      stale.value = e.body?.current_revision ?? null;
    } else {
      notice.value = "保存失败";
    }
  }
}

async function reloadServer() {
  if (!confirm("放弃本地未保存的修改，重新加载服务器上的草稿？")) return;
  await load();
  notice.value = "已重新加载服务器草稿";
}

async function forceSave() {
  // 先取服务器当前 revision，再用本地内容覆盖保存
  try {
    const server = await api.getProof(proofId);
    revision.value = server.revision;
    await save();
  } catch {
    notice.value = "强制保存失败";
  }
}

async function publish() {
  try {
    const v = await api.publishVersion(proofId, revision.value, publishNote.value || undefined);
    versions.value = await api.listVersions(proofId);
    publishNote.value = "";
    notice.value = `已发布不可变版本 v${v.version_no}`;
    stale.value = null;
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) {
      stale.value = e.body?.current_revision ?? null;
    } else {
      notice.value = "发布失败";
    }
  }
}

async function checkVersion(no: number) {
  const resp = await api.verifyVersion(proofId, no);
  versionResult.value = { no, result: resp.result };
}

// ---------------- 轨道编辑 ----------------
function addTrack() {
  let n = tracks.value.length + 1;
  while (tracks.value.some((t) => t.id === `轨道${n}`)) n += 1;
  tracks.value.push({ id: `轨道${n}`, period: "2", phase: "0" });
}
function removeTrack(i: number) {
  tracks.value.splice(i, 1);
}
function trackProblems(t: Track, i: number): string[] {
  const problems: string[] = [];
  if (!t.id.trim()) problems.push("ID 不能为空");
  if (tracks.value.some((o, j) => j !== i && o.id === t.id)) problems.push("ID 重复");
  if (!isPosIntText(t.period)) problems.push("周期需为正整数");
  if (!isNonNegIntText(t.phase)) problems.push("相位需为非负整数（零基）");
  return problems;
}

// ---------------- 卡片编辑 ----------------
function addCard(type: CardType) {
  const last = cards.value.length - 1;
  const prev = cards.value.length - 2;
  switch (type) {
    case "source":
      cards.value.push({ type, track: tracks.value[0]?.id ?? "" });
      break;
    case "combine":
      cards.value.push({
        type,
        left: Math.max(0, prev),
        right: Math.max(0, last),
        witness: { u: "0", v: "0" },
      });
      break;
    case "normalize":
      cards.value.push({ type, card: Math.max(0, last) });
      break;
    case "contradiction":
      cards.value.push({ type, left: Math.max(0, prev), right: Math.max(0, last) });
      break;
  }
}
function updateCard(i: number, card: Card) {
  cards.value[i] = card;
}
function removeCard(i: number) {
  // 有后续卡引用时禁止删除（按钮已禁用，这里再兜底）
  const used = cards.value.some((c, j) => j > i && cardRefs(c).includes(i));
  if (used) return;
  cards.value.splice(i, 1);
  // 大于 i 的引用整体前移一位
  for (const c of cards.value) {
    if (c.type === "combine" || c.type === "contradiction") {
      if (c.left > i) c.left -= 1;
      if (c.right > i) c.right -= 1;
    } else if (c.type === "normalize") {
      if (c.card > i) c.card -= 1;
    }
  }
}

const firstErrorIndex = computed(() => result.value?.first_error?.card_index ?? null);
watch(firstErrorIndex, (idx) => {
  if (idx !== null) selected.value = idx;
});

onMounted(load);
</script>

<template>
  <div v-if="loadError" class="banner bad">
    {{ loadError }} <button @click="router.push('/')">返回列表</button>
  </div>
  <div v-else-if="!loaded" class="muted">加载中…</div>

  <div v-else class="editor">
    <div class="toolbar panel">
      <input v-model="title" class="title-input" placeholder="证明标题" />
      <span class="tag">revision {{ revision }}</span>
      <span v-if="verifying" class="muted">核验中…</span>
      <span class="spacer" />
      <button class="primary" @click="save">保存草稿</button>
      <input v-model="publishNote" class="note" placeholder="版本备注（可选）" />
      <button @click="publish">发布不可变版本</button>
      <button @click="router.push('/compare')">去对照</button>
    </div>

    <div v-if="stale !== null" class="banner warn">
      ⚠ 草稿已在别处更新（服务器 revision {{ stale }}，你基于 {{ revision }}）。
      核验与保存已被拒绝。
      <button @click="reloadServer">重新加载服务器草稿</button>
      <button @click="forceSave">以我的内容强制保存</button>
    </div>
    <div v-if="notice" class="banner info">{{ notice }}</div>

    <div class="columns">
      <div class="left-col">
        <section class="panel">
          <h3>轨道（翻页循环）</h3>
          <table class="grid">
            <thead>
              <tr><th>ID</th><th>周期 m（正整数）</th><th>相位 a（零基）</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="(t, i) in tracks" :key="i">
                <td>
                  <input v-model="t.id" :class="{ invalid: trackProblems(t, i).some((p) => p.includes('ID')) }" />
                </td>
                <td>
                  <input v-model="t.period" class="mono" :class="{ invalid: !isPosIntText(t.period) }" />
                </td>
                <td>
                  <input v-model="t.phase" class="mono" :class="{ invalid: !isNonNegIntText(t.phase) }" />
                </td>
                <td>
                  <button class="danger" @click="removeTrack(i)">✕</button>
                  <div v-if="trackProblems(t, i).length" class="problems">
                    {{ trackProblems(t, i).join("；") }}
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <button @click="addTrack">＋ 添加轨道</button>
          <p class="muted">每条轨道给出同余式 x ≡ 相位 (mod 周期)：第 x 帧时该轨道回到相位画面。</p>
        </section>

        <section class="panel">
          <h3>证明卡（按序引用前卡）</h3>
          <div class="add-row">
            <button @click="addCard('source')">＋来源</button>
            <button @click="addCard('combine')">＋合并</button>
            <button @click="addCard('normalize')">＋规范化</button>
            <button @click="addCard('contradiction')">＋冲突</button>
          </div>
          <div class="cards">
            <CardEditor
              v-for="(c, i) in cards"
              :key="i"
              :card="c"
              :index="i"
              :cards="cards"
              :tracks="tracks"
              :result="result"
              :selected="selected === i"
              @update="updateCard(i, $event)"
              @remove="removeCard(i)"
              @select="selected = selected === i ? null : i"
            />
          </div>
          <p v-if="!cards.length" class="muted">还没有卡。先为每条轨道添加「来源」卡。</p>
        </section>

        <section class="panel">
          <h3>不可变版本</h3>
          <p v-if="!versions.length" class="muted">尚未发布版本。发布后内容冻结，可随时核验与对照。</p>
          <table v-else class="grid">
            <thead>
              <tr><th>版本</th><th>备注</th><th>发布时间</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="v in versions" :key="v.version_no">
                <td class="mono">v{{ v.version_no }}</td>
                <td>{{ v.note || "—" }}</td>
                <td class="muted">{{ v.created_at }}</td>
                <td>
                  <button @click="checkVersion(v.version_no)">核验</button>
                  <button
                    @click="router.push({ path: '/compare', query: { left: `${proofId}:draft`, right: `${proofId}:v${v.version_no}` } })"
                  >
                    与草稿对照
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="versionResult" class="version-result">
            <h4>版本 v{{ versionResult.no }} 的核验结果</h4>
            <ResultView
              :result="versionResult.result"
              :loading="false"
              :selected="null"
              :hovered="null"
              compact
            />
          </div>
        </section>
      </div>

      <div class="right-col">
        <section class="panel">
          <h3>证明图（SVG 联动）</h3>
          <ProofGraph
            v-model:selected="selected"
            v-model:hovered="hovered"
            :cards="cards"
            :result="result"
          />
        </section>
        <section class="panel">
          <h3>核验结果</h3>
          <ResultView
            v-model:selected="selected"
            v-model:hovered="hovered"
            :result="result"
            :loading="verifying"
          />
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.editor {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.title-input {
  font-size: 16px;
  font-weight: 600;
  min-width: 220px;
}
.note {
  width: 160px;
}
.spacer {
  flex: 1;
}
.columns {
  display: grid;
  grid-template-columns: minmax(430px, 5fr) minmax(380px, 4fr);
  gap: 14px;
  align-items: start;
}
@media (max-width: 1100px) {
  .columns {
    grid-template-columns: 1fr;
  }
}
.left-col,
.right-col {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.add-row {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.cards {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.problems {
  color: var(--bad);
  font-size: 12px;
  margin-top: 3px;
}
.version-result {
  margin-top: 12px;
  border-top: 1px dashed var(--line);
  padding-top: 10px;
}
td input {
  width: 100%;
}
</style>
