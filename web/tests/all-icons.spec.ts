// Every icon of Home Assistant (app 0.4.115): the picker finds any icon of Material Design Icons by its name beyond the
// set it opens with, a tile keeps one, and the icon alone on a card, without its circle, is kept as the add-on keeps it.
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import IconChoices from "../src/components/IconChoices.vue";
import { canonicalOptions } from "../src/model/tile-options";
import type { Inventory } from "../src/types";
import { useEntitiesStore } from "../src/stores/entities";
import { useInventoryStore } from "../src/stores/inventory";

const ALL = { "lamp": "F06B5", "fridge-outline": "F0293", "fridge-alert": "F11B1", "bee": "F0FA1" };

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn((url: string) => url === "api/icons/all"
    ? Promise.resolve(new Response(JSON.stringify(ALL), { status: 200, headers: { "Content-Type": "application/json" } }))
    : Promise.reject(new Error("offline"))));
  useInventoryStore().inventory = { csrf: "t", connected: true, screens: [], entities: [],
    icons: { groups: [{ label: "Lighting", icons: [{ name: "lamp", cp: "F06B5", label: "Table lamp" }]}], defaults: {}, fallback: "F0425",
             builtin: {}, weather: {}, sun: {}, controls: {} } } as unknown as Inventory;
});

describe("every icon of Home Assistant", () => {
  it("finds an icon beyond the set by its name and picks it", async () => {
    const wrapper = mount(IconChoices, { props: { selected: "auto", automatic: "F0335", autoLabel: "Automatic" } });
    await flushPromises();
    await wrapper.find("input").setValue("fridge");
    const found = wrapper.findAll(".icon-choice").filter((button) => button.attributes("title")?.startsWith("fridge"));
    expect(found.map((button) => button.attributes("title"))).toEqual(["fridge-outline", "fridge-alert"]);
    await found[0].trigger("click");
    expect(wrapper.emitted("pick")?.[0]).toEqual(["fridge-outline"]);
    // The set's own icon shows once, in its group.
    await wrapper.find("input").setValue("lamp");
    expect(wrapper.findAll(".icon-choice").filter((button) => button.attributes("title") === "lamp")).toHaveLength(0);
  });

  it("names an icon beyond the set once the whole list is here", async () => {
    const entities = useEntitiesStore();
    expect(entities.iconNamed("bee")).toBeUndefined();
    await flushPromises();
    expect(entities.iconNamed("bee")).toEqual({ name: "bee", cp: "F0FA1", label: "bee" });
    expect(entities.iconNamed("lamp")?.label).toBe("Table lamp");
  });

  it("keeps the icon alone only as true", () => {
    expect(canonicalOptions("light.a", { icon_plain: true })).toEqual({ icon_plain: true });
    expect(canonicalOptions("light.a", { icon_plain: false })).toEqual({});
    expect(canonicalOptions("light.a", { icon: "fridge-outline" })).toEqual({ icon: "fridge-outline" });
  });
});
