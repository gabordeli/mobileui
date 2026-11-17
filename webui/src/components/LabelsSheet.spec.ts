import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { setLocale, t } from "../i18n";
import { labels } from "./__fixtures__";
import LabelsSheet from "./LabelsSheet.vue";

beforeEach(() => setLocale("en"));

function factory(overrides: Record<string, unknown> = {}) {
  return mount(LabelsSheet, {
    props: { labels, canWrite: true, ...overrides },
    global: { stubs: { teleport: true } },
  });
}

describe("LabelsSheet", () => {
  it("lists the labels and emits a new id", async () => {
    const wrapper = factory();
    expect(wrapper.text()).toContain("film");
    expect(wrapper.text()).toContain("2");

    await wrapper.get(".label-add input").setValue("  new-label ");
    await wrapper.get(".label-add .action").trigger("click");

    expect(wrapper.emitted("add")?.[0]).toEqual(["new-label"]);
  });

  it("asks for confirmation before removing", async () => {
    const confirmMock = vi.fn(() => true);
    vi.stubGlobal("confirm", confirmMock);
    const wrapper = factory();

    await wrapper.get(".label-list .action").trigger("click");

    expect(confirmMock).toHaveBeenCalledWith(
      t("labels.confirmRemove", { name: "film" }),
    );
    expect(wrapper.emitted("remove")?.[0]).toEqual(["film"]);
  });

  it("does not remove when the confirmation is cancelled", async () => {
    vi.stubGlobal("confirm", vi.fn(() => false));
    const wrapper = factory();

    await wrapper.get(".label-list .action").trigger("click");

    expect(wrapper.emitted("remove")).toBeUndefined();
  });

  it("shows the empty state", () => {
    const wrapper = factory({ labels: [] });
    expect(wrapper.text()).toContain(t("labels.empty"));
  });

  it("hides the controls for a read-only account", () => {
    const wrapper = factory({ canWrite: false });

    expect(wrapper.find(".label-add").exists()).toBe(false);
    expect(wrapper.find(".label-list .action").exists()).toBe(false);
    expect(wrapper.get(".readonly-note").text()).toBe(t("auth.readonly"));
  });
});
