import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../api";
import { setLocale, t } from "../i18n";
import type { DirListing } from "../types";
import DirectoryPicker from "./DirectoryPicker.vue";

vi.mock("../api", () => ({
  listDirs: vi.fn(),
}));

const listings: Record<string, DirListing> = {
  "/data": {
    path: "/data",
    parent: "/",
    writable: true,
    dirs: [
      { name: "movies", path: "/data/movies", writable: true },
      { name: "locked", path: "/data/locked", writable: false },
    ],
    truncated: false,
  },
  "/data/movies": {
    path: "/data/movies",
    parent: "/data",
    writable: true,
    dirs: [],
    truncated: false,
  },
  "/data/locked": {
    path: "/data/locked",
    parent: "/data",
    writable: false,
    dirs: [],
    truncated: false,
  },
};

function factory(initialPath = "/data") {
  return mount(DirectoryPicker, {
    props: { initialPath },
    global: { stubs: { teleport: true } },
  });
}

beforeEach(() => {
  setLocale("en");
  vi.clearAllMocks();
  vi.mocked(api.listDirs).mockImplementation(async (path) => {
    const listing = listings[path];
    if (!listing) throw new Error("missing listing");
    return listing;
  });
});

describe("DirectoryPicker", () => {
  it("loads the initial directory and lists subdirectories", async () => {
    const wrapper = factory();
    await flushPromises();

    expect(api.listDirs).toHaveBeenCalledWith("/data");
    expect(wrapper.get(".fs-path").text()).toBe("/data");
    expect(wrapper.text()).toContain("movies");
    expect(wrapper.text()).toContain("locked");
    expect(wrapper.text()).toContain(t("fs.locked"));
  });

  it("navigates into a directory and selects it", async () => {
    const wrapper = factory();
    await flushPromises();

    await wrapper.findAll(".fs-row")[0].trigger("click");
    await flushPromises();

    expect(api.listDirs).toHaveBeenLastCalledWith("/data/movies");
    expect(wrapper.get(".fs-path").text()).toBe("/data/movies");
    expect(wrapper.text()).toContain(t("fs.empty"));

    await wrapper.get(".add-actions .primary").trigger("click");

    expect(wrapper.emitted("select")?.[0]).toEqual(["/data/movies"]);
  });

  it("navigates up and refreshes", async () => {
    const wrapper = factory("/data/movies");
    await flushPromises();

    await wrapper.findAll(".fs-tools .action")[0].trigger("click");
    await flushPromises();
    expect(api.listDirs).toHaveBeenLastCalledWith("/data");

    await wrapper.findAll(".fs-tools .action")[1].trigger("click");
    await flushPromises();
    expect(api.listDirs).toHaveBeenLastCalledWith("/data");
  });

  it("shows the truncation notice and closes", async () => {
    vi.mocked(api.listDirs).mockResolvedValueOnce({
      ...listings["/data"],
      truncated: true,
    });
    const wrapper = factory();
    await flushPromises();

    expect(wrapper.text()).toContain(t("fs.truncated"));

    await wrapper
      .get(`button[aria-label="${t("sheet.close")}"]`)
      .trigger("click");

    expect(wrapper.emitted("close")).toHaveLength(1);
  });

  it("disables selecting a read-only directory", async () => {
    const wrapper = factory("/data/locked");
    await flushPromises();

    expect(wrapper.text()).toContain(t("fs.notWritable"));
    expect(
      (wrapper.get(".add-actions .primary").element as HTMLButtonElement)
        .disabled,
    ).toBe(true);
  });

  it("shows the backend error", async () => {
    vi.mocked(api.listDirs).mockRejectedValueOnce(new Error("denied"));
    const wrapper = factory();
    await flushPromises();

    expect(wrapper.get('[role="alert"]').text()).toBe("denied");
  });
});
