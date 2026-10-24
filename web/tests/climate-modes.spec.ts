// The modes a thermostat's tile shows (app 0.4.113, model/climate-modes.ts): kept as the add-on keeps them, through the
// page document, chosen with the panel's chips, and the mockup's state cut the same way the screen's is.
import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ClimateModesSection from "../src/components/inspector/ClimateModesSection.vue";
import { setTileOption } from "../src/editor/tiles";
import { withModes } from "../src/model/climate-modes";
import { canonicalOptions } from "../src/model/tile-options";
import type { Inventory, Tile } from "../src/types";
import { useDocumentStore } from "../src/stores/document";
import { useEntitiesStore } from "../src/stores/entities";
import { useInventoryStore } from "../src/stores/inventory";
import { useScreenStore } from "../src/stores/screen";
import { current, loadLayout, loadTiles } from "./helpers/fixtures";

const AIRCO = { state: "cool", a: { hvac_modes: ["off", "heat", "cool", "dry", "fan_only"], fan_modes: ["low", "high"] } };

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline"))));
  useInventoryStore().inventory = { csrf: "t", connected: true,
    screens: [{ id: "living", name: "Living room", online: true, firmware: "0.67.0", board: "guition", tile_sizes: ["tall", "square"],
      shape: { width: 480, height: 480, columns: 2, rows: 3 }, layout: { title: "Living room", tiles: [] } }],
    entities: [{ id: "climate.hall", name: "Airco", state: "cool", area: "" }] } as unknown as Inventory;
  useScreenStore().selected = "living";
  useDocumentStore().documentGrid = { columns: 2, rows: 3 };
  loadLayout({ title: "Living room", tiles: [] });
});

describe("a thermostat's modes", () => {
  it("cuts the mockup's lists to the modes kept", () => {
    const tile: Tile = { entity: "climate.hall", name: "", slot: 0, options: { hvac_modes: ["heat", "cool"] } };
    expect(withModes(tile, AIRCO)!.a!.hvac_modes).toEqual(["heat", "cool"]);
    expect(withModes(tile, AIRCO)!.a!.fan_modes).toEqual(["low", "high"]);
    expect(withModes({ ...tile, options: {} }, AIRCO)).toBe(AIRCO);
  });

  it("keeps a list on a climate tile alone, and drops a broken one", () => {
    expect(canonicalOptions("climate.hall", { hvac_modes: ["heat", "cool"] })).toEqual({ hvac_modes: ["heat", "cool"] });
    expect(canonicalOptions("switch.fan", { hvac_modes: ["heat"] })).toEqual({});
    expect(canonicalOptions("climate.hall", { hvac_modes: [] })).toEqual({});
    expect(canonicalOptions("climate.hall", { hvac_modes: ["heat", "heat"] })).toEqual({});
  });

  it("is chosen with chips and kept through the page document", async () => {
    const target: Tile = { entity: "climate.hall", name: "", slot: 0 };
    loadTiles([target]);
    useEntitiesStore().liveStates["climate.hall"] = { ...AIRCO, word: "Cooling" } as never;
    const panel = mount(ClimateModesSection, { props: { tile: current(target)! } });
    const chips = panel.findAllComponents({ name: "UiChips" });
    expect(chips).toHaveLength(2);
    chips[0].vm.$emit("update:modelValue", ["heat", "cool"]);
    expect(current(target)!.options?.hvac_modes).toEqual(["heat", "cool"]);
    // The last mode stays; all of them again is no key.
    chips[0].vm.$emit("update:modelValue", []);
    expect(current(target)!.options?.hvac_modes).toEqual(["heat", "cool"]);
    chips[0].vm.$emit("update:modelValue", AIRCO.a.hvac_modes);
    expect(current(target)!.options?.hvac_modes).toBeUndefined();
    setTileOption(current(target)!, "fan_modes", ["high"]);
    expect(current(target)!.options?.fan_modes).toEqual(["high"]);
  });
});
