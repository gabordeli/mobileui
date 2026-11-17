import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function stubMatchMedia(light: boolean): void {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: query.includes("light") ? light : !light,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  );
}

async function loadTheme() {
  vi.resetModules();
  return import("./theme");
}

function themeColor(): string | null {
  return document
    .querySelector('meta[name="theme-color"]')
    ?.getAttribute("content") ?? null;
}

beforeEach(() => {
  localStorage.clear();
  document.head.innerHTML = '<meta name="theme-color" content="">';
  delete document.documentElement.dataset.theme;
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("theme", () => {
  it("defaults to the system light preference", async () => {
    stubMatchMedia(true);
    const { theme } = await loadTheme();
    expect(theme.value).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(themeColor()).toBe("#f3f6fb");
  });

  it("defaults to dark when the system prefers dark", async () => {
    stubMatchMedia(false);
    const { theme } = await loadTheme();
    expect(theme.value).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(themeColor()).toBe("#0b0d10");
  });

  it("prefers the stored theme over the system preference", async () => {
    localStorage.setItem("mobileui.theme", "dark");
    stubMatchMedia(true);
    const { theme } = await loadTheme();
    expect(theme.value).toBe("dark");
  });

  it("persists setTheme and toggleTheme", async () => {
    stubMatchMedia(true);
    const { setTheme, toggleTheme, theme } = await loadTheme();

    setTheme("dark");
    expect(theme.value).toBe("dark");
    expect(localStorage.getItem("mobileui.theme")).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(themeColor()).toBe("#0b0d10");

    toggleTheme();
    expect(theme.value).toBe("light");
    expect(localStorage.getItem("mobileui.theme")).toBe("light");
    expect(themeColor()).toBe("#f3f6fb");
  });
});
