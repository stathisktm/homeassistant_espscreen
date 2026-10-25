#pragma once
// Colour pictures of the weather in the place of its icons (firmware 0.69.0, module weather_emoji, docs/MODULES.md):
// a weather tile whose option weather_icons is "emoji" shows the Iris pictures (fonts/iris, MIT License, firmware
// 0.70.0) on its card, its forecast's days and its week, where every other tile shows Material Design Icons. The card's
// own picture moves (15 frames round in four seconds) on a board with room for its frames, and shows the night's
// picture while the sun is down.
// packages/core.yaml has ESPHome scale each picture to the look's two icon sizes when it builds and hands them over at
// boot (weather_pictures.h); a lite board builds them as single pixels and never draws them, as this code is not in
// its firmware.
//
// The picture stands over the icon's label, which keeps its glyph for its size and place and draws it transparent, so
// every card lays out as it does with the icon and the switch back to icons is the label's ink alone. The code lives in
// module_weather_emoji.cpp, a compilation unit of its own: main.cpp is close to the Xtensa literal range on the S3
// boards (docs/RELEASING.md).
#include "esphome/core/defines.h"
#ifdef SD_MOD_WEATHER_EMOJI
#include <string>
#include "lvgl.h"

namespace weather_emoji {

// Dress a weather icon's label: with `on` and a condition that has a picture, the picture over it and its glyph
// transparent; else the glyph as it was. `large_picture` takes the card's picture whatever the label's font is now, as
// a tile's own icon may take another font later in its render, and moves through its frames; `night` takes the
// condition's picture for the night.
void dress(lv_obj_t *label, const std::string &condition, bool on, bool large_picture = false, bool night = false);

}  // namespace weather_emoji
#endif
