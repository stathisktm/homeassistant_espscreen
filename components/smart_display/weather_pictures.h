#pragma once
// The colour pictures of the weather a board was built with (firmware 0.69.0; Iris since 0.70.0, fonts/iris, MIT):
// packages/core.yaml hands them over at boot, each picture at the mini and at the card icon font's size, and its frames
// where the board has room for them. Only the module weather_emoji draws them, over a weather icon; a board without it
// is built with single pixels and this table alone.
#include <cstddef>
#include <cstdint>
#include <vector>
#include "lvgl.h"

namespace weather_pictures {

// The pictures, in the order packages/core.yaml hands them over (Iris's names).
inline constexpr const char *NAMES[] = {"sunny", "clear-night", "cloudy", "partly-cloudy-day", "partly-cloudy-night", "rain",
                                        "night-rain", "heavy-rain", "snow", "snow-night", "sleet", "fog", "fog-night", "hail",
                                        "thunderstorm", "thunderstorm-night", "thunderstorm-rain", "windy", "wind", "hurricane"};
inline constexpr size_t COUNT = sizeof(NAMES) / sizeof(NAMES[0]);
// Home Assistant's weather conditions and the picture of each by day and by night (Iris's mappings/home-assistant.json).
struct Condition { const char *word; uint8_t day, night; };
inline constexpr Condition CONDITIONS[] = {
    {"sunny", 0, 1}, {"clear-night", 1, 1}, {"cloudy", 2, 2}, {"partlycloudy", 3, 4}, {"rainy", 5, 6},
    {"pouring", 7, 7}, {"snowy", 8, 9}, {"snowy-rainy", 10, 10}, {"fog", 11, 12}, {"hail", 13, 13},
    {"lightning", 14, 15}, {"lightning-rainy", 16, 15}, {"windy", 17, 17}, {"windy-variant", 18, 18},
    {"exceptional", 19, 19}};
// How long the frames of a picture take round (Iris's loop), whatever their number.
inline constexpr uint32_t LOOP_MS = 4000;

inline const lv_image_dsc_t *small[COUNT]{};
inline const lv_image_dsc_t *large[COUNT]{};
// A picture's frames at the card's size, empty on a board built without them (single pixels).
inline std::vector<lv_image_dsc_t> frames[COUNT];
// Whether the glass is lit: frames turn only then (set at boot).
inline bool (*awake)() = nullptr;

inline void set(size_t index, const lv_image_dsc_t *mini, const lv_image_dsc_t *card) {
  if (index < COUNT) { small[index] = mini; large[index] = card; }
}
// The frames of an ESPHome animation, each its own image descriptor, so LVGL draws any frame without the animation's
// current one changing under it.
template<typename Animation> void set_frames(size_t index, Animation *animation) {
  if (index >= COUNT || !animation) return;
  frames[index].clear();
  const uint32_t count = animation->get_animation_frame_count();
  for (uint32_t frame = 0; frame < count; ++frame) {
    animation->set_frame(static_cast<int>(frame));
    const lv_image_dsc_t *dsc = animation->get_lv_image_dsc();
    if (!dsc || dsc->header.w <= 1) { frames[index].clear(); return; }
    frames[index].push_back(*dsc);
  }
  animation->set_frame(0);
}

}  // namespace weather_pictures
