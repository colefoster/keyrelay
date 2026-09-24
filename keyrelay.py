#!/usr/bin/env python3
"""One-time, tailnet-only credential handoff for CLI commands."""

import argparse
import html
import ipaddress
import json
import os
import secrets
import shlex
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


MAX_BODY = 65536
TTL = 300
POLL_SECONDS = 2
requests = {}
lock = threading.Lock()


def reply(handler, status, data, content_type="application/json; charset=utf-8"):
    body = json.dumps(data).encode() if content_type.startswith("application/json") else data.encode()
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.end_headers()
    handler.wfile.write(body)


def api(url, method="GET", data=None, token=None):
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    payload = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            message = json.load(exc)["error"]
        except (ValueError, KeyError):
            message = exc.reason
        raise RuntimeError("broker: " + str(message)) from None


def page(item, request_id):
    status = "Ready for a secret" if item["status"] == "waiting" else "This request is no longer available"
    active = item["status"] == "waiting"
    form = """
      <form id="form" autocomplete="off">
        <label for="secret">Token or key</label>
        <input id="secret" type="password" autocomplete="off" spellcheck="false" autofocus required>
        <button type="submit">Send once</button>
      </form>
      <p id="message" role="status"></p>
    """ if active else ""
    script = """
      <script>
      const form = document.getElementById('form');
      if (form) form.addEventListener('submit', async event => {
        event.preventDefault();
        const button = form.querySelector('button');
        button.disabled = true;
        const secret = document.getElementById('secret').value;
        try {
          const response = await fetch(location.pathname + '/submit', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({secret})
          });
          if (!response.ok) throw new Error((await response.json()).error);
          document.getElementById('secret').value = '';
          form.remove();
          document.getElementById('message').textContent = 'Sent. You can close this tab.';
        } catch (error) {
          button.disabled = false;
          document.getElementById('message').textContent = error.message;
        }
      });
      </script>
    """ if active else ""
    return """<!doctype html><html lang="en"><meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1">
      <title>Keyrelay</title><style>
      body{background:#101820;color:#f1f5f9;font:16px system-ui;margin:0;min-height:100vh;display:grid;place-items:center}
      main{box-sizing:border-box;width:min(34rem,100%);padding:2rem}
      .eyebrow{color:#67e8f9;font-size:.85rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
      h1{font-size:2rem;margin:.4rem 0 1.5rem}dl{background:#1e293b;border-radius:12px;padding:1rem 1.2rem;overflow-wrap:anywhere}
      dt{color:#94a3b8;font-size:.85rem;margin-top:.8rem}dt:first-child{margin-top:0}dd{margin:.2rem 0 0;font-family:ui-monospace,monospace}
      label{display:block;margin:1.4rem 0 .5rem}input,button{box-sizing:border-box;width:100%;padding:.85rem;border-radius:8px;font:inherit}
      input{background:#fff;border:0;color:#111827}button{background:#67e8f9;border:0;color:#082f49;font-weight:700;margin-top:.8rem;cursor:pointer}
      button:disabled{opacity:.5}p{color:#cbd5e1;line-height:1.5}#message{color:#67e8f9}
      </style><main><div class="eyebrow">One-time credential handoff</div>
      <h1>""" + html.escape(status) + """</h1><p>Review the command before supplying the secret. The request expires after five minutes.</p>
      <dl><dt>Environment variable / input</dt><dd>""" + html.escape(item["target"]) + """</dd>
      <dt>Command</dt><dd>""" + html.escape(item["command"]) + """</dd>
      <dt>Request</dt><dd>""" + html.escape(request_id) + """</dd></dl>""" + form + script + "</main></html>"


def home_page():
    return """<!doctype html><html lang="en"><meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1">
      <title>Keyrelay</title><style>
      body{background:#101820;color:#f1f5f9;font:16px system-ui;margin:0;min-height:100vh;display:grid;place-items:center}
      main{box-sizing:border-box;width:min(34rem,100%);padding:2rem}
      span{color:#67e8f9;font-size:.85rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
      h1{font-size:2rem;margin:.4rem 0 1rem}p{color:#cbd5e1;line-height:1.6}
      </style><main><span>Tailnet only</span><h1>Keyrelay is ready</h1>
      <p>Ask your coding agent to use Keyrelay when a command needs a token or key. It will give you a one-time link to enter the credential here.</p>
      </main></html>"""


def tailnet_login(ip):
    try:
        if ipaddress.ip_address(ip) not in ipaddress.ip_network("100.64.0.0/10"):
            return None
        result = subprocess.run(["tailscale", "whois", "--json", ip], capture_output=True, text=True, timeout=3)
        if result.returncode:
            return None
        return json.loads(result.stdout).get("UserProfile", {}).get("LoginName")
    except (ValueError, OSError, subprocess.TimeoutExpired):
        return None


def handler_factory(allowed_email, auth_mode="serve"):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Never log request URLs or headers; they may contain sensitive metadata.
            pass

        def authorized(self):
            if auth_mode == "serve":
                login = self.headers.get("Tailscale-User-Login")
            else:
                if self.headers.get("Host") != "keyrelay.colefoster.ca":
                    return False
                login = tailnet_login(self.headers.get("X-Real-IP", ""))
            return (login or "").lower() == allowed_email.lower()

        def read_json(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_BODY or self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                    raise ValueError()
                return json.loads(self.rfile.read(size))
            except (ValueError, json.JSONDecodeError):
                return None

        def route(self):
            if not self.authorized():
                return reply(self, 403, {"error": "Tailscale user is not allowed"})
            origin = self.headers.get("Origin")
            if self.command == "POST" and origin and urllib.parse.urlsplit(origin).netloc != self.headers.get("Host"):
                return reply(self, 403, {"error": "Invalid origin"})
            path = urllib.parse.urlsplit(self.path).path
            if self.command == "GET" and path == "/":
                return reply(self, 200, home_page(), "text/html; charset=utf-8")
            if self.command == "GET" and path == "/health":
                return reply(self, 200, {"ok": True})
            if self.command == "POST" and path == "/api/requests":
                body = self.read_json()
                if not isinstance(body, dict) or not isinstance(body.get("command"), str) or not isinstance(body.get("target"), str):
                    return reply(self, 400, {"error": "Invalid request"})
                if not 0 < len(body["command"]) <= 2000 or not 0 < len(body["target"]) <= 100:
                    return reply(self, 400, {"error": "Invalid request"})
                request_id = secrets.token_urlsafe(18)
                token = secrets.token_urlsafe(32)
                with lock:
                    self.cleanup()
                    if len(requests) >= 100:
                        return reply(self, 429, {"error": "Too many pending requests"})
                    requests[request_id] = {"token": token, "secret": None, "status": "waiting", "expires": time.monotonic() + TTL, "command": body["command"], "target": body["target"]}
                return reply(self, 201, {"id": request_id, "token": token, "expires_in": TTL})
            parts = path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] == "r":
                request_id = parts[1]
                with lock:
                    self.cleanup()
                    item = requests.get(request_id)
                    if not item:
                        return reply(self, 404, {"error": "Request expired or missing"})
                    if self.command == "GET" and len(parts) == 2:
                        return reply(self, 200, page(item, request_id), "text/html; charset=utf-8")
                    if self.command == "POST" and len(parts) == 3 and parts[2] == "submit":
                        body = self.read_json()
                        if item["status"] != "waiting" or not isinstance(body, dict) or not isinstance(body.get("secret"), str) or not 0 < len(body["secret"]) <= 16384:
                            return reply(self, 400, {"error": "Invalid or already used request"})
                        item["secret"] = body["secret"]
                        item["status"] = "ready"
                        return reply(self, 200, {"ok": True})
            if len(parts) == 3 and parts[0] == "api" and parts[1] == "requests":
                request_id = parts[2]
                with lock:
                    self.cleanup()
                    item = requests.get(request_id)
                    bearer = self.headers.get("Authorization", "")
                    if not item or not secrets.compare_digest(bearer, "Bearer " + item["token"]):
                        return reply(self, 404, {"error": "Request expired or missing"})
                    if self.command == "GET":
                        return reply(self, 200, {"status": item["status"]})
                    if self.command == "POST":
                        if item["status"] != "ready":
                            return reply(self, 409, {"error": "Secret not ready"})
                        secret = item["secret"]
                        del requests[request_id]
                        return reply(self, 200, {"secret": secret})
            return reply(self, 404, {"error": "Not found"})

        @staticmethod
        def cleanup():
            now = time.monotonic()
            for request_id, item in list(requests.items()):
                if item["expires"] < now:
                    del requests[request_id]

        do_GET = route
        do_POST = route

    return Handler


def run(args):
    command = args.command[1:] if args.command and args.command[0] == "--" else args.command
    if not command:
        raise RuntimeError("Provide a command after --")
    if args.env and not args.env.isidentifier():
        raise RuntimeError("Environment variable name must be an identifier")
    base = args.url.rstrip("/")
    if not base.startswith("https://") and not (args.allow_http and base.startswith("http://127.0.0.1:")):
        raise RuntimeError("Broker URL must use HTTPS")
    target = args.env or "standard input"
    display = shlex.join(command)
    created = api(base + "/api/requests", "POST", {"command": display, "target": target})
    request_id, token = created["id"], created["token"]
    print("Open " + base + "/r/" + request_id, flush=True)
    print("Waiting up to five minutes for the secret...", flush=True)
    deadline = time.monotonic() + created["expires_in"]
    while time.monotonic() < deadline:
        status = api(base + "/api/requests/" + request_id, token=token)["status"]
        if status == "ready":
            break
        time.sleep(POLL_SECONDS)
    else:
        raise RuntimeError("Request expired")
    secret = api(base + "/api/requests/" + request_id, "POST", {}, token=token)["secret"]
    env = os.environ.copy()
    if args.env:
        env[args.env] = secret
    try:
        result = subprocess.run(command, input=(secret + "\n") if not args.env else None, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        # Redact accidental plain-text echoes before output reaches the model context.
        sys.stdout.write(result.stdout.replace(secret, "[REDACTED]"))
        sys.stderr.write(result.stderr.replace(secret, "[REDACTED]"))
        return result.returncode
    finally:
        del secret
        if args.env:
            env.pop(args.env, None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    serve = sub.add_parser("serve", help="Start the localhost broker")
    serve.add_argument("--email", required=True, help="Only this Tailscale user may use the broker")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--auth", choices=("serve", "whois"), default="serve", help="Identity source: Tailscale Serve header or nginx client IP")
    runner = sub.add_parser("run", help="Request a secret and run a command")
    runner.add_argument("--url", required=True, help="Private broker HTTPS URL")
    mode = runner.add_mutually_exclusive_group(required=True)
    mode.add_argument("--env", help="Inject as this environment variable")
    mode.add_argument("--stdin", action="store_true", help="Pass secret to command on standard input")
    runner.add_argument("--allow-http", action="store_true", help=argparse.SUPPRESS)
    runner.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.action == "serve":
            if args.port < 1 or args.port > 65535:
                raise RuntimeError("Invalid port")
            server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_factory(args.email, args.auth))
            print("Listening on 127.0.0.1:%d" % args.port, flush=True)
            server.serve_forever()
        else:
            return run(args)
    except (RuntimeError, urllib.error.URLError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
