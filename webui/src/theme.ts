import { ref } from "vue";

export type Theme = "dark" | "light";

const KEY = "mobileui.theme";
const stored = localStorage.getItem(KEY);
const systemLight = window.matchMedia?.("(prefers-color-scheme: light)").matches;
let initial: Theme = systemLight ? "light" : "dark";
if (stored === "dark" || stored === "light") initial = stored;

export const theme = ref<Theme>(initial);

export function applyTheme(): void {
  document.documentElement.dataset.theme = theme.value;
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", theme.value === "dark" ? "#0b0d10" : "#f3f6fb");
}

export function setTheme(next: Theme): void {
  theme.value = next;
  localStorage.setItem(KEY, next);
  applyTheme();
}

export function toggleTheme(): void {
  setTheme(theme.value === "dark" ? "light" : "dark");
}

applyTheme();
