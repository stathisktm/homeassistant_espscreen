// What the mockup shows of this fork's features (app 0.4.114): a page's background behind its cards, painted by the
// add-on (api/page-background), and a line set by hand that is too wide for its card going round (vMarquee).
import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, withDirectives } from "vue";
import DevicePage from "../src/components/DevicePage.vue";
import { vMarquee } from "../src/composables/marquee";
import { setPageBackground } from "../src/editor/pages";
import type { Inventory } from "../src/types";
import { useDocumentStore } from "../src/stores/document";
import { useInventoryStore } from "../src/stores/inventory";
import { useScreenStore } from "../src/stores/screen";
import { loadLayout } from "./helpers/fixtures";

const URL = "https://example.com/sky.jpg";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline"))));
  useInventoryStore().inventory = { csrf: "t", connected: true,
    screens: [{ id: "living", name: "Living room", online: true, firmware: "0.67.0", board: "guition", tile_sizes: ["tall", "square"],
      shape: { width: 480, height: 480, columns: 2, rows: 3 }, layout: { title: "Living room", tiles: [] } }],
    entities: [] } as unknown as Inventory;
  useScreenStore().selected = "living";
  useDocumentStore().documentGrid = { columns: 2, rows: 3 };
  loadLayout({ title: "Living room", tiles: [] });
});

describe("the mockup", () => {
  it("draws a page's background behind its cards", async () => {
    const doc = useDocumentStore();
    setPageBackground(doc.document!.pages[0].id, { source: URL, dim: 40 });
    const page = mount(DevicePage, { props: { page: 0, entries: [], pages: 1, moving: null } });
    const style = page.find(".device").attributes("style") || "";
    expect(style).toContain("api/page-background?");
    expect(style).toContain(encodeURIComponent(URL));
    expect(style).toContain("dim=40");
    expect(style).toContain("w=480");
    setPageBackground(doc.document!.pages[0].id, undefined);
    await page.vm.$nextTick();
    expect(page.find(".device").attributes("style") || "").not.toContain("page-background");
  });

  it("lets a line set by hand go round when it is too wide", async () => {
    vi.stubGlobal("requestAnimationFrame", (run: FrameRequestCallback) => { run(0); return 0; });
    const Line = defineComponent({ props: { on: Boolean }, setup: (props) => () => withDirectives(h("span", { class: "st" }, "MEGA HD · Mega Non Stop"), [[vMarquee, props.on]]) });
    const wide = mount(Line, { props: { on: true }, attachTo: document.body });
    const el = wide.find(".st").element as HTMLElement;
    Object.defineProperty(el, "scrollWidth", { value: 300, configurable: true });
    Object.defineProperty(el, "clientWidth", { value: 120, configurable: true });
    await wide.setProps({ on: false });
    await wide.setProps({ on: true });
    expect(el.classList.contains("marquee")).toBe(true);
    expect(el.style.getPropertyValue("--marquee-shift")).toBe("-184px");
    await wide.setProps({ on: false });
    expect(el.classList.contains("marquee")).toBe(false);
    wide.unmount();
  });
});
