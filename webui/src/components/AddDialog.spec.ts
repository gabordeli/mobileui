import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { setLocale, t } from "../i18n";
import { labels } from "./__fixtures__";
import AddDialog from "./AddDialog.vue";
import DirectoryPicker from "./DirectoryPicker.vue";

vi.mock("../api", () => ({
  addTorrentMagnet: vi.fn(),
  addTorrentUrl: vi.fn(),
  addTorrentFile: vi.fn(),
  listDirs: vi.fn(),
}));

beforeEach(() => {
  setLocale("en");
  vi.clearAllMocks();
  vi.mocked(api.addTorrentMagnet).mockResolvedValue({ id: "abc" });
  vi.mocked(api.addTorrentUrl).mockResolvedValue({ id: "ghi" });
  vi.mocked(api.addTorrentFile).mockResolvedValue({ id: "def" });
  vi.mocked(api.listDirs).mockResolvedValue({
    path: "/data/downloads",
    parent: "/data",
    writable: true,
    dirs: [],
    truncated: false,
  });
});

afterEach(() => localStorage.clear());

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
  it("prefills a shared magnet and submits it", async () => {
    const wrapper = factory({ initialMagnet: "magnet:?xt=urn:btih:deadbeef" });

    expect((wrapper.get("textarea").element as HTMLTextAreaElement).value).toBe(
      "magnet:?xt=urn:btih:deadbeef",
    );

    await button(wrapper, t("add.submit")).trigger("click");
    await flushPromises();

    expect(api.addTorrentMagnet).toHaveBeenCalledWith(
      "magnet:?xt=urn:btih:deadbeef",
      expect.any(Object),
    );
  });

  it("remembers the last path and label and resets the path", async () => {
    localStorage.setItem("mobileui.add.path", "/saved/path");
    localStorage.setItem("mobileui.add.label", "film");
    const wrapper = factory();

    expect(
      (wrapper.get('input[type="text"]').element as HTMLInputElement).value,
    ).toBe("/saved/path");
    expect((wrapper.get("select").element as HTMLSelectElement).value).toBe(
      "film",
    );

    await button(wrapper, t("add.defaultPath")).trigger("click");

    expect(
      (wrapper.get('input[type="text"]').element as HTMLInputElement).value,
    ).toBe("/data/downloads");
    expect(localStorage.getItem("mobileui.add.path")).toBeNull();
  });

  it("stores the path and label after a successful add", async () => {
    const wrapper = factory();
    await wrapper.get("textarea").setValue("magnet:?xt=urn:btih:abc");
    await wrapper.get('input[type="text"]').setValue("/new/path");
    await wrapper.get("select").setValue("film");

    await button(wrapper, t("add.submit")).trigger("click");
    await flushPromises();

    expect(localStorage.getItem("mobileui.add.path")).toBe("/new/path");
    expect(localStorage.getItem("mobileui.add.label")).toBe("film");
  });

  it("prefills the default path and closes", async () => {
    const wrapper = factory();
    expect(
      (wrapper.get('input[type="text"]').element as HTMLInputElement).value,
    ).toBe("/data/downloads");

    await wrapper.get(`button[aria-label="${t("sheet.close")}"]`).trigger("click");
    expect(wrapper.emitted("close")).toHaveLength(1);
  });

  it("picks the save path from the directory picker", async () => {
    const wrapper = factory();

    await button(wrapper, t("fs.browse")).trigger("click");
    await flushPromises();

    expect(api.listDirs).toHaveBeenCalledWith("/data/downloads");

    wrapper.findComponent(DirectoryPicker).vm.$emit("select", "/picked/path");
    await flushPromises();

    expect(
      (wrapper.get('input[type="text"]').element as HTMLInputElement).value,
    ).toBe("/picked/path");
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

  it("adds a torrent from a URL", async () => {
    const wrapper = factory();
    await button(wrapper, t("add.urlTab")).trigger("click");
    await wrapper
      .get('input[type="url"]')
      .setValue("https://example.com/demo.torrent");

    await button(wrapper, t("add.submit")).trigger("click");
    await flushPromises();

    expect(api.addTorrentUrl).toHaveBeenCalledWith(
      "https://example.com/demo.torrent",
      {
        label: undefined,
        download_location: "/data/downloads",
        add_paused: false,
      },
    );
    expect(wrapper.emitted("added")?.[0]).toEqual([{ id: "ghi" }]);
  });

  it("requires a URL before submitting", async () => {
    const wrapper = factory();
    await button(wrapper, t("add.urlTab")).trigger("click");
    await button(wrapper, t("add.submit")).trigger("click");

    expect(wrapper.get('[role="alert"]').text()).toBe(t("add.needUrl"));
    expect(api.addTorrentUrl).not.toHaveBeenCalled();
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
