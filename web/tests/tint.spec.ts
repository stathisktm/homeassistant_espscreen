// A card's colour by state (app 0.4.91, model/tint.ts): the first rule that fits, the temperature a rule compares, and
// the softening the screen gives a colour of its own (theme::surface) so the mockup matches the glass.
import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TintSection from "../src/components/inspector/TintSection.vue";
import { canonicalOptions } from "../src/model/tile-options";
import { soften, tintColour, tintRules } from "../src/model/tint";
import type { Live } from "../src/model/tile-text";
import type { Inventory, Tile } from "../src/types";
import { useDocumentStore } from "../src/stores/document";
import { useInventoryStore } from "../src/stores/inventory";
import { useScreenStore } from "../src/stores/screen";
import { current, loadLayout, loadTiles } from "./helpers/fixtures";

const live = (state: string, a: Record<string, any> = {}): Live => ({ state, a });
const tile = (options: Tile["options"], entity = "climate.hall"): Tile => ({ id: "t", entity, name: "", slot: 0, options });
const none = () => null;

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline"))));
  useInventoryStore().inventory = { csrf: "t", connected: true,
    screens: [{ id: "living", name: "Living room", online: true, firmware: "0.57.0", board: "guition", tile_sizes: ["tall", "square"],
      shape: { width: 480, height: 480, columns: 2, rows: 3 }, layout: { title: "Living room", tiles: [] } }],
    entities: [{ id: "light.desk", name: "Desk", state: "on", area: "" }] } as unknown as Inventory;
  useScreenStore().selected = "living";
  useDocumentStore().documentGrid = { columns: 2, rows: 3 };
  loadLayout({ title: "Living room", tiles: [] });
});

describe("a card's colour by state", () => {
  it("lays a chosen colour over the card as the firmware does", () => {
    // theme::surface: two thirds of the colour over white in the light look, over black in the dark one.
    expect(soften("#f44336")).toBe("#f7857c");
    expect(soften("#f44336", true)).toBe("#85241d");
    // A name of the palette is the colour itself first (model/meter's names).
    expect(soften("deep-orange")).toBe(soften("#ff6f22"));
    expect(soften("nonsense")).toBe("");
  });

  it("gives the colour of the first rule that fits, and none when nothing does", () => {
    const rules = tile({ background: "mint", tint: [{ when: "heating", c: "deep-orange" }, { when: "cooling", c: "blue" },
      { below: 5, c: "indigo" }, { above: 28, c: "red" }] });
    // What the entity does counts as well as its state.
    expect(tintColour(rules, live("heat", { hvac_action: "heating" }), none)).toBe(soften("deep-orange"));
    expect(tintColour(rules, live("heat", { hvac_action: "cooling" }), none)).toBe(soften("blue"));
    // A temperature rule, in the card's own temperature.
    expect(tintColour(rules, live("heat", { hvac_action: "idle", current_temperature: 2 }), none)).toBe(soften("indigo"));
    expect(tintColour(rules, live("heat", { hvac_action: "idle", current_temperature: 31 }), none)).toBe(soften("red"));
    // Nothing fits: the tile's own colour stands (the mockup keeps what it had), so no colour comes from here.
    expect(tintColour(rules, live("off", { hvac_action: "idle", current_temperature: 21 }), none)).toBeNull();
    expect(tintColour(tile({}), live("on"), none)).toBeNull();
  });

  it("takes a temperature from the entity the second line reads", () => {
    const heater = tile({ tint: [{ below: 18, c: "blue" }] }, "switch.heater");
    const of = (id: string) => (id === "sensor.outside" ? live("12", { unit_of_measurement: "°C" }) : null);
    expect(tintColour(heater, live("on"), of, "sensor.outside")).toBe(soften("blue"));
    // A card that measures a temperature of its own does not look at the other one.
    const thermostat = tile({ tint: [{ above: 25, c: "red" }] });
    const warm = (id: string) => (id === "sensor.outside" ? live("30") : null);
    expect(tintColour(thermostat, live("cool", { current_temperature: 21 }), warm, "sensor.outside")).toBeNull();
    expect(tintColour(thermostat, live("cool", { current_temperature: 26 }), warm, "sensor.outside")).toBe(soften("red"));
  });

  it("keeps the rules the add-on takes and drops what it would refuse", () => {
    expect(tintRules(tile({ tint: [{ when: "on", c: "red" }] }))).toHaveLength(1);
    expect(tintRules(tile({}))).toEqual([]);
    // tint.validate's own shape: a word or a temperature, a colour the screen knows, at most eight.
    expect(canonicalOptions("light.a", { tint: [{ when: "on", c: "red" }, { when: "Bad Word", c: "red" }, { above: 5, c: "nonsense" }] }))
      .toEqual({ tint: [{ when: "on", c: "red" }] });
    expect(canonicalOptions("light.a", { tint: [{ when: "on", c: "red" }, { when: "off", c: "red" }, { when: "on", c: "red" },
      { when: "off", c: "red" }, { when: "on", c: "red" }, { when: "off", c: "red" }, { when: "on", c: "red" },
      { when: "off", c: "red" }, { when: "on", c: "red" }] })).toEqual({ tint: [
      { when: "on", c: "red" }, { when: "off", c: "red" }, { when: "on", c: "red" }, { when: "off", c: "red" },
      { when: "on", c: "red" }, { when: "off", c: "red" }, { when: "on", c: "red" }, { when: "off", c: "red" }] });
    expect(canonicalOptions("light.a", { tint: [{ when: "Bad Word", c: "red" }] })).toEqual({});
  });

  it("adds, changes and removes a rule from the panel", async () => {
    const target: Tile = { entity: "light.desk", name: "", slot: 0 };
    loadTiles([target]);
    const panel = mount(TintSection, { props: { tile: current(target)! } });
    await panel.find(".tint-add").trigger("click");
    // A new rule is for the state the entity is in, in one of the palette's colours.
    expect(current(target)!.options?.tint).toHaveLength(1);
    expect(current(target)!.options?.tint![0].when).toBeDefined();
    await panel.setProps({ tile: current(target)! });
    await panel.findAll(".tint-remove")[0].trigger("click");
    expect(current(target)!.options?.tint).toBeUndefined();
  });
});
