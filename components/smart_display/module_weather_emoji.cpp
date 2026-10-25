// A weather tile's colour pictures (module weather_emoji, tier full; its header says what they are).
// Compiled on its own, as module_doorbell.cpp is: on Xtensa the literal pool of one object file must stay within reach
// of all of its code, and the full tier holds S3 boards too.
#include "esphome/core/defines.h"
#ifdef SD_MOD_WEATHER_EMOJI
#include "module_weather_emoji.h"
#include "weather_pictures.h"

namespace weather_emoji {

// The picture's index for a condition; windy-variant is windy, as its icon is. -1 for a word Home Assistant does not use.
static int index_of(const std::string &condition) {
  const std::string word = condition == "windy-variant" ? "windy" : condition;
  for (size_t i = 0; i < weather_pictures::COUNT; ++i) if (word == weather_pictures::CONDITIONS[i]) return static_cast<int>(i);
  return -1;
}

// The smallest picture at least `side` large, else the larger one; a single pixel (a board built without them) is none.
static const lv_image_dsc_t *picture_for(int index, int side) {
  if (index < 0) return nullptr;
  const lv_image_dsc_t *mini = weather_pictures::small[index], *card = weather_pictures::large[index];
  if (mini && mini->header.w > 1 && mini->header.w >= side) return mini;
  if (card && card->header.w > 1) return card;
  return mini && mini->header.w > 1 ? mini : nullptr;
}

#if LV_USE_IMAGE
// The label's own picture: its one child, made the first time it is asked for.
static lv_obj_t *picture_of(lv_obj_t *label, bool make) {
  for (uint32_t i = 0; i < lv_obj_get_child_count(label); ++i) {
    auto *child = lv_obj_get_child(label, i);
    if (lv_obj_check_type(child, &lv_image_class)) return child;
  }
  if (!make) return nullptr;
  auto *p = lv_image_create(label);
  lv_obj_remove_flag(p, LV_OBJ_FLAG_CLICKABLE);
  lv_image_set_inner_align(p, LV_IMAGE_ALIGN_CONTAIN);
  return p;
}

// The picture follows the label's box (nine tenths of its height, as a Material Design glyph fills its em, its shape
// kept), so it fits any font; it comes from the picture nearest that size.
void dress(lv_obj_t *label, const std::string &condition, bool on, bool large_picture) {
  if (!label) return;
  const lv_font_t *font = lv_obj_get_style_text_font(label, LV_PART_MAIN);
  const int side = large_picture ? 1 << 14 : font ? lv_font_get_line_height(font) * 9 / 10 : 0;
  const lv_image_dsc_t *src = on && side > 0 ? picture_for(index_of(condition), side) : nullptr;
  lv_obj_t *picture = picture_of(label, src != nullptr);
  if (!src) {
    if (picture) lv_obj_add_flag(picture, LV_OBJ_FLAG_HIDDEN);
    lv_obj_set_style_text_opa(label, LV_OPA_COVER, 0);
    return;
  }
  lv_obj_set_style_text_opa(label, LV_OPA_TRANSP, 0);
  if (lv_image_get_src(picture) != src) lv_image_set_src(picture, src);
  lv_obj_set_size(picture, lv_pct(100), lv_pct(90));
  lv_obj_align(picture, LV_ALIGN_CENTER, 0, 0);
  lv_obj_remove_flag(picture, LV_OBJ_FLAG_HIDDEN);
}
#else
// A profile without LVGL's image widget keeps the icons.
void dress(lv_obj_t *, const std::string &, bool, bool) {}
#endif

}  // namespace weather_emoji
#endif
