import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { setLocale, t } from "../i18n";
import { labels } from "./__fixtures__";
import AddDialog from "./AddDialog.vue";

vi.mock("../api", () => ({
  addTorrentMagnet: vi.fn(),
  addTorrentFile: vi.fn(),
}));

beforeEach(() => {
  setLocale("en");
  vi.clearAllMocks();
  vi.mocked(api.addTorrentMagnet).mockResolvedValue({ id: "abc" });
  vi.mocked(api.addTorrentFile).mockResolvedValue({ id: "def" });
});

function factory(overrides: Record<string, unknown> = {}) {
  return mount(AddDialog, {
    props: {
      labels,
      noLabelCount: 1,
      defaultPath: "/data/downloads",
      ...overrides,
    },
    global: { stubs: { teleport: true } },
  });
}

function button(wrapper: ReturnType<typeof factory>, label: string) {
  const found = wrapper.findAll("button").find((item) => item.text() === label);
  if (!found) throw new Error(`button not found: ${label}`);
  return found;
}

describe("AddDialog", () => {
  it("prefills the default path and closes", async () => {
    const wrapper = factory();
    expect(
      (wrapper.get('input[type="text"]').element as HTMLInputElement).value,
    ).toBe("/data/downloads");

    await wrapper.get(`button[aria-label="${t("sheet.close")}"]`).trigger("click");
    expect(wrapper.emitted("close")).toHaveLength(1);
  });

  it("requires a magnet before submitting", async () => {
    const wrapper = factory();
    await button(wrapper, t("add.submit")).trigger("click");

    expect(wrapper.get('[role="alert"]').text()).toBe(t("add.needMagnet"));
    expect(api.addTorrentMagnet).not.toHaveBeenCalled();
  });

  it("adds a magnet with the form options", async () => {
    const wrapper = factory();

    await wrapper.get("textarea").setValue("magnet:?xt=urn:btih:abc");
    await wrapper.get("select").setValue("film");
    await wrapper.get('input[type="text"]').setValue("/data/media");
    await wrapper.get('input[type="checkbox"]').setValue(true);
    await button(wrapper, t("add.submit")).trigger("click");
    await flushPromises();

    expect(api.addTorrentMagnet).toHaveBeenCalledWith(
      "magnet:?xt=urn:btih:abc",
      {
        label: "film",
        download_location: "/data/media",
        add_paused: true,
      },
    );
    expect(wrapper.emitted("added")?.[0]).toEqual([{ id: "abc" }]);
    expect(wrapper.emitted("toast")?.[0]).toEqual([t("toast.added")]);
    expect(wrapper.emitted("close")).toHaveLength(1);
  });

  it("uploads a .torrent file", async () => {
    const wrapper = factory();
    await button(wrapper, t("add.fileTab")).trigger("click");

    const file = new File(["x"], "demo.torrent", {
      type: "application/x-bittorrent",
    });
    const input = wrapper.get('input[type="file"]');
    Object.defineProperty(input.element, "files", {
      configurable: true,
      value: [file],
    });
    await input.trigger("change");
    await button(wrapper, t("add.submit")).trigger("click");
    await flushPromises();

    expect(api.addTorrentFile).toHaveBeenCalledWith(file, {
      label: undefined,
      download_location: "/data/downloads",
      add_paused: false,
    });
    expect(wrapper.emitted("added")?.[0]).toEqual([{ id: "def" }]);
  });

  it("shows the API error and stays open", async () => {
    vi.mocked(api.addTorrentMagnet).mockRejectedValueOnce(new Error("boom"));
    const wrapper = factory();

    await wrapper.get("textarea").setValue("magnet:?xt=urn:btih:abc");
    await button(wrapper, t("add.submit")).trigger("click");
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toBe("boom");
    expect(wrapper.emitted("close")).toBeUndefined();
  });
});
