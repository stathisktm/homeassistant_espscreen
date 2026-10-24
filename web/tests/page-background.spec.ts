// A page's own background picture (app 0.4.109, model/page-background.ts): the editor keeps exactly what the add-on's
// page_backdrop.validate keeps, and a document with a background passes the page validation.
import { describe, expect, it } from "vitest";
import { backgroundKind, backgroundRefresh, validBackground } from "../src/model/page-background";

describe("a page's background", () => {
  it("knows every kind of source the add-on takes", () => {
    expect(backgroundKind("https://example.com/sky.jpg")).toBe("url");
    expect(backgroundKind("http://example.com/a.png")).toBe("url");
    expect(backgroundKind("/local/backgrounds/kitchen.jpg")).toBe("www");
    expect(backgroundKind("media-source://media_source/local/a.jpg")).toBe("media");
    expect(backgroundKind("camera.garden")).toBe("entity");
    for (const bad of ["", "ftp://example.com/a.jpg", "/local/../secrets.yaml", "/api/states", "not an entity", "https://a.com/a b.jpg", "x".repeat(600)])
      expect(backgroundKind(bad)).toBeNull();
  });

  it("keeps a background as the add-on does, and nothing else", () => {
    expect(validBackground({ source: "camera.garden", dim: 45, refresh: 300 })).toBe(true);
    expect(validBackground({ source: "/local/sky.jpg" })).toBe(true);
    for (const bad of [{ source: "camera.garden", dim: 90 }, { source: "camera.garden", dim: 1.5 }, { source: "camera.garden", refresh: 7 },
      { source: "camera.garden", x: 1 }, { dim: 10 }, { source: "/api/states" }, null, "camera.garden"])
      expect(validBackground(bad)).toBe(false);
  });

  it("refreshes a camera once a minute unless it says otherwise", () => {
    expect(backgroundRefresh({ source: "camera.garden" })).toBe(60);
    expect(backgroundRefresh({ source: "camera.garden", refresh: 0 })).toBe(0);
    expect(backgroundRefresh({ source: "https://example.com/a.jpg" })).toBe(0);
    expect(backgroundRefresh(undefined)).toBe(0);
  });
});
