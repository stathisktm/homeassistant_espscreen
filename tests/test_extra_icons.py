"""Every icon of Home Assistant (app 0.4.115, firmware 0.68.0): a tile, a rule, a page and a top bar item may pick any icon
of Material Design Icons, a screen is built with the ones its own pages use beyond the set (extra_icons.py), and until
then it draws the icon of the set the app names beside it. And the icon alone on a card, without its circle."""
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
import extra_icons  # noqa: E402
import header_bar  # noqa: E402
import page_delivery  # noqa: E402
import tile_icons  # noqa: E402
import yaml  # noqa: E402
from core import Grid, screen_options, state_message, validate_layout  # noqa: E402
from firmware import Firmware, LenientLoader, profile_meta  # noqa: E402
from page_layout import APPEARANCE  # noqa: E402

PROFILE = 'substitutions:\n  DEVICE_NAME: "a"\nesphome:\n  name: a\npackages:\n  display: !include /r/packages/core.yaml\n'


class TheWholeFont(unittest.TestCase):
    def test_every_icon_of_the_font_by_name(self):
        self.assertGreater(len(tile_icons.ALL_GLYPHS), 7000)
        # The set every screen carries has the same codepoints in the whole table.
        for name, code in tile_icons.GLYPHS.items():
            self.assertEqual(tile_icons.ALL_GLYPHS[name], code, name)
        self.assertTrue(tile_icons.known('fridge-outline'))
        self.assertFalse(tile_icons.known('mdi:fridge'))
        self.assertFalse(tile_icons.known('no-such-icon'))

    def test_every_icon_font_has_room_for_the_screen_s_own(self):
        core = (ROOT / 'packages/core.yaml').read_text(encoding='utf-8')
        self.assertIn('  EXTRA_ICONS: ""\n', core)
        self.assertIn('  EXTRA_ICONS_BIG: ""\n', core)
        self.assertEqual(len(re.findall(r'- "\$\{EXTRA_ICONS\}"', core)), 1, 'the anchor the card fonts share')
        self.assertEqual(len(re.findall(r'- "\$\{EXTRA_ICONS_BIG\}"', core)), 1, 'the full-page card font')


class Options(unittest.TestCase):
    def test_any_icon_on_a_tile_a_rule_and_a_bar_item(self):
        layout = validate_layout({'title': 'Hall', 'tiles': [{'entity': 'switch.fridge', 'name': '', 'slot': 0, 'options': {
            'icon': 'fridge-outline', 'icons': [{'when': 'on', 'icon': 'fridge-alert'}]}}]}, grid=Grid())
        self.assertEqual(layout['tiles'][0]['options']['icon'], 'fridge-outline')
        self.assertEqual(layout['tiles'][0]['options']['icons'][0]['icon'], 'fridge-alert')

    def test_the_icon_alone_is_kept_only_as_true(self):
        self.assertEqual(APPEARANCE['iconPlain'], 'icon_plain')
        tile = lambda value: {'title': 'Hall', 'tiles': [{'entity': 'light.a', 'name': '', 'slot': 0, 'options': {'icon_plain': value}}]}
        self.assertTrue(validate_layout(tile(True), grid=Grid())['tiles'][0]['options']['icon_plain'])
        self.assertNotIn('icon_plain', validate_layout(tile(False), grid=Grid())['tiles'][0].get('options', {}))
        with self.assertRaises(ValueError):
            validate_layout(tile('yes'), grid=Grid())
        # The screen gets it with the tile's options.
        self.assertTrue(screen_options({'entity': 'light.a', 'options': {'icon_plain': True}}, {}, 'on')['icon_plain'])


class TheWire(unittest.TestCase):
    def setUp(self):
        # Home Assistant's icons of a domain: the one of the set a screen draws in place of an icon it lacks.
        tile_icons.use_ha_icons({'entity_component': {'switch': {'_': {'default': 'mdi:toggle-switch-variant', 'state': {'on': 'mdi:power'}}},
                                                      'light': {'_': {'default': 'mdi:lightbulb'}}}})
        self.addCleanup(tile_icons.use_ha_icons, {})

    def test_an_icon_beyond_the_set_travels_with_one_of_the_set(self):
        states = {'switch.fridge': {'state': 'on', 'attributes': {}}}
        message = state_message(0, {'entity': 'switch.fridge', 'name': '', 'options': {'icon': 'fridge-outline'}}, states)
        self.assertEqual(message['o']['icon'], tile_icons.ALL_GLYPHS['fridge-outline'])
        self.assertIn(message['o']['icon_fb'], tile_icons.CARRIED, 'what a screen without it draws')
        # A state message names both too, as the screen reads a changed icon there.
        state = page_delivery.tile_message(message, {'entity': 'switch.fridge', 'slot': 0}, initial=False)
        self.assertEqual((state['icon'], state['ifb']), (message['o']['icon'], message['o']['icon_fb']))
        # An icon of the set needs no second one.
        plain = state_message(0, {'entity': 'switch.fridge', 'name': '', 'options': {'icon': 'lamp'}}, states)
        self.assertNotIn('icon_fb', plain['o'])
        # Without an icon of the set to name, the screen draws its own for the domain, as before.
        tile_icons.use_ha_icons({})
        bare = state_message(0, {'entity': 'switch.fridge', 'name': '', 'options': {'icon': 'fridge-outline'}}, states)
        self.assertNotIn('icon_fb', bare['o'])

    def test_home_assistant_s_own_icon_beyond_the_set(self):
        states = {'light.a': {'state': 'on', 'attributes': {'icon': 'mdi:fridge-outline'}}}
        message = state_message(0, {'entity': 'light.a', 'name': ''}, states)
        self.assertEqual(message['o']['icon'], tile_icons.ALL_GLYPHS['fridge-outline'])
        self.assertEqual(message['o']['icon_fb'], tile_icons.GLYPHS['lightbulb'])

    def test_a_bar_item_names_one_of_the_set_beside_it(self):
        item = {'type': 'entity', 'entity': 'sensor.fridge', 'content': 'state', 'icon': 'fridge-outline', 'show': 'always'}
        wire, _ = header_bar.entity_item(item, {'sensor.fridge': {'state': '4', 'attributes': {}}})
        self.assertEqual(wire['i'], tile_icons.ALL_GLYPHS['fridge-outline'])
        self.assertIn(wire['j'], tile_icons.CARRIED)
        item['icon'] = 'lamp'
        wire, _ = header_bar.entity_item(item, {'sensor.fridge': {'state': '4', 'attributes': {}}})
        self.assertNotIn('j', wire)


class WhatAScreenCarries(unittest.TestCase):
    def test_the_icons_its_pages_use_beyond_the_set(self):
        icons = {'entity_component': {'binary_sensor': {'door': {'default': 'mdi:door-closed', 'state': {'on': 'mdi:door-open'}}},
                                      'sensor': {'_': {'default': 'mdi:eye'}}}}
        tiles = [{'entity': 'switch.fridge', 'options': {'icon': 'fridge-outline', 'icons': [{'when': 'on', 'icon': 'fridge-alert'}]}},
                 {'entity': 'light.a', 'options': {'icon': 'lamp'}},
                 {'entity': 'binary_sensor.door', 'options': {}},
                 {'entity': 'light.b', 'options': {}}]
        states = {'binary_sensor.door': {'state': 'off', 'attributes': {'device_class': 'door'}},
                  'light.b': {'state': 'on', 'attributes': {'icon': 'mdi:ceiling-fan-light'}}}
        pages = [{'icon': 'sofa-single', 'topbar': {'trailing': [
            {'type': 'entity', 'entity': 'sensor.x', 'icon': 'auto'}, {'type': 'entity', 'entity': 'sensor.y', 'icon': 'bee'}]}}]
        names, big = extra_icons.wanted(tiles, pages, states, {}, icons)
        # The chosen ones first, then Home Assistant's in every state; never one of the set (lamp, door-open, eye).
        self.assertEqual(names[:4], ['fridge-outline', 'fridge-alert', 'sofa-single', 'bee'])
        self.assertIn('ceiling-fan-light', names)
        for name in ('lamp', 'eye', 'door-open', 'door-closed'):
            self.assertEqual(name in names, name not in tile_icons.GLYPHS, name)
        # Only a tile takes the whole page: the big font gets the tiles' alone.
        self.assertNotIn('sofa-single', big)
        self.assertNotIn('bee', big)
        self.assertIn('fridge-outline', big)

    def test_a_small_board_carries_fewer(self):
        names = [name for name in tile_icons.ALL_GLYPHS if name not in tile_icons.GLYPHS][:300]
        self.assertEqual(extra_icons.capped(names, names, 'lite'), (names[:extra_icons.MOST['lite']], []))
        full = extra_icons.capped(names, names, 'full')
        self.assertEqual((len(full[0]), len(full[1])), (extra_icons.MOST['full'], extra_icons.MOST_BIG['full']))

    def test_the_text_and_back(self):
        text = extra_icons.text(['fridge-outline', 'bee'])
        self.assertEqual(text, chr(int(tile_icons.ALL_GLYPHS['fridge-outline'], 16)) + chr(int(tile_icons.ALL_GLYPHS['bee'], 16)))
        self.assertEqual(extra_icons.names_of(text), ['fridge-outline', 'bee'])


class TheProfile(unittest.TestCase):
    def test_the_icons_are_written_as_escapes_and_read_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            firmware = Firmware(tmp, tmp)
            path = Path(tmp) / 'a.yaml'
            path.write_bytes(PROFILE.encode())
            self.assertFalse(firmware.set_extra_icons('a.yaml', '', ''), 'none needed, no line')
            self.assertEqual(path.read_bytes().decode(), PROFILE)
            text = extra_icons.text(['fridge-outline', 'bee'])
            self.assertTrue(firmware.set_extra_icons('a.yaml', text, text[:1]))
            out = path.read_bytes().decode()
            self.assertIn('EXTRA_ICONS: "\\U000' + tile_icons.ALL_GLYPHS['fridge-outline'], out)
            data = yaml.load(out, Loader=LenientLoader)
            self.assertEqual((data['substitutions']['EXTRA_ICONS'], data['substitutions']['EXTRA_ICONS_BIG']), (text, text[:1]))
            self.assertEqual(data['substitutions']['DEVICE_NAME'], 'a')
            self.assertEqual(profile_meta(out)['icons'], text)
            self.assertFalse(firmware.set_extra_icons('a.yaml', text, text[:1]), 'nothing to do the second time')


class TheUpdate(unittest.TestCase):
    def test_an_icon_the_build_lacks_makes_the_update_due(self):
        import updates
        text = extra_icons.text(['fridge-outline'])

        class Manager:
            def __init__(self, built):
                self.built = built
                self.firmware = type('F', (), {'profile_names': lambda _: {'a.yaml': {'node': 'a', 'screen': True, 'icons': self.built}}})()
            def extra_icons_of(self, inbox, meta):
                return ['fridge-outline'], []
        updater = updates.Updater.__new__(updates.Updater)
        updater.hosts = {}
        screen = {'id': 'text.a_inbox', 'node': 'a'}
        updater.manager = Manager('')
        self.assertTrue(updater.icons_due(screen))
        updater.manager = Manager(text)
        self.assertFalse(updater.icons_due(screen))
        # A profile that is not one of ESP Screens' says nothing.
        updater.manager = Manager('')
        updater.manager.firmware = type('F', (), {'profile_names': lambda _: {'a.yaml': {'node': 'a', 'screen': False, 'icons': ''}}})()
        self.assertFalse(updater.icons_due(screen))


if __name__ == '__main__':
    unittest.main()
