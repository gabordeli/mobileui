import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setLocale, t } from "../i18n";
import { torrent } from "./__fixtures__";
import TorrentRow from "./TorrentRow.vue";

beforeEach(() => setLocale("en"));
afterEach(() => vi.useRealTimers());

function factory(overrides: Record<string, unknown> = {}) {
  return mount(TorrentRow, {
    props: { torrent, selected: false, selectionMode: false, ...overrides },
  });
}

describe("TorrentRow", () => {
  it("renders the torrent and emits select on click", async () => {
    const wrapper = factory();

    expect(wrapper.text()).toContain("Demo Movie 2024");
    expect(wrapper.text()).toContain("42.5%");
    expect(wrapper.text()).toContain("ETA");
    expect(wrapper.get("button").attributes("aria-label")).toBe(torrent.name);

    await wrapper.get("button").trigger("click");
    expect(wrapper.emitted("select")?.[0]).toEqual([torrent]);
  });

  it("emits longPress after 500ms and suppresses the click", async () => {
    vi.useFakeTimers();
    const wrapper = factory();
    const row = wrapper.get("button");

    await row.trigger("pointerdown", { button: 0, clientX: 10, clientY: 10 });
    vi.advanceTimersByTime(500);

    expect(wrapper.emitted("longPress")?.[0]).toEqual([torrent]);

    await row.trigger("pointerup");
    await row.trigger("click");
    expect(wrapper.emitted("select")).toBeUndefined();
  });

  it("cancels the long press when the pointer moves", async () => {
    vi.useFakeTimers();
    const wrapper = factory();
    const row = wrapper.get("button");

    await row.trigger("pointerdown", { button: 0, clientX: 10, clientY: 10 });
    await row.trigger("pointermove", { clientX: 30, clientY: 10 });
    vi.advanceTimersByTime(500);

    expect(wrapper.emitted("longPress")).toBeUndefined();

    await row.trigger("pointerup");
    await row.trigger("click");
    expect(wrapper.emitted("select")).toBeUndefined();

    await row.trigger("click");
    expect(wrapper.emitted("select")?.[0]).toEqual([torrent]);
  });

  it("hides ETA when paused and clamps the progress", () => {
    const wrapper = factory({
      torrent: { ...torrent, state: "Paused", progress: 150 },
    });

    expect(wrapper.text()).toContain("100.0%");
    expect(wrapper.text()).not.toContain("ETA");
  });

  it("shows the selection check and pressed state", () => {
    const wrapper = factory({ selectionMode: true, selected: true });

    expect(wrapper.get("button").attributes("aria-pressed")).toBe("true");
    expect(wrapper.get(".row-check").classes()).toContain("on");
    expect(wrapper.get("button").classes()).toContain("selected");
  });

  it("does not show the check outside selection mode", () => {
    const wrapper = factory({ selected: true });

    expect(wrapper.find(".row-check").exists()).toBe(false);
    expect(wrapper.get("button").attributes("aria-pressed")).toBeUndefined();
  });

  it("shows an error badge for a failed torrent", () => {
    const wrapper = factory({
      torrent: { ...torrent, state: "Error", message: "Tracker error" },
    });

    expect(wrapper.get(".row-error").text()).toBe(t("row.error"));
    expect(wrapper.get(".row-error").attributes("title")).toBe("Tracker error");
    expect(wrapper.get("button").classes()).toContain("error");
  });
});
