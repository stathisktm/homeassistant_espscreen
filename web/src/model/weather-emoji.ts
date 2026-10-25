// A weather tile's colour pictures (app 0.4.116, module weather_emoji): Noto Emoji's pictures of Home Assistant's
// conditions (web/src/assets/weather-emoji, the same as fonts/weather-emoji-*.png the screens are built with), as the
// firmware picks them (module_weather_emoji.h, weather_pictures.h).
const pictures = import.meta.glob("../assets/weather-emoji/*.png", { eager: true, import: "default" }) as Record<string, string>;
const byCondition: Record<string, string> = Object.fromEntries(
  Object.entries(pictures).map(([path, url]) => [path.slice(path.lastIndexOf("/") + 1, -4), url]));

/** The picture of a condition, windy-variant as windy; null for a word Home Assistant does not use. */
export function weatherPicture(condition: string | undefined): string | null {
  const word = condition === "windy-variant" ? "windy" : condition || "";
  return byCondition[word] ?? null;
}
