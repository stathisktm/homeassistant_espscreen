// A weather tile's colour pictures (app 0.4.116, module weather_emoji): the editor keeps the option as the add-on does,
// on a weather tile alone, and finds the picture of each of Home Assistant's conditions, as the screen draws it.
import { describe, expect, it } from "vitest";
import { canonicalOptions } from "../src/model/tile-options";
import { weatherPicture } from "../src/model/weather-emoji";

const CONDITIONS = ["sunny", "clear-night", "cloudy", "partlycloudy", "rainy", "pouring", "snowy", "snowy-rainy", "fog", "hail",
  "lightning", "lightning-rainy", "windy", "windy-variant", "exceptional"];

describe("a weather tile's colour pictures", () => {
  it("keeps the option on a weather tile only, and only as emoji", () => {
    expect(canonicalOptions("weather.home", { weather_icons: "emoji" })).toEqual({ weather_icons: "emoji" });
    expect(canonicalOptions("light.a", { weather_icons: "emoji" })).toEqual({});
    expect(canonicalOptions("weather.home", { weather_icons: "icons" as never })).toEqual({});
  });

  it("has a picture for every condition, windy-variant as windy", () => {
    for (const condition of CONDITIONS) expect(weatherPicture(condition), condition).toBeTruthy();
    expect(weatherPicture("rainy", true)).not.toBe(weatherPicture("rainy"));
    expect(weatherPicture("sunny", true)).toBe(weatherPicture("clear-night"));
    expect(weatherPicture("unavailable")).toBeNull();
    expect(weatherPicture(undefined)).toBeNull();
  });
});
