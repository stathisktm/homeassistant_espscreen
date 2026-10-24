// A page's own background picture (app 0.4.109, firmware 0.65.0, screen_manager/app/page_backdrop.py): where it comes
// from, how much it is darkened under the cards and how often it is fetched again. The add-on fetches and paints it;
// these rules are page_backdrop.validate's, so the editor never stores a background the add-on would refuse.
export type PageBackground = { source: string; dim?: number; refresh?: number };
export type BackgroundKind = "url" | "www" | "media" | "entity";

export const BACKGROUND_DIM_MAX = 80;
export const BACKGROUND_DIM_DEFAULT = 30;
export const BACKGROUND_REFRESHES = [0, 60, 300, 900, 3600] as const;
export const BACKGROUND_DIMS = [0, 10, 20, 30, 40, 50, 60, 70, 80] as const;
const ENTITY = /^[a-z0-9_]+\.[a-z0-9_]+$/;
const MEDIA = /^media-source:\/\/\S{1,480}$/;

/** What kind of address a source is, as page_backdrop.kind_of says, or null for one the add-on would refuse. */
export function backgroundKind(source: unknown): BackgroundKind | null {
  if (typeof source !== "string" || !source || source.length > 512 || /\s/.test(source)) return null;
  if (source.startsWith("https://") || source.startsWith("http://")) return "url";
  if (source.startsWith("/local/")) {
    const path = source.split("?", 1)[0];
    return path.includes("..") || source.slice(1).includes("//") ? null : "www";
  }
  if (MEDIA.test(source)) return "media";
  if (ENTITY.test(source) && source.length <= 120) return "entity";
  return null;
}

/** Whether a page's `background` is one the add-on keeps (page_backdrop.validate). */
export function validBackground(value: unknown): value is PageBackground {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const background = value as Record<string, unknown>;
  if (Object.keys(background).some((key) => !["source", "dim", "refresh"].includes(key))) return false;
  if (backgroundKind(background.source) === null) return false;
  if (background.dim !== undefined && !(Number.isInteger(background.dim) && (background.dim as number) >= 0 && (background.dim as number) <= BACKGROUND_DIM_MAX)) return false;
  if (background.refresh !== undefined && !(BACKGROUND_REFRESHES as readonly unknown[]).includes(background.refresh)) return false;
  return true;
}

/** Seconds between two fetches while the page is on the glass (page_backdrop.refresh_of): a camera's minute by default. */
export function backgroundRefresh(background: PageBackground | undefined) {
  if (!background) return 0;
  if (background.refresh !== undefined) return background.refresh;
  const kind = backgroundKind(background.source), domain = background.source.split(".")[0];
  return kind === "entity" && (domain === "camera" || domain === "image") ? 60 : 0;
}
