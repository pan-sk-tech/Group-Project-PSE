"""Start the practice app on this computer, or share it with devices on the same LAN."""
import argparse
import errno
import hashlib
import http.client
import json
import ipaddress
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from server import CampusServer, Handler, prepare_database


ROOT = Path(__file__).resolve().parent


class LauncherHandler(Handler):
    def do_GET(self):
        if self.path == "/api/launcher":
            self.send_json(200, {"instance": self.server.instance, "lan": self.server.lan})
        else:
            super().do_GET()


class LauncherServer(CampusServer):
    # Permit quick restart after an HTTP connection enters TIME_WAIT on Unix.
    # An active listener is checked separately before widening the bind to LAN.
    allow_reuse_address = sys.platform != "win32"


def has_listener(host, port):
    try:
        with socket.create_connection((host, port), timeout=0.35):
            return True
    except OSError:
        return False


def existing_instance(port):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
    try:
        connection.request("GET", "/api/launcher")
        response = connection.getresponse()
        if response.status == 200:
            info = json.loads(response.read(512))
            return info if isinstance(info, dict) else {}
    except (OSError, http.client.HTTPException, ValueError):
        pass
    finally:
        connection.close()
    return {}


def show_addresses(port, address):
    url = f"http://127.0.0.1:{port}/"
    print(f"On this computer: {url}", flush=True)
    if address:
        print(f"On a phone on the same network: http://{address}:{port}/", flush=True)
    return url


def lan_ipv4(value):
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError:
        return None
    if address.is_loopback or address.is_multicast or address.is_unspecified or address.is_reserved:
        return None
    return str(address)


def detect_lan_address():
    if sys.platform == "darwin":
        # macOS can resolve its hostname to a loopback or VPN address. Prefer Ethernet/Wi-Fi.
        for _, name in socket.if_nameindex():
            if name.startswith("en"):
                result = subprocess.run(["/usr/sbin/ipconfig", "getifaddr", name],
                                        capture_output=True, text=True, check=False)
                address = lan_ipv4(result.stdout.strip())
                if address:
                    return address

    # A UDP connect asks the kernel for the default interface's address without sending data.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            address = lan_ipv4(probe.getsockname()[0])
            if address:
                return address
    except OSError:
        pass

    try:
        records = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM)
    except OSError:
        return None
    for record in records:
        address = lan_ipv4(record[4][0])
        if address:
            return address
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lan", action="store_true", help="share the app on the local network")
    parser.add_argument("--address", help="this computer's LAN IPv4 address to display to phone users")
    parser.add_argument("--port", type=int, help="preferred port (default: a stable address for this database; 0 selects a free port)")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "campus.sqlite3")
    parser.add_argument("--no-browser", action="store_true", help="do not open the local browser")
    args = parser.parse_args()
    if args.port is not None and not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    if args.address is not None and (not args.lan or not lan_ipv4(args.address)):
        parser.error("--address requires --lan and a valid LAN IPv4 address")
    address = None
    if args.lan:
        address = args.address or detect_lan_address()
        if not address:
            parser.error("unable to detect a LAN IPv4 address; supply your Wi-Fi IPv4 using --lan --address")
    host = "0.0.0.0" if args.lan else "127.0.0.1"
    db = args.db.expanduser().resolve()
    # Browser-held management rights belong to an origin. Reopening the same
    # installation must use the same address after the previous server stops.
    instance = hashlib.sha256(str(db).encode("utf-8")).hexdigest()
    preferred = args.port if args.port is not None else 22000 + int(instance[:8], 16) % 20000
    prepare_database(db)
    try:
        if preferred and (has_listener("127.0.0.1", preferred) or (address and has_listener(address, preferred))):
            raise OSError(errno.EADDRINUSE, "Port already has a listener")
        service = LauncherServer((host, preferred), db)
    except OSError as exc:
        if exc.errno != errno.EADDRINUSE or not preferred:
            raise
        current = existing_instance(preferred)
        if current.get("instance") == instance:
            if args.lan and not current.get("lan"):
                parser.exit(1, "The prototype is running in local mode. Stop its window with Ctrl+C, then start Wi-Fi mode again.\n")
            url = show_addresses(preferred, address)
            if not args.no_browser:
                webbrowser.open(url)
            return
        if args.port is None:
            parser.exit(1, f"Port {preferred} is being used by another app. Free that port or start with --port and a different fixed number.\n")
        print(f"Port {preferred} is in use. Choosing an available port.", flush=True)
        service = LauncherServer((host, 0), db)

    with service:
        service.instance = instance
        service.lan = args.lan
        service.RequestHandlerClass = LauncherHandler
        url = show_addresses(service.server_port, address)
        print("Press Ctrl+C in this window to stop.", flush=True)
        if not args.no_browser:
            timer = threading.Timer(0.4, webbrowser.open, args=[url])
            timer.daemon = True
            timer.start()
        try:
            service.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
