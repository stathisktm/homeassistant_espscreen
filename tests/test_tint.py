"""A card's colour by state (app 0.4.91, tint.py): the rules a tile keeps, the colour the first match gives, and the
temperature a rule compares."""
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
import tint  # noqa: E402


class Rules(unittest.TestCase):
    def test_the_rules_the_add_on_keeps(self):
        kept = tint.validate({'tint': [{'when': 'heating', 'c': 'deep-orange'}, {'above': 25, 'c': '#ff0000'},
                                       {'below': 5, 'c': 'blue'}], 'background': 'mint'})
        self.assertEqual(kept, {'tint': [{'when': 'heating', 'c': 'deep-orange'}, {'c': '#ff0000', 'above': 25},
                                         {'c': 'blue', 'below': 5}], 'background': 'mint'})
        # No rules is no key, and nothing else of the tile's options changes.
        self.assertEqual(tint.validate({'tint': [], 'background': 'mint'}), {'background': 'mint'})
        self.assertEqual(tint.validate({'background': 'mint'}), {'background': 'mint'})
        # A shape the editor never makes is refused: a word that is not one, a colour no screen knows, too many rules.
        for bad in ('heating', [{'when': 'Heating', 'c': 'red'}], [{'when': 'heating'}], [{'c': 'red'}],
                    [{'when': 'heating', 'above': 2, 'c': 'red'}], [{'above': 'warm', 'c': 'red'}],
                    [{'when': 'heating', 'c': 'not-a-colour'}], [{'when': 'heating', 'c': 'red', 'x': 1}],
                    [{'when': 'on', 'c': 'red'}] * (tint.RULES + 1)):
            with self.assertRaises(ValueError, msg=bad):
                tint.validate({'tint': bad})

    def test_a_colour_is_the_colour_itself(self):
        # The screen is sent the colour, never a table of names: Home Assistant's own, or a colour typed as it is.
        self.assertEqual(tint.colour_value('deep-orange'), '#ff6f22')
        self.assertEqual(tint.colour_value('#AABBCC'.lower()), '#aabbcc')
        self.assertIsNone(tint.colour_value('mint'))


class Weather(unittest.TestCase):
    """A weather tile (app 0.4.101): its states as Home Assistant reports them, dashes too, and a temperature rule that
    reads the entity of the tile's line instead of the weather's own when it says `"of": "line"`."""
    TILE = {'entity': 'weather.home', 'options': {'background': 'mint', 'tint': [
        {'when': 'clear-night', 'c': 'indigo'}, {'above': 25, 'c': 'red', 'of': 'line'}, {'below': 5, 'c': 'blue'}]}}

    def test_a_state_with_a_dash_is_a_state(self):
        for word in ('clear-night', 'snowy-rainy', 'lightning-rainy', 'windy-variant'):
            self.assertEqual(tint.validate({'tint': [{'when': word, 'c': 'indigo'}]})['tint'], [{'when': word, 'c': 'indigo'}])
        self.assertEqual(tint.card_background(self.TILE, 'clear-night', {'temperature': 12}), tint.colour_value('indigo'))

    def test_of_the_line_reads_the_lines_entity_alone(self):
        kept = tint.validate(self.TILE['options'])['tint']
        self.assertEqual(kept[1], {'c': 'red', 'of': 'line', 'above': 25})
        outside = ('sensor.outside', {'state': '31', 'attributes': {'unit_of_measurement': '°C'}})
        # The weather says 18 and the thermometer outside 31: the rule of the line's entity fits.
        self.assertEqual(tint.card_background(self.TILE, 'sunny', {'temperature': 18}, outside), tint.colour_value('red'))
        # Without the line's entity that rule compares nothing; the weather's own 3 degrees fit the next rule.
        self.assertEqual(tint.card_background(self.TILE, 'sunny', {'temperature': 3}), tint.colour_value('blue'))
        self.assertEqual(tint.card_background(self.TILE, 'sunny', {'temperature': 18}), 'mint')
        for bad in ([{'above': 25, 'c': 'red', 'of': 'sensor.outside'}], [{'when': 'sunny', 'c': 'red', 'of': 'line'}]):
            with self.assertRaises(ValueError, msg=bad):
                tint.validate({'tint': bad})


class IconWhileOff(unittest.TestCase):
    """`tint_icon` (app 0.4.107): the rules' colour on the icon alone while the tile is off. The screen decides what off
    is (firmware 0.64.0); the app keeps the option beside rules and keeps the tile's own colour in its options."""

    def test_kept_as_true_and_only_beside_rules(self):
        rules = [{'when': 'on', 'c': 'red'}]
        self.assertEqual(tint.validate({'tint': rules, 'tint_icon': True}), {'tint': rules, 'tint_icon': True})
        self.assertEqual(tint.validate({'tint_icon': True, 'background': 'mint'}), {'background': 'mint'})
        self.assertEqual(tint.validate({'tint': [], 'tint_icon': True}), {})
        for bad in (False, 1, 'yes'):
            with self.assertRaises(ValueError, msg=bad):
                tint.validate({'tint': rules, 'tint_icon': bad})

    def test_the_tile_keeps_its_own_colour_in_its_options(self):
        whole = tint.wire({'o': {'background': 'mint'}}, '#ff0000')
        self.assertEqual((whole['x']['bg'], whole['o']['background']), ('#ff0000', '#ff0000'))
        icon = tint.wire({'o': {'background': 'mint'}}, '#ff0000', icon=True)
        self.assertEqual((icon['x']['bg'], icon['o']['background']), ('#ff0000', 'mint'))


class Colours(unittest.TestCase):
    CLIMATE = {'entity': 'climate.hall', 'options': {'background': 'mint', 'tint': [
        {'when': 'heating', 'c': 'deep-orange'}, {'when': 'cooling', 'c': 'blue'},
        {'below': 5, 'c': 'indigo'}, {'above': 28, 'c': 'red'}]}}

    def test_the_first_rule_that_fits_gives_the_colour(self):
        self.assertEqual(tint.card_background(self.CLIMATE, 'heat', {'hvac_action': 'heating', 'current_temperature': 21}), '#ff6f22')
        # What the entity does counts as well as its state: a thermostat's mode is heat while it cools.
        self.assertEqual(tint.card_background(self.CLIMATE, 'heat', {'hvac_action': 'cooling'}), '#2196f3')
        # A temperature rule, in the card's own temperature.
        self.assertEqual(tint.card_background(self.CLIMATE, 'heat', {'hvac_action': 'idle', 'current_temperature': 2}), '#3f51b5')
        self.assertEqual(tint.card_background(self.CLIMATE, 'heat', {'hvac_action': 'idle', 'current_temperature': 31}), '#f44336')
        # Nothing fits: the card goes back to the colour it was given.
        self.assertEqual(tint.card_background(self.CLIMATE, 'off', {'hvac_action': 'idle', 'current_temperature': 21}), 'mint')
        # A tile without rules carries no colour at all, so every screen draws it as it always did.
        self.assertIsNone(tint.card_background({'entity': 'light.desk', 'options': {}}, 'on', {}))

    def test_a_temperature_can_come_from_the_second_line(self):
        tile = {'entity': 'switch.heater', 'options': {'tint': [{'below': 18, 'c': 'blue'}]}}
        outside = ('sensor.outside', {'state': '12', 'attributes': {'unit_of_measurement': '°C'}})
        self.assertEqual(tint.card_background(tile, 'on', {}, second=outside), '#2196f3')
        # At 21° the rule does not fit and the card keeps its own colour (none, so the plain card).
        self.assertEqual(tint.card_background(tile, 'on', {}, second=('sensor.outside', {'state': '21', 'attributes': {}})), '')
        # A switch measures nothing and reads nothing: its temperature rules never fit.
        self.assertEqual(tint.card_background(tile, 'on', {}), '')

    def test_the_cards_own_temperature_comes_first(self):
        tile = {'entity': 'climate.hall', 'options': {'tint': [{'above': 25, 'c': 'red'}]}}
        second = ('sensor.outside', {'state': '30', 'attributes': {}})
        self.assertEqual(tint.card_background(tile, 'cool', {'current_temperature': 21}, second=second), '')
        self.assertEqual(tint.card_background(tile, 'cool', {'current_temperature': 26}, second=second), '#f44336')


class Message(unittest.TestCase):
    def test_the_colour_rides_both_ways_a_screen_reads_it(self):
        # x.bg on every message, and the tile's own options too, so a card drawn at its first message (a forecast, a
        # graph) takes the colour as well (app 0.4.95).
        message = tint.wire({'index': 3, 'o': {'entity': 'weather.home', 'background': 'mint'}}, '#ffeb3b')
        self.assertEqual(message['x'], {'bg': '#ffeb3b'})
        self.assertEqual(message['o']['background'], '#ffeb3b')
        # A named card colour and a colourless card are not options: the screen knows every name already.
        self.assertEqual(tint.wire({'index': 3, 'o': {'background': 'mint'}}, 'mint'), {'index': 3, 'x': {'bg': 'mint'}, 'o': {'background': 'mint'}})
        # A tile that keeps no rules is a message that carries no colour at all.
        self.assertEqual(tint.wire({'index': 3}, None), {'index': 3})


if __name__ == '__main__':
    unittest.main()
