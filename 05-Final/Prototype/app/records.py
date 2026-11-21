"""Durable lost notices and finder-confirmed handovers."""
import hmac
import sqlite3
from datetime import datetime, timezone

from alerts import AlertAccessError, timestamp, token_hash
from matching import CATEGORIES, InputError, choice, local_minute, location_value, required_text


ITEM_FIELDS = "id, category, colour, location, foundAt, description, spot, collectionPoint, status"
NOTICE_FIELDS = "id, category, location, lostAt, description, status, createdAt, revision"


class RecordConflict(ValueError):
    pass


class RecordNotFound(LookupError):
    pass


def install_records(db, item_columns):
    # Existing items remain searchable and have no public management credential.
    if "status" not in item_columns:
        db.execute("ALTER TABLE items ADD COLUMN status TEXT NOT NULL DEFAULT 'available' "
                   "CHECK(status IN ('available', 'claimed'))")
    if "manageHash" not in item_columns:
        db.execute("ALTER TABLE items ADD COLUMN manageHash BLOB")
    db.execute("""CREATE TABLE IF NOT EXISTS lost_notices (
        id INTEGER PRIMARY KEY, category TEXT NOT NULL, location TEXT NOT NULL,
        lostAt TEXT NOT NULL, description TEXT NOT NULL, createdAt TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'resolved')),
        manageHash BLOB NOT NULL, revision INTEGER NOT NULL DEFAULT 1
    )""")
    if not any(row[1] == "revision" for row in db.execute("PRAGMA table_info(lost_notices)")):
        db.execute("ALTER TABLE lost_notices ADD COLUMN revision INTEGER NOT NULL DEFAULT 1")


def notice_details(payload):
    return {
        "category": choice(payload.get("category"), CATEGORIES, "category"),
        "location": location_value(payload.get("location")),
        "lostAt": local_minute(payload.get("lostAt"), "Lost time").isoformat(timespec="minutes"),
        "description": required_text(payload.get("description"), "description", 2000),
    }


def valid_id(value):
    if type(value) is not int or not 1 <= value <= 2**63 - 1:
        raise InputError("Supply a valid numeric record ID.")
    return value


def public_record(db, kind, record_id):
    valid_id(record_id)
    db.row_factory = sqlite3.Row
    if kind == "item":
        row = db.execute(f"SELECT {ITEM_FIELDS} FROM items WHERE id=?", (record_id,)).fetchone()
    elif kind == "notice":
        row = db.execute(f"SELECT {NOTICE_FIELDS} FROM lost_notices WHERE id=?", (record_id,)).fetchone()
    else:
        raise ValueError("Unknown record type")
    if row is None:
        raise RecordNotFound("Record not found.")
    return {kind: dict(row)}


def list_notices(db):
    db.row_factory = sqlite3.Row
    rows = db.execute(f"SELECT {NOTICE_FIELDS} FROM lost_notices WHERE status='open' ORDER BY id DESC")
    return {"notices": [dict(row) for row in rows]}


def create_lost_notice(db, payload, token):
    fields = notice_details(payload)
    cursor = db.execute("""INSERT INTO lost_notices (category, location, lostAt, description, createdAt, manageHash)
        VALUES (:category,:location,:lostAt,:description,:createdAt,:manageHash)""",
        {**fields, "createdAt": timestamp(datetime.now(timezone.utc)), "manageHash": token_hash(token)})
    return public_record(db, "notice", cursor.lastrowid)


def change_record(db, path, payload):
    # Authenticate and mutate under the same write lock: concurrent edits cannot reopen resolved notices.
    record_id = valid_id(payload.get("id"))
    token = payload.get("manageToken")
    if not isinstance(token, str) or not token:
        raise InputError("Use the management credential from the original report.")
    is_claim = path == "/api/items/claim"
    table = "items" if is_claim else "lost_notices"
    db.execute("BEGIN IMMEDIATE")
    row = db.execute(f"SELECT manageHash, status FROM {table} WHERE id=?", (record_id,)).fetchone()
    if row is None or row[0] is None or not hmac.compare_digest(row[0], token_hash(token)):
        raise AlertAccessError("This credential cannot manage this record.")
    if is_claim:
        db.execute("UPDATE items SET status='claimed' WHERE id=?", (record_id,))
        return public_record(db, "item", record_id)
    if path == "/api/lost-notices/resolve":
        db.execute("UPDATE lost_notices SET status='resolved', revision=revision+1 WHERE id=? AND status='open'",
                   (record_id,))
    elif path == "/api/lost-notices/update":
        if row[1] != "open":
            raise RecordConflict("This notice has already been resolved and cannot be edited.")
        fields = notice_details(payload)
        expected = payload.get("expectedRevision")
        if "expectedRevision" in payload and (type(expected) is not int or expected < 1):
            raise InputError("Supply a valid notice revision.")
        db.row_factory = sqlite3.Row
        current = db.execute("SELECT category, location, lostAt, description, revision FROM lost_notices WHERE id=?",
                             (record_id,)).fetchone()
        # A retry after a lost response succeeds if the requested values are already stored.
        if any(current[name] != value for name, value in fields.items()):
            if expected is not None and expected != current["revision"]:
                raise RecordConflict("This notice changed. Reload it before editing again.")
            db.execute("""UPDATE lost_notices SET category=:category, location=:location, lostAt=:lostAt,
                description=:description, revision=revision+1 WHERE id=:id""", {**fields, "id": record_id})
    else:
        raise ValueError("Unknown record action")
    return public_record(db, "notice", record_id)
