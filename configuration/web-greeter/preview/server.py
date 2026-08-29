#!/usr/bin/env python3
"""Dev/preview server for the web-greeter themes.

Serves the panel + theme files over HTTP, watches the theme tree and the
global ~/.config/config.json, regenerates each theme's theme.css when
something relevant changes, and pushes a reload event to any connected
WebSocket client.

Run:
    pip install -r ../../../requirements-dev.txt
    python server.py [--port 8765] [--ws-port 8766]
"""

import argparse
import asyncio
import contextlib
import json
import os
import re
import shutil
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

try:
    import websockets
except ImportError:
    sys.stderr.write(
        "missing dependency 'websockets'. install with: "
        "pip install -r requirements-dev.txt\n"
    )
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
GREETER_ROOT = os.path.dirname(HERE)
THEMES_DIR = os.path.join(GREETER_ROOT, "themes")
PANEL_DIR = os.path.join(HERE, "panel")
REPO_ROOT = os.path.dirname(os.path.dirname(GREETER_ROOT))
HELPER_DIR = os.path.join(REPO_ROOT, "helper")
GLOBAL_CONFIG = os.path.expanduser("~/.config/config.json")

try:
    from helper.patch_web_greeter import patch_web_greeter
except ImportError:
    # This file is run as a script, so the repo root is not on sys.path yet.
    sys.path.insert(0, REPO_ROOT)
    from helper.patch_web_greeter import patch_web_greeter

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".js":   "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".yml":  "text/yaml; charset=utf-8",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg":  "image/svg+xml",
    ".ico":  "image/x-icon",
}


def mime_for(path: str) -> str:
    return MIME.get(os.path.splitext(path)[1].lower(), "application/octet-stream")


def list_themes() -> list:
    if not os.path.isdir(THEMES_DIR):
        return []
    return sorted(
        name for name in os.listdir(THEMES_DIR)
        if not name.startswith("_")
        and os.path.isfile(os.path.join(THEMES_DIR, name, "theme.json"))
    )


def safe_join(base: str, *parts: str) -> str | None:
    # Block ../ traversal at the path-string level but allow symlinks within
    # the theme dir to point outside the repo (e.g. wallpaper -> ~/.config/...).
    base_abs = os.path.abspath(base)
    target = os.path.abspath(os.path.join(base_abs, *parts))
    if not (target == base_abs or target.startswith(base_abs + os.sep)):
        return None
    return target


# ---------- HTTP handler ----------

class PreviewHandler(BaseHTTPRequestHandler):
    server_version = "WebGreeterPreview/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write(f"[http] {self.address_string()} - {fmt % args}\n")

    def _send_bytes(
        self,
        status: int,
        body: bytes,
        content_type: str = "application/octet-stream",
        extra_headers: dict | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_text(
        self, status: int, text: str,
        content_type: str = "text/plain; charset=utf-8",
    ) -> None:
        self._send_bytes(status, text.encode("utf-8"), content_type)

    def _send_json(self, status: int, payload: object) -> None:
        self._send_bytes(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def _send_file(self, path: str) -> None:
        try:
            with open(path, "rb") as fh:
                body = fh.read()
        except OSError:
            self._send_text(404, "not found")
            return
        self._send_bytes(200, body, mime_for(path))

    # ---- routing ----

    def do_GET(self) -> None:
        try:
            self._route_get()
        except Exception as exc:
            self.log_message("error: %s", exc)
            self._send_text(500, f"server error: {exc}")

    def do_POST(self) -> None:
        try:
            self._route_post()
        except Exception as exc:
            self.log_message("error: %s", exc)
            self._send_text(500, f"server error: {exc}")

    def _route_get(self) -> None:
        url = urlparse(self.path)
        path = url.path
        if path == "/":
            return self._send_file(os.path.join(PANEL_DIR, "panel.html"))
        if path == "/favicon.ico":
            return self._send_bytes(204, b"", "image/x-icon")
        if path.startswith("/__api/"):
            return self._api_get(path, parse_qs(url.query))
        if path.startswith("/panel/"):
            return self._serve_under(PANEL_DIR, path[len("/panel/"):])
        if path == "/_shared" or path.startswith("/_shared/"):
            rel = path[len("/_shared/"):] if path != "/_shared" else ""
            return self._serve_under(os.path.join(THEMES_DIR, "_shared"), rel)
        # /<theme>/... or /<theme>
        parts = path.lstrip("/").split("/", 1)
        theme = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        if not theme or theme not in list_themes():
            return self._send_text(404, "no such theme")
        if rest in {"", "/"}:
            return self._serve_under(os.path.join(THEMES_DIR, theme), "index.html")
        if rest.startswith("_shared/"):
            return self._serve_under(os.path.join(THEMES_DIR, "_shared"), rest[len("_shared/"):])
        target = safe_join(os.path.join(THEMES_DIR, theme), rest)
        if target and os.path.isfile(target):
            return self._send_file(target)
        # fall back to shared
        shared = safe_join(os.path.join(THEMES_DIR, "_shared"), rest)
        if shared and os.path.isfile(shared):
            return self._send_file(shared)
        return self._send_text(404, "not found")

    def _serve_under(self, base: str, rel: str) -> None:
        if rel in ("", "/"):
            rel = "index.html"
        target = safe_join(base, rel)
        if not target or not os.path.isfile(target):
            return self._send_text(404, "not found")
        return self._send_file(target)

    def _api_get(self, path: str, query: dict) -> None:
        if path == "/__api/themes":
            return self._send_json(200, {"themes": list_themes()})
        if path == "/__api/theme.json":
            theme = (query.get("theme") or [""])[0]
            if theme not in list_themes():
                return self._send_text(404, "no such theme")
            with open(os.path.join(THEMES_DIR, theme, "theme.json")) as fh:
                return self._send_json(200, json.load(fh))
        if path == "/__api/config.json":
            try:
                with open(GLOBAL_CONFIG) as fh:
                    return self._send_json(200, json.load(fh))
            except OSError as exc:
                return self._send_text(404, f"config.json not readable: {exc}")
        if path == "/__api/wallpaper_keys":
            try:
                with open(GLOBAL_CONFIG) as fh:
                    cfg = json.load(fh)
                return self._send_json(200, {"keys": sorted(cfg.get("wallpapers", {}).keys())})
            except OSError:
                return self._send_json(200, {"keys": []})
        return self._send_text(404, "no such endpoint")

    def _route_post(self) -> None:
        url = urlparse(self.path)
        if url.path == "/__api/theme.json":
            theme = (parse_qs(url.query).get("theme") or [""])[0]
            if theme not in list_themes():
                return self._send_text(404, "no such theme")
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                return self._send_text(400, f"invalid JSON: {exc}")
            target = os.path.join(THEMES_DIR, theme, "theme.json")
            tmp = target + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(payload, fh, indent=4)
                fh.write("\n")
            os.replace(tmp, target)
            return self._send_json(200, {"ok": True})
        if url.path == "/__api/regenerate":
            ok, err = regenerate_now()
            return self._send_json(200 if ok else 500, {"ok": ok, "error": err})
        if url.path == "/__api/themes/clone":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                return self._send_text(400, f"invalid JSON: {exc}")
            ok, result = clone_theme(payload.get("source"), payload.get("name"))
            return self._send_json(200 if ok else 400, result)
        return self._send_text(404, "no such endpoint")


# ---------- File watcher ----------

def _is_generated_artifact(root: str, name: str) -> bool:
    """Return True for files patch_web_greeter writes (and thus must not be watched)."""
    if name == "theme.css":
        return True
    if name.startswith("wallpaper."):
        return True
    # _shared/ copies inside individual theme dirs are generated; only the
    # canonical themes/_shared/ source-of-truth should be watched.
    parts = os.path.relpath(root, THEMES_DIR).split(os.sep)
    return bool(len(parts) >= 2 and not parts[0].startswith("_") and parts[1] == "_shared")


def snapshot() -> dict:
    """Return dict[path -> mtime] for source files we care about.

    Generated artifacts (theme.css, wallpaper symlinks, per-theme _shared
    copies) are excluded so the watcher does not see its own writes and
    trigger an infinite regeneration loop.
    """
    snap = {}
    with contextlib.suppress(OSError):
        snap[GLOBAL_CONFIG] = os.stat(GLOBAL_CONFIG).st_mtime
    if os.path.isdir(THEMES_DIR):
        for root, _dirs, files in os.walk(THEMES_DIR):
            for name in files:
                if _is_generated_artifact(root, name):
                    continue
                p = os.path.join(root, name)
                with contextlib.suppress(OSError):
                    snap[p] = os.stat(p).st_mtime
    return snap


def regenerate_now() -> dict:
    try:
        with open(GLOBAL_CONFIG) as fh:
            configuration = json.load(fh)
        patch_web_greeter(configuration)
        return True, None
    except Exception as exc:
        sys.stderr.write(f"[watcher] regenerate failed: {exc}\n")
        return False, str(exc)


THEME_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,30}$")
# Files copied when cloning a theme. Generated artifacts (theme.css,
# wallpaper.*, per-theme _shared/) are recreated by patch_web_greeter.
CLONE_FILES = ("index.html", "index_blank.html", "style.css", "theme.json", "index.yml")


def clone_theme(source: str, name: str) -> dict:
    if not source or source not in list_themes():
        return False, {"ok": False, "error": "source theme not found"}
    if not name or not THEME_NAME_RE.match(name):
        return False, {"ok": False, "error": "name must match ^[a-z][a-z0-9-]{0,30}$"}
    if name.startswith("_"):
        return False, {"ok": False, "error": "name must not start with '_'"}
    dest_dir = os.path.join(THEMES_DIR, name)
    if os.path.exists(dest_dir):
        return False, {"ok": False, "error": f"theme '{name}' already exists"}
    source_dir = os.path.join(THEMES_DIR, source)
    try:
        os.makedirs(dest_dir, exist_ok=False)
        for fname in CLONE_FILES:
            src = os.path.join(source_dir, fname)
            if not os.path.isfile(src):
                continue
            shutil.copy2(src, os.path.join(dest_dir, fname))
    except OSError as exc:
        shutil.rmtree(dest_dir, ignore_errors=True)
        return False, {"ok": False, "error": str(exc)}
    regenerate_now()
    sys.stderr.write(f"[clone] {source} -> {name}\n")
    return True, {"ok": True, "name": name}


def watcher_loop(broadcast_threadsafe: object, interval: float = 0.25) -> None:
    prev = snapshot()
    while True:
        time.sleep(interval)
        cur = snapshot()
        if cur == prev:
            continue
        changed = sorted(set(prev) ^ set(cur)) + sorted(
            p for p in (set(prev) & set(cur)) if prev[p] != cur[p]
        )
        prev = cur
        needs_regen = any(
            p == GLOBAL_CONFIG or os.path.basename(p) == "theme.json"
            for p in changed
        )
        if needs_regen:
            regenerate_now()
        for p in changed:
            sys.stderr.write(f"[watcher] changed: {p}\n")
        broadcast_threadsafe({"event": "reload", "changed": changed[:8]})


# ---------- WebSocket server ----------

class WSHub:
    def __init__(self) -> None:
        self.clients = set()
        self.loop = None

    async def handler(self, ws: object) -> None:
        self.clients.add(ws)
        try:
            async for _ in ws:
                pass  # we don't expect inbound messages
        except websockets.ConnectionClosed:
            pass
        finally:
            self.clients.discard(ws)

    async def broadcast(self, payload: object) -> None:
        if not self.clients:
            return
        msg = json.dumps(payload)
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    def threadsafe_broadcast(self, payload: object) -> None:
        if self.loop is None:
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(payload), self.loop)


# ---------- main ----------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port",    type=int, default=8765)
    ap.add_argument("--ws-port", type=int, default=8766)
    args = ap.parse_args()

    if not list_themes():
        sys.stderr.write("no themes found under themes/. did you create theme.json?\n")
        sys.exit(1)

    regenerate_now()  # initial bake

    hub = WSHub()

    http_server = ThreadingHTTPServer(("127.0.0.1", args.port), PreviewHandler)
    http_thread = threading.Thread(target=http_server.serve_forever, name="http", daemon=True)
    http_thread.start()

    watch_thread = threading.Thread(
        target=watcher_loop,
        args=(hub.threadsafe_broadcast,),
        name="watcher",
        daemon=True,
    )
    watch_thread.start()

    sys.stderr.write(
        f"Serving on http://127.0.0.1:{args.port}  (ws://127.0.0.1:{args.ws_port})\n"
    )
    sys.stderr.write(f"Themes: {', '.join(list_themes())}\n")

    async def run_ws() -> None:
        hub.loop = asyncio.get_running_loop()
        async with websockets.serve(hub.handler, "127.0.0.1", args.ws_port):
            await asyncio.Future()  # run forever

    try:
        asyncio.run(run_ws())
    except KeyboardInterrupt:
        sys.stderr.write("shutting down\n")
        http_server.shutdown()


if __name__ == "__main__":
    main()
