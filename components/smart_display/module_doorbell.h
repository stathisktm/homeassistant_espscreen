#pragma once
// The doorbell (module doorbell, tier full; docs/DOORBELL.md, docs/MODULES.md): what runtime_tiles.h and the page
// receiver reach of it. Someone rings, ESP Screens sees the ring in Home Assistant (a doorbell's event entity, event type
// `ring`) and sends the op "doorbell" to every screen whose hello says `doorbell` (a P4 that streams): the screen wakes,
// chimes and opens the camera full view as a doorbell, with its live picture and sound. The view is the camera's own
// (camera_open): a header of its own, the picture in the room beside or above its keys, never under them, because a live
// picture is written to the glass past LVGL (live_view.h). The rest is module_doorbell.cpp, a compilation unit of its own;
// a lite screen has neither, and a screen whose switch Doorbell (Extras) is off lets a ring pass.
#include "esphome/core/defines.h"
#ifdef SD_MOD_DOORBELL
#include <cstdint>
#include <functional>
#include <string>
#include "lvgl.h"
#include "live_view.h"

namespace esphome {
namespace speaker {
class Speaker;
}
}  // namespace esphome

namespace runtime_tiles {
namespace doorbell {
// Bound at boot (packages/core.yaml, features/audio-player.yaml): the switch Doorbell under Extras, and the report of how a
// ring's view ended to ESP Screens (esphome.screen_doorbell): "answered" at the first touch, "closed" by its close key or
// anything else that closed it, "missed" when nobody touched it, "seen" when a missed ring was opened from the top bar.
extern std::function<bool()> enabled;
extern std::function<void(const std::string &action, const std::string &key)> report;
// The chime plays on the speaker for announcements (ts_speaker).
void bind_speaker(esphome::speaker::Speaker *speaker);

// The op "doorbell" from ESP Screens: a ring of `camera`, its doorbell's `name`, the app's `key` for this ring and when it
// rang (unix time); or the close of that ring, answered on another screen.
void ring(const std::string &camera, const std::string &name, const std::string &key, uint32_t rang);
void close_ring(const std::string &key);
// The top bar's item of a missed ring (`b`): the ring this screen showed last, opened again without a chime.
void reopen();

// The camera view as a doorbell (runtime_tiles.h calls these from the camera's own functions).
bool shown();
bool holds();                                       // keeps the screen from going to standby
void build(lv_obj_t *root, const std::string &name);  // camera_open: its header, its keys
live_view::Rect area();                             // the room of its picture (live_area)
void picture_shown(lv_obj_t *picture);              // the first still: into that room, under the keys
void sound_changed();                               // camera_muted changed
void spinner_place(lv_obj_t *spinner, int size);    // where the spinner turns until the picture is live
void closing();                                     // camera_close: report the end, forget the view's parts
void tick(uint32_t now);                            // every 250 ms: the note, the chime, the close of an unanswered ring
}  // namespace doorbell
}  // namespace runtime_tiles
#endif
