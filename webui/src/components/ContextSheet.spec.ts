import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setLocale, t } from "../i18n";
import { labels, torrent } from "./__fixtures__";
import ContextSheet from "./ContextSheet.vue";

beforeEach(() => setLocale("en"));

afterEach(() => {
  vi.unstubAllGlobals();
});

function factory(overrides: Record<string, unknown> = {}) {
  return mount(ContextSheet, {
    props: {
      torrent,
      labels,
      noLabelCount: 1,
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

describe("ContextSheet", () => {
  it("emits close from the close button and the backdrop", async () => {
    const wrapper = factory();

    await wrapper.get(`button[aria-label="${t("sheet.close")}"]`).trigger("click");
    await wrapper.get(".sheet-backdrop").trigger("click");

    expect(wrapper.emitted("close")).toHaveLength(2);
  });

  it("emits pause or resume depending on the state", async () => {
    const downloading = factory();
    await button(downloading, t("sheet.pause")).trigger("click");
    expect(downloading.emitted("action")?.[0]).toEqual([{ kind: "pause" }]);

    const paused = factory({ torrent: { ...torrent, state: "Paused" } });
    await button(paused, t("sheet.resume")).trigger("click");
    expect(paused.emitted("action")?.[0]).toEqual([{ kind: "resume" }]);
  });

  it("emits queue actions", async () => {
    const wrapper = factory();
    await button(wrapper, t("sheet.top")).trigger("click");
    await button(wrapper, t("sheet.up")).trigger("click");
    await button(wrapper, t("sheet.down")).trigger("click");
    await button(wrapper, t("sheet.bottom")).trigger("click");

    expect(wrapper.emitted("action")).toEqual([
      [{ kind: "queue", action: "top" }],
      [{ kind: "queue", action: "up" }],
      [{ kind: "queue", action: "down" }],
      [{ kind: "queue", action: "bottom" }],
    ]);
  });

  it("saves the selected label", async () => {
    const wrapper = factory();
    await wrapper.get("select").setValue("No Label");
    await button(wrapper, t("sheet.save")).trigger("click");

    expect(wrapper.emitted("action")?.[0]).toEqual([
      { kind: "label", label: "No Label" },
    ]);
  });

  it("removes with the data flag after confirmation", async () => {
    const confirm = vi.fn(() => true);
    vi.stubGlobal("confirm", confirm);
    const wrapper = factory();

    await wrapper.get('input[type="checkbox"]').setValue(true);
    await button(wrapper, t("sheet.remove")).trigger("click");

    expect(confirm).toHaveBeenCalledOnce();
    expect(wrapper.emitted("action")?.[0]).toEqual([
      { kind: "remove", remove_data: true },
    ]);
  });

  it("does not remove when the confirmation is cancelled", async () => {
    vi.stubGlobal("confirm", vi.fn(() => false));
    const wrapper = factory();

    await button(wrapper, t("sheet.remove")).trigger("click");

    expect(wrapper.emitted("action")).toBeUndefined();
  });
});
