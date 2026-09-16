import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// 开发服务器把 /api 代理到本地后端；容器里由 nginx 反代到 api 服务
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.API_ORIGIN ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
