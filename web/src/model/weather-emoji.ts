// A weather tile's colour pictures (app 0.4.116, module weather_emoji): the Iris weather emoji (MIT License) of Home
// Assistant's conditions, by day and by night, as the firmware picks them (weather_pictures.h). The editor shows them
// moving (web/src/assets/weather-emoji, the screens' 15 frames at 64 px), as a board of 16 MB draws its card's.
const pictures = import.meta.glob("../assets/weather-emoji/*.webp", { eager: true, import: "default" }) as Record<string, string>;
const byName: Record<string, string> = Object.fromEntries(
  Object.entries(pictures).map(([path, url]) => [path.slice(path.lastIndexOf("/") + 1, -5), url]));

/** Home Assistant's conditions and their pictures by day and by night (Iris's mappings/home-assistant.json). */
export const WEATHER_PICTURES: Record<string, [string, string]> = {
  "sunny": ["sunny", "clear-night"], "clear-night": ["clear-night", "clear-night"], "cloudy": ["cloudy", "cloudy"],
  "partlycloudy": ["partly-cloudy-day", "partly-cloudy-night"], "rainy": ["rain", "night-rain"],
  "pouring": ["heavy-rain", "heavy-rain"], "snowy": ["snow", "snow-night"], "snowy-rainy": ["sleet", "sleet"],
  "fog": ["fog", "fog-night"], "hail": ["hail", "hail"], "lightning": ["thunderstorm", "thunderstorm-night"],
  "lightning-rainy": ["thunderstorm-rain", "thunderstorm-night"], "windy": ["windy", "windy"],
  "windy-variant": ["wind", "wind"], "exceptional": ["hurricane", "hurricane"],
};

/** The picture of a condition, the night's while the sun is down; null for a word Home Assistant does not use. */
export function weatherPicture(condition: string | undefined, night = false): string | null {
  const names = WEATHER_PICTURES[condition || ""];
  return names ? byName[names[night ? 1 : 0]] ?? null : null;
}
