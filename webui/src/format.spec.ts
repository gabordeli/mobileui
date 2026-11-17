import { beforeEach, describe, expect, it } from "vitest";

import {
  formatBytes,
  formatEta,
  formatRate,
  formatRatio,
  stateClass,
} from "./format";
import { setLocale } from "./i18n";

beforeEach(() => setLocale("en"));

describe("formatBytes", () => {
  it("handles empty and negative values", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(-1)).toBe("0 B");
  });

  it("uses binary units and sensible precision", () => {
    expect(formatBytes(1024)).toBe("1.00 KiB");
    expect(formatBytes(1536)).toBe("1.50 KiB");
    expect(formatBytes(10 * 1024 * 1024)).toBe("10.0 MiB");
    expect(formatBytes(100 * 1024 * 1024)).toBe("100 MiB");
  });

  it("formats rates", () => {
    expect(formatRate(1024)).toBe("1.00 KiB/s");
  });
});

describe("formatEta", () => {
  it("handles unknown and zero", () => {
    expect(formatEta(-1)).toBe("∞");
    expect(formatEta(0)).toBe("—");
  });

  it("uses the locale units", () => {
    expect(formatEta(30)).toBe("30 s");
    expect(formatEta(90)).toBe("2 m");
    expect(formatEta(3600)).toBe("1 h");
    expect(formatEta(86400)).toBe("1 d");
  });
});

describe("formatRatio", () => {
  it("formats finite ratios", () => {
    expect(formatRatio(1.234)).toBe("1.23");
  });

  it("handles infinite ratios", () => {
    expect(formatRatio(-1)).toBe("∞");
  });
});

describe("stateClass", () => {
  it("normalizes Deluge states", () => {
    expect(stateClass("Downloading")).toBe("state-downloading");
    expect(stateClass("Allocating")).toBe("state-allocating");
    expect(stateClass("Some State")).toBe("state-some-state");
  });
});
