#pragma once
#include <cstdint>
#include <string>
#include "theme.h"

namespace tile_palette {
// The named card colours ESP Screens offers (theme::SWATCHES). A tile and an alert keep the light value as the colour's
// identity; theme::surface() draws it in the current look. Unknown future names and "auto" are 0: the normal card.
// A colour chosen by the add-on for this tile (app 0.4.91, a state's colour) travels as "#RRGGBB" and is kept as it is.
inline uint32_t color(const std::string &name) {
  if (!name.empty() && name[0] == '#') {
    uint32_t rgb = 0;
    unsigned digits = 0;
    for (size_t i = 1; i < name.size(); ++i) {
      const char c = name[i];
      const int value = c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1;
      if (value < 0 || digits == 6) return 0;  // a shape this firmware does not read: the card's own colour
      rgb = (rgb << 4) | static_cast<uint32_t>(value);
      ++digits;
    }
    return digits == 6 ? rgb : 0;
  }
  return theme::swatch(name);
}
// "None": no card behind the tile contents. Older firmware treats it as automatic.
inline bool transparent(const std::string &name) { return name=="none"; }
}
