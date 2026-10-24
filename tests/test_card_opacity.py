"""How much of a card covers what lies under it (app 0.4.111, firmware 0.67.0): a page's background shows through a
card of 80, 60, 40 or 20 percent. The app keeps it as the editor makes it and sends it to the screen with the tile."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'screen_manager/app'))
from core import Grid, screen_options, validate_layout  # noqa: E402


def options_of(options):
    return validate_layout({'title': 'Hall', 'tiles': [{'entity': 'light.hall', 'name': '', 'slot': 0, 'options': options}]},
                           grid=Grid())['tiles'][0].get('options', {})


class Opacity(unittest.TestCase):
    def test_kept_dropped_and_refused(self):
        for value in (80, 60, 40, 20):
            self.assertEqual(options_of({'opacity': value})['opacity'], value)
        # The whole card is no key, and a card without one (Background: none) has nothing to make see-through.
        self.assertNotIn('opacity', options_of({'opacity': 100}))
        self.assertNotIn('opacity', options_of({'opacity': 40, 'background': 'none'}))
        for bad in (50, 0, '40', True, 40.0):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                options_of({'opacity': bad})

    def test_the_screen_gets_it_with_the_tile(self):
        options = screen_options({'entity': 'light.hall', 'options': {'opacity': 40, 'background': 'mint'}}, {}, 'on')
        self.assertEqual(options['opacity'], 40)


    def test_it_survives_the_page_document(self):
        import itertools
        from layout_migrations import migrate_legacy
        from page_layout import compile_tiles, validate_document
        counter = itertools.count(1)
        record = migrate_legacy({'title': 'Hall', 'tiles': [{'entity': 'light.hall', 'slot': 0, 'options': {'opacity': 60}}]},
                                Grid(), lambda: f'{next(counter):016x}')
        self.assertEqual(record['layout']['pages'][0]['tiles'][0]['appearance']['opacity'], 60)
        validate_document(record['layout'], Grid())
        self.assertEqual(compile_tiles(record['layout'], Grid())[0]['options']['opacity'], 60)

if __name__ == '__main__':
    unittest.main()
