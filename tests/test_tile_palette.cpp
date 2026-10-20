#include "screen_text_en.h"
#define THEME_TEST
#include "components/smart_display/tile_palette.h"
#include <cassert>
int main() {
  assert(tile_palette::color("auto")==0);
  assert(tile_palette::color("")==0);
  assert(tile_palette::color("unknown-future-choice")==0);
  assert(tile_palette::color("red")==0xFADADD);
  assert(tile_palette::color("green")!=tile_palette::color("red"));
  // A colour the add-on chose for this tile (app 0.4.91): "#RRGGBB" is that colour; a broken one is no colour at all.
  assert(tile_palette::color("#F44336")==0xF44336);
  assert(tile_palette::color("#f44336")==0xF44336);
  assert(tile_palette::color("#123")==0);
  assert(tile_palette::color("#GGGGGG")==0);
  assert(tile_palette::color("#1234567")==0);
  // "None" is not a colour: the card is hidden, and old firmware falls back to automatic.
  assert(tile_palette::color("none")==0);
  assert(tile_palette::transparent("none"));
  assert(!tile_palette::transparent("auto") && !tile_palette::transparent("red") && !tile_palette::transparent(""));
}
