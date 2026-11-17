import { beforeEach, describe, expect, it } from "vitest";

import { locale, setLocale, stateLabel, t, toggleLocale } from "./i18n";

beforeEach(() => setLocale("hu"));

describe("t", () => {
  it("translates messages with variables", () => {
    expect(t("filters.total", { count: 3 })).toBe("3 torrent");
    setLocale("en");
    expect(t("filters.total", { count: 3 })).toBe("3 torrents");
  });

  it("falls back to the key for unknown messages", () => {
    expect(t("missing.key")).toBe("missing.key");
  });
});

describe("locale", () => {
  it("toggles and persists the language", () => {
    setLocale("hu");
    toggleLocale();
    expect(locale.value).toBe("en");
    expect(document.documentElement.lang).toBe("en");
    expect(localStorage.getItem("mobileui.locale")).toBe("en");
  });
});

describe("stateLabel", () => {
  it("translates known states and preserves unknown ones", () => {
    expect(stateLabel("Queued")).toBe("Sorban");
    setLocale("en");
    expect(stateLabel("Queued")).toBe("Queued");
    expect(stateLabel("Unknown")).toBe("Unknown");
  });
});
