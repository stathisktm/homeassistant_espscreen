"""A camera live on a P4 screen (screen_manager/app/live_feed.py, docs/CAMERA.md "Live on the P4 boards"): the room a
screen asks for, the size a frame goes out at, which JPEGs the P4's decoder takes as they are, and the stream itself
(a snapshot camera through a real aiohttp server, read the way the screen reads it). The WebRTC route needs aiortc and
a Home Assistant; it is proven on the bench (docs/CAMERA.md)."""
import asyncio
import contextlib
import importlib.util
import io
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
import live_feed  # noqa: E402
from PIL import Image  # noqa: E402


def jpeg(width, height, **options):
    out = io.BytesIO()
    Image.new('RGB', (width, height), (40, 120, 200)).save(out, 'JPEG', **options)
    return out.getvalue()


class Sizes(unittest.TestCase):
    def test_the_room_a_screen_asks_for(self):
        self.assertEqual(live_feed.parse_box('1280x728'), (1280, 728))
        self.assertEqual(live_feed.parse_box('800X1137'), (800, 1137))
        for bad in (None, '', '1280', 'x', '12x800', '1280x99999', 'axb', '1280x728x2'):
            self.assertIsNone(live_feed.parse_box(bad), bad)

    def test_a_frame_goes_out_at_its_own_size_when_it_fits(self):
        # A substream stays small: the screen's PPA scales it up, and Home Assistant's host does a fraction of the work.
        self.assertEqual(live_feed.size_for(512, 288, (1280, 728)), (512, 288))
        self.assertEqual(live_feed.size_for(1280, 720, (1280, 728)), (1280, 720))
        # A larger one is scaled down to the room, in whole JPEG blocks, its proportions kept.
        self.assertEqual(live_feed.size_for(1920, 1080, (1280, 715)), (1264, 704))
        self.assertEqual(live_feed.size_for(2560, 1440, (1280, 728)), (1280, 720))
        self.assertEqual(live_feed.size_for(1080, 1920, (1280, 728)), (400, 720))
        # Never beyond what the screen takes as it is.
        width, height = live_feed.size_for(3000, 2000, (4096, 4096))
        self.assertLessEqual(max(width, height), live_feed.MAX_SIDE)

    def test_the_jpegs_the_decoder_takes_as_they_are(self):
        self.assertEqual(live_feed.jpeg_size(jpeg(640, 360)), (640, 360))  # Pillow's default: baseline 4:2:0
        self.assertEqual(live_feed.jpeg_size(jpeg(640, 360, subsampling=0)), (640, 360))  # 4:4:4
        grey = io.BytesIO()
        Image.new('L', (320, 240), 90).save(grey, 'JPEG')
        self.assertEqual(live_feed.jpeg_size(grey.getvalue()), (320, 240))
        # Progressive, too large, sides whose product is not a multiple of eight, and anything that is no JPEG: remade.
        self.assertIsNone(live_feed.jpeg_size(jpeg(640, 360, progressive=True)))
        self.assertIsNone(live_feed.jpeg_size(jpeg(live_feed.MAX_SIDE + 16, 100)))
        self.assertIsNone(live_feed.jpeg_size(jpeg(9, 7)))
        png = io.BytesIO()
        Image.new('RGB', (64, 64)).save(png, 'PNG')
        self.assertIsNone(live_feed.jpeg_size(png.getvalue()))
        self.assertIsNone(live_feed.jpeg_size(b''))

    def test_what_the_decoder_does_not_take_is_remade_to_fit(self):
        for raw in (jpeg(640, 360, progressive=True), jpeg(3840, 2160)):
            made, ms = live_feed.remake(raw, (1280, 728))
            self.assertGreaterEqual(ms, 0)
            size = live_feed.jpeg_size(made)
            self.assertIsNotNone(size)
            self.assertLessEqual(size[0], 1280)
            self.assertLessEqual(size[1], 728)


class LiveTiles(unittest.TestCase):
    """A camera tile set to Live (pace 0): the pace each screen is sent, and the size its pictures go out at."""

    def message(self, options, features):
        message = {'v': 1, 'op': 'state', 'i': 0, 'o': {'display': 'live'}}
        live_feed.live_pace(message, {'entity': 'camera.door', 'options': options}, features)
        return message['o'].get('refresh')

    def test_live_goes_only_to_a_screen_that_streams(self):
        streams, older = frozenset({'live', 'plugins'}), frozenset({'plugins'})
        # Live is the default where the screen streams, and what the tile says.
        self.assertEqual(self.message({'display': 'live'}, streams), 0)
        self.assertEqual(self.message({'display': 'live', 'refresh': 0}, streams), 0)
        # A screen that does not stream refreshes a Live tile at the pace every camera tile has by default.
        self.assertEqual(self.message({'display': 'live', 'refresh': 0}, older), live_feed.DEFAULT_PACE)
        self.assertIsNone(self.message({'display': 'live'}, older))
        # A pace of its own stays, everywhere; the editor's preview (no hello) runs the newest firmware.
        self.assertIsNone(self.message({'display': 'live', 'refresh': 10}, streams))
        self.assertEqual(self.message({'display': 'live'}, None), 0)
        # Only a camera's live picture: an image entity, a camera tile without a picture, are left alone.
        message = {'o': {}}
        live_feed.live_pace(message, {'entity': 'image.door', 'options': {'display': 'live'}}, streams)
        live_feed.live_pace(message, {'entity': 'camera.door', 'options': {}}, streams)
        self.assertEqual(message, {'o': {}})

    def test_a_tile_that_fills_its_card_gets_as_little_as_covers_it(self):
        self.assertEqual(live_feed.size_to_cover(1920, 1080, (434, 244)), (434, 246))
        self.assertEqual(live_feed.size_to_cover(1920, 1080, (434, 434)), (772, 434))
        # Smaller than the card: as it is, the screen scales it up.
        self.assertEqual(live_feed.size_to_cover(512, 288, (868, 488)), (512, 288))
        self.assertEqual(live_feed.size_to_cover(511, 287, (868, 488)), (510, 286))

    def test_a_tile_link_says_whether_its_picture_is_whole(self):
        feed = live_feed.LiveFeed(None, None, lambda e: True)
        token = feed.link('camera.door', (434, 244), cover=True)
        self.assertTrue(feed.links[token].cover)
        self.assertFalse(feed.links[feed.link('camera.door', (1280, 715))].cover)


class Held(unittest.TestCase):
    def test_a_full_view_keeps_the_cameras_of_its_screens_tiles_running(self):
        async def main():
            feed = live_feed.LiveFeed(None, None, lambda e: True)
            feed.link('camera.yard', (434, 244), cover=True, screen='a', tile=True)
            feed.link('camera.door', (240, 135), cover=True, screen='a', tile=True)
            feed.link('camera.shed', (434, 244), cover=True, screen='b', tile=True)
            for entity in ('camera.yard', 'camera.door', 'camera.shed'):
                feed.source(entity).task = asyncio.create_task(asyncio.sleep(5))
            # The full view of camera.door on screen a: its own camera runs anyway, and screen b's tiles are not its own.
            held = feed.hold(feed.links[feed.link('camera.door', (1280, 715), screen='a')])
            self.assertEqual([source.entity for source in held], ['camera.yard'])
            self.assertEqual(held[0].viewers, 1)
            # A tile holds nothing; a tile that streamed long ago is not held either.
            self.assertEqual(feed.hold(feed.links[feed.link('camera.door', (240, 135), screen='a', tile=True)]), [])
            for link in feed.links.values():
                link.used -= live_feed.LINGER_SECONDS
            self.assertEqual(feed.hold(feed.links[feed.link('camera.door', (1280, 715), screen='a')]), [])
            feed.let_go(held)
            self.assertEqual(held[0].viewers, 0)
            self.assertTrue(held[0].watched())  # and then the usual linger
            for source in feed.sources.values():
                source.task.cancel()

        asyncio.run(main())


class Stream(unittest.TestCase):
    """A snapshot camera through LiveFeed on a real socket, read like the screen reads it: HTTP/1.0, then parts."""

    def run_stream(self, entity='camera.door', parts=3, token=None, streams_open=0, rtc=None, box=(1280, 728), exact=False):
        """`rtc`: the camera has a stream, and this stands in for its WebRTC session (Source.rtc)."""
        from aiohttp import web
        picture = jpeg(512, 288)
        asked = []
        self.heads = []

        async def fetch(name):
            asked.append(name)
            await asyncio.sleep(0.01)
            return picture

        async def main():
            live = live_feed.LiveFeed(fetch, None, lambda name: rtc is not None)
            if rtc is not None:
                source = live.source(entity)
                source.rtc = lambda kinds, take, keep: rtc(source, take)

            async def stream(request):
                return await live.serve(request, request.match_info['token'])

            app = web.Application()
            app.router.add_get(r'/camera/{token:[A-Za-z0-9_-]{16,64}}.mjpeg', stream)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '127.0.0.1', 0)
            await site.start()
            port = site._server.sockets[0].getsockname()[1]
            link = token or live.link(entity, box, exact=exact)
            for _ in range(streams_open):
                live.links[live.link(entity, (1280, 728))].streaming = 1
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(f'GET /camera/{link}.mjpeg HTTP/1.0\r\nHost: test\r\n\r\n'.encode())
            await writer.drain()
            data, got = b'', []
            while len(got) < parts:
                chunk = await asyncio.wait_for(reader.read(65536), 5)
                if not chunk:
                    break
                data += chunk
                while True:
                    found = re.search(rb'Content-Length: (\d+)\r\n\r\n', data)
                    if not found or len(data) < found.end() + int(found.group(1)):
                        break
                    self.heads.append(data[:found.end()])
                    got.append(data[found.end():found.end() + int(found.group(1))])
                    data = data[found.end() + int(found.group(1)):]
            writer.close()
            await asyncio.sleep(0.1)
            await runner.cleanup()
            return data, got

        return asyncio.run(main()), picture, asked

    def test_a_snapshot_camera_streams_its_jpegs_untouched(self):
        (head, got), picture, asked = self.run_stream()
        self.assertEqual(len(got), 3)
        # The P4 takes the camera's own JPEG as it is: this app spent nothing on it.
        self.assertTrue(all(part == picture for part in got))
        self.assertTrue(set(asked) == {'camera.door'})

    def test_a_snapshot_camera_is_live_from_its_first_picture(self):
        self.run_stream()
        # No part is marked as a still: the screen shows no loader (live_view.h, "Until it is live").
        self.assertTrue(self.heads and not any(b'X-Picture' in head for head in self.heads), self.heads)

    def test_the_stills_before_webrtc_are_marked_and_its_frames_are_not(self):
        try:
            import av
        except ImportError:
            self.skipTest('PyAV is not installed here (the add-on image has it)')

        async def rtc(source, take):
            await asyncio.sleep(0.45)  # the camera's next key frame
            for _ in range(3):
                await take('video', av.VideoFrame.from_image(Image.new('RGB', (320, 180), (200, 80, 30))))
                await asyncio.sleep(0.05)
            await asyncio.sleep(5)
            return True
        before = live_feed.STILL_SECONDS
        live_feed.STILL_SECONDS = 0.1
        try:
            (_, got), _, asked = self.run_stream(parts=6, rtc=rtc)
        finally:
            live_feed.STILL_SECONDS = before
        marks = [b'X-Picture: still\r\n' in head for head in self.heads]
        # The stills first, each marked; then WebRTC's frames, none marked, and no still after them.
        self.assertTrue(marks[0], self.heads)
        self.assertFalse(marks[-1], self.heads)
        self.assertEqual(marks, sorted(marks, reverse=True), marks)
        # The mark is a line of the part's own head, before its length, as picture_fetch::parse_head reads it.
        self.assertRegex(self.heads[0], rb'--frame\r\nContent-Type: image/jpeg\r\nX-Picture: still\r\nContent-Length: \d+')

    def test_an_unknown_link_and_too_many_streams_are_refused(self):
        (head, got), _, asked = self.run_stream(token='x' * 24, parts=1)
        self.assertEqual(got, [])
        self.assertIn(b'404', head)
        (head, got), _, asked = self.run_stream(parts=1, streams_open=live_feed.MAX_STREAMS)
        self.assertEqual(got, [])
        self.assertIn(b'503', head)
        self.assertEqual(asked, [])


class WaitForWebRTC(unittest.TestCase):
    """A camera with a stream until WebRTC's first frame: its stills keep the screen's stream going (the screen closes one
    silent for 6 s, live_view::QUIET_MS), and an offer Home Assistant refuses gives way to the snapshots at once."""

    def test_the_still_comes_again_until_the_first_frame(self):
        async def main():
            stills = []

            async def fetch(entity):
                stills.append(entity)
                return jpeg(64, 36)

            source = live_feed.Source(live_feed.LiveFeed(fetch, None, lambda e: True), 'camera.door', True)
            source.viewers = 1

            async def rtc(kinds, take, keep):
                await asyncio.sleep(0.35)  # a camera's key frame that takes its time
                await take('video', object())
                return True
            source.rtc = rtc
            before = live_feed.STILL_SECONDS
            live_feed.STILL_SECONDS = 0.1
            try:
                self.assertTrue(await source.webrtc())
                came = len(stills)
                await asyncio.sleep(0.3)
            finally:
                live_feed.STILL_SECONDS = before
            # A still every STILL_SECONDS while WebRTC waited, the first at once; none once its frame came.
            self.assertGreaterEqual(came, 3)
            self.assertEqual(len(stills), came)
            self.assertIsNotNone(source.frame.video)

        asyncio.run(main())

    @unittest.skipUnless(importlib.util.find_spec('aiortc'), 'needs aiortc (the app has it)')
    def test_a_refused_offer_gives_way_at_once(self):
        class Message:
            def json(self):
                return {'id': 1, 'type': 'result', 'success': False,
                        'error': {'message': 'Camera does not support WebRTC'}}

        sent = []

        class Socket:
            async def send_json(self, data):
                sent.append(asyncio.get_running_loop().time())

            def __aiter__(self):
                async def messages():
                    yield Message()
                    await asyncio.sleep(60)
                return messages()

        @contextlib.asynccontextmanager
        async def websocket():
            yield Socket()

        async def main():
            source = live_feed.Source(live_feed.LiveFeed(None, websocket, lambda e: True), 'camera.door', True)
            started = asyncio.get_running_loop().time()
            with self.assertLogs('live_feed', 'INFO') as logged:
                gave = await source.rtc(('video',), None, lambda: True)
            done = asyncio.get_running_loop().time()
            return gave, sent[0] - started, done - sent[0], logged.output

        gave, offering, refused, output = asyncio.run(main())
        self.assertFalse(gave)
        # The offer goes out at once (no STUN server to wait for, about five seconds before), and the refusal ends the
        # session at once, not after WEBRTC_FIRST_SECONDS.
        self.assertLess(offering, 1.5)
        self.assertLess(refused, 1.5)
        self.assertTrue(any('Camera does not support WebRTC' in line for line in output), output)


class Encoder(unittest.TestCase):
    def test_frames_become_jpegs_the_decoder_takes(self):
        try:
            import av
        except ImportError:
            self.skipTest('PyAV is not installed here (the add-on image has it)')
        frame = av.VideoFrame.from_image(Image.new('RGB', (1920, 1080), (200, 80, 30)))
        encoder = live_feed.Encoder(*live_feed.size_for(1920, 1080, (1280, 728)))
        made, ms = encoder.encode(frame)
        self.assertEqual(live_feed.jpeg_size(made), (1280, 720))
        self.assertGreaterEqual(ms, 0)


class SoftLive(unittest.TestCase):
    """An ESP32-S3 streams its camera full screen too (app 0.4.123, firmware 0.74.0, soft_live.cpp): it scales nothing,
    so each picture comes at its room's size exactly (`exact`), a baseline JPEG its ROM's TJpgDec reads."""

    def test_a_frame_is_made_the_room_s_size(self):
        # Whole JPEG blocks of 16 (firmware 0.76.0's decoder), the nearest within the room.
        self.assertEqual(live_feed.size_exact(512, 288, (480, 418)), (480, 272))      # smaller
        self.assertEqual(live_feed.size_exact(1920, 1080, (480, 418)), (480, 272))    # larger
        self.assertEqual(live_feed.size_exact(320, 240, (480, 418)), (480, 352))      # scaled up, as the S3 cannot
        self.assertEqual(live_feed.size_exact(480, 270, (480, 404)), (480, 272))
        self.assertEqual(live_feed.size_exact(1080, 1920, (480, 404)), (224, 400))   # standing, within the room
        self.assertIs(live_feed.sizing_of(exact=True), live_feed.size_exact)
        self.assertIs(live_feed.sizing_of(cover=True), live_feed.size_to_cover)
        self.assertIs(live_feed.sizing_of(), live_feed.size_for)

    def test_the_stream_of_an_s3_comes_at_its_room_s_size(self):
        (head, got), picture, asked = Stream().run_stream(box=(480, 418), exact=True)
        self.assertEqual(len(got), 3)
        for part in got:
            image = Image.open(io.BytesIO(part))
            self.assertEqual((image.format, image.size), ('JPEG', (480, 272)))
            self.assertFalse(image.info.get('progressive'), 'baseline, as TJpgDec reads it')
        # A P4's stream of the same camera keeps the camera's own JPEG.
        (head, got), picture, asked = Stream().run_stream()
        self.assertTrue(all(part == picture for part in got))

    def test_a_small_camera_s_frames_are_scaled_up_for_it(self):
        try:
            import av
        except ImportError:
            self.skipTest('PyAV is not installed here (the add-on image has it)')
        # A substream of 320 x 180 for a room of 480 x 418: the app scales it up, as the S3 scales nothing.
        frame = av.VideoFrame.from_image(Image.new('RGB', (320, 180), (200, 80, 30)))
        made, ms = live_feed.Encoder(*live_feed.size_exact(320, 180, (480, 418))).encode(frame)
        image = Image.open(io.BytesIO(made))
        self.assertEqual(image.size, (480, 272))
        self.assertFalse(image.info.get('progressive'))

    def test_its_pictures_are_made_at_the_best_quality(self):
        """App 0.4.130: an S3's pictures are small and it keeps up with the camera, so they go out at the best quality,
        where 6 to 7 KB at the P4's QSCALE showed blocks in the details."""
        try:
            import av
        except ImportError:
            self.skipTest('PyAV is not installed here (the add-on image has it)')
        import random
        rng = random.Random(7)
        detail = Image.new('RGB', (480, 272))
        detail.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(480 * 272)])
        frame = av.VideoFrame.from_image(detail.resize((1920, 1080)))
        source = live_feed.Source(None, 'camera.door', None)
        exact = asyncio.run(source.make(live_feed.Frame(1, video=frame), (480, 404), exact=True))
        plain = asyncio.run(source.make(live_feed.Frame(1, video=frame), (480, 404)))
        self.assertGreater(len(exact), len(plain) * 1.3)
        self.assertEqual(sorted(q for _, q in source.encoders), [live_feed.QSCALE_EXACT, live_feed.QSCALE])

    def test_the_question_says_it_and_the_link_keeps_it(self):
        import json
        import picture_question as pq
        box = {'box': [480, 480], 'at': [[0, 0, 480, 480, 0, 0]], 'fit': ['shrink'], 'fmt': ['bmp16', 'bmp24']}
        asked = lambda **more: pq.parse(json.dumps({'o': 'view', 'src': ['camera:camera.door'], **box, **more}), 3, (480, 480))
        self.assertTrue(asked(live=[480, 418], exact=1).exact)
        self.assertFalse(asked(live=[480, 418]).exact, 'a P4 scales its pictures itself')
        self.assertFalse(asked(exact=1).exact, 'no stream, nothing exact')
        live = live_feed.LiveFeed(None, None, lambda name: False)
        self.assertTrue(live.links[live.link('camera.door', (480, 418), exact=True)].exact)
        self.assertFalse(live.links[live.link('camera.door', (1280, 728))].exact)

    def test_the_s3_builds_it_and_only_its_view_streams(self):
        component = ROOT / 'components/smart_display'
        init = (component / '__init__.py').read_text()
        self.assertIn('return get_esp32_variant() == VARIANT_ESP32S3', init)
        self.assertRegex(init, r'elif _esp32_s3\(\):\n\s+await _s3\(config\)')
        # Straight to the panel on an st7701s (firmware 0.79.0): its handle picked up as ESP-IDF makes it.
        self.assertIn('cg.add_build_flag("-Wl,--wrap=esp_lcd_new_rgb_panel")', init)
        # And a QSPI panel (firmware 0.85.0, the JC3248W535): the picture turned as it decodes, sent through the display.
        self.assertIn('cg.add_define("USE_SOFT_LIVE_SPI")', init)
        soft = (component / 'soft_live.cpp').read_text()
        # Turned by the copier a strip at a time (firmware 0.85.1): esp_new_jpeg's own turn needs memory inside the chip,
        # and with it every picture failed on the JC3248W535.
        self.assertNotIn('config.rotate', soft)
        self.assertIn('turn_strip(s, f, s.strip, top, rows);', soft)
        self.assertIn('case 1: px = nw - y - f.lh; py = x; break;', soft)
        self.assertIn('cg.add_define("USE_SOFT_LIVE")', init)
        soft = (component / 'soft_live.cpp').read_text()
        self.assertIn('#if defined(USE_SOFT_LIVE) && defined(SCREEN_PICTURES)', soft)
        self.assertIn('jd_prepare(&jd, read_jpeg', soft)
        # Espressif's decoder first (firmware 0.76.0), straight into a 16-byte aligned frame, TJpgDec where it is not.
        self.assertIn('add_idf_component(name="espressif/esp_new_jpeg", ref="1.0.2")', init)
        self.assertIn('#if __has_include("esp_jpeg_dec.h")', soft)
        # The panel's frame buffer holds LVGL's pixels byte-swapped (LV_COLOR_16_SWAP): a picture for it is decoded so.
        self.assertIn('config.output_type = f.swap ? JPEG_PIXEL_FORMAT_RGB565_BE : JPEG_PIXEL_FORMAT_RGB565_LE;', soft)
        self.assertIn('s->frames[0].swap = s->frames[1].swap = s->direct;', soft)
        self.assertIn('heap_caps_aligned_alloc(16, s->frame_bytes, MALLOC_CAP_SPIRAM)', soft)
        # The glass sets the pace (firmware 0.77.0): LVGL's own timer shows each picture, and one that comes while the
        # last still waits is read past, not decoded for nothing.
        self.assertIn('if (!pacer && !s->direct) pacer = lv_timer_create(pace, 5, nullptr);', soft)
        self.assertIn('const bool waits = s.ready >= 0, skip = waits && !still;', soft)
        self.assertIn('if (!skip && s.ready == target) s.ready = -1;', soft)
        # Two tasks (firmware 0.81.0): one reads the next picture while the other decodes the last.
        self.assertIn('xTaskCreatePinnedToCore(decoder_main, "soft_decode", 6144, s, 2, &s->decoder, 0)', soft)
        # The reader's and the copier's stacks in PSRAM (firmware 0.83.0): the memory inside the chip ran short.
        self.assertIn('xTaskCreatePinnedToCoreWithCaps(task_main, "soft_live", 8192, s, 3, nullptr, 0, MALLOC_CAP_SPIRAM)', soft)
        self.assertNotIn('MALLOC_CAP_INTERNAL', soft)
        self.assertIn('while (i == s.pending || i == s.decoding) ++i;', soft)
        # And a copier on the other core, straight to the panel (firmware 0.82.0), while the next picture is decoded.
        self.assertIn('xTaskCreatePinnedToCoreWithCaps(putter_main, "soft_put", 4096, s, copier_priority, &s->putter, 1,', soft)
        # Over QSPI the glass is held a strip at a time, and the copier shares the main loop's priority (firmware 0.85.2).
        self.assertIn('if (spi_display) copier_priority = 1;', soft)
        self.assertIn('LV_EVENT_RENDER_READY', soft)
        # Straight to the panel: one writer on the glass, LVGL out of the picture's spot, nothing written after close.
        self.assertIn('extern "C" esp_err_t __wrap_esp_lcd_new_rgb_panel(', soft)
        self.assertIn('lv_display_add_event_cb(display, keep_out, LV_EVENT_RENDER_START, nullptr);', soft)
        self.assertIn('xSemaphoreTakeRecursive(glass, portMAX_DELAY);\n  if (!s.stopping) {', soft)
        self.assertIn('if (streams[handle]->direct) disarm(*streams[handle]);', soft)
        # A page's picture fetched ahead only where it fits beside what the store holds: one that does not was let go
        # and fetched again every half second.
        tiles = (component / 'runtime_tiles.h').read_text()
        self.assertIn('pictures.size() + bytes <= pictures.budget / 4 * 3', tiles.split('inline void backdrop_wants() {', 1)[1])
        self.assertIn('if (look.tile || !available()', soft, 'a live tile keeps its stills')
        header = (component / 'live_view.h').read_text()
        self.assertIn('inline bool tiles_stream() { return false; }', header)
        tiles = (component / 'runtime_tiles.h').read_text()
        self.assertIn('return live_view::tiles_stream() && tiles_seen()', tiles)
        self.assertIn('q.exact = true;', tiles)
        self.assertIn('if (q.exact) out += ",\\"exact\\":1";', (component / 'picture_question.h').read_text())


class P4Build(unittest.TestCase):
    """The P4 boards build with the larger TCP window and the live view, keyed on the chip in the component."""

    def test_the_window_and_the_live_view_are_the_p4s_alone(self):
        source = (ROOT / 'components/smart_display/__init__.py').read_text()
        self.assertIn('"CONFIG_LWIP_TCP_WND_DEFAULT": 65534', source)
        self.assertRegex(source, r'if _esp32_p4\(\):\n\s+await _p4\(config\)')
        self.assertIn('return get_esp32_variant() == VARIANT_ESP32P4', source)
        self.assertIn('-Wl,--wrap=esp_lcd_new_panel_dpi', source)
        self.assertIn('-Wl,--wrap=ppa_register_client', source)  # every PPA burst shorter: live_view.cpp
        self.assertIn('-Wl,--wrap=ppa_do_scale_rotate_mirror', source)  # a turned copy in pieces: ppa_guard.cpp
        # A screen's own sdkconfig_options keep the last word.
        self.assertIn('if name not in own', source)


if __name__ == '__main__':
    unittest.main()
