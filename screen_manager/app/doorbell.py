"""A doorbell's ring on the screens (docs/DOORBELL.md): someone rings, and every screen that streams opens the doorbell's
camera live with its sound and a chime.

Home Assistant decides what a ring is, one to one: an `event` entity with the device class `doorbell` whose event type
becomes `ring` (the standard event type since April 2026, `DoorbellEventType.RING`), as its own trigger `doorbell.rang`
reads it (homeassistant/components/doorbell/trigger.py): a new state with that event type, but not a doorbell coming
back from unavailable. Its camera is the camera on the same device, which every video doorbell integration has.

The app sends the op "doorbell" to every screen whose hello says `doorbell` (module doorbell, a P4); a screen whose switch
Doorbell is off lets it pass. A screen reports how the ring ended there (esphome.screen_doorbell): the first that answers
it (a touch, or its close key) closes it on the others; when nobody answered, the ring is missed, and the top bar of those
screens shows it ("2 min ago") until someone opens it again there or answers a later ring.
"""
import secrets
import time

import tile_icons
from core import epoch

FEATURE = 'doorbell'
EVENT = 'esphome.screen_doorbell'
# What the screen reports (module_doorbell.cpp): answered and closed end a ring for every screen.
ANSWERS = ('answered', 'closed')
# A screen closes an unanswered ring a minute after it rang; a little later the app counts it as missed, also when no
# screen could report (one that may not send events to Home Assistant).
MISSED_AFTER = 65
# The top bar's item of a missed ring: the doorbell's icon and how long ago it rang, which the screen counts itself.
ICON = tile_icons.ICONS['doorbell'][0]


def rang(body):
    """Whether this state_changed event is a doorbell's ring, as Home Assistant's doorbell.rang trigger reads one."""
    if not isinstance(body, dict) or not str(body.get('entity_id', '')).startswith('event.'):
        return False
    new, old = body.get('new_state'), body.get('old_state')
    if not isinstance(new, dict) or new.get('state') in (None, 'unavailable', 'unknown'):
        return False
    attributes = new.get('attributes') or {}
    if attributes.get('device_class') != 'doorbell' or attributes.get('event_type') != 'ring':
        return False
    # The state of an event entity is the moment it fired: the same moment again is no new ring, and a doorbell that
    # comes back from unavailable did not ring.
    if isinstance(old, dict) and (old.get('state') == 'unavailable' or old.get('state') == new.get('state')):
        return False
    return True


def camera_of(entries, states):
    """The camera on the doorbell's device (`entries`: the registry entries of that device), one that is not disabled,
    and the first that Home Assistant has a state for; None without one."""
    cameras = [item.get('entity_id') for item in entries or () if isinstance(item, dict)
               and str(item.get('entity_id', '')).startswith('camera.') and not item.get('disabled_by')]
    usable = [entity for entity in cameras if (states.get(entity) or {}).get('state') not in (None, 'unavailable')]
    return (usable or cameras or [None])[0]


def name_of(event_entity, device_name, states):
    """What the screen calls the doorbell: its device's name as Home Assistant shows it, else the event's own name."""
    if device_name:
        return device_name
    friendly = ((states.get(event_entity) or {}).get('attributes') or {}).get('friendly_name')
    return friendly or event_entity


def moment(body):
    """When it rang, as unix time: the event entity's state is that moment (ISO 8601)."""
    return epoch(((body or {}).get('new_state') or {}).get('state')) or int(time.time())


class Doorbells:
    """The rings of this app's lifetime: the one going on, and the last one nobody answered (for the top bars)."""

    def __init__(self):
        self.rings = {}      # key -> {'camera', 'name', 'at', 'screens': inboxes it went to, 'answered': bool, 'since'}
        self.missed = None   # {'key', 'camera', 'name', 'at'} or None

    def start(self, camera, name, at, screens):
        key = secrets.token_hex(4)
        self.rings[key] = {'camera': camera, 'name': name, 'at': at, 'screens': list(screens), 'answered': False,
                           'since': time.monotonic()}
        # Rings older than a few minutes are history.
        for old in [k for k, ring in self.rings.items() if time.monotonic() - ring['since'] > 600]:
            del self.rings[old]
        return key

    def message(self, key, close=False):
        ring = self.rings.get(key)
        if close or ring is None:
            return {'v': 1, 'op': 'doorbell', 'k': key, 'c': 1}
        return {'v': 1, 'op': 'doorbell', 'e': ring['camera'], 'n': ring['name'], 'k': key, 'r': ring['at']}

    def answered(self, key):
        """A screen answered or closed ring `key`: the screens to close it on (the others it went to), once."""
        ring = self.rings.get(key)
        if ring is None or ring['answered']:
            return []
        ring['answered'] = True
        if self.missed and self.missed['camera'] == ring['camera']:
            self.missed = None
        return ring['screens']

    def unanswered(self, key):
        """MISSED_AFTER seconds after ring `key`: True when it became the missed ring (nobody answered it)."""
        ring = self.rings.get(key)
        if ring is None or ring['answered']:
            return False
        self.missed = {'key': key, 'camera': ring['camera'], 'name': ring['name'], 'at': ring['at']}
        return True

    def seen(self):
        """Someone opened the missed ring again on a screen: it leaves every top bar. True when there was one."""
        was = self.missed is not None
        self.missed = None
        return was

    def bar_item(self):
        """The top bar's item of the missed ring, for a screen whose hello says `doorbell`; None without one."""
        if not self.missed:
            return None
        return {'k': 'ago', 'i': ICON, 'e': self.missed['at'], 'b': 1}


def with_missed(items, item, limit):
    """A page's bar items with the missed ring's item first, at most `limit` (the screen refuses a longer bar)."""
    if not item:
        return items
    return [item, *items][:limit]
