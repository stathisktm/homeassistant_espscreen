"""A weather tile's colour pictures (app 0.4.116, firmware 0.69.0, module weather_emoji; Iris and moving since
0.4.117): the option the app keeps, the pictures and frames every board is built with (single pixels where the
module or the flash is not), and the conditions the firmware knows."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
from core import Grid, screen_options, state_message, validate_header, validate_layout, weather_temperature  # noqa: E402
import header_bar  # noqa: E402
from page_layout import APPEARANCE  # noqa: E402
import tile_icons  # noqa: E402

CORE = (ROOT / 'packages/core.yaml').read_text(encoding='utf-8')
TABLE = (ROOT / 'components/smart_display/weather_pictures.h').read_text(encoding='utf-8')
NAMES = re.findall(r'"([a-z-]+)"', TABLE.split('NAMES[] = {', 1)[1].split('};', 1)[0])
CONDITIONS = re.findall(r'\{"([a-z-]+)", \d+, \d+\}', TABLE)


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


class TheNight(unittest.TestCase):
    """The night's pictures come the moment the sun sets (app 0.4.118), as a template on sun.sun has them."""

    def test_a_weather_tile_with_its_pictures_follows_the_sun(self):
        try:
            from server import Manager
        except ImportError as error:  # the app's server needs aiohttp
            self.skipTest(str(error))
        manager = object.__new__(Manager)          # nothing of the app is touched: a weather tile reaches no other branch
        self.assertEqual(manager.related_entities({'entity': 'weather.home', 'options': {'weather_icons': 'emoji'}}), ('sun.sun',))
        # With its icons, it follows nothing more.
        self.assertEqual(manager.related_entities({'entity': 'weather.home', 'options': {}}), ())

    def test_the_night_is_a_boolean_as_the_screen_reads_it(self):
        # The screen reads `nt` as a boolean (ArduinoJson's `| false` takes no number for it): the app sends true.
        server = (ROOT / 'screen_manager/app/server.py').read_text(encoding='utf-8')
        receiver = (ROOT / 'components/smart_display/page_receiver.cpp').read_text(encoding='utf-8')
        self.assertIn("extra = {**(extra or {}), 'nt': True}", server)
        self.assertNotIn("'nt': 1}", server)
        self.assertIn('tile.weather_night = extra["nt"] | false;', receiver)


class TheTopBar(unittest.TestCase):
    """A weather entity's item in a top bar takes its colour picture too (app 0.4.121, firmware 0.72.0)."""

    def test_emoji_is_an_icon_of_a_weather_item_only(self):
        item = {'type': 'entity', 'entity': 'weather.home', 'content': 'state', 'icon': 'emoji', 'show': 'always'}
        self.assertEqual(validate_header({'items': [item]})['items'][0]['icon'], 'emoji')
        with self.assertRaises(ValueError):
            validate_header({'items': [{**item, 'entity': 'sensor.outside'}]})

    def test_the_item_says_its_condition_and_the_night(self):
        item = {'type': 'entity', 'entity': 'weather.home', 'content': 'state', 'icon': 'emoji', 'show': 'always'}
        states = {'weather.home': {'state': 'rainy', 'attributes': {'temperature': 12, 'temperature_unit': '°C'}}}
        wire, shown = header_bar.entity_item(item, states)
        self.assertEqual(wire['w'], 'rainy')
        self.assertIn('i', wire, 'the icon stays for a screen without the pictures')
        self.assertNotIn('n', wire)
        wire, _ = header_bar.entity_item(item, {**states, 'sun.sun': {'state': 'below_horizon'}})
        self.assertIs(wire['n'], True, 'a boolean, as the screen reads it')
        # Its own icon, or none, says nothing of the weather.
        self.assertNotIn('w', header_bar.entity_item({**item, 'icon': 'auto'}, states)[0])
        receiver = (ROOT / 'components/smart_display/page_receiver.cpp').read_text(encoding='utf-8')
        self.assertIn('item.weather = string(value["w"], 20);', receiver)
        self.assertIn('item.weather_night = value["n"] | false;', receiver)


class OwnTemperature(unittest.TestCase):
    """A weather tile's temperature from a sensor of one's own (app 0.4.121)."""

    def test_kept_on_a_weather_tile_and_left_with_the_app(self):
        layout = lambda entity, value: validate_layout({'title': 'Hall', 'tiles': [{'entity': entity, 'name': '', 'slot': 0,
                                                       'options': {'temp_entity': value}}]}, grid=Grid())
        self.assertEqual(layout('weather.home', 'sensor.balcony')['tiles'][0]['options']['temp_entity'], 'sensor.balcony')
        self.assertNotIn('temp_entity', layout('light.a', 'sensor.balcony')['tiles'][0].get('options', {}))
        for bad in ('light.a', 'sensor.Bad', 'sensor.', 3):
            with self.assertRaises(ValueError, msg=bad):
                layout('weather.home', bad)
        # The screen is sent the temperature, never the sensor.
        self.assertNotIn('temp_entity', screen_options({'entity': 'weather.home', 'options': {'temp_entity': 'sensor.balcony'}}, {}, 'sunny') or {})

    def test_the_sensor_s_number_in_the_weather_s_unit(self):
        tile = {'entity': 'weather.home', 'name': '', 'options': {'temp_entity': 'sensor.balcony'}}
        weather = {'state': 'sunny', 'attributes': {'temperature': 25, 'temperature_unit': '°C'}}
        states = {'weather.home': weather, 'sensor.balcony': {'state': '21.46', 'attributes': {'unit_of_measurement': '°C'}}}
        self.assertEqual(state_message(0, tile, states)['a']['temperature'], 21.5)
        fahrenheit = {**states, 'sensor.balcony': {'state': '68', 'attributes': {'unit_of_measurement': '°F'}}}
        self.assertEqual(weather_temperature(tile, weather['attributes'], fahrenheit)['temperature'], 20.0)
        # A sensor without a number leaves the weather's own.
        for state in ('unavailable', '', None):
            gone = {**states, 'sensor.balcony': {'state': state}}
            self.assertEqual(state_message(0, tile, gone)['a']['temperature'], 25)


class TheChart(unittest.TestCase):
    """The days and hours of the week and of the card a tap opens take the pictures too (firmware 0.71.0)."""

    def test_the_chart_draws_a_picture_where_its_tile_has_them(self):
        component = ROOT / 'components/smart_display'
        chart = (component / 'weather_chart.h').read_text(encoding='utf-8')
        # A picture item, asked for through the module's hook, for the days, the hours and the weather now.
        self.assertIn('enum Kind : uint8_t { TEXT, RECT, LINE, DOT, IMAGE }', chart)
        self.assertIn('inline const lv_image_dsc_t *(*picture)(const std::string &condition, bool night, int side) = nullptr;', chart)
        self.assertEqual(chart.count(', c.pictures);'), 2, 'the days of the week and the hours')
        self.assertIn('c.pictures, c.night);', chart)
        self.assertIn('a.pictures != b.pictures || a.night != b.night', chart)
        # Every chart of a tile says whether it has them, and the module answers the hook.
        self.assertIn('c.pictures=t.weather_emoji;c.night=t.weather_night;', (component / 'runtime_tiles.h').read_text(encoding='utf-8'))
        self.assertIn('c.pictures=t.weather_emoji;c.night=t.weather_night;', (component / 'weather_cards.cpp').read_text(encoding='utf-8'))
        self.assertIn('weather_chart::picture = &chart_picture', (component / 'module_weather_emoji.cpp').read_text(encoding='utf-8'))


class ThePictures(unittest.TestCase):
    def test_every_condition_of_home_assistant_has_a_picture(self):
        # Home Assistant's conditions (tile_icons.WEATHER), each with a picture by day and by night (Iris's mapping).
        self.assertEqual(set(CONDITIONS), set(tile_icons.WEATHER))
        for name in NAMES:
            for path in (f'fonts/iris/{name}.png', f'fonts/iris/{name}.webp', f'web/src/assets/weather-emoji/{name}.webp'):
                self.assertTrue((ROOT / path).exists(), path)
        self.assertTrue((ROOT / 'fonts/iris/LICENSE.txt').exists())

    def test_built_at_both_icon_sizes_with_their_frames_and_handed_over_in_order(self):
        for index, name in enumerate(NAMES):
            ident = name.replace('-', '_')
            for suffix in ('s', 'm'):
                self.assertIn(f'  - id: weather_emoji_{ident}_{suffix}\n    file: "${{FONT_DIR}}/iris/{name}.png"', CORE)
            self.assertIn(f'  - id: weather_motion_{ident}\n    file: "${{FONT_DIR}}/iris/{name}.webp"', CORE)
            self.assertIn(f'weather_pictures::set({index}, id(weather_emoji_{ident}_s)->get_lv_image_dsc(), '
                          f'id(weather_emoji_{ident}_m)->get_lv_image_dsc());', CORE)
            self.assertIn(f'weather_pictures::set_frames({index}, id(weather_motion_{ident}));', CORE)
        # Fifteen frames of Iris's sixty, round in its four seconds.
        from PIL import Image
        frames = Image.open(ROOT / f'fonts/iris/{NAMES[0]}.webp')
        self.assertEqual(frames.n_frames, 15)

    def test_a_board_without_the_module_builds_single_pixels(self):
        self.assertIn('  WEATHER_EMOJI: "1"\n', CORE)
        flash = (ROOT / 'packages/hardware/flash-4mb.yaml').read_text(encoding='utf-8')
        self.assertIn('  WEATHER_EMOJI: "0"\n', flash)
        self.assertEqual(CORE.count('(WEATHER_EMOJI | int)'), 6 * len(NAMES), 'width and height of both sizes and the frames')

    def test_a_board_with_less_than_16_mb_keeps_its_pictures_still(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        import profiles
        self.assertIn('  WEATHER_MOTION: "1"\n', CORE)
        for board, path in profiles.BOARDS.items():
            if profiles.flash_mb(board) >= 16 or profiles.flash_mb(board) < 8:
                continue
            self.assertIn('  WEATHER_MOTION: "0"\n', Path(path).read_text(encoding='utf-8'), board)
        # The Waveshare 4.3 is built with 8 MB or 16 MB, as New screen chooses.
        self.assertIn("WEATHER_MOTION: ${ 1 if FLASH_SIZE == '16MB' else 0 }",
                      (ROOT / 'packages/boards/waveshare-esp32s3-43.yaml').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
