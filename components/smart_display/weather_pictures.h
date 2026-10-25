#pragma once
// The colour pictures of the weather a board was built with (firmware 0.69.0): packages/core.yaml hands them over at
// boot, each condition at the mini and at the card icon font's size. Only the module weather_emoji draws them,
// over a weather icon; a board without it is built with single pixels and this table alone.
#include <cstddef>
#include "lvgl.h"

namespace weather_pictures {

// Home Assistant's weather conditions, in the order packages/core.yaml hands their pictures over.
inline constexpr const char *CONDITIONS[] = {"sunny", "clear-night", "cloudy", "partlycloudy", "rainy", "pouring", "snowy",
                                             "snowy-rainy", "fog", "hail", "lightning", "lightning-rainy", "windy",
                                             "exceptional"};
inline constexpr size_t COUNT = sizeof(CONDITIONS) / sizeof(CONDITIONS[0]);
inline const lv_image_dsc_t *small[COUNT]{};
inline const lv_image_dsc_t *large[COUNT]{};

inline void set(size_t index, const lv_image_dsc_t *mini, const lv_image_dsc_t *card) {
  if (index < COUNT) { small[index] = mini; large[index] = card; }
}

}  // namespace weather_pictures
