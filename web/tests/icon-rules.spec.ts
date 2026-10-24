// An icon by state (app 0.4.112, model/icon-rules.ts): the editor keeps the rules as the add-on does, through the page
// document, the panel adds and removes them, and the mockup's card takes the icon the first fitting rule gives.
import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import IconRulesSection from "../src/components/inspector/IconRulesSection.vue";
import { setTileOption } from "../src/editor/tiles";
import { iconRuleMatch } from "../src/model/icon-rules";
import { canonicalOptions } from "../src/model/tile-options";
import type { Live } from "../src/model/tile-text";
import type { Inventory, Tile } from "../src/types";
import { useDocumentStore } from "../src/stores/document";
import { useInventoryStore } from "../src/stores/inventory";
import { useScreenStore } from "../src/stores/screen";
import { current, loadLayout, loadTiles } from "./helpers/fixtures";

const live = (state: string, a: Record<string, any> = {}): Live => ({ state, a });
const tile = (options: Tile["options"], entity = "climate.hall"): Tile => ({ id: "t", entity, name: "", slot: 0, options });

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline"))));
  useInventoryStore().inventory = { csrf: "t", connected: true,
    screens: [{ id: "living", name: "Living room", online: true, firmware: "0.67.0", board: "guition", tile_sizes: ["tall", "square"],
      shape: { width: 480, height: 480, columns: 2, rows: 3 }, layout: { title: "Living room", tiles: [] } }],
    entities: [{ id: "light.desk", name: "Desk", state: "on", area: "" }] } as unknown as Inventory;
  useScreenStore().selected = "living";
  useDocumentStore().documentGrid = { columns: 2, rows: 3 };
  loadLayout({ title: "Living room", tiles: [] });
});

describe("an icon by state", () => {
  it("gives the icon of the first rule that fits", () => {
    const rules = tile({ icons: [{ when: "heating", icon: "lightbulb" }, { below: 5, icon: "chandelier" }] });
    expect(iconRuleMatch(rules, live("heat", { hvac_action: "heating" }))).toBe("lightbulb");
    expect(iconRuleMatch(rules, live("heat", { hvac_action: "idle", current_temperature: 2 }))).toBe("chandelier");
    expect(iconRuleMatch(rules, live("heat", { hvac_action: "idle", current_temperature: 20 }))).toBeNull();
    expect(iconRuleMatch(tile({}), live("on"))).toBeNull();
  });

  it("keeps the rules the add-on takes and drops what it would refuse", () => {
    expect(canonicalOptions("light.a", { icons: [{ when: "on", icon: "lightbulb" }, { when: "Bad Word", icon: "lamp" },
      { above: 5, icon: "Not An Icon" }, { when: "clear-night", icon: "chandelier" }] }))
      .toEqual({ icons: [{ when: "on", icon: "lightbulb" }, { when: "clear-night", icon: "chandelier" }] });
    expect(canonicalOptions("light.a", { icons: [] })).toEqual({});
  });

  it("is kept through the page document, and the panel adds and removes a rule", async () => {
    const target: Tile = { entity: "light.desk", name: "", slot: 0 };
    loadTiles([target]);
    setTileOption(current(target)!, "icons", [{ when: "on", icon: "lamp" }]);
    expect(current(target)!.options?.icons).toEqual([{ when: "on", icon: "lamp" }]);
    const panel = mount(IconRulesSection, { props: { tile: current(target)! } });
    await panel.find(".icon-add").trigger("click");
    expect(current(target)!.options?.icons).toHaveLength(2);
    await panel.setProps({ tile: current(target)! });
    await panel.findAll(".icon-remove")[0].trigger("click");
    await panel.setProps({ tile: current(target)! });
    await panel.findAll(".icon-remove")[0].trigger("click");
    expect(current(target)!.options?.icons).toBeUndefined();
  });
});
