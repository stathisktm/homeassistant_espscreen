"""An icon by state (app 0.4.112, tint.validate_icons, tint.icon_of): rules like a colour's that give a tile another
icon, resolved by the app and sent as the icon itself with every state, so no firmware knows them."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'screen_manager/app'))
import tile_icons  # noqa: E402
import tint  # noqa: E402
from core import Grid, screen_options, state_message, tile_icon, validate_layout  # noqa: E402


class Rules(unittest.TestCase):
    def test_kept_as_the_editor_makes_them(self):
        rules = [{'when': 'on', 'icon': 'lightbulb'}, {'above': 25, 'icon': 'lamp'}, {'when': 'clear-night', 'icon': 'chandelier'}]
        self.assertEqual(tint.validate_icons({'icons': rules}, tile_icons.ICONS)['icons'],
                         [{'when': 'on', 'icon': 'lightbulb'}, {'icon': 'lamp', 'above': 25}, {'when': 'clear-night', 'icon': 'chandelier'}])
        self.assertEqual(tint.validate_icons({'icons': []}, tile_icons.ICONS), {})
        for bad in ([{'when': 'on', 'icon': 'no-such-icon'}], [{'when': 'on'}], [{'icon': 'lamp'}],
                    [{'when': 'on', 'above': 2, 'icon': 'lamp'}], [{'when': 'on', 'icon': 'lamp', 'c': 'red'}],
                    [{'when': 'on', 'icon': 'lamp'}] * (tint.RULES + 1), 'lamp'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                tint.validate_icons({'icons': bad}, tile_icons.ICONS)

    def test_the_first_rule_that_fits_gives_the_icon(self):
        tile = {'entity': 'climate.hall', 'options': {'icon': 'lamp', 'icons': [
            {'when': 'heating', 'icon': 'lightbulb'}, {'below': 5, 'icon': 'chandelier'}]}}
        self.assertEqual(tint.icon_of(tile, 'heat', {'hvac_action': 'heating'}), 'lightbulb')
        self.assertEqual(tint.icon_of(tile, 'heat', {'hvac_action': 'idle', 'current_temperature': 2}), 'chandelier')
        self.assertIsNone(tint.icon_of(tile, 'heat', {'hvac_action': 'idle', 'current_temperature': 20}))
        # The screen gets the icon itself: the rule's, else the tile's own choice.
        self.assertEqual(tile_icon(tile, {'hvac_action': 'heating'}, 'heat'), tile_icons.ICONS['lightbulb'][0])
        self.assertEqual(tile_icon(tile, {'hvac_action': 'idle', 'current_temperature': 20}, 'heat'), tile_icons.ICONS['lamp'][0])


class Screen(unittest.TestCase):
    def test_the_rules_stay_in_the_app_and_the_icon_follows_the_state(self):
        tile = {'entity': 'switch.fan', 'name': '', 'options': {'icons': [{'when': 'on', 'icon': 'lightbulb'}]}}
        options = screen_options(tile, {}, 'on')
        self.assertNotIn('icons', options)
        self.assertEqual(options['icon'], tile_icons.ICONS['lightbulb'][0])
        on = state_message(0, tile, {'switch.fan': {'state': 'on', 'attributes': {}}})
        off = state_message(0, tile, {'switch.fan': {'state': 'off', 'attributes': {}}})
        self.assertEqual(on['o']['icon'], tile_icons.ICONS['lightbulb'][0])
        self.assertNotEqual(off['o'].get('icon'), tile_icons.ICONS['lightbulb'][0])

    def test_a_layout_keeps_them(self):
        layout = validate_layout({'title': 'Hall', 'tiles': [{'entity': 'switch.fan', 'name': '', 'slot': 0,
                                  'options': {'icons': [{'when': 'on', 'icon': 'lightbulb'}]}}]}, grid=Grid())
        self.assertEqual(layout['tiles'][0]['options']['icons'], [{'when': 'on', 'icon': 'lightbulb'}])
        with self.assertRaises(ValueError):
            validate_layout({'title': 'Hall', 'tiles': [{'entity': 'switch.fan', 'name': '', 'slot': 0,
                             'options': {'icons': [{'when': 'on', 'icon': 'nope'}]}}]}, grid=Grid())


if __name__ == '__main__':
    unittest.main()
