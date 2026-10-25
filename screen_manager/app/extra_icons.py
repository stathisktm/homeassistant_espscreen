"""The icons a screen's own pages use beyond the set every screen carries (app 0.4.115, firmware 0.68.0).

Home Assistant knows every icon of Material Design Icons, some seven thousand, and a tile, an icon rule, a page and a top
bar item may pick any of them (tile_icons.ALL_GLYPHS). A screen's fonts carry the set of tile_icons.GLYPHS on every
board, and the rest only where its own pages use them: this module names those, and the app writes them into the
screen's YAML before each build (the EXTRA_ICONS and EXTRA_ICONS_BIG substitutions of packages/core.yaml), so a screen
spends flash on the icons it shows and on no others. A set that grew since the screen was built makes its update due
(updates.icons_due), as a new language does.

What counts, in this order, so the ones someone chose go first when a board has room for fewer:

    the icon a tile, a rule, a page or a top bar item names
    every icon Home Assistant may show for an entity of a tile or a top bar item left on Automatic, in each of its
    states and ranges (an integration's icon for its translation key, the ones its frontend picks in code, and its
    domain's for the device class), and the entity's own `icon` attribute
"""
from __future__ import annotations

import tile_icons

# How many icons beyond the set a screen carries. Each one costs flash in the three card fonts (and the full-page
# card's font on a large board): a board of the `lite` tier (the 4 MB ESP32 boards, the CYD first) is close to its
# budget, so it takes few, and none in its big font.
MOST = {'full': 120, 'lite': 24}
MOST_BIG = {'full': 32, 'lite': 0}

# The icons Home Assistant's frontend picks in code for these domains (tile_icons.state_icon), in every state.
CODE_ICONS = {
    'update': ('package-down', 'package-up', 'package'),
    'device_tracker': ('lan-connect', 'lan-disconnect', 'bluetooth-connect', 'bluetooth', 'account-arrow-right', 'account'),
    'input_datetime': ('clock', 'calendar'),
}


def spec_icons(spec):
    """Every icon of one entry of Home Assistant's icon resources: its default, its states' and its ranges'."""
    if not isinstance(spec, dict):
        return []
    found = [spec.get('default')]
    for key in ('state', 'range'):
        if isinstance(spec.get(key), dict):
            found += list(spec[key].values())
    return found


def entity_icons(entity_id, state, entry=None, icons=None):
    """The MDI names Home Assistant may show for this entity as its state changes (tile_icons.ha_default_icon's sources,
    all of them), its own `icon` attribute first."""
    domain = entity_id.split('.', 1)[0]
    if domain in tile_icons.OWN_ICON_DOMAINS:
        return []
    icons = tile_icons.HA_ICONS if icons is None else icons
    icons = icons if isinstance(icons, dict) else {}
    attributes = (state or {}).get('attributes') if isinstance(state, dict) else None
    attributes = attributes if isinstance(attributes, dict) else {}
    entry = entry if isinstance(entry, dict) else {}
    found = [attributes.get('icon')]
    if entry.get('platform') and entry.get('translation_key'):
        platform = ((icons.get('entity') or {}).get(entry['platform']) or {}).get(domain) or {}
        found += spec_icons(platform.get(entry['translation_key']))
    found += [f'mdi:{name}' for name in CODE_ICONS.get(domain, ())]
    component = (icons.get('entity_component') or {}).get(domain) or {}
    device_class = attributes.get('device_class')
    found += spec_icons((isinstance(device_class, str) and component.get(device_class)) or component.get('_'))
    return [icon[4:] for icon in found if isinstance(icon, str) and icon.startswith('mdi:')]


def wanted(tiles, pages, states, entries=None, icons=None):
    """(names, big) the screen's pages use beyond the set, in the order they count: `names` for the card fonts, `big` for
    the full-page card's (the tiles' alone, as only a tile takes the whole page). Uncapped."""
    entries = entries if isinstance(entries, dict) else {}
    chosen, automatic, chosen_big, automatic_big = [], [], [], []
    for tile in tiles or ():
        if not isinstance(tile, dict) or not isinstance(tile.get('entity'), str):
            continue
        options = tile.get('options') if isinstance(tile.get('options'), dict) else {}
        own = options.get('icon', 'auto')
        names = [own] if own not in ('auto', 'none') else []
        names += [rule.get('icon') for rule in options.get('icons') or () if isinstance(rule, dict)]
        chosen += names
        chosen_big += names
        if own == 'auto':
            entity = tile['entity']
            found = entity_icons(entity, states.get(entity), entries.get(entity), icons)
            automatic += found
            automatic_big += found
    for page in pages or ():
        if not isinstance(page, dict):
            continue
        chosen.append(page.get('icon'))
        for item in ((page.get('topbar') or {}).get('trailing') or ()):
            if not isinstance(item, dict) or item.get('type') != 'entity' or not isinstance(item.get('entity'), str):
                continue
            icon = item.get('icon', 'auto')
            if icon == 'auto':
                automatic += entity_icons(item['entity'], states.get(item['entity']), entries.get(item['entity']), icons)
            elif icon != 'none':
                chosen.append(icon)
    def beyond(names):
        return [name for name in dict.fromkeys(names)
                if isinstance(name, str) and name not in tile_icons.GLYPHS and name in tile_icons.ALL_GLYPHS]
    return beyond(chosen + automatic), beyond(chosen_big + automatic_big)


def capped(names, big, tier):
    """The names a board of this tier carries: the first ones, as many as it has room for."""
    tier = tier if tier in MOST else 'lite'
    return names[:MOST[tier]], big[:MOST_BIG[tier]]


def text(names):
    """The characters of these icons, as the EXTRA_ICONS substitution carries them."""
    return ''.join(chr(int(tile_icons.ALL_GLYPHS[name], 16)) for name in names)


def names_of(text_value):
    """The names of the icons a substitution's characters are, as far as the font has them."""
    by_code = tile_icons.ALL_BY_CODE
    return [by_code[f'{ord(char):X}'] for char in text_value or '' if f'{ord(char):X}' in by_code]
