import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it } from "vitest";

import { setLocale, t } from "../i18n";
import TokenGate from "./TokenGate.vue";

beforeEach(() => setLocale("en"));

function factory(overrides: Record<string, unknown> = {}) {
  return mount(TokenGate, {
    props: {
      initialToken: "",
      error: "",
      cancelable: false,
      pluginVersion: "0.1.3",
      ...overrides,
    },
  });
}

describe("TokenGate", () => {
  it("submits the trimmed token and shows the plugin version", async () => {
    const wrapper = factory({ initialToken: "  secret  " });
    expect(wrapper.text()).toContain("MobileUi v0.1.3");

    await wrapper.get("input").setValue("  abc  ");
    await wrapper.get("form").trigger("submit");

    expect(wrapper.emitted("submit")?.[0]).toEqual(["abc"]);
  });

  it("shows an error and emits cancel when cancelable", async () => {
    const wrapper = factory({ error: "bad token", cancelable: true });
    expect(wrapper.get('[role="alert"]').text()).toBe("bad token");

    const cancel = wrapper
      .findAll("button")
      .find((button) => button.text() === t("token.cancel"));
    expect(cancel).toBeDefined();
    await cancel!.trigger("click");

    expect(wrapper.emitted("cancel")).toHaveLength(1);
  });

  it("hides the cancel button and the error by default", () => {
    const wrapper = factory();
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(wrapper.findAll("button")).toHaveLength(1);
  });
});
