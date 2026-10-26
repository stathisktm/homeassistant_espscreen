// A weather tile's temperature from a sensor of one's own (app 0.4.121, core.weather_temperature): its number in the
// place of the weather's, in the weather's unit, as the add-on sends it to the screen. The mockup shows the same.
import type { Live } from "./tile-text";
import type { Tile } from "../types";

/** The weather's state with its own sensor's temperature; the same state while the sensor has no number. */
export function withOwnTemperature(tile: Tile, live: Live | null, liveOf: (id: string) => Live | null | undefined): Live | null {
  const own = tile.options?.temp_entity;
  if (!live || !own || !tile.entity.startsWith("weather.")) return live;
  const sensor = liveOf(own);
  const raw = sensor?.state;
  let value = raw === undefined || raw === "" ? NaN : Number(raw);
  if (!Number.isFinite(value)) return live;
  const unit = String(sensor?.a?.unit_of_measurement ?? "");
  const wanted = String(live.a?.temperature_unit ?? (unit || "°C"));
  if (unit === "°F" && wanted === "°C") value = (value - 32) * 5 / 9;
  else if (unit === "°C" && wanted === "°F") value = value * 9 / 5 + 32;
  return { ...live, a: { ...(live.a || {}), temperature: Math.round(value * 10) / 10, temperature_unit: wanted } };
}
