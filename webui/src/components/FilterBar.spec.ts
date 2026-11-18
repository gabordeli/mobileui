import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it } from "vitest";

import { setLocale, t } from "../i18n";
import type { TorrentFilters } from "../types";
import { labels } from "./__fixtures__";
import FilterBar from "./FilterBar.vue";

const filters: TorrentFilters = { q: "", state: "", label: "", sort: "name" };

beforeEach(() => setLocale("en"));

function factory(overrides: Record<string, unknown> = {}) {
  return mount(FilterBar, {
    props: {
      filters,
      labels,
      noLabelCount: 1,
      total: 4,
      loaded: 2,
      ...overrides,
    },
  });
}

describe("FilterBar", () => {
  it("renders the counts and the label options", () => {
    const wrapper = factory();
    expect(wrapper.text()).toContain(t("filters.total", { count: 4 }));
    expect(wrapper.text()).toContain(t("filters.loaded", { count: 2 }));
    expect(wrapper.text()).toContain("film (2)");
    expect(wrapper.text()).toContain(`${t("add.noLabel")} (1)`);
  });

  it("emits search changes", async () => {
    const wrapper = factory();
    await wrapper.get('input[type="search"]').setValue("abc");
    expect(wrapper.emitted("update")?.[0]).toEqual([{ q: "abc" }]);
  });

  it("maps the state filter and clears it with All", async () => {
    const wrapper = factory();
    const state = wrapper.findAll("select")[0];

    await state.setValue("Paused");
    expect(wrapper.emitted("update")?.[0]).toEqual([{ state: "Paused" }]);

    await state.setValue("All");
    expect(wrapper.emitted("update")?.[1]).toEqual([{ state: "" }]);
  });

  it("emits label and sort changes", async () => {
    const wrapper = factory();
    const [, label, sort] = wrapper.findAll("select");

    await label.setValue("film");
    expect(wrapper.emitted("update")?.[0]).toEqual([{ label: "film" }]);

    await label.setValue("No Label");
    expect(wrapper.emitted("update")?.[1]).toEqual([{ label: "No Label" }]);

    await sort.setValue("-ratio");
    expect(wrapper.emitted("update")?.[2]).toEqual([{ sort: "-ratio" }]);
  });

  it("offers sorting by the added date", async () => {
    const wrapper = factory();
    const sort = wrapper.findAll("select")[2];
    const option = sort
      .findAll("option")
      .find((item) => item.element.value === "-time_added");

    expect(option?.text()).toBe(t("sort.added"));

    await sort.setValue("-time_added");
    expect(wrapper.emitted("update")?.[0]).toEqual([{ sort: "-time_added" }]);
  });

  it("emits manageLabels from the labels button", async () => {
    const wrapper = factory();

    await wrapper.get(".filter-labels").trigger("click");

    expect(wrapper.emitted("manageLabels")).toHaveLength(1);
  });
});
