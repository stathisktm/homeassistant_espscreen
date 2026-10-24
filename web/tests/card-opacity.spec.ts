// How much of a card covers a page's background (app 0.4.111): the editor keeps it as the add-on does, through the
// page document, and the mockup's card lets the page show through it.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setTileOption } from "../src/editor/tiles";
import { canonicalOptions } from "../src/model/tile-options";
import type { Inventory, Tile } from "../src/types";
import { useDocumentStore } from "../src/stores/document";
import { useInventoryStore } from "../src/stores/inventory";
import { useScreenStore } from "../src/stores/screen";
import { current, loadLayout, loadTiles } from "./helpers/fixtures";

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

describe("a card's opacity", () => {
  it("keeps 80 to 20 percent, and none on the whole card or a card without one", () => {
    for (const value of [80, 60, 40, 20]) expect(canonicalOptions("light.a", { opacity: value })).toEqual({ opacity: value });
    expect(canonicalOptions("light.a", { opacity: 100 })).toEqual({});
    expect(canonicalOptions("light.a", { opacity: 50 })).toEqual({});
    expect(canonicalOptions("light.a", { opacity: 40, background: "none" })).toEqual({ background: "none" });
  });

  it("is kept through the page document", () => {
    const target: Tile = { entity: "light.desk", name: "", slot: 0 };
    loadTiles([target]);
    setTileOption(current(target)!, "opacity", 40);
    expect(current(target)!.options?.opacity).toBe(40);
    setTileOption(current(target)!, "opacity", undefined);
    expect(current(target)!.options?.opacity).toBeUndefined();
  });
});
