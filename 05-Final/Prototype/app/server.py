"""Run python3 server.py, then open the printed URL for Campus Lost and Found.

Choose a campus area to view voluntary lost-item alerts. Alerts expire after
30 minutes. Only the creator receives the token to close an alert early.
"""

import argparse
import base64
import hashlib
import json
import re
import secrets
import sqlite3
import sys
import zlib
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from campus_places import lookup_place
from alerts import CREATE_ALERTS, AlertAccessError, close_alert, create_alert, list_alerts
from records import (ITEM_FIELDS, RecordConflict, RecordNotFound, change_record, create_lost_notice,
                     install_records, list_notices, public_record)
from alerts import token_hash
from matching import CATALOG, InputError, find_matches, validate_item, validate_search


ROOT = Path(__file__).resolve().parent
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/campus-lake.jpg": ("campus-lake.jpg", "image/jpeg"),
    "/PHOTO-CREDIT.txt": ("PHOTO-CREDIT.txt", "text/plain; charset=utf-8"),
}
CREATE_ITEMS = """
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY,
        category TEXT NOT NULL,
        colour TEXT NOT NULL,
        location TEXT NOT NULL,
        foundAt TEXT NOT NULL,
        description TEXT NOT NULL,
        spot TEXT NOT NULL DEFAULT '',
        collectionPoint TEXT NOT NULL
    )
"""
INSERT_ITEM = """
    INSERT INTO items (category, colour, location, foundAt, description, collectionPoint, spot)
    VALUES (:category, :colour, :location, :foundAt, :description, :collectionPoint, :spot)
"""
LEGACY_SEED_ITEMS = (
    ("Umbrella", "Black", "Library", "2026-11-08T11:20", "Foldable black umbrella with a wooden handle.", "Library help desk"),
    ("Umbrella", "Orange", "Library", "2026-11-08T11:12", "Orange umbrella with a striped wrist strap.", "Library help desk"),
    ("Umbrella", "Black", "Cafeteria", "2026-11-08T12:55", "Compact umbrella in a black travel sleeve.", "Cafeteria service counter"),
    ("Umbrella", "Orange", "Cafeteria", "2026-11-08T12:40", "Orange canopy and a curved handle.", "Cafeteria service counter"),
    ("Umbrella", "Black", "Library", "2026-11-08T09:40", "Tall black umbrella with a silver tip.", "Library help desk"),
    ("Water bottle", "Blue", "Sports centre", "2026-11-08T15:10", "Blue metal bottle with a flip lid.", "Sports centre reception"),
    ("Keys", "", "Bus stop", "2026-11-08T17:10", "Two keys on a small ring.", "Student centre reception"),
)
SAMPLE_VENUES = {
    "Library": ("library-study-room", "Campus Central (Block A, Level 2)"),
    "Cafeteria": ("grand-hall", "Security Control Room (Block B, Level 1)"),
    "Sports centre": ("unigym", "Campus Central (Block A, Level 2)"),
    "Bus stop": ("main-roundabout", "Security Control Room (Block B, Level 1)"),
}


def install_sample_items(db, version):
    for row_id, old in enumerate(LEGACY_SEED_ITEMS, start=1):
        category, colour, old_site, found_at, old_description, _ = old
        venue, counter = SAMPLE_VENUES[old_site]
        description = f"Demo item: {old_description}"
        if version == 0:
            db.execute(INSERT_ITEM, {"category": category, "colour": colour, "location": venue,
                                     "foundAt": found_at, "description": description,
                                     "collectionPoint": counter, "spot": ""})
        else:
            # Match every original field so an edited sample or later user entry is preserved.
            db.execute(
                """UPDATE items SET location = ?, description = ?, collectionPoint = ?
                   WHERE id = ? AND category = ? AND colour = ? AND location = ? AND foundAt = ?
                     AND description = ? AND collectionPoint = ? AND spot = ''""",
                (venue, description, counter, row_id, *old),
            )


def prepare_database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=10)) as db, db:
        # Start-up is serialized so concurrent starts cannot duplicate the sample reports.
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE IF NOT EXISTS submissions (
            endpoint TEXT NOT NULL, keyHash BLOB NOT NULL, dataHash BLOB NOT NULL,
            recordId INTEGER NOT NULL, PRIMARY KEY (endpoint, keyHash)
        )""")
        db.execute(CREATE_ITEMS)
        columns = {row[1] for row in db.execute("PRAGMA table_info(items)")}
        if "spot" not in columns:
            db.execute("ALTER TABLE items ADD COLUMN spot TEXT NOT NULL DEFAULT ''")
        install_records(db, columns)
        db.execute(CREATE_ALERTS)
        alert_columns = {row[1] for row in db.execute("PRAGMA table_info(alerts)")}
        if "zone" not in alert_columns:
            db.execute("ALTER TABLE alerts ADD COLUMN zone TEXT NOT NULL DEFAULT ''")
            for (location,) in db.execute("SELECT DISTINCT location FROM alerts").fetchall():
                place = lookup_place(location)
                if place:
                    db.execute("UPDATE alerts SET zone=? WHERE location=?", (place["zone"], location))
        db.execute("CREATE INDEX IF NOT EXISTS alerts_by_zone ON alerts(zone, closed, createdAt DESC)")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version < 2:
            install_sample_items(db, version)
            db.execute("PRAGMA user_version = 2")


CREATE_PATHS = ("/api/items", "/api/alerts", "/api/lost-notices")
RECORD_ACTIONS = ("/api/items/claim", "/api/lost-notices/update", "/api/lost-notices/resolve")
RECORD_PATH = re.compile(r"/api/(items|lost-notices)/([0-9]{1,19})")


def create_submission(db, path, payload):
    """Reuse a committed response when the submitting tab retries after losing it."""
    key = payload.pop("submissionKey", None)
    if key is not None:
        if not isinstance(key, str) or re.fullmatch("[0-9a-f]{64}", key) is None:
            raise InputError("Invalid submission key.")
        token = owner_token(path, key)
        # Never store the bearer secret or the owner's close credential in clear text.
        key_hash = hashlib.sha256(key.encode("ascii")).digest()
        data_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).digest()
        # A concurrent second request must see both the submission row and its receipt.
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute(
            "SELECT recordId, dataHash FROM submissions WHERE endpoint=? AND keyHash=?",
            (path, key_hash),
        ).fetchone()
        if previous and previous[1] != data_hash:
            raise RecordConflict("This submission key was already used with different details.")
        if previous:
            db.row_factory = sqlite3.Row
            if path == "/api/items":
                # An original pre-upgrade submission key is the only proof eligible to adopt its old receipt.
                db.execute("UPDATE items SET manageHash=? WHERE id=? AND manageHash IS NULL",
                           (token_hash(token), previous[0]))
                return {**public_record(db, "item", previous[0]), "manageToken": token}
            if path == "/api/lost-notices":
                return {**public_record(db, "notice", previous[0]), "manageToken": token}
            row = dict(db.execute(
                "SELECT id, category, location, spot, description, createdAt, expiresAt, closed "
                "FROM alerts WHERE id=?", (previous[0],),
            ).fetchone())
            closed = row.pop("closed")
            response = {"alert": row, "manageToken": token}
            if closed:
                response["closed"] = True
            return response

    else:
        token = secrets.token_urlsafe(32)

    if path == "/api/items":
        item = validate_item(payload)
        record_id = db.execute(INSERT_ITEM, item).lastrowid
        db.execute("UPDATE items SET manageHash=? WHERE id=?", (token_hash(token), record_id))
        response = {**public_record(db, "item", record_id), "manageToken": token}
    elif path == "/api/lost-notices":
        response = {**create_lost_notice(db, payload, token), "manageToken": token}
        record_id = response["notice"]["id"]
    else:
        response = create_alert(db, payload, token)
        record_id = response["alert"]["id"]
    if key is not None:
        db.execute("INSERT INTO submissions(endpoint,keyHash,dataHash,recordId) VALUES (?,?,?,?)",
                   (path, key_hash, data_hash, record_id))
    return response


def owner_token(path, key):
    # Preserve the existing alert credential derivation across upgrades.
    prefix = "alert-owner:" if path == "/api/alerts" else path + ":owner:"
    return hashlib.sha256((prefix + key).encode("ascii")).hexdigest()


class CampusServer(ThreadingHTTPServer):
    def __init__(self, address, db_path):
        self.db_path = db_path
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, data, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def send_json(self, status, payload):
        # Escaping Unicode keeps the JSON encodable even if a client sent an unpaired surrogate.
        self.respond(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def read_body(self):
        if self.headers.get_content_type() != "application/json":
            self.send_json(415, {"error": "Send the request as application/json."})
            return None
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise InputError("Send a JSON request with a valid Content-Length.") from None
        if length > 65536:
            self.send_json(413, {"error": "Request exceeds the 64 KiB limit."})
            return None
        if length <= 0:
            raise InputError("Send a JSON object in the request body.")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, RecursionError):
            raise InputError("The request body must be valid UTF-8 JSON.") from None
        if not isinstance(payload, dict):
            raise InputError("Send a JSON object in the request body.")
        return payload

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        target = urlsplit(self.path)
        path = target.path
        if path == "/diagram":
            # draw.io reads the editable mxfile from the URL fragment in the browser.
            diagram = (ROOT / "diagrams" / "Campus Lost and Found.drawio").read_text(encoding="utf-8")
            escaped = quote(diagram, safe="~()*!.'-").encode("ascii")
            encoder = zlib.compressobj(level=9, wbits=-15)
            compressed = encoder.compress(escaped) + encoder.flush()
            fragment = quote(base64.b64encode(compressed).decode("ascii"), safe="")
            self.send_response(302)
            self.send_header("Location", "https://app.diagrams.net/?splash=0&title=Campus%20Lost%20and%20Found.drawio#R" + fragment)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif path == "/api/catalog":
            self.send_json(200, CATALOG)
        elif path == "/api/lost-notices" or RECORD_PATH.fullmatch(path):
            try:
                with closing(sqlite3.connect(self.server.db_path, timeout=10)) as db:
                    if path == "/api/lost-notices":
                        result = list_notices(db)
                    else:
                        collection, number = RECORD_PATH.fullmatch(path).groups()
                        kind = "item" if collection == "items" else "notice"
                        result = public_record(db, kind, int(number))
                self.send_json(200, result)
            except (InputError, RecordNotFound):
                self.send_json(404, {"error": "Record not found."})
            except sqlite3.Error as exc:
                self.database_error(exc)
        elif path == "/api/alerts":
            try:
                locations = parse_qs(target.query, keep_blank_values=True).get("location", [])
                if len(locations) != 1:
                    raise InputError("Select exactly one campus area to view its alerts.")
                with closing(sqlite3.connect(self.server.db_path, timeout=10)) as db:
                    result = list_alerts(db, locations[0])
                self.send_json(200, result)
            except InputError as exc:
                self.send_json(400, {"error": str(exc)})
            except sqlite3.Error as exc:
                self.database_error(exc)
        elif path in STATIC:
            name, content_type = STATIC[path]
            try:
                data = (ROOT / name).read_bytes()
            except FileNotFoundError:
                self.send_json(404, {"error": "Page asset unavailable."})
                return
            self.respond(200, data, content_type)
        else:
            self.send_json(404, {"error": "Resource not found."})

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in (*CREATE_PATHS, *RECORD_ACTIONS, "/api/search", "/api/alerts/close"):
            self.send_json(404, {"error": "Resource not found."})
            return
        try:
            payload = self.read_body()
            if payload is None:
                return
            if path in CREATE_PATHS:
                with closing(sqlite3.connect(self.server.db_path, timeout=10)) as db, db:
                    result = create_submission(db, path, payload)
                self.send_json(201, result)
            elif path == "/api/search":
                category, colour, visits = validate_search(payload)
                with closing(sqlite3.connect(self.server.db_path, timeout=10)) as db:
                    db.row_factory = sqlite3.Row
                    rows = db.execute(f"SELECT {ITEM_FIELDS} FROM items WHERE category=? AND status='available'", (category,))
                    matches = find_matches((dict(row) for row in rows), category, colour, visits)
                self.send_json(200, {"matches": matches})
            else:
                with closing(sqlite3.connect(self.server.db_path, timeout=10)) as db, db:
                    result = close_alert(db, payload) if path == "/api/alerts/close" else change_record(db, path, payload)
                self.send_json(200, result)
        except RecordConflict as exc:
            self.send_json(409, {"error": str(exc)})
        except InputError as exc:
            self.send_json(400, {"error": str(exc)})
        except AlertAccessError as exc:
            self.send_json(403, {"error": str(exc)})
        except UnicodeEncodeError:
            self.send_json(400, {"error": "Use valid Unicode text for item details."})
        except sqlite3.Error as exc:
            self.database_error(exc)

    def database_error(self, exc):
        print(f"Database error: {exc}", file=sys.stderr)
        self.send_json(503, {"error": "The local database is unavailable. Try again shortly."})

    def log_request(self, code="-", size="-"):
        # Route searches are transient. The server keeps no access log.
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", type=Path, default=ROOT / "campus.sqlite3")
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    path = args.db.expanduser().resolve()
    prepare_database(path)
    with CampusServer((args.host, args.port), path) as server:
        print(f"Campus Lost and Found: http://{args.host}:{server.server_port}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
