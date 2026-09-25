#!/usr/bin/env python3
"""AULA keyboard driver — offline local server.

Serves the mirrored frontend (originally https://hev.aulacn.com/#/)
locally, and proxies + caches CDN / API requests:

  /                       -> offline/index.html (this dir)
  /static/*, /*.wasm      -> local files
  /cdn_static/*           -> local cdn_static/*, else fetch
                             https://static.driveall.cn/static/* and cache
  /cfg/*                  -> local cfg_cache/*, else fetch
                             https://config.driveall.cn/* and cache
  /api/*                  -> proxy to https://cp.driveall.cn/api/* (no cache)

Patched JS expects these prefixes (see static/js/*.js, backups in *.orig).
First run ONLINE to warm the cache for your keyboard model(s),
then the visited pages keep working OFFLINE (except cloud login/share
which needs /api, and the USB daemon on 127.0.0.1:9191 which must run).

Usage:
  python3 server.py [--port 8080] [--offline]
  --offline: never fetch remote, serve cache only (true offline test).
"""
import argparse
import mimetypes
import os
import ssl
import sys
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent
mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("font/ttf", ".ttf")
mimetypes.add_type("image/svg+xml", ".svg")
ssl._create_default_https_context = ssl._create_unverified_context
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"


def fetch_remote(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read(), r.headers.get_content_type()


class Handler(SimpleHTTPRequestHandler):
    offline_only = False

    def log_message(self, fmt, *args):
        sys.stdout.write("[%s] %s\n" % (self.address_string(), fmt % args))

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=3600")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, token")
        self.end_headers()

    def do_GET(self):
        self.route(cache_only=True)

    def do_POST(self):
        self.route(cache_only=False)

    def route(self, cache_only: bool):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/__log":
                return self.collect_log()
            if path.startswith("/api/"):
                return self.proxy_api()
            if path.startswith("/cdn_static/"):
                return self.serve_cached(
                    local=BASE / path.lstrip("/"),
                    remote="https://static.driveall.cn/static/" + path[len("/cdn_static/"):],
                    query=parsed.query,
                )
            if path.startswith("/cfg/"):
                return self.serve_cached(
                    local=BASE / "cfg_cache" / path[len("/cfg/"):],
                    remote="https://config.driveall.cn/" + path[len("/cfg/"):],
                    query=parsed.query,
                )
            # static frontend
            return super().do_GET()
        except BrokenPipeError:
            pass

    def collect_log(self):
        # 临时诊断: 收前端报错, 写到 err-frontend.log
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b""
        try:
            with open(BASE / "err-frontend.log", "a", encoding="utf-8") as f:
                f.write(body.decode(errors="ignore")[:2000] + "\n")
        except Exception as e:
            print("  log write failed: %s" % e)
        self.send_response(204)
        self.end_headers()

    def serve_cached(self, local: Path, remote: str, query: str = ""):
        # path traversal guard
        try:
            local.resolve().relative_to(BASE.resolve())
        except ValueError:
            self.send_error(403)
            return
        if local.is_file():
            self.serve_file(local)
            return
        if self.offline_only:
            self.send_error(404, "offline cache miss: %s" % local.name)
            return
        url = remote + ("?" + query if query else "")
        print("  FETCH %s" % url)
        try:
            data, ctype = fetch_remote(url)
        except urllib.error.HTTPError as e:
            self.send_error(e.code, "remote %s" % url)
            return
        except Exception as e:
            self.send_error(502, "fetch failed: %s" % e)
            return
        local.parent.mkdir(parents=True, exist_ok=True)
        try:
            local.write_bytes(data)
            print("  CACHED %s (%d bytes)" % (local, len(data)))
        except Exception as e:
            print("  cache write failed: %s" % e)
        ctype = ctype or mimetypes.guess_type(str(local))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_file(self, local: Path):
        ctype = mimetypes.guess_type(str(local))[0] or "application/octet-stream"
        data = local.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def proxy_api(self):
        if self.offline_only:
            self.send_error(503, "API disabled in --offline mode")
            return
        target = "https://cp.driveall.cn" + self.path
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else None
        headers = {"User-Agent": UA, "Content-Type": self.headers.get("Content-Type", "application/json")}
        for h in ("Authorization", "token"):
            if self.headers.get(h):
                headers[h] = self.headers[h]
        print("  API %s %s" % (self.command, target))
        try:
            req = urllib.request.Request(target, data=body, headers=headers, method=self.command)
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read()
                self.send_response(r.status)
                self.send_header("Content-Type", r.headers.get_content_type())
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            try:
                data = e.read()
            except Exception:
                data = b""
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if data:
                self.wfile.write(data)
        except Exception as e:
            self.send_error(502, "api proxy failed: %s" % e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--offline", action="store_true", help="serve cache only, no remote fetch")
    args = ap.parse_args()
    Handler.offline_only = args.offline
    os.chdir(BASE)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    mode = "OFFLINE-ONLY (cache)" if args.offline else "ONLINE (cache-on-demand)"
    print("AULA offline driver: http://127.0.0.1:%d/#/  [%s]" % (args.port, mode))
    print("  frontend : %s" % BASE)
    print("  NOTE: keyboard USB control needs the local daemon on 127.0.0.1:9191")
    print("  cloud login/share needs /api (disabled with --offline). Ctrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
