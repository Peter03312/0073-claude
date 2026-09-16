<script setup lang="ts">
import { RouterLink, RouterView } from "vue-router";
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink to="/" class="brand">
        <span class="brand-mark">🎞️</span>
        <span>
          <strong>同帧证明所</strong>
          <small>翻页动画 · 循环对齐的机器核验</small>
        </span>
      </RouterLink>
      <nav>
        <RouterLink to="/" exact-active-class="active">证明列表</RouterLink>
        <RouterLink to="/compare" active-class="active">对照两份证明</RouterLink>
      </nav>
    </header>
    <main>
      <RouterView />
    </main>
    <footer class="foot">
      所有核验都在服务端用任意精度整数完成：不猜、不枚举、不信浮点。
    </footer>
  </div>
</template>

<style>
:root {
  --ink: #2b2440;
  --ink-soft: #6b6484;
  --paper: #f6f4fb;
  --card: #ffffff;
  --line: #e3def0;
  --accent: #6c5ce7;
  --accent-soft: #ece9fd;
  --ok: #1e9e6a;
  --ok-soft: #e2f6ec;
  --bad: #d84a4a;
  --bad-soft: #fdeaea;
  --warn: #c98a04;
  --warn-soft: #fdf3d8;
  --mono: "SFMono-Regular", "JetBrains Mono", Consolas, "Liberation Mono", monospace;
}
* {
  box-sizing: border-box;
}
body {
  margin: 0;
  font-family:
    "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC",
    system-ui, sans-serif;
  color: var(--ink);
  background: var(--paper);
}
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 22px;
  background: var(--card);
  border-bottom: 1px solid var(--line);
  position: sticky;
  top: 0;
  z-index: 10;
}
.brand {
  display: flex;
  gap: 10px;
  align-items: center;
  text-decoration: none;
  color: var(--ink);
}
.brand-mark {
  font-size: 26px;
}
.brand strong {
  display: block;
  font-size: 17px;
}
.brand small {
  color: var(--ink-soft);
  font-size: 12px;
}
.topbar nav {
  display: flex;
  gap: 6px;
}
.topbar nav a {
  padding: 7px 14px;
  border-radius: 999px;
  text-decoration: none;
  color: var(--ink-soft);
  font-size: 14px;
}
.topbar nav a.active {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
}
main {
  flex: 1;
  padding: 20px 22px 40px;
  max-width: 1440px;
  width: 100%;
  margin: 0 auto;
}
.foot {
  text-align: center;
  color: var(--ink-soft);
  font-size: 12px;
  padding: 14px;
}

/* ---------- 通用控件 ---------- */
button {
  font: inherit;
  cursor: pointer;
  border: 1px solid var(--line);
  background: var(--card);
  color: var(--ink);
  border-radius: 8px;
  padding: 6px 14px;
  transition: 0.15s;
}
button:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}
button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
button.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
button.primary:hover:not(:disabled) {
  background: #5a4bd1;
  color: #fff;
}
button.danger:hover:not(:disabled) {
  border-color: var(--bad);
  color: var(--bad);
}
input,
select,
textarea {
  font: inherit;
  color: var(--ink);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 6px 10px;
  background: #fff;
}
input:focus,
select:focus,
textarea:focus {
  outline: 2px solid var(--accent-soft);
  border-color: var(--accent);
}
input.invalid {
  border-color: var(--bad);
  background: var(--bad-soft);
}
input.mono,
.mono {
  font-family: var(--mono);
  font-size: 13px;
}
.panel {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 16px 18px;
}
.panel h2,
.panel h3 {
  margin: 0 0 12px;
}
.muted {
  color: var(--ink-soft);
  font-size: 13px;
}
.tag {
  display: inline-block;
  padding: 1px 9px;
  border-radius: 999px;
  font-size: 12px;
  background: var(--accent-soft);
  color: var(--accent);
}
.banner {
  border-radius: 10px;
  padding: 10px 14px;
  margin-bottom: 12px;
  font-size: 14px;
}
.banner.ok {
  background: var(--ok-soft);
  color: var(--ok);
  border: 1px solid #b7e6cf;
}
.banner.bad {
  background: var(--bad-soft);
  color: var(--bad);
  border: 1px solid #f3c1c1;
}
.banner.warn {
  background: var(--warn-soft);
  color: var(--warn);
  border: 1px solid #eed9a0;
}
.banner.info {
  background: var(--accent-soft);
  color: var(--accent);
  border: 1px solid #d4ccf5;
}
table.grid {
  border-collapse: collapse;
  width: 100%;
}
table.grid th,
table.grid td {
  text-align: left;
  padding: 6px 8px;
  border-bottom: 1px solid var(--line);
  font-size: 14px;
}
table.grid th {
  color: var(--ink-soft);
  font-weight: 600;
  font-size: 12px;
}
</style>
