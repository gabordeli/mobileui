import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setLocale } from "../i18n";
import { torrent } from "./__fixtures__";
import TorrentRow from "./TorrentRow.vue";

beforeEach(() => setLocale("en"));
afterEach(() => vi.useRealTimers());

describe("TorrentRow", () => {
  it("renders the torrent and emits select on click", async () => {
    const wrapper = mount(TorrentRow, { props: { torrent } });

    expect(wrapper.text()).toContain("Demo Movie 2024");
    expect(wrapper.text()).toContain("42.5%");
    expect(wrapper.text()).toContain("ETA");
    expect(wrapper.get("article").attributes("aria-label")).toBe(torrent.name);

    await wrapper.get("article").trigger("click");
    expect(wrapper.emitted("select")?.[0]).toEqual([torrent]);
  });

  it("emits longPress after 500ms and suppresses the click", async () => {
    vi.useFakeTimers();
    const wrapper = mount(TorrentRow, { props: { torrent } });
    const row = wrapper.get("article");

    await row.trigger("pointerdown", { button: 0, clientX: 10, clientY: 10 });
    vi.advanceTimersByTime(500);

    expect(wrapper.emitted("longPress")?.[0]).toEqual([torrent]);

    await row.trigger("pointerup");
    await row.trigger("click");
    expect(wrapper.emitted("select")).toBeUndefined();
  });

  it("cancels the long press when the pointer moves", async () => {
    vi.useFakeTimers();
    const wrapper = mount(TorrentRow, { props: { torrent } });
    const row = wrapper.get("article");

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
    const wrapper = mount(TorrentRow, {
      props: { torrent: { ...torrent, state: "Paused", progress: 150 } },
    });

    expect(wrapper.text()).toContain("100.0%");
    expect(wrapper.text()).not.toContain("ETA");
  });
});
