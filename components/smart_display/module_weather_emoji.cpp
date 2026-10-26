// A weather tile's colour pictures (module weather_emoji, tier full; its header says what they are).
// Compiled on its own, as module_doorbell.cpp is: on Xtensa the literal pool of one object file must stay within reach
// of all of its code, and the full tier holds S3 boards too.
#include "esphome/core/defines.h"
#ifdef SD_MOD_WEATHER_EMOJI
#include <algorithm>
#include "module_weather_emoji.h"
#include "page_header.h"
#include "weather_chart.h"
#include "weather_pictures.h"

namespace weather_emoji {

namespace wp = weather_pictures;

// The picture of a condition by day or by night; -1 for a word Home Assistant does not use.
static int index_of(const std::string &condition, bool night) {
  for (const auto &c : wp::CONDITIONS) if (condition == c.word) return night ? c.night : c.day;
  return -1;
}

// The smallest picture at least `side` large, else the larger one; a single pixel (a board built without them) is none.
static const lv_image_dsc_t *picture_for(int index, int side) {
  if (index < 0) return nullptr;
  const lv_image_dsc_t *mini = wp::small[index], *card = wp::large[index];
  if (mini && mini->header.w > 1 && mini->header.w >= side) return mini;
  if (card && card->header.w > 1) return card;
  return mini && mini->header.w > 1 ? mini : nullptr;
}

// The days and hours of the weather's chart (the week, the card a tap opens) take the pictures too (firmware 0.71.0),
// still ones: weather_chart.h asks for them through its hook, which this sets before anything is drawn.
static const lv_image_dsc_t *chart_picture(const std::string &condition, bool night, int side) {
  return picture_for(index_of(condition, night), side);
}
static const bool chart_hooked = (weather_chart::picture = &chart_picture, true);

#if LV_USE_IMAGE
// The pictures that turn through their frames (a weather tile's own icon on a board built with frames), and the one
// timer that turns them all, in step, while the glass is lit and the picture can be seen.
struct Moving { lv_obj_t *picture; uint8_t index; };
static std::vector<Moving> moving;
static lv_timer_t *timer = nullptr;
static uint32_t frame = 0;

static void turn(lv_timer_t *) {
  if (moving.empty() || (wp::awake && !wp::awake())) return;
  ++frame;
  for (const auto &m : moving) {
    const auto &frames = wp::frames[m.index];
    if (frames.empty() || !lv_obj_is_visible(m.picture)) continue;
    lv_image_set_src(m.picture, &frames[frame % frames.size()]);
  }
}
static void forget(lv_obj_t *picture) {
  moving.erase(std::remove_if(moving.begin(), moving.end(), [&](const Moving &m) { return m.picture == picture; }), moving.end());
}
static void keep_moving(lv_obj_t *picture, int index) {
  forget(picture);
  if (index < 0 || wp::frames[index].empty()) return;
  moving.push_back({picture, static_cast<uint8_t>(index)});
  if (!timer) timer = lv_timer_create(turn, wp::LOOP_MS / std::max<size_t>(1, wp::frames[index].size()), nullptr);
}

// The label's own picture: its one child, made the first time it is asked for, and let go of when it is deleted.
static lv_obj_t *picture_of(lv_obj_t *label, bool make) {
  for (uint32_t i = 0; i < lv_obj_get_child_count(label); ++i) {
    auto *child = lv_obj_get_child(label, i);
    if (lv_obj_check_type(child, &lv_image_class)) return child;
  }
  if (!make) return nullptr;
  auto *p = lv_image_create(label);
  lv_obj_remove_flag(p, LV_OBJ_FLAG_CLICKABLE);
  lv_image_set_inner_align(p, LV_IMAGE_ALIGN_CONTAIN);
  lv_obj_add_event_cb(p, [](lv_event_t *e) { forget(static_cast<lv_obj_t *>(lv_event_get_target(e))); }, LV_EVENT_DELETE, nullptr);
  return p;
}

// The picture follows the label's box (nine tenths of its height, as a Material Design glyph fills its em, its shape
// kept), so it fits any font; it comes from the picture nearest that size. The card's own picture (`large_picture`)
// turns through its frames where the board has them.
void dress(lv_obj_t *label, const std::string &condition, bool on, bool large_picture, bool night) {
  if (!label) return;
  const lv_font_t *font = lv_obj_get_style_text_font(label, LV_PART_MAIN);
  const int side = large_picture ? 1 << 14 : font ? lv_font_get_line_height(font) * 9 / 10 : 0;
  const int index = index_of(condition, night);
  const lv_image_dsc_t *src = on && side > 0 ? picture_for(index, side) : nullptr;
  lv_obj_t *picture = picture_of(label, src != nullptr);
  if (!src) {
    if (picture) { forget(picture); lv_obj_add_flag(picture, LV_OBJ_FLAG_HIDDEN); }
    lv_obj_set_style_text_opa(label, LV_OPA_COVER, 0);
    return;
  }
  lv_obj_set_style_text_opa(label, LV_OPA_TRANSP, 0);
  if (large_picture && !wp::frames[index].empty()) {
    const auto &frames = wp::frames[index];
    src = &frames[frame % frames.size()];
    keep_moving(picture, index);
  } else {
    forget(picture);
  }
  if (lv_image_get_src(picture) != src) lv_image_set_src(picture, src);
  lv_obj_set_size(picture, lv_pct(100), lv_pct(90));
  lv_obj_align(picture, LV_ALIGN_CENTER, 0, 0);
  lv_obj_remove_flag(picture, LV_OBJ_FLAG_HIDDEN);
}
// A top bar item's weather picture (firmware 0.72.0): still, the size of the bar's icons.
static const bool bar_hooked = (page_header::weather_picture = [](lv_obj_t *label, const std::string &condition, bool night) {
  dress(label, condition, !condition.empty(), false, night);
}, true);
#else
// A profile without LVGL's image widget keeps the icons.
void dress(lv_obj_t *, const std::string &, bool, bool, bool) {}
#endif

}  // namespace weather_emoji
#endif
