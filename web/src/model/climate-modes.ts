// The modes a thermostat's tile shows (app 0.4.113, core.CLIMATE_MODE_LISTS): as Home Assistant's own climate features
// choose them, a list of the HVAC, fan and swing modes kept per tile; left out, all of them. The add-on sends the screen
// the lists cut to those, and the mockup cuts them the same way (withModes), so its mode bar is the glass's.
import type { Live } from "./tile-text";
import type { Tile, TileOptions } from "../types";

export const CLIMATE_MODE_LISTS = ["hvac_modes", "fan_modes", "swing_modes"] as const;
export type ClimateModeList = (typeof CLIMATE_MODE_LISTS)[number];

/** Whether a kept list is one the add-on takes: one to sixteen distinct names of at most 48 bytes. */
export function validModes(value: unknown): value is string[] {
  return Array.isArray(value) && value.length >= 1 && value.length <= 16 && new Set(value).size === value.length &&
    value.every((mode) => typeof mode === "string" && mode.length > 0 && new TextEncoder().encode(mode).length <= 48);
}
/** The entity's state with each kept list cut to the modes the tile shows; the same state where it keeps none. */
export function withModes(tile: Tile, live: Live | null): Live | null {
  if (!live || !tile.entity.startsWith("climate.") || !live.a) return live;
  const options = (tile.options || {}) as TileOptions;
  const cut = CLIMATE_MODE_LISTS.filter((key) => validModes(options[key]) && Array.isArray(live.a![key]));
  if (!cut.length) return live;
  const a = { ...live.a };
  for (const key of cut) a[key] = (live.a[key] as unknown[]).filter((mode) => (options[key] as string[]).includes(String(mode)));
  return { ...live, a };
}
