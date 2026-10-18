#!/usr/bin/env python3
"""One-time credential handoff for CLI commands, locally or over a Tailnet."""

import argparse
import html
import json
import os
import secrets
import shlex
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


MAX_BODY = 65536
MAX_SECRET = 16384
MAX_PENDING = 100
TTL = 300
POLL_SECONDS = 2
# Shorter field values would redact ordinary text such as "1" or "yes" throughout the output.
MIN_REDACT = 4
pending = {}
lock = threading.Lock()


def reply(handler, status, data, content_type="application/json; charset=utf-8"):
    body = json.dumps(data).encode() if content_type.startswith("application/json") else data.encode()
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Content-Security-Policy", "default-src 'none'; connect-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
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


HEAD = """<!doctype html><html lang="en"><meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>%s · Keyrelay</title><style>
  body{background:#101820;color:#f1f5f9;font:16px system-ui;margin:0;min-height:100vh;display:grid;place-items:center}
  main{box-sizing:border-box;width:min(34rem,100%%);padding:2rem}
  .eyebrow{color:#67e8f9;font-size:.85rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
  h1{font-size:2rem;margin:.4rem 0 1.5rem}dl{background:#1e293b;border-radius:12px;padding:1rem 1.2rem;overflow-wrap:anywhere}
  dt{color:#94a3b8;font-size:.85rem;margin-top:.8rem}dt:first-child{margin-top:0}dd{margin:.2rem 0 0;font-family:ui-monospace,monospace}
  label{display:block;margin:1.4rem 0 .5rem}input,button{box-sizing:border-box;width:100%%;padding:.85rem;border-radius:8px;font:inherit}
  input{background:#fff;border:0;color:#111827}button{background:#67e8f9;border:0;color:#082f49;font-weight:700;margin-top:.8rem;cursor:pointer}
  button:disabled{opacity:.5;cursor:wait}p{color:#cbd5e1;line-height:1.5}#message{color:#67e8f9}#message.error{color:#fca5a5}
  .hint{font-size:.85rem;margin:.5rem 0 0}input:focus,button:focus-visible,#message:focus-visible{outline:3px solid #67e8f9;outline-offset:3px}
  .instructions{white-space:pre-wrap;overflow-wrap:anywhere}#reveal{background:transparent;color:#cbd5e1;border:1px solid #64748b}
  </style><main><div class="eyebrow">One-time credential handoff</div>"""

FORM = """<form id="form" autocomplete="off" data-bundle="%s">%s
  <p id="hint" class="hint">Sent once, only to this request. The fields clear after every attempt.</p>
  <button type="submit">Send once</button>
  <button id="reveal" type="button" aria-pressed="false">Show values</button>
</form>
<p id="message" role="status" tabindex="-1"></p>"""

SCRIPT = """<script>
const form = document.getElementById('form');
const message = document.getElementById('message');
const reveal = document.getElementById('reveal');
const inputs = [...form.querySelectorAll('input')];
const button = form.querySelector('button');
let sending = false;
function setVisible(visible) {
  inputs.forEach(input => { input.type = visible ? 'text' : 'password'; });
  reveal.textContent = visible ? 'Hide values' : 'Show values';
  reveal.setAttribute('aria-pressed', String(visible));
}
function setDisabled(disabled) {
  inputs.forEach(input => { input.disabled = disabled; });
  reveal.disabled = disabled;
  button.disabled = disabled;
}
function show(text, error) {
  message.textContent = text;
  message.classList.toggle('error', error);
}
reveal.addEventListener('click', () => {
  if (!sending) setVisible(reveal.getAttribute('aria-pressed') !== 'true');
});
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (sending) return;
  sending = true;
  const secret = form.dataset.bundle
    ? JSON.stringify(Object.fromEntries(inputs.map(input => [input.dataset.name, input.value])))
    : inputs[0].value;
  // Clear before sending so no outcome leaves the secret in the page.
  inputs.forEach(input => { input.value = ''; });
  setVisible(false);
  // Disabled so nothing typed while in flight stays in the fields afterward.
  setDisabled(true);
  button.textContent = 'Sending…';
  show('Sending…', false);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  let response = null;
  try {
    response = await fetch(location.pathname + '/submit', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({secret}), signal: controller.signal
    });
  } catch (error) {
    // Network failure or timeout: the broker may still have accepted it.
  } finally {
    clearTimeout(timer);
  }
  sending = false;
  if (response && response.ok) {
    form.remove();
    document.querySelector('h1').textContent = 'Secret sent';
    document.getElementById('intro').textContent = 'Keyrelay accepted the secret for this request. Check your terminal for the command result.';
    document.title = 'Secret sent · Keyrelay';
    show('Sent. The command in your terminal can continue. You can close this tab.', false);
    message.focus();
    return;
  }
  setDisabled(false);
  button.textContent = 'Send once';
  const status = response ? response.status : 0;
  show(
    status === 0 ? 'Could not confirm delivery. It may have arrived: check your terminal before sending again, or reload this page to see whether the request is still waiting.'
    : status === 400 ? 'Not accepted. This request may already have a secret, or a value was empty or too long. Reload this page to check whether it is still waiting.'
    : status === 404 ? 'This request expired or was already completed. Ask your agent for a new link.'
    : status === 403 ? 'Access denied. Open the link on the computer running the command, or with the Tailscale account the broker allows.'
    : 'Not sent (error ' + status + '). Reload this page to check whether the request is still waiting.',
    true);
  inputs[0].focus();
});
</script>"""


def page(item, request_id):
    active = item["status"] == "waiting"
    status = "Ready for a secret" if active else "This request is no longer available"
    if active:
        intro = "Review the command before supplying the secret. The request expires after five minutes."
    else:
        intro = "A secret was already sent for this request. Check your terminal; if you need to try again, ask your agent for a new link."
    body = ""
    if active:
        # A single-key request is one field whose raw value is sent; labeled fields send a JSON object.
        fields = item["fields"] or [{"name": "secret", "label": "Token or key"}]
        inputs = "".join(
            '\n  <label for="field-%d">%s</label><input id="field-%d" data-name="%s" type="password" autocomplete="off" spellcheck="false" required%s aria-describedby="hint%s">%s'
            % (i, html.escape(field["label"]), i, html.escape(field["name"], quote=True), " autofocus" if i == 0 else "",
               " help-%d" % i if field.get("help") else "",
               '<p id="help-%d" class="hint instructions">%s</p>' % (i, html.escape(field["help"])) if field.get("help") else "")
            for i, field in enumerate(fields))
        if item["note"]:
            body = '<p class="instructions">' + html.escape(item["note"]) + "</p>"
        body += FORM % ("1" if item["fields"] else "", inputs) + SCRIPT
    return (HEAD % html.escape(status) + "<h1>" + html.escape(status) + '</h1><p id="intro">' + intro + "</p>"
            + "<dl><dt>Environment variable / input</dt><dd>" + html.escape(item["target"]) + "</dd>"
            + "<dt>Command</dt><dd>" + html.escape(item["command"]) + "</dd>"
            + "<dt>Request</dt><dd>" + html.escape(request_id) + "</dd></dl>" + body + "</main></html>")


def home_page():
    return (HEAD % "Ready" + "<h1>Keyrelay is ready</h1><p>Ask your coding agent to use Keyrelay when a command needs"
            " a token or key. It will give you a one-time link to enter the credential here.</p></main></html>")


def valid_field(field):
    return (isinstance(field, dict) and {"name", "label"} <= set(field) <= {"name", "label", "help"}
            and isinstance(field["name"], str) and field["name"].isascii() and field["name"].isidentifier()
            and len(field["name"]) <= 100 and isinstance(field["label"], str) and 0 < len(field["label"]) <= 100
            and isinstance(field.get("help", ""), str) and len(field.get("help", "")) <= 1000)


def handler_factory(allowed_email=None, host=None):
    """Local mode when allowed_email is None; otherwise Tailscale Serve mode for that login at that exact host."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Never log request URLs or headers; they may contain sensitive metadata.
            pass

        def handle(self):
            try:
                super().handle()
            except ConnectionError:
                # A cancelled runner drops its poll mid-reply; socketserver would print a traceback to stderr.
                pass

        def login(self):
            # Trustworthy only behind Tailscale Serve, which sets this header and replaces client-supplied copies.
            return self.headers.get("Tailscale-User-Login")

        def authorized(self):
            if allowed_email is None:
                # Exact authority prevents DNS rebinding; do not trust proxy headers.
                expected = "127.0.0.1:%d" % self.server.server_port
                return self.client_address[0] == "127.0.0.1" and self.headers.get("Host") == expected
            return self.headers.get("Host") == host and (self.login() or "").lower() == allowed_email.lower()

        def read_json(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_BODY or self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                    raise ValueError()
                return json.loads(self.rfile.read(size))
            except ValueError:
                return None

        def route(self):
            if not self.authorized():
                return reply(self, 403, {"error": "Local access denied" if allowed_email is None else "Tailscale user is not allowed"})
            origin = self.headers.get("Origin")
            if self.command == "POST" and origin and urllib.parse.urlsplit(origin).netloc != self.headers.get("Host"):
                return reply(self, 403, {"error": "Invalid origin"})
            path = urllib.parse.urlsplit(self.path).path
            parts = path.strip("/").split("/")
            with lock:
                now = time.monotonic()
                for request_id in [key for key, item in pending.items() if item["expires"] < now]:
                    del pending[request_id]
                if self.command == "GET" and path == "/":
                    return reply(self, 200, home_page(), "text/html; charset=utf-8")
                if self.command == "GET" and path == "/health":
                    return reply(self, 200, {"ok": True})
                if self.command == "POST" and path == "/api/requests":
                    return self.create()
                if len(parts) in (2, 3) and parts[0] == "r":
                    return self.browser(parts)
                if len(parts) == 3 and parts[:2] == ["api", "requests"]:
                    return self.claim(parts[2])
            return reply(self, 404, {"error": "Not found"})

        def create(self):
            body = self.read_json()
            if (not isinstance(body, dict) or not isinstance(body.get("command"), str) or not isinstance(body.get("target"), str)
                    or not 0 < len(body["command"]) <= 2000 or not 0 < len(body["target"]) <= 100):
                return reply(self, 400, {"error": "Invalid request"})
            fields, note = body.get("fields", []), body.get("note", "")
            if not isinstance(note, str) or len(note) > 2000:
                return reply(self, 400, {"error": "Invalid note (maximum 2000 characters)"})
            if (not isinstance(fields, list) or len(fields) > 16 or not all(valid_field(f) for f in fields)
                    or len({f["name"] for f in fields}) != len(fields)):
                return reply(self, 400, {"error": "Invalid fields"})
            if len(pending) >= MAX_PENDING:
                return reply(self, 429, {"error": "Too many pending requests"})
            request_id, token = secrets.token_urlsafe(18), secrets.token_urlsafe(32)
            pending[request_id] = {"token": token, "secret": None, "status": "waiting", "expires": time.monotonic() + TTL,
                                   "command": body["command"], "target": body["target"], "fields": fields, "note": note}
            return reply(self, 201, {"id": request_id, "token": token, "expires_in": TTL, "field_count": len(fields), "supports_notes": True})

        def browser(self, parts):
            item = pending.get(parts[1])
            if not item:
                return reply(self, 404, {"error": "Request expired or missing"})
            if self.command == "GET" and len(parts) == 2:
                return reply(self, 200, page(item, parts[1]), "text/html; charset=utf-8")
            if self.command != "POST" or parts[2:] != ["submit"]:
                return reply(self, 404, {"error": "Not found"})
            body = self.read_json()
            if item["status"] != "waiting" or not isinstance(body, dict) or not isinstance(body.get("secret"), str) or not 0 < len(body["secret"]) <= MAX_SECRET:
                return reply(self, 400, {"error": "Invalid or already used request"})
            if item["fields"]:
                try:
                    values = json.loads(body["secret"])
                    if (not isinstance(values, dict) or set(values) != {f["name"] for f in item["fields"]}
                            or any(not isinstance(v, str) or not v or "\x00" in v for v in values.values())):
                        raise ValueError()
                except (ValueError, TypeError):
                    return reply(self, 400, {"error": "All credential fields are required"})
            item["secret"], item["status"] = body["secret"], "ready"
            return reply(self, 200, {"ok": True})

        def claim(self, request_id):
            item = pending.get(request_id)
            if not item or not secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + item["token"]):
                return reply(self, 404, {"error": "Request expired or missing"})
            if self.command == "GET":
                return reply(self, 200, {"status": item["status"]})
            if item["status"] != "ready":
                return reply(self, 409, {"error": "Secret not ready"})
            del pending[request_id]
            return reply(self, 200, {"secret": item["secret"]})

        do_GET = route
        do_POST = route

    return Handler


class Terminated(Exception):
    pass


def terminate(signum, frame):
    raise Terminated()


def parse_fields(args):
    fields = []
    for specification in args.field:
        name, separator, label = specification.partition("=")
        if not separator:
            raise RuntimeError("Fields use NAME=Label")
        fields.append({"name": name, "label": label})
    for specification in args.field_help:
        name, separator, help_text = specification.partition("=")
        matches = [field for field in fields if field["name"] == name]
        if not separator or len(matches) != 1 or "help" in matches[0] or not help_text or len(help_text) > 1000:
            raise RuntimeError("Field help uses NAME=Instructions for one existing field, once per field (maximum 1000 characters)")
        matches[0]["help"] = help_text
    if len(args.note) > 2000:
        raise RuntimeError("Note must be at most 2000 characters")
    return fields


def request_secret(base, args, command, fields):
    created = api(base + "/api/requests", "POST", {"command": shlex.join(command), "target": args.env or "standard input",
                                                   "fields": fields, "note": args.note})
    if (args.note or args.field_help) and not created.get("supports_notes"):
        raise RuntimeError("Broker does not support instructions; update the broker first")
    if fields and created.get("field_count") != len(fields):
        raise RuntimeError("Broker does not support labeled fields; update the broker first")
    request_id, token = created["id"], created["token"]
    print("Open " + base + "/r/" + request_id, flush=True)
    print("Waiting up to five minutes for the secret...", flush=True)
    deadline = time.monotonic() + created["expires_in"]
    while api(base + "/api/requests/" + request_id, token=token)["status"] != "ready":
        if time.monotonic() >= deadline:
            raise RuntimeError("Request expired")
        time.sleep(POLL_SECONDS)
    return api(base + "/api/requests/" + request_id, "POST", {}, token=token)["secret"]


def run(args):
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        raise RuntimeError("Provide a command after --")
    if args.env and not args.env.isidentifier():
        raise RuntimeError("Environment variable name must be an identifier")
    fields = parse_fields(args)
    server = None
    if args.url:
        base = args.url.rstrip("/")
        if not base.startswith("https://") and not (args.allow_http and base.startswith("http://127.0.0.1:")):
            raise RuntimeError("Broker URL must use HTTPS")
    else:
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory())
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % server.server_port
    try:
        secret = request_secret(base, args, command, fields)
    finally:
        if server:
            server.shutdown()
            server.server_close()
            with lock:
                pending.clear()
    env = dict(os.environ, **{args.env: secret}) if args.env else None
    # Raising inside subprocess.run makes it kill and reap the command instead of orphaning it.
    previous_sigterm = signal.signal(signal.SIGTERM, terminate)
    try:
        # POSIX encodes the environment with fsencode; use the same bytes for stdin and for redaction.
        result = subprocess.run(command, input=None if args.env else os.fsencode(secret) + b"\n",
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)
    # Redact accidental plain-text echoes before output reaches the model context.
    values = [os.fsencode(value) for value in json.loads(secret).values()] if fields else []
    redactions = sorted({os.fsencode(secret)} | {value for value in values if len(value) >= MIN_REDACT}, key=len, reverse=True)
    for stream, data in ((sys.stdout, result.stdout), (sys.stderr, result.stderr)):
        for value in redactions:
            data = data.replace(value, b"[REDACTED]")
        stream.flush()
        stream.buffer.write(data)
        stream.flush()
    # Report a signal-terminated command the way a shell does (128 + signal number).
    return 128 - result.returncode if result.returncode < 0 else result.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    serve = sub.add_parser("serve", help="Start a broker on localhost for Tailscale Serve")
    serve.add_argument("--email", required=True, help="Only this Tailscale user may use the broker")
    serve.add_argument("--host", required=True, help="Exact Host header to accept, such as broker.your-tailnet.ts.net")
    serve.add_argument("--port", type=int, default=8765)
    runner = sub.add_parser("run", help="Request a secret and run a command")
    runner.add_argument("--url", help="Optional private broker HTTPS URL; omit for a temporary local broker")
    mode = runner.add_mutually_exclusive_group(required=True)
    mode.add_argument("--env", help="Inject as this environment variable")
    mode.add_argument("--stdin", action="store_true", help="Pass secret to command on standard input")
    runner.add_argument("--field", action="append", default=[], metavar="NAME=Label", help="Add a labeled credential field; delivers a JSON object through --env or --stdin")
    runner.add_argument("--note", default="", metavar="Instructions", help="Instructions above the form (plain text, maximum 2000 characters; never include secrets)")
    runner.add_argument("--field-help", action="append", default=[], metavar="NAME=Instructions", help="Help below a named --field (plain text, maximum 1000 characters; never include secrets)")
    runner.add_argument("--allow-http", action="store_true", help=argparse.SUPPRESS)
    runner.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.action == "serve":
            if args.port < 1 or args.port > 65535:
                raise RuntimeError("Invalid port")
            server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_factory(args.email, args.host))
            print("Listening on 127.0.0.1:%d for %s" % (args.port, args.host), flush=True)
            server.serve_forever()
            return 0
        return run(args)
    except KeyboardInterrupt:
        return 130
    except Terminated:
        return 128 + signal.SIGTERM
    except (RuntimeError, urllib.error.URLError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
