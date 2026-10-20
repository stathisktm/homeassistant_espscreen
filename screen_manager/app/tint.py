"""Colour by state (app 0.4.91): a tile's card drawn in the colour of what its entity is doing.

A tile keeps an ordered list of rules in its `tint` option, at most RULES of them:

    {"when": "heating", "c": "deep-orange"}     a state, or what the entity does ("heating", "idle")
    {"above": 25, "c": "red"}                   warmer than this
    {"below": 5, "c": "blue"}                   colder than this

The first rule that matches gives the colour; with none, the tile keeps the card colour it was given
(`background`). A colour is a name of meter.COLORS (the same nineteen the meter offers) or one of the screen's own
named card colours, turned into the colour itself here: the screen never keeps a table, and a screen that does not
know this choice simply draws the card it always did.

The temperature a rule compares is the one the card is about: a thermostat's current temperature, a weather card's
temperature, a sensor's own value, else the value of the entity the tile's second line reads (app 0.4.90), else the
last number the tile's entity reports (a humidifier's current humidity is not one of them, but a cover's temperature
is).

The rules never reach a screen (core.screen_options strips them): the colour does, in `x.bg`, with every message of
the tile, so a card that changes colour with its state repaints, and one that goes back to its own colour does too.
"""
from __future__ import annotations

import math
import re

import meter

# The most rules one tile keeps: a page carries up to 64 tiles and a screen's memory is not free, though a rule costs
# the screen nothing (it stays in the app).
RULES = 8
WHEN = re.compile(r'[a-z0-9_]{1,24}')
HEX = re.compile(r'#[0-9a-f]{6}')
# The colours a rule may name: Home Assistant's own theme colours, the same nineteen a meter's segments offer
# (meter.COLORS), so one name means one colour in the whole editor. A "#rrggbb" is taken as it is.
KEYS = ('tint',)
# The attributes a card's temperature is read from, in order.
TEMPERATURES = ('current_temperature', 'temperature')
# The domains whose state itself is the number a rule compares.
NUMERIC = ('sensor', 'number', 'input_number')


def number(value):
    """A finite number of JSON (not a bool), else None."""
    return meter.number(value)


def colour_value(colour):
    """The colour a rule names, as "#rrggbb", or None for a name no screen knows."""
    if not isinstance(colour, str):
        return None
    if HEX.fullmatch(colour):
        return colour
    if colour in meter.COLORS:
        return '#%06x' % meter.COLORS[colour]
    return None


def validate(options):
    """The `tint` rules of a tile's options, checked and as stored; ValueError for a shape the editor does not make.
    Everything else in `options` comes back untouched."""
    if 'tint' not in options:
        return options
    rules = options.get('tint')
    if not isinstance(rules, list) or len(rules) > RULES:
        raise ValueError('tint')
    checked = []
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) - {'when', 'above', 'below', 'c'}:
            raise ValueError('tint')
        if colour_value(rule.get('c')) is None:
            raise ValueError('tint')
        if 'when' in rule:
            if not isinstance(rule['when'], str) or not WHEN.fullmatch(rule['when']) or 'above' in rule or 'below' in rule:
                raise ValueError('tint')
            checked.append({'when': rule['when'], 'c': rule['c']})
            continue
        if 'above' not in rule and 'below' not in rule:
            raise ValueError('tint')
        line = {'c': rule['c']}
        for edge in ('above', 'below'):
            if edge in rule:
                if number(rule[edge]) is None:
                    raise ValueError('tint')
                line[edge] = rule[edge]
        checked.append(line)
    out = dict(options)
    if checked:
        out['tint'] = checked
    else:
        out.pop('tint', None)
    return out


def temperature_of(entity, state, attributes):
    """The temperature this card is about, or None: Home Assistant's own temperature attributes, else a number the
    entity's state is."""
    for key in TEMPERATURES:
        value = (attributes or {}).get(key)
        if number(value) is not None:
            return float(value)
    if isinstance(entity, str) and entity.split('.')[0] in NUMERIC:
        try:
            value = float(state)
        except (TypeError, ValueError):
            return None
        return value if math.isfinite(value) else None
    return None


def temperature(tile, state, attributes, second=None):
    """The temperature a rule compares: the tile's own where it has one, else the entity its second line reads
    (`second`: (entity_id, state) of that entity), else the tile's again - so a card that measures nothing compares
    against nothing and its temperature rules never match."""
    own = temperature_of(tile['entity'], state, attributes)
    if own is not None:
        return own
    if second:
        return temperature_of(second[0], (second[1] or {}).get('state'), (second[1] or {}).get('attributes'))
    return None


def words(entity, state, attributes):
    """What the entity is: its state and what it is doing (a thermostat's action, a humidifier's, a robot's), which
    a `when` rule may name."""
    found = [state] if isinstance(state, str) and state else []
    for key in ('hvac_action', 'action'):
        value = (attributes or {}).get(key)
        if isinstance(value, str) and value and value not in found:
            found.append(value)
    return found


def matching(tile, state, attributes, second=None):
    """The colour the first matching rule gives as "#rrggbb", or None when no rule matches."""
    rules = (tile.get('options') or {}).get('tint')
    if not isinstance(rules, list) or not rules:
        return None
    doing = words(tile['entity'], state, attributes)
    value = None
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if 'when' in rule:
            if rule['when'] in doing:
                return colour_value(rule.get('c'))
            continue
        if value is None:
            value = temperature(tile, state, attributes, second)
        if value is None:
            continue
        above, below = number(rule.get('above')), number(rule.get('below'))
        if above is not None and not value > above:
            continue
        if below is not None and not value < below:
            continue
        if above is None and below is None:
            continue
        return colour_value(rule.get('c'))
    return None


def card_background(tile, state, attributes, second=None):
    """The colour this card is drawn in, as a screen reads it (a "#rrggbb", a named card colour, "none", or "" for
    the plain card): the rule that matches, else the colour the tile was given. None when the tile keeps no rules, so
    no message carries a colour and every screen draws the card as it always did."""
    rules = (tile.get('options') or {}).get('tint')
    if not isinstance(rules, list) or not rules:
        return None
    return matching(tile, state, attributes, second) or str((tile.get('options') or {}).get('background') or '')
