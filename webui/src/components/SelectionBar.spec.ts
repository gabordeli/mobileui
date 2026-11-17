import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { setLocale, t } from "../i18n";
import SelectionBar from "./SelectionBar.vue";

beforeEach(() => setLocale("en"));

const labels = [{ id: "movies", count: 2 }];

function factory(overrides: Record<string, unknown> = {}) {
  return mount(SelectionBar, {
    props: { count: 3, busy: false, canWrite: true, labels, ...overrides },
  });
}

function button(wrapper: ReturnType<typeof factory>, label: string) {
  return wrapper.findAll("button").find((item) => item.text() === label)!;
}

describe("SelectionBar", () => {
  it("shows the selected count and emits close/selectAll", async () => {
    const wrapper = factory();
    expect(wrapper.text()).toContain(t("bulk.selected", { count: 3 }));

    await button(wrapper, t("bulk.all")).trigger("click");
    expect(wrapper.emitted("selectAll")).toHaveLength(1);

    await wrapper
      .get(`button[aria-label="${t("bulk.cancel")}"]`)
      .trigger("click");
    expect(wrapper.emitted("close")).toHaveLength(1);
  });

  it("emits pause and resume actions", async () => {
    const wrapper = factory();

    await button(wrapper, t("bulk.pause")).trigger("click");
    await button(wrapper, t("bulk.resume")).trigger("click");

    expect(wrapper.emitted("action")?.[0]).toEqual([{ kind: "pause" }]);
    expect(wrapper.emitted("action")?.[1]).toEqual([{ kind: "resume" }]);
  });

  it("asks for confirmation before removing", async () => {
    const wrapper = factory();

    await button(wrapper, t("bulk.remove")).trigger("click");
    expect(wrapper.text()).toContain(t("bulk.confirmRemove", { count: 3 }));
    expect(wrapper.get(".selection-remove input").element).toHaveProperty(
      "checked",
      false,
    );

    await wrapper.get(".selection-remove .action.danger").trigger("click");

    expect(wrapper.emitted("action")?.[0]).toEqual([
      { kind: "remove", removeData: false },
    ]);
  });

  it("can delete the downloaded data with the bulk remove", async () => {
    const wrapper = factory();

    await button(wrapper, t("bulk.remove")).trigger("click");
    await wrapper.get(".selection-remove input").setValue(true);
    await wrapper.get(".selection-remove .action.danger").trigger("click");

    expect(wrapper.emitted("action")?.[0]).toEqual([
      { kind: "remove", removeData: true },
    ]);
  });

  it("applies a label from the picker", async () => {
    const wrapper = factory();

    await button(wrapper, t("bulk.label")).trigger("click");
    await wrapper.get("select").setValue("movies");
    await button(wrapper, t("sheet.save")).trigger("click");

    expect(wrapper.emitted("action")?.[0]).toEqual([
      { kind: "label", label: "movies" },
    ]);
  });

  it("hides the actions for a read-only account", () => {
    const wrapper = factory({ canWrite: false });

    expect(wrapper.findAll("button")).toHaveLength(2);
    expect(wrapper.get(".readonly-note").text()).toBe(t("auth.readonly"));
    expect(wrapper.find("select").exists()).toBe(false);
  });
});
