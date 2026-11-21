"""Input validation and deterministic route-based matching for the practice app."""

import re
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from campus_places import LOCATIONS, PLACES, ROOM_ALIASES, describe_place, lookup_place

CATEGORIES = ("Umbrella", "Water bottle", "Bag", "Electronics", "Clothing", "Keys", "Stationery", "Other")
COLOURS = ("Black", "Blue", "Grey", "Green", "Orange", "Pink", "Purple", "Red", "White", "Yellow", "Brown", "Multicolour")
CATALOG = {"categories": CATEGORIES, "locations": LOCATIONS, "places": PLACES, "roomAliases": ROOM_ALIASES, "colours": COLOURS}
LOCAL_MINUTE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}")
MALAYSIA_TIME = timezone(timedelta(hours=8))


class InputError(ValueError):
    """An input problem suitable for display to the person using the app."""


class Visit(NamedTuple):
    location: str
    start: datetime
    end: datetime


def require_object(value, label):
    if not isinstance(value, dict):
        raise InputError(f"{label} must be a JSON object.")
    return value


def choice(value, options, label):
    if value not in options:
        raise InputError(f"Select a listed {label}.")
    return value


def location_value(value):
    place = lookup_place(value)
    if place is None:
        raise InputError("Choose a campus place or enter a room number such as C7.09.")
    return place["id"]


def optional_colour(value):
    if value is None or value == "":
        return ""
    return choice(value, COLOURS, "colour")


def local_minute(value, label):
    # Compare campus wall time to the current Malaysian minute regardless of host timezone.
    if isinstance(value, str) and LOCAL_MINUTE.fullmatch(value):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            pass
        else:
            now = datetime.now(MALAYSIA_TIME).replace(tzinfo=None, second=0, microsecond=0)
            if parsed > now:
                raise InputError(f"{label} cannot be in the future in Malaysia (UTC+8).")
            return parsed
    raise InputError(f"{label} must be a valid date and time in YYYY-MM-DDTHH:MM format.")


def required_text(value, label, limit):
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"Enter a {label}.")
    value = value.strip()
    if len(value) > limit:
        raise InputError(f"The {label} must be at most {limit} characters.")
    return value


def validate_item(payload):
    require_object(payload, "Item")
    spot = payload.get("spot")
    if isinstance(spot, str):
        spot = spot.strip()
    return {
        "category": choice(payload.get("category"), CATEGORIES, "category"),
        "colour": optional_colour(payload.get("colour")),
        "location": location_value(payload.get("location")),
        "foundAt": local_minute(payload.get("foundAt"), "Found time").isoformat(timespec="minutes"),
        "description": required_text(payload.get("description"), "description", 2000),
        "spot": "" if spot is None or spot == "" else required_text(spot, "specific spot", 140),
        "collectionPoint": required_text(payload.get("collectionPoint"), "collection point", 200),
    }


def validate_search(payload):
    require_object(payload, "Search")
    category = choice(payload.get("category"), CATEGORIES, "category")
    colour = optional_colour(payload.get("colour"))
    rows = payload.get("visits")
    if not isinstance(rows, list) or not rows:
        raise InputError("Add at least one campus visit.")
    visits = []
    for number, row in enumerate(rows, start=1):
        require_object(row, f"Visit {number}")
        location = location_value(row.get("location"))
        start = local_minute(row.get("start"), f"Arrival for visit {number}")
        end = local_minute(row.get("end"), f"Departure for visit {number}")
        if end <= start:
            raise InputError(f"Visit {number} must end after it starts. For overnight visits, use the next date.")
        for other in visits:
            if other.location != location and max(start, other.start) < min(end, other.end):
                raise InputError(f"Visit {number} overlaps a visit at another location.")
        visits.append(Visit(location, start, end))
    return category, colour, visits


def find_matches(items, category, colour, visits):
    """Only a visit to the item's site can qualify it. Ignore arrivals after it was found."""
    ranked = []
    for item in items:
        if item["category"] != category:
            continue
        item["location"] = location_value(item["location"])
        found_at = datetime.fromisoformat(item["foundAt"])
        eligible = [v for v in visits if v.location == item["location"] and v.start <= found_at]
        if not eligible:
            continue
        during = any(found_at <= v.end for v in eligible)
        colour_match = bool(colour) and colour == item["colour"]
        if during:
            minutes_after = 0
            timing = "Found during your visit, including the arrival and departure times."
        else:
            latest_departure = max(v.end for v in eligible)
            minutes_after = int((found_at - latest_departure).total_seconds() // 60)
            unit = "minute" if minutes_after == 1 else "minutes"
            timing = f"Found {minutes_after} {unit} after your most recent visit to this location."
        reasons = [f"Category matches: {category}.", f"On your route: {describe_place(item['location'])}.", timing]
        if colour_match:
            reasons.append(f"Matches your requested colour: {colour}.")
        match = {"item": item, "reasons": reasons, "during": during, "colourMatch": colour_match}
        rank = (not colour_match, not during, minutes_after, item["id"])
        ranked.append((rank, match))
    ranked.sort(key=lambda entry: entry[0])
    return [match for _, match in ranked]
