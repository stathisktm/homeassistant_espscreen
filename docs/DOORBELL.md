# The doorbell

Someone rings, and every screen that can stream (the ESP32-P4 screens) wakes up, plays a chime and opens the doorbell's
camera full screen, live, with its sound on. Nothing to set up: a doorbell that Home Assistant knows as a doorbell is
enough.

## What you need

- A video doorbell in Home Assistant with an **event entity of the doorbell class** (`event.front_door_doorbell`, for
  example) and a **camera** on the same device. Home Assistant made `ring` the standard event type of a doorbell in April 2026:
  every doorbell integration fires it when the button is pressed, and Home Assistant's own "Doorbell rang" trigger reads it.
- A screen whose firmware has the doorbell: the ESP32-P4 screens (8 MB of flash or more and a live picture,
  docs/MODULES.md). Their hello says `doorbell`.
- The screen allowed to perform Home Assistant actions (docs/EASY_SETUP.md, chapter 3), so it can say when someone
  answered.

## What happens

1. ESP Screens sees the doorbell's event entity change to a new moment with the event type `ring`. A doorbell that
   comes back from unavailable did not ring, and another event type (a long press) is not a ring.
2. It finds the camera on the doorbell's device (a camera that is not disabled, one that works first) and sends every
   screen that draws a doorbell the op `doorbell` with that camera, the doorbell device's name and the moment it rang.
3. The screen wakes from standby or Sleep, closes the settings page, a card or another camera, plays the chime on its
   speaker and opens the camera full screen as a doorbell: the doorbell's disc where the back key stands, its name and
   how long ago it rang beside it, the close key at the right, and the picture beside the keys (glass lying down) or
   above them (square or standing glass). The picture is live as soon as the stream starts; until then its still and a
   spinner in the top bar.
4. The first touch on the view **answers** the ring: ESP Screens closes it on the other screens. The close key answers
   it too.
5. Nobody touches it: it closes a minute after the last ring. The ring is then **missed**, and every doorbell screen
   shows it at the left of its top bar (the doorbell's icon and "2 min ago") until someone taps that item, which opens
   the doorbell's camera again, or answers a later ring.

The view stays lit while it is open: standby and Back to Home wait for it, five minutes after the last touch or ring at
most (Back to Home counts from the last touch, so without this a ring after two quiet minutes closed at once). A second ring
while it is open plays the chime again and starts the minute over.

## Turning it off on one screen

Every P4 screen has a switch **Doorbell** under Extras: on the screen's settings page, in the editor's Screen settings
and as `switch.<screen>_doorbell` in Home Assistant. Off, the screen lets a ring pass. An automation can switch it off
at night for a bedroom's screen.

## The sound

The doorbell's sound plays as the camera full screen's sound does (docs/CAMERA.md), on at every ring; the key **Sound**
mutes it for this ring. The chime is two notes made by the screen itself and plays on the speaker for announcements, at
the screen's volume (Extras, Volume).

## Other screens

A screen without the doorbell (a CYD, an ESP32-S3) gets nothing from a ring by itself. An automation can show it the
doorbell's picture in an alert (docs/CAMERA.md, "A doorbell"):

```yaml
triggers:
  - trigger: doorbell.rang
    target:
      entity_id: event.front_door_doorbell
actions:
  - event: esp_screens_show_alert
    event_data:
      title: Someone is at the door
      icon: doorbell
      camera: camera.front_door
      timeout: 60
      screen: hallway
```

## How it fits together

| Part | Where |
|---|---|
| What a ring is, which camera, the screens, answered and missed | `screen_manager/app/doorbell.py`, `Manager.doorbell_*` in `server.py` |
| The missed ring in the top bar | `page_service.sync_pages` (`with_missed`), the item's `b` |
| The op `doorbell` | `page_receiver.cpp` |
| The view, the chime, the times | `module_doorbell.cpp` (module doorbell), hooked into the camera full view of `runtime_tiles.h` |
| The switch Doorbell | `packages/features/audio-player.yaml`, `boards.yaml` `settings` |
| The report of how a ring ended | `doorbell_report` in `packages/core.yaml`, the event `esphome.screen_doorbell` (`action`: answered, closed, missed or seen; `key`; `screen`) |

The view never lays anything of LVGL over its picture: a live picture is written to the glass past LVGL
(docs/PICTURES.md), so the keys stand beside it.

## Not yet

- **Open the door.** A key that opens a lock or presses a button of the doorbell's device, or one picked for it.
- **Talk.** The screen's microphone to the doorbell's speaker, through Home Assistant's own go2rtc and the doorbell's
  backchannel, while the key is held.
