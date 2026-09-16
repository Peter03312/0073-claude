<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api, ApiError } from "../api";
import { EXAMPLES } from "../examples";
import type { ProofDraft } from "../types";

const router = useRouter();
const proofs = ref<ProofDraft[]>([]);
const loading = ref(true);
const error = ref("");
const newTitle = ref("");
const templateKey = ref("compatible");

async function load() {
  loading.value = true;
  try {
    proofs.value = await api.listProofs();
    error.value = "";
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : "无法连接核验服务";
  } finally {
    loading.value = false;
  }
}

async function create() {
  const tpl = EXAMPLES.find((t) => t.key === templateKey.value) ?? EXAMPLES[0];
  const proof = await api.createProof({
    title: newTitle.value.trim() || tpl.title,
    tracks: tpl.tracks,
    cards: tpl.cards,
  });
  router.push(`/proofs/${proof.id}`);
}

async function remove(p: ProofDraft) {
  if (!confirm(`删除证明「${p.title}」及其全部版本？`)) return;
  await api.deleteProof(p.id);
  await load();
}

onMounted(load);
</script>

<template>
  <div class="home">
    <section class="panel intro">
      <h2>给翻页动画一个不用猜的答案</h2>
      <p>
        每条轨道是一个固定周期的翻页循环。想证明“第几帧所有轨道再次同帧”，
        就把证明卡一张张摆出来：<b>来源</b>引入轨道、<b>合并</b>用中国剩余定理拼接、
        <b>规范化</b>化简余数、<b>冲突</b>宣告无解。服务器用任意精度整数逐卡核验，
        第一处非法步骤会被精确定位——不靠预览，不靠猜。
      </p>
    </section>

    <section class="panel">
      <h3>新建证明</h3>
      <div class="create-row">
        <input v-model="newTitle" placeholder="标题（可留空）" />
        <select v-model="templateKey">
          <option v-for="t in EXAMPLES" :key="t.key" :value="t.key">{{ t.label }}</option>
        </select>
        <button class="primary" @click="create">创建并打开</button>
      </div>
    </section>

    <section class="panel">
      <h3>我的证明</h3>
      <p v-if="loading" class="muted">加载中…</p>
      <p v-else-if="error" class="banner bad">{{ error }}</p>
      <p v-else-if="!proofs.length" class="muted">还没有证明，从上面的模板开始吧。</p>
      <table v-else class="grid">
        <thead>
          <tr>
            <th>标题</th><th>revision</th><th>版本数</th><th>更新时间</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in proofs" :key="p.id">
            <td>
              <a class="link" @click="router.push(`/proofs/${p.id}`)">{{ p.title }}</a>
            </td>
            <td class="mono">{{ p.revision }}</td>
            <td class="mono">{{ p.version_count }}</td>
            <td class="muted">{{ p.updated_at }}</td>
            <td>
              <button @click="router.push(`/proofs/${p.id}`)">打开</button>
              <button class="danger" @click="remove(p)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 900px;
}
.intro p {
  line-height: 1.8;
  margin: 0;
}
.create-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.create-row input {
  flex: 1;
  min-width: 200px;
}
.link {
  color: var(--accent);
  cursor: pointer;
  text-decoration: none;
  font-weight: 600;
}
.link:hover {
  text-decoration: underline;
}
td button {
  margin-right: 6px;
}
</style>
