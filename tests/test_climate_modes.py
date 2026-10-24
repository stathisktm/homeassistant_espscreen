"""The modes a thermostat's tile shows (app 0.4.113): as Home Assistant's own climate features choose them, a list of
the HVAC, fan and swing modes kept per tile. The screen gets the lists cut to those, so every firmware shows only them."""
import itertools
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'screen_manager/app'))
from core import Grid, screen_options, state_message, validate_layout  # noqa: E402
from layout_migrations import migrate_legacy  # noqa: E402
from page_layout import compile_tiles, validate_document  # noqa: E402

AIRCO = {'state': 'cool', 'attributes': {
    'hvac_modes': ['off', 'heat', 'cool', 'heat_cool', 'auto', 'dry', 'fan_only', 'eco', 'turbo'],
    'fan_modes': ['auto', 'low', 'medium', 'high'], 'swing_modes': ['off', 'vertical', 'horizontal', 'both']}}


def options_of(entity, options):
    return validate_layout({'title': 'Hall', 'tiles': [{'entity': entity, 'name': '', 'slot': 0, 'options': options}]},
                           grid=Grid())['tiles'][0].get('options', {})


class Modes(unittest.TestCase):
    def test_kept_on_a_thermostat_and_refused_when_broken(self):
        kept = options_of('climate.hall', {'hvac_modes': ['heat', 'cool'], 'fan_modes': ['low', 'high'], 'swing_modes': ['off']})
        self.assertEqual((kept['hvac_modes'], kept['fan_modes'], kept['swing_modes']), (['heat', 'cool'], ['low', 'high'], ['off']))
        self.assertNotIn('hvac_modes', options_of('switch.fan', {'hvac_modes': ['heat']}), 'a climate tile alone')
        for bad in ([], ['heat', 'heat'], [''], [3], 'heat', ['x' * 60], ['m'] * 17):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                options_of('climate.hall', {'hvac_modes': bad})

    def test_the_screen_gets_the_kept_modes_alone(self):
        tile = {'entity': 'climate.hall', 'name': '', 'options': {'hvac_modes': ['off', 'cool', 'turbo'], 'fan_modes': ['high']}}
        message = state_message(0, tile, {'climate.hall': AIRCO})
        # Cut before the list is bounded to eight: the ninth mode, turbo, is one of them.
        self.assertEqual(message['a']['hvac_modes'], ['off', 'cool', 'turbo'])
        self.assertEqual(message['a']['fan_modes'], ['high'])
        self.assertEqual(message['a']['swing_modes'], AIRCO['attributes']['swing_modes'], 'a kind not chosen keeps all')
        self.assertNotIn('hvac_modes', screen_options(tile, AIRCO['attributes'], 'cool'))
        # Without a choice the tile shows what Home Assistant lists, as before.
        plain = state_message(0, {'entity': 'climate.hall', 'name': '', 'options': {}}, {'climate.hall': AIRCO})
        self.assertEqual(plain['a']['hvac_modes'], AIRCO['attributes']['hvac_modes'][:8])

    def test_it_survives_the_page_document(self):
        counter = itertools.count(1)
        record = migrate_legacy({'title': 'Hall', 'tiles': [{'entity': 'climate.hall', 'slot': 0, 'options': {'hvac_modes': ['heat', 'cool']}}]},
                                Grid(), lambda: f'{next(counter):016x}')
        self.assertEqual(record['layout']['pages'][0]['tiles'][0]['interaction']['hvac_modes'], ['heat', 'cool'])
        validate_document(record['layout'], Grid())
        self.assertEqual(compile_tiles(record['layout'], Grid())[0]['options']['hvac_modes'], ['heat', 'cool'])


if __name__ == '__main__':
    unittest.main()
