"""An off light and an off binary sensor look off, as in Home Assistant (app 0.2.62 / firmware 0.2.53).

Home Assistant's own light icon is a bulb that is crossed out while off (`mdi:lightbulb-off`), and every entity that is
off is grey. An icon of its own, or one chosen in ESP Screens, stays the same and turns grey, as in Home Assistant.
"""
from firmware_sources import runtime_source
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import profiles  # noqa: E402
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
import header_bar  # noqa: E402
import tile_icons  # noqa: E402

TILES = runtime_source()
THEME = (ROOT / 'components/smart_display/theme.h').read_text()


class OffLook(unittest.TestCase):
    def test_the_fonts_carry_the_bulb_that_is_off(self):
        self.assertEqual(tile_icons.GLYPHS['lightbulb-off'], 'F0E4F')
        for name in ('checkout/guition.yaml', 'checkout/cyd.yaml', 'packages/cyd.yaml', 'packages/guition.yaml'):
            self.assertIn('"\\U000F0E4F" # lightbulb-off', profiles.text(name), name)

    def test_the_screen_crosses_out_its_own_bulb_and_greys_what_is_off(self):
        self.assertIn('if (d == "light" && tile.state == "off") return "\\U000F0E4F";', TILES)
        # Since firmware 0.2.71 every tile follows Home Assistant's stateActive() (Tile::active), not a list of domains.
        self.assertIn('bool on = t.builtin() || (fresh() && t.active());', TILES)
        # A colour by state on the icon alone while off (firmware 0.64.0, option tint_icon) takes the rule's colour.
        self.assertIn('uint32_t state_color=icon_tint?t.background:on?accent:theme::STATE_OFF;', TILES)
        self.assertIn('constexpr uint32_t STATE_OFF = ha::GREY;', THEME)
        self.assertIn('constexpr uint32_t GREY = 0x9E9E9E;', THEME)

    def test_the_top_bar_does_the_same(self):
        light = lambda state, **attrs: {'state': state, 'attributes': attrs}
        self.assertEqual(header_bar.auto_icon('light.hall', light('off')), tile_icons.GLYPHS['lightbulb-off'])
        self.assertEqual(header_bar.auto_icon('light.hall', light('on')), tile_icons.GLYPHS['lightbulb'])
        self.assertEqual(header_bar.auto_icon('light.hall', light('unavailable')), tile_icons.GLYPHS['lightbulb'])
        self.assertEqual(header_bar.auto_icon('light.lamp', light('off', icon='mdi:lamp')), tile_icons.GLYPHS['lamp'])
        self.assertIsNone(header_bar.accent('light.hall', light('off')))


if __name__ == '__main__':
    unittest.main()
