// An icon by state (app 0.4.112, tint.validate_icons and tint.icon_of in the add-on): rules of the same shape as a colour
// by state, each with an icon of the set in the colour's place. The first that fits gives the tile's icon; with none,
// its own icon stands. The add-on resolves them and sends the icon itself, so the mockup does the same here.
import { firstRule, TINT_RULES, TINT_WHEN } from "./tint";
import type { Live } from "./tile-text";
import type { Tile } from "../types";

export type IconRule = { when?: string; above?: number; below?: number; icon: string };
/** The most rules one tile keeps (tint.RULES). */
export const ICON_RULES = TINT_RULES;
const ICON_NAME = /^[a-z0-9-]{1,64}$/;

/** The rules a tile keeps, or none. */
export function iconRules(tile: Tile): IconRule[] {
  const kept = tile.options?.icons;
  return Array.isArray(kept) ? (kept as IconRule[]).filter((rule) => rule && typeof rule === "object") : [];
}
/** Whether a rule is one the add-on keeps: a state word or a temperature, and an icon's name. */
export function validIconRule(rule: unknown): rule is IconRule {
  if (!rule || typeof rule !== "object") return false;
  const r = rule as Record<string, unknown>;
  if (Object.keys(r).some((key) => !["when", "above", "below", "icon"].includes(key))) return false;
  if (typeof r.icon !== "string" || !ICON_NAME.test(r.icon)) return false;
  if (typeof r.when === "string") return TINT_WHEN.test(r.when) && r.above === undefined && r.below === undefined;
  return r.when === undefined && (typeof r.above === "number" || typeof r.below === "number");
}
/** The name of the icon the first fitting rule gives, or null. */
export function iconRuleMatch(tile: Tile, live: Live | null | undefined) {
  return firstRule(iconRules(tile), tile, live, () => null)?.icon ?? null;
}
