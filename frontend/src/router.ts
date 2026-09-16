import { createRouter, createWebHistory } from "vue-router";
import HomeView from "./views/HomeView.vue";
import EditorView from "./views/EditorView.vue";
import CompareView from "./views/CompareView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: HomeView },
    { path: "/proofs/:id", name: "editor", component: EditorView },
    { path: "/compare", name: "compare", component: CompareView },
  ],
});
