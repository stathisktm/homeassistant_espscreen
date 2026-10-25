"""A weather tile's colour pictures (app 0.4.116, firmware 0.69.0, module weather_emoji): the option the app keeps, the
pictures every board is built with (single pixels where the module is not), and the conditions the firmware knows."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
from core import Grid, screen_options, validate_layout  # noqa: E402
from page_layout import APPEARANCE  # noqa: E402
import tile_icons  # noqa: E402

CORE = (ROOT / 'packages/core.yaml').read_text(encoding='utf-8')
TABLE = (ROOT / 'components/smart_display/weather_pictures.h').read_text(encoding='utf-8')
CONDITIONS = re.findall(r'"([a-z-]+)"', TABLE.split('CONDITIONS[] = {', 1)[1].split('};', 1)[0])


class TheOption(unittest.TestCase):
    def layout(self, entity, value):
        return validate_layout({'title': 'Hall', 'tiles': [{'entity': entity, 'name': '', 'slot': 0,
                                                            'options': {'weather_icons': value}}]}, grid=Grid())

    def test_kept_on_a_weather_tile_only(self):
        self.assertEqual(APPEARANCE['weatherIcons'], 'weather_icons')
        self.assertEqual(self.layout('weather.home', 'emoji')['tiles'][0]['options']['weather_icons'], 'emoji')
        self.assertNotIn('weather_icons', self.layout('weather.home', 'icons')['tiles'][0].get('options', {}))
        self.assertNotIn('weather_icons', self.layout('light.a', 'emoji')['tiles'][0].get('options', {}))
        with self.assertRaises(ValueError):
            self.layout('weather.home', 'pictures')
        # The screen gets it with the tile's options.
        self.assertEqual(screen_options({'entity': 'weather.home', 'options': {'weather_icons': 'emoji'}}, {}, 'sunny')['weather_icons'], 'emoji')


class ThePictures(unittest.TestCase):
    def test_every_condition_of_home_assistant_has_a_picture(self):
        # Home Assistant's conditions (tile_icons.WEATHER), windy-variant drawn as windy.
        self.assertEqual(set(CONDITIONS), set(tile_icons.WEATHER) - {'windy-variant'})
        for condition in CONDITIONS:
            self.assertTrue((ROOT / f'fonts/weather-emoji-{condition}.png').exists(), condition)
            self.assertTrue((ROOT / f'web/src/assets/weather-emoji/{condition}.png').exists(), condition)

    def test_built_at_both_icon_sizes_and_handed_over_in_order(self):
        for index, condition in enumerate(CONDITIONS):
            ident = condition.replace('-', '_')
            for suffix in ('s', 'm'):
                self.assertIn(f'  - id: weather_emoji_{ident}_{suffix}\n    file: "${{FONT_DIR}}/weather-emoji-{condition}.png"', CORE)
            self.assertIn(f'weather_pictures::set({index}, id(weather_emoji_{ident}_s)->get_lv_image_dsc(), '
                          f'id(weather_emoji_{ident}_m)->get_lv_image_dsc());', CORE)

    def test_a_board_without_the_module_builds_single_pixels(self):
        self.assertIn('  WEATHER_EMOJI: "1"\n', CORE)
        flash = (ROOT / 'packages/hardware/flash-4mb.yaml').read_text(encoding='utf-8')
        self.assertIn('  WEATHER_EMOJI: "0"\n', flash)
        self.assertEqual(CORE.count('(WEATHER_EMOJI | int)'), 4 * len(CONDITIONS), 'width and height of both sizes')


if __name__ == '__main__':
    unittest.main()
