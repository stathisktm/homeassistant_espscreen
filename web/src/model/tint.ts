// A card's colour by state (app 0.4.91, screen_manager/app/tint.py): an ordered list of rules on a tile, and the colour
// the first rule that fits gives. The add-on resolves it for the screens (they are sent the colour); this mirrors the
// same rules and the same softening the firmware gives a colour of its own (theme::surface), so the mockup is what the
// glass will be. A rule is `{ when }` with a state or an action word ("heating", "sunny", "on"), or `{ above }`/`{ below }`
// with a temperature, and always a colour of the palette (model/meter's names, the same nineteen everywhere).
import { meterColorNames, meterHex } from "./meter";
import type { Live } from "./tile-text";
import type { Tile } from "../types";

export type TintRule = { when?: string; above?: number; below?: number; c: string };
/** The most rules one tile keeps, as tint.RULES has it. */
export const TINT_RULES = 8;
export const TINT_HEX = /^#[0-9a-f]{6}$/;
export const TINT_WHEN = /^[a-z0-9_]{1,24}$/;
/** The colour names a rule offers: Home Assistant's own theme colours, as a meter's segments do. */
export const tintColors = meterColorNames;

/** What the entity is doing, as a `when` rule names it: its state and its action (a thermostat's heating, a
 * humidifier's drying), which is what tint.words gives the add-on. */
export function doing(live: Live | null | undefined): string[] {
  const state = live?.state, a = live?.a || {}, found: string[] = [];
  if (typeof state === "string" && state) found.push(state);
  for (const key of ["hvac_action", "action"] as const) {
    const value = a[key];
    if (typeof value === "string" && value && !found.includes(value)) found.push(value);
  }
  return found;
}

/** The temperature a rule compares: the tile's own where it has one, else the entity its second line reads, as
 * tint.temperature does it. */
export function temperatureOf(entity: string, live: Live | null | undefined) {
  const a = live?.a || {};
  for (const key of ["current_temperature", "temperature"] as const) {
    const value = a[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  const domain = entity.split(".")[0];
  if (["sensor", "number", "input_number"].includes(domain) && live) {
    const value = Number(live.state);
    if (live.state.trim() !== "" && Number.isFinite(value)) return value;
  }
  return null;
}
export function tintTemperature(tile: Tile, live: Live | null | undefined, liveOf: (entity: string) => Live | null | undefined, second: string) {
  const own = temperatureOf(tile.entity, live);
  if (own !== null) return own;
  return second ? temperatureOf(second, liveOf(second)) : null;
}

/** The rules a tile keeps, or none. */
export function tintRules(tile: Tile): TintRule[] {
  const kept = tile.options?.tint;
  return Array.isArray(kept) ? (kept as TintRule[]).filter((rule) => rule && typeof rule === "object") : [];
}
export const hasTint = (tile: Tile) => tintRules(tile).length > 0;

/** A rule's colour as `#rrggbb`: a palette name or a colour typed as it is. */
export function tintHex(colour: unknown) {
  if (typeof colour !== "string") return "";
  if (TINT_HEX.test(colour)) return colour;
  return meterHex(colour) || "";
}
/** The firmware's theme::surface for a colour the add-on chose (a swatch keeps its own two values): laid over the
 * look's ground, so the words stay readable, but keeping two thirds of the colour picked (0.4.91 kept a fifth, which read
 * as a faded colour). The arithmetic is LVGL's own lv_color_mix, so the mockup is the glass to the last step. */
export function soften(colour: string, dark = false) {
  const hex = tintHex(colour);
  if (!hex) return "";
  const value = parseInt(hex.slice(1), 16), amount = dark ? 140 : 165, ground = dark ? 0 : 0xffffff;
  const channel = (shift: number) =>
    Math.floor((((value >> shift) & 255) * amount + ((ground >> shift) & 255) * (255 - amount)) * 0x8081 / 8388608);
  return `#${((channel(16) << 16) | (channel(8) << 8) | channel(0)).toString(16).padStart(6, "0")}`;
}

/** The colour the card is drawn in for this state, or null when no rule fits (the tile's own colour stands). */
export function tintColour(tile: Tile, live: Live | null | undefined, liveOf: (entity: string) => Live | null | undefined, second = "") {
  const rules = tintRules(tile);
  if (!rules.length) return null;
  const words = doing(live);
  let value: number | null | undefined;
  for (const rule of rules) {
    if (typeof rule.when === "string") {
      if (words.includes(rule.when)) return soften(rule.c) || null;
      continue;
    }
    if (value === undefined) value = tintTemperature(tile, live, liveOf, second);
    if (value === null) continue;
    if (typeof rule.above === "number" && !(value > rule.above)) continue;
    if (typeof rule.below === "number" && !(value < rule.below)) continue;
    if (typeof rule.above !== "number" && typeof rule.below !== "number") continue;
    return soften(rule.c) || null;
  }
  return null;
}

// The states a row offers: what the domain can be doing, the words Home Assistant itself reports.
const STATES: Record<string, string[]> = {
  climate: ["heat", "cool", "heat_cool", "auto", "fan_only", "dry", "off", "heating", "cooling", "drying", "idle", "fan"],
  humidifier: ["on", "off", "humidifying", "drying", "idle"],
  weather: ["sunny", "clear-night", "partlycloudy", "cloudy", "rainy", "pouring", "snowy", "snowy-rainy", "hail",
    "lightning", "lightning-rainy", "fog", "windy", "windy-variant", "exceptional"],
  media_player: ["playing", "paused", "idle", "off", "standby", "buffering"],
  vacuum: ["cleaning", "docked", "paused", "idle", "returning", "error"],
  cover: ["open", "opening", "closed", "closing"],
  lock: ["locked", "unlocked", "locking", "unlocking", "jammed"],
  person: ["home", "not_home"],
  device_tracker: ["home", "not_home"],
  alarm_control_panel: ["disarmed", "armed_home", "armed_away", "armed_night", "arming", "pending", "triggered"],
  sun: ["above_horizon", "below_horizon"],
  automation: ["on", "off"],
};
export const TINT_FALLBACK = ["on", "off"];
/** The states a tile's rows offer: its domain's own, the state it is in now, and on/off for everything else. */
export function tintStates(entity: string, live: Live | null | undefined) {
  const domain = entity.split(".")[0], found = [...(STATES[domain] ?? TINT_FALLBACK)];
  for (const word of doing(live)) if (!found.includes(word)) found.push(word);
  return found;
}
/** A state as the panel names it: Home Assistant's own words are small and underscored ("heat_cool"). */
export const stateLabel = (word: string) => word.replace(/_/g, " ").replace(/^./, (letter) => letter.toUpperCase());
