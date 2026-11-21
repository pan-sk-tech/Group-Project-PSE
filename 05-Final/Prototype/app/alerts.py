"""Thirty-minute lost-item requests for people voluntarily viewing one campus area."""

import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from campus_places import lookup_place
from matching import CATEGORIES, InputError, choice, location_value, required_text


CREATE_ALERTS = """
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY,
        category TEXT NOT NULL,
        location TEXT NOT NULL,
        spot TEXT NOT NULL,
        description TEXT NOT NULL,
        createdAt TEXT NOT NULL,
        expiresAt TEXT NOT NULL,
        manageHash BLOB NOT NULL,
        zone TEXT NOT NULL,
        closed INTEGER NOT NULL DEFAULT 0
    )
"""
ALERT_LIFETIME = timedelta(minutes=30)


class AlertAccessError(Exception):
    """The provided credential cannot manage the requested alert."""


def timestamp(instant):
    return instant.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).digest()


def create_alert(db, payload, token=None):
    created = datetime.now(timezone.utc)
    alert = {
        "category": choice(payload.get("category"), CATEGORIES, "category"),
        "location": location_value(payload.get("location")),
        "spot": required_text(payload.get("spot"), "specific spot", 140),
        "description": required_text(payload.get("description"), "description", 280),
        "createdAt": timestamp(created),
        "expiresAt": timestamp(created + ALERT_LIFETIME),
    }
    token = token or secrets.token_urlsafe(32)
    cursor = db.execute(
        """
        INSERT INTO alerts (category, location, spot, description, createdAt, expiresAt, manageHash, zone)
        VALUES (:category, :location, :spot, :description, :createdAt, :expiresAt, :manageHash, :zone)
        """,
        {**alert, "manageHash": token_hash(token), "zone": lookup_place(alert["location"])["zone"]},
    )
    alert["id"] = cursor.lastrowid
    return {"alert": alert, "manageToken": token}


def list_alerts(db, location):
    zone = lookup_place(location_value(location))["zone"]
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """
        SELECT id, category, location, spot, description, createdAt, expiresAt
        FROM alerts
        WHERE zone = ? AND closed = 0 AND julianday(expiresAt) > julianday(?)
        ORDER BY createdAt DESC, id DESC
        """,
        (zone, timestamp(datetime.now(timezone.utc))),
    )
    return {"alerts": [dict(row) for row in rows]}


def close_alert(db, payload):
    alert_id = payload.get("id")
    if type(alert_id) is not int or not 1 <= alert_id <= 2**63 - 1:
        raise InputError("Supply a valid numeric alert ID.")
    token = payload.get("manageToken")
    if not isinstance(token, str) or not token:
        raise InputError("Supply the management token from the original request.")
    # Matching the owner on this update keeps repeated close requests successful.
    cursor = db.execute(
        "UPDATE alerts SET closed = 1 WHERE id = ? AND manageHash = ?",
        (alert_id, token_hash(token)),
    )
    if cursor.rowcount != 1:
        raise AlertAccessError("The management token does not grant access to this alert.")
    return {"closed": True}
