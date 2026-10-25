"""A page's own background picture (app 0.4.109, firmware 0.65.0): one picture behind the whole page, from anywhere.

A page of the document may say

    "background": {"source": "<where>", "dim": 30, "refresh": 0}

`source` is where the picture comes from, in one of five shapes:

    https://example.com/sky.jpg          a public address on the internet (never one in the house: _allow_media_url)
    /local/backgrounds/kitchen.jpg       a file of Home Assistant's www folder
    media-source://media_source/local/x  a file of Home Assistant's media, as its media browser names it
    camera.garden, image.weather_map     a camera's or image entity's picture
    person.anna, media_player.tv         any other entity's own picture (entity_picture)

`dim` darkens it by that many percent so the cards stay readable (the dark look darkens it a little more), and
`refresh` fetches it again every that many seconds while its page is on the glass (0: once; a camera's default is a
minute). The screen never learns the address: it asks for "the background of page n" (picture source page:<n>), and
the app reads this from the page and paints the picture at the glass's size. A page without it has the plain page.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time

LOG = logging.getLogger('screen_manager')

MAX_SOURCE = 512
DIM_MAX = 80
DIM_DEFAULT = 30
# How often a picture may be fetched again while its page is on the glass, in seconds (0: once).
REFRESHES = (0, 60, 300, 900, 3600)
# A camera that names no pace of its own refreshes once a minute; anything else is fetched once.
CAMERA_REFRESH = 60
# A picture fetched once is kept this long before it is fetched again for another question: a page that comes back
# costs nothing, and a picture changed at its address shows within the hour.
KEEP_SECONDS = 3600
FAIL_SECONDS = 60
ENTITY = re.compile(r'[a-z0-9_]+\.[a-z0-9_]+')
MEDIA = re.compile(r'media-source://[^\s]{1,480}')
CAMERA_DOMAINS = ('camera', 'image')


def kind_of(source):
    """'url', 'www', 'media', 'entity' for a source this app takes, else None."""
    if not isinstance(source, str) or not source or len(source) > MAX_SOURCE or any(c.isspace() for c in source):
        return None
    if source.startswith(('https://', 'http://')):
        return 'url'
    if source.startswith('/local/'):
        path = source.split('?', 1)[0]
        return 'www' if '..' not in path and '//' not in source[1:] else None
    if MEDIA.fullmatch(source):
        return 'media'
    if ENTITY.fullmatch(source) and len(source) <= 120:
        return 'entity'
    return None


def validate(background):
    """A page's `background` as stored, or ValueError for a shape the editor does not make."""
    if not isinstance(background, dict) or set(background) - {'source', 'dim', 'refresh'} or 'source' not in background:
        raise ValueError('background')
    source = background['source']
    if kind_of(source) is None:
        raise ValueError('background')
    out = {'source': source}
    if 'dim' in background:
        dim = background['dim']
        if type(dim) is not int or not 0 <= dim <= DIM_MAX:
            raise ValueError('background')
        out['dim'] = dim
    if 'refresh' in background:
        if background['refresh'] not in REFRESHES or type(background['refresh']) is not int:
            raise ValueError('background')
        out['refresh'] = background['refresh']
    return out


def dim_of(background):
    return background.get('dim', DIM_DEFAULT) if isinstance(background, dict) else 0


def refresh_of(background):
    """Seconds between two fetches while the page is on the glass, 0 for once."""
    if not isinstance(background, dict):
        return 0
    if 'refresh' in background:
        return background['refresh']
    source = background.get('source', '')
    return CAMERA_REFRESH if kind_of(source) == 'entity' and source.split('.', 1)[0] in CAMERA_DOMAINS else 0


def mark(background):
    """What the screen is told of a page's background (page message `bg`): a short mark that changes with it and says
    nothing of where the picture is. '' for none."""
    if not isinstance(background, dict) or not background.get('source'):
        return ''
    text = f"{background['source']}|{dim_of(background)}|{refresh_of(background)}"
    return hashlib.sha1(text.encode()).hexdigest()[:12]


class Backdrops:
    """The pictures of the pages' backgrounds, fetched once for every screen and kept by source."""

    def __init__(self, ha, clock=time.monotonic):
        self.ha, self.clock = ha, clock
        self.kept = {}    # source -> (raw or None, digest, fetched_at)
        self.locks = {}

    async def picture(self, source, refresh=0):
        """(raw, digest) of the picture at `source`, or None when it cannot be had now. Fetched again once `refresh`
        seconds (or KEEP_SECONDS) passed since the last fetch, a failure after FAIL_SECONDS."""
        kind = kind_of(source)
        if kind is None:
            return None
        lock = self.locks.setdefault(source, asyncio.Lock())
        async with lock:
            entry = self.kept.get(source)
            if entry is not None:
                raw, digest, at = entry
                keep = (refresh or KEEP_SECONDS) if raw is not None else FAIL_SECONDS
                if self.clock() - at < keep:
                    return (raw, digest) if raw is not None else None
            try:
                raw = await self._fetch(kind, source)
                if not raw:
                    raise ValueError('empty picture')
                digest = hashlib.sha1(raw).hexdigest()
                self.kept[source] = (raw, digest, self.clock())
                return raw, digest
            except asyncio.CancelledError:
                raise
            except Exception as error:  # noqa: BLE001 - an address, a file or an entity that has no picture now
                # What went wrong and which kind, never the address (it may hold a key of the owner's).
                LOG.info('A page background (%s) could not be had (%s)', kind, type(error).__name__)
                old = self.kept.get(source)
                self.kept[source] = (None, '', self.clock())
                return (old[0], old[1]) if old and old[0] is not None else None

    async def _fetch(self, kind, source):
        ha = self.ha
        if kind == 'url':
            url, headers = await ha.picture_address(source, lambda path: False, 'background')
            return await ha.picture_bytes(url, headers, 'photo')
        if kind == 'www':
            url, headers, options = await ha.www_address(source)
            return await ha.picture_bytes(url, headers, 'photo', **options)
        if kind == 'media':
            resolved = await ha.request('media_source/resolve_media', media_content_id=source)
            address = (resolved or {}).get('url')
            if not isinstance(address, str) or not address:
                raise ValueError('no address')
            return await ha.media_file(address)
        domain = source.split('.', 1)[0]
        if domain in CAMERA_DOMAINS:
            return await ha.camera_image(source)
        if domain == 'media_player':
            return await ha.media_image(source)
        picture = ((ha.states.get(source) or {}).get('attributes') or {}).get('entity_picture') or ''
        if not picture:
            raise ValueError('no picture')
        return await ha.entity_picture(picture)


def preview_jpeg(raw, width, height, dim):
    """The editor's mockup of a page's background (app 0.4.114): the picture cut to the page's shape and darkened as the
    screen gets it (picture_paint, fit cover), as a JPEG the browser shows behind the mockup's cards."""
    import io
    import picture_paint
    import picture_question as pq
    question = pq.Question(pq.Owner('page', 0), (pq.Source('page', '0'),), (width, height),
                           (pq.Place(0, 0, width, height, fit='cover', dim=dim),))
    image = picture_paint.picture(question, [raw])
    out = io.BytesIO()
    image.save(out, 'JPEG', quality=85, optimize=True)
    return out.getvalue()
