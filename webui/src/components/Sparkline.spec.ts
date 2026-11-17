import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import Sparkline from "./Sparkline.vue";

describe("Sparkline", () => {
  it("draws a line for both series", () => {
    const wrapper = mount(Sparkline, {
      props: { down: [0, 10, 5], up: [0, 2, 4] },
    });

    expect(wrapper.findAll("polyline")).toHaveLength(2);
    expect(wrapper.get(".spark-down").attributes("points")).toContain("0.00");
    expect(wrapper.get(".spark-up").attributes("points")).toContain("30.00");
  });

  it("renders a flat line for a single point", () => {
    const wrapper = mount(Sparkline, {
      props: { down: [5], up: [] },
    });

    const points = wrapper.get(".spark-down").attributes("points") ?? "";
    expect(points.split(" ")).toHaveLength(2);
    expect(wrapper.findAll("polyline")).toHaveLength(1);
  });

  it("renders only the baseline without data", () => {
    const wrapper = mount(Sparkline, { props: { down: [], up: [] } });

    expect(wrapper.findAll("polyline")).toHaveLength(0);
    expect(wrapper.find(".spark-base").exists()).toBe(true);
  });
});
