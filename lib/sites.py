#!/usr/bin/env python3
"""Sites and the locations in them, by name.

"The Saffron House#Ilaria's Room" is the location Ilaria's Room in the site The
Saffron House. The site is a place too: "The Saffron House" is its common rooms, or
somewhere in it. One level only: a location in a site holds no locations, and every
place without "#" is a site, with or without locations.

What is at a site counts for all its locations (`at`): a fact recorded at the site
or at one of its locations ranks as the site's on its card, an `on_location` trigger
on the site fires in each of them, a faction's presence and an NPC's usual place
written for the site hold in each of them. A location's own records count only
there. Within a site every location can be reached from every other: a move between
two of them adds no connection (connections there are the site's layout, written by
hand or by the site-architect agent).
"""

SEP = "#"


def _key(place) -> str:
    """A place's key, from the key or its id (location:<key>)."""
    text = str(place or "").strip()
    return text[len("location:"):] if text.lower().startswith("location:") else text


def site_of(place) -> str:
    """The site a place is in, or the place itself if it is a site ('' for none)."""
    return _key(place).split(SEP, 1)[0].strip()


def own_name(place) -> str:
    """A location's name within its site ("Ilaria's Room"); a site's whole name."""
    key = _key(place)
    return key.split(SEP, 1)[1].strip() if SEP in key else key


def in_site(place) -> bool:
    """Whether a place is a location in a site."""
    return SEP in _key(place)


def same_site(a, b) -> bool:
    """Whether two places are in one site (or are it)."""
    return bool(site_of(a)) and site_of(a).lower() == site_of(b).lower()


def at(place, where) -> bool:
    """Whether `place` is at `where`: the same place, or `where` is a site and `place`
    one of its locations. Keys or ids (location:<key>), case-insensitive."""
    p, w = _key(place).lower(), _key(where).lower()
    return bool(w) and (p == w or (SEP not in w and p.startswith(w + SEP)))


def name_errors(name: str, locations: dict) -> list[str]:
    """Why a new place can't have this name ([] if it can): one "#" at most, a site
    that exists and is no location itself, and each part a valid name."""
    from validators import Validators
    key = str(name or "").strip()
    if key.count(SEP) > 1:
        return [f"'{key}': one \"{SEP}\" at most, between the site and the location "
                f"(\"The Saffron House{SEP}Ilaria's Room\"); a location in a site holds none."]
    errors = []
    for part in key.split(SEP):
        valid, error = Validators.validate_name(part.strip())
        if not valid:
            errors.append(error)
    if SEP in key and not errors and site_of(key) not in (locations or {}):
        errors.append(f"No site '{site_of(key)}' for '{key}': add the site first "
                      f"(bash tools/gm-location.sh add \"{site_of(key)}\" \"<where it is>\" "
                      f"\"<what it is like>\").")
    return errors
