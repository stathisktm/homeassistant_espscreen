"""A doorbell's ring on the screens (docs/DOORBELL.md): the app sees a doorbell's event entity ring in Home Assistant,
opens its camera on every screen that streams, closes it on the others when one answers, and shows a missed ring in
their top bars."""
import asyncio
import importlib.util
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'screen_manager/app'))
import doorbell  # noqa: E402

HAS_AIOHTTP = importlib.util.find_spec('aiohttp') is not None
if HAS_AIOHTTP:
    from server import Manager


def ring(entity='event.front_door_doorbell', when='2026-10-22T10:07:52.120+00:00', before='2026-10-21T18:00:00.000+00:00',
         device_class='doorbell', event_type='ring'):
    return {'entity_id': entity,
            'old_state': {'state': before} if before is not None else None,
            'new_state': {'state': when, 'attributes': {'device_class': device_class, 'event_type': event_type}}}


class WhatARingIs(unittest.TestCase):
    # As Home Assistant's own trigger doorbell.rang reads one (homeassistant/components/doorbell/trigger.py).
    def test_a_doorbell_that_rings(self):
        self.assertTrue(doorbell.rang(ring()))
        self.assertTrue(doorbell.rang(ring(before='unknown')), 'the first ring after Home Assistant starts counts')
        self.assertTrue(doorbell.rang(ring(before=None)))

    def test_not_a_ring(self):
        self.assertFalse(doorbell.rang(ring(event_type='double_press')), 'only the standard event type ring')
        self.assertFalse(doorbell.rang(ring(device_class='button')))
        self.assertFalse(doorbell.rang(ring(entity='binary_sensor.front_door')))
        self.assertFalse(doorbell.rang(ring(before='unavailable')), 'coming back from unavailable is no ring')
        self.assertFalse(doorbell.rang(ring(when='unavailable')))
        same = ring()
        same['old_state']['state'] = same['new_state']['state']
        self.assertFalse(doorbell.rang(same), 'an attribute change of the same moment is no new ring')
        self.assertFalse(doorbell.rang(None))

    def test_when_it_rang(self):
        self.assertEqual(doorbell.moment(ring()), 1792663672)


class ItsCamera(unittest.TestCase):
    def test_the_camera_on_the_doorbells_device(self):
        entries = [{'entity_id': 'event.front_door_doorbell'}, {'entity_id': 'camera.front_door_snapshots', 'disabled_by': 'user'},
                   {'entity_id': 'camera.front_door_fluent'}, {'entity_id': 'camera.front_door_clear'}]
        states = {'camera.front_door_fluent': {'state': 'unavailable'}, 'camera.front_door_clear': {'state': 'idle'}}
        self.assertEqual(doorbell.camera_of(entries, states), 'camera.front_door_clear', 'not disabled, and one that works')
        self.assertEqual(doorbell.camera_of(entries, {}), 'camera.front_door_fluent')
        self.assertIsNone(doorbell.camera_of([{'entity_id': 'event.x'}], {}))

    def test_its_name(self):
        self.assertEqual(doorbell.name_of('event.x', 'Front door', {}), 'Front door')
        self.assertEqual(doorbell.name_of('event.x', None, {'event.x': {'attributes': {'friendly_name': 'Doorbell'}}}), 'Doorbell')


class TheRings(unittest.TestCase):
    def test_answered_on_one_screen_closes_it_on_the_others_once(self):
        rings = doorbell.Doorbells()
        key = rings.start('camera.front_door', 'Front door', 1792663672, ['a', 'b'])
        self.assertEqual(rings.message(key), {'v': 1, 'op': 'doorbell', 'e': 'camera.front_door', 'n': 'Front door', 'k': key,
                                              'r': 1792663672})
        self.assertEqual(rings.answered(key), ['a', 'b'])
        self.assertEqual(rings.answered(key), [], 'the second screen that answers closes nothing')
        self.assertFalse(rings.unanswered(key), 'an answered ring is not missed')
        self.assertEqual(rings.message(key, close=True), {'v': 1, 'op': 'doorbell', 'k': key, 'c': 1})

    def test_missed_until_seen_or_a_later_ring_is_answered(self):
        rings = doorbell.Doorbells()
        first = rings.start('camera.front_door', 'Front door', 100, ['a'])
        self.assertIsNone(rings.bar_item())
        self.assertTrue(rings.unanswered(first))
        self.assertEqual(rings.bar_item(), {'k': 'ago', 'i': 'F12E6', 'e': 100, 'b': 1})
        later = rings.start('camera.front_door', 'Front door', 200, ['a'])
        rings.answered(later)
        self.assertIsNone(rings.bar_item(), 'answering the next ring of that door clears it')
        rings.unanswered(rings.start('camera.front_door', 'Front door', 300, ['a']))
        self.assertTrue(rings.seen())
        self.assertFalse(rings.seen())
        self.assertIsNone(rings.bar_item())

    def test_the_item_goes_first_within_the_bar_limit(self):
        item = {'k': 'ago', 'i': 'F12E6', 'e': 1, 'b': 1}
        self.assertEqual(doorbell.with_missed([{'k': 'clock'}], item, 6), [item, {'k': 'clock'}])
        self.assertEqual(len(doorbell.with_missed([{'k': 'clock'}] * 6, item, 6)), 6)
        self.assertEqual(doorbell.with_missed([{'k': 'clock'}], None, 6), [{'k': 'clock'}])


class TheFirmwareReadsTheSame(unittest.TestCase):
    def test_the_op_the_report_and_the_item(self):
        receiver = (ROOT / 'components/smart_display/page_receiver.cpp').read_text()
        self.assertIn('op == "doorbell"', receiver)
        for field in ('"k"', '"c"', '"e"', '"n"', '"r"'):
            self.assertIn(f'root[{field}]', receiver)
        self.assertIn('value["b"]', receiver)
        core = (ROOT / 'packages/core.yaml').read_text()
        self.assertIn(f'event: {doorbell.EVENT}', core)
        self.assertIn(f'features.add("{doorbell.FEATURE}")', core)
        # Standby and Back to Home wait while a ring shows (a ring after two quiet minutes closed at once without it).
        self.assertEqual(core.count('if (runtime_tiles::doorbell_holds()) return false;'), 2)
        module = (ROOT / 'components/smart_display/module_doorbell.cpp').read_text()
        for action in (*doorbell.ANSWERS, 'missed', 'seen'):
            self.assertIn(f'say("{action}")', module)
        # The app counts a ring as missed only after the screen closed it.
        untouched = int(re.search(r'UNTOUCHED_MS = (\d+)', module)[1])
        self.assertGreater(doorbell.MISSED_AFTER * 1000, untouched)


class Screen:
    def __init__(self, inbox, node, features=('doorbell',), online=True):
        self.record = {'id': inbox, 'node': node, 'name': node, 'online': online}
        self.sender = type('Sender', (), {'features': set(features)})()


@unittest.skipUnless(HAS_AIOHTTP, 'aiohttp')
class TheManager(unittest.TestCase):
    def manager(self, screens):
        manager = Manager.__new__(Manager)
        manager.ha = type('HA', (), {})()
        manager.ha.states = {'camera.front_door': {'state': 'idle'}}
        manager.ha.changed = asyncio.Event()
        manager.page_senders = {s.record['id']: s.sender for s in screens}
        manager.screens = lambda: [s.record for s in screens]
        manager.transport = lambda inbox, screen=None: 'v2'
        manager.page_scope = lambda inbox: {}
        manager.device_entries = lambda entity: [{'entity_id': entity}, {'entity_id': 'camera.front_door'}]
        manager.device_name_of = lambda entity: 'Front door'
        manager.alert_cameras = {}
        manager.doorbells = doorbell.Doorbells()
        manager.sent_messages = []

        async def send_auxiliary(inbox, message, action, request):
            manager.sent_messages.append((inbox, message))
            return True
        manager.send_auxiliary = send_auxiliary
        return manager

    def test_a_ring_goes_to_the_screens_that_draw_doorbells(self):
        screens = [Screen('a', 'hall'), Screen('b', 'kitchen'), Screen('c', 'cyd', features=()), Screen('d', 'off', online=False)]
        manager = self.manager(screens)
        manager.doorbell_unanswered = lambda key: asyncio.sleep(0)
        asyncio.run(manager.doorbell_ring(ring()))
        self.assertEqual([inbox for inbox, _ in manager.sent_messages], ['a', 'b'])
        message = manager.sent_messages[0][1]
        self.assertEqual((message['op'], message['e'], message['n'], message['r']), ('doorbell', 'camera.front_door', 'Front door', 1792663672))
        self.assertIn('camera.front_door', manager.alert_cameras, 'the screens may open its camera')

        # The hall answers: the kitchen closes it.
        manager.sent_messages.clear()
        asyncio.run(manager.doorbell_report({'action': 'answered', 'key': message['k'], 'screen': 'hall'}))
        self.assertEqual(manager.sent_messages, [('b', {'v': 1, 'op': 'doorbell', 'k': message['k'], 'c': 1})])

    def test_a_doorbell_without_a_camera_opens_nothing(self):
        manager = self.manager([Screen('a', 'hall')])
        manager.device_entries = lambda entity: [{'entity_id': entity}]
        asyncio.run(manager.doorbell_ring(ring()))
        self.assertEqual(manager.sent_messages, [])

    def test_a_missed_ring_is_seen_once(self):
        manager = self.manager([Screen('a', 'hall')])
        key = manager.doorbells.start('camera.front_door', 'Front door', 1, ['a'])
        manager.doorbells.unanswered(key)
        asyncio.run(manager.doorbell_report({'action': 'seen', 'key': key, 'screen': 'hall'}))
        self.assertIsNone(manager.doorbells.bar_item())
        self.assertTrue(manager.ha.changed.is_set(), 'the top bars are sent again')


if __name__ == '__main__':
    unittest.main()
