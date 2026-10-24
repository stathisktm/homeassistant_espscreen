"""A page's own background picture (app 0.4.109, page_backdrop.py): what a page may say, what the screen is told of
it, how the app fetches it from each kind of source, and that only its own page asks for it."""
import asyncio
import itertools
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'screen_manager/app'))
from core import Grid  # noqa: E402
import page_backdrop  # noqa: E402
import page_delivery  # noqa: E402
import picture_question as pq  # noqa: E402
from page_layout import LayoutError, validate_document  # noqa: E402
from layout_migrations import migrate_legacy  # noqa: E402


class Shape(unittest.TestCase):
    def test_every_kind_of_source(self):
        for source, kind in (('https://example.com/sky.jpg', 'url'), ('http://example.com/a.png', 'url'),
                             ('/local/backgrounds/kitchen.jpg', 'www'), ('media-source://media_source/local/a.jpg', 'media'),
                             ('camera.garden', 'entity'), ('person.someone', 'entity')):
            with self.subTest(source=source):
                self.assertEqual(page_backdrop.kind_of(source), kind)
                self.assertEqual(page_backdrop.validate({'source': source}), {'source': source})
        for bad in ('', 'ftp://example.com/a.jpg', '/local/../secrets.yaml', '/api/states', 'not an entity',
                    'https://example.com/a b.jpg', 'x' * 600):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                page_backdrop.validate({'source': bad})

    def test_dim_and_refresh(self):
        kept = page_backdrop.validate({'source': 'camera.garden', 'dim': 45, 'refresh': 300})
        self.assertEqual(kept, {'source': 'camera.garden', 'dim': 45, 'refresh': 300})
        for bad in ({'source': 'camera.garden', 'dim': 90}, {'source': 'camera.garden', 'dim': True},
                    {'source': 'camera.garden', 'refresh': 7}, {'source': 'camera.garden', 'x': 1}, {'dim': 10}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                page_backdrop.validate(bad)
        # A camera refreshes once a minute unless it says otherwise; anything else is fetched once.
        self.assertEqual(page_backdrop.refresh_of({'source': 'camera.garden'}), 60)
        self.assertEqual(page_backdrop.refresh_of({'source': 'camera.garden', 'refresh': 0}), 0)
        self.assertEqual(page_backdrop.refresh_of({'source': 'https://example.com/a.jpg'}), 0)
        self.assertEqual(page_backdrop.dim_of({'source': 'camera.garden'}), page_backdrop.DIM_DEFAULT)

    def test_the_screen_is_told_a_mark_and_never_the_address(self):
        background = {'source': 'https://example.com/secret-key/a.jpg', 'dim': 30}
        mark = page_backdrop.mark(background)
        self.assertRegex(mark, r'^[0-9a-f]{12}$')
        self.assertNotEqual(mark, page_backdrop.mark({**background, 'dim': 40}))
        page = {'id': 'p1', 'icon': None, 'topbar': {'title': {'source': 'text', 'text': 'Kitchen'}, 'leading': False},
                'navigation': {'excludeFromPagination': False}, 'background': {'source': 'camera.garden'}}
        message = page_delivery.page_message(page, 0, [], initial=True)
        self.assertEqual(message['bg'], page_backdrop.mark(page['background']))
        self.assertEqual(message['bgr'], 60)
        self.assertNotIn('camera.garden', json.dumps(message))
        del page['background']
        self.assertNotIn('bg', page_delivery.page_message(page, 0, [], initial=True))


class Document(unittest.TestCase):
    def test_a_page_keeps_its_background_and_refuses_a_broken_one(self):
        counter = itertools.count(1)
        record = migrate_legacy({'title': 'Screen', 'tiles': []}, Grid(), lambda: f'{next(counter):016x}')
        layout = record['layout']
        layout['pages'][0]['background'] = {'source': '/local/sky.jpg', 'dim': 20}
        validate_document(layout, Grid())
        self.assertEqual(layout['pages'][0]['background'], {'source': '/local/sky.jpg', 'dim': 20})
        layout['pages'][0]['background'] = {'source': '/api/states'}
        with self.assertRaises(LayoutError):
            validate_document(layout, Grid())


class Question(unittest.TestCase):
    def test_a_page_asks_for_its_own_background(self):
        self.assertEqual(pq.source('page:2'), pq.Source('page', '2'))
        for bad in ('page:x', 'page:123', 'page:1?focus=a'):
            self.assertIsNone(pq.source(bad), bad)
        owner = pq.owner_of({'o': 'page', 'i': 2})
        self.assertEqual((owner.kind, owner.index), ('page', 2))
        self.assertIsNone(pq.owner_of({'o': 'page'}))


class FakeHA:
    def __init__(self):
        self.calls = []
        self.states = {'person.someone': {'attributes': {'entity_picture': '/api/image/serve/abc/512x512'}}}

    async def picture_address(self, address, allowed, what='picture'):
        self.calls.append(('address', address))
        return address, {}

    async def picture_bytes(self, url, headers, kind, timeout=None, **options):
        self.calls.append(('bytes', url, kind))
        return b'picture of ' + url.encode()

    async def www_address(self, address):
        return 'http://ha' + address, {}, {}

    async def request(self, kind, **data):
        self.calls.append(('request', kind, data.get('media_content_id')))
        return {'url': '/media/local/a.jpg?authSig=x'}

    async def media_file(self, address):
        self.calls.append(('media', address))
        return b'photo'

    async def camera_image(self, entity):
        self.calls.append(('camera', entity))
        return b'camera'

    async def media_image(self, entity):
        return b'cover'

    async def entity_picture(self, picture):
        self.calls.append(('entity', picture))
        return b'entity'


class Fetch(unittest.IsolatedAsyncioTestCase):
    async def test_each_kind_goes_its_own_way_and_is_kept(self):
        ha, now = FakeHA(), [1000.0]
        backdrops = page_backdrop.Backdrops(ha, clock=lambda: now[0])
        raw, digest = await backdrops.picture('https://example.com/a.jpg')
        self.assertEqual(raw, b'picture of https://example.com/a.jpg')
        self.assertEqual(ha.calls[:2], [('address', 'https://example.com/a.jpg'), ('bytes', 'https://example.com/a.jpg', 'photo')])
        self.assertEqual(await backdrops.picture('/local/sky.jpg'), (b'picture of http://ha/local/sky.jpg', backdrops.kept['/local/sky.jpg'][1]))
        self.assertEqual((await backdrops.picture('media-source://media_source/local/a.jpg'))[0], b'photo')
        self.assertIn(('request', 'media_source/resolve_media', 'media-source://media_source/local/a.jpg'), ha.calls)
        self.assertEqual((await backdrops.picture('camera.garden'))[0], b'camera')
        self.assertEqual((await backdrops.picture('person.someone'))[0], b'entity')
        # Kept: the same address again is no fetch, until its refresh (or the hour) passed.
        calls = len(ha.calls)
        await backdrops.picture('camera.garden', refresh=60)
        self.assertEqual(len(ha.calls), calls)
        now[0] += 61
        await backdrops.picture('camera.garden', refresh=60)
        self.assertEqual(len(ha.calls), calls + 1)

    async def test_a_failure_keeps_the_last_picture(self):
        ha = FakeHA()
        backdrops = page_backdrop.Backdrops(ha, clock=lambda: 1000.0)
        await backdrops.picture('camera.garden')

        async def broken(entity):
            raise OSError('away')
        ha.camera_image = broken
        backdrops.kept['camera.garden'] = (b'camera', 'd', 0.0)
        self.assertEqual(await backdrops.picture('camera.garden'), (b'camera', 'd'))
        self.assertIsNone(await backdrops.picture('light.no_picture'))



class Sources(unittest.IsolatedAsyncioTestCase):
    """The question of a page's background goes through the app's rules and sources (picture_sources.py)."""

    async def test_only_its_page_asks_and_it_comes_darkened(self):
        import picture_sources

        class Manager:
            def __init__(self):
                self.backdrops = page_backdrop.Backdrops(FakeHA(), clock=lambda: 1000.0)

            def page_background(self, inbox, index):
                return {'source': 'camera.garden', 'dim': 40} if index == 1 else None

        sources = picture_sources.Sources(Manager(), None)
        box = {'box': [480, 480], 'at': [[0, 0, 480, 480, 0, 0]], 'fit': ['cover'], 'fmt': ['bmp16', 'bmp24']}
        mine = pq.parse(json.dumps({'o': 'page', 'i': 1, 'src': ['page:1'], 'look': 'd', **box}), 7, (480, 480))
        self.assertIsNotNone(mine)
        source = mine.sources[0]
        self.assertIsNone(sources.may('text.hall', {}, mine, source))
        other = pq.parse(json.dumps({'o': 'page', 'i': 0, 'src': ['page:1'], **box}), 8, (480, 480))
        self.assertIsNotNone(sources.may('text.hall', {}, other, other.sources[0]), 'another page may not have it')
        none = pq.parse(json.dumps({'o': 'page', 'i': 0, 'src': ['page:0'], **box}), 9, (480, 480))
        self.assertIsNotNone(sources.may('text.hall', {}, none, none.sources[0]), 'a page without a background')
        tile = pq.parse(json.dumps({'o': 'tile', 'i': 1, 'src': ['page:1'], **box}), 10, (480, 480))
        self.assertIsNotNone(sources.may('text.hall', {}, tile, tile.sources[0]), 'a tile may not have it')
        found = await sources.get('text.hall', {}, mine, source, mine.places[0])
        self.assertEqual(found.raw, b'camera')
        self.assertEqual(found.dim, 55, 'its 40 and 15 more in the dark look')

if __name__ == '__main__':
    unittest.main()
