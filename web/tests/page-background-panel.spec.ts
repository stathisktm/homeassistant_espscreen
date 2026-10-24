// The page panel's Background (app 0.4.109): what is typed there reaches the page of the document.
import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PageBackgroundSection from "../src/components/inspector/PageBackgroundSection.vue";
import type { Inventory } from "../src/types";
import { useDocumentStore } from "../src/stores/document";
import { useInventoryStore } from "../src/stores/inventory";
import { useScreenStore } from "../src/stores/screen";
import { loadLayout } from "./helpers/fixtures";

const URL = "https://img.magnific.com/free-photo/leaves-salmon-cloured-frame_23-2148317550.jpg?semt=ais_hybrid&w=740&q=80";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline"))));
  useInventoryStore().inventory = { csrf: "t", connected: true,
    screens: [{ id: "living", name: "Living room", online: true, firmware: "0.65.0", board: "guition", tile_sizes: ["tall", "square"],
      shape: { width: 480, height: 480, columns: 2, rows: 3 }, layout: { title: "Living room", tiles: [] } }],
    entities: [{ id: "camera.garden", name: "Garden", state: "idle", area: "" }] } as unknown as Inventory;
  useScreenStore().selected = "living";
  useDocumentStore().documentGrid = { columns: 2, rows: 3 };
  loadLayout({ title: "Living room", tiles: [] });
});

describe("the page panel's background", () => {
  it("keeps an address typed for the page", async () => {
    const doc = useDocumentStore();
    const page = () => doc.document!.pages[0];
    const panel = mount(PageBackgroundSection, { props: { page: page() }, attachTo: document.body });
    const select = panel.findComponent({ name: "UiSelect" });
    select.vm.$emit("update:modelValue", "url");
    await panel.vm.$nextTick();
    const field = panel.find("input[type=text]");
    expect(field.exists()).toBe(true);
    await field.setValue(URL);
    await field.trigger("blur");
    expect(page().background).toEqual({ source: URL });
    panel.unmount();
  });
});
