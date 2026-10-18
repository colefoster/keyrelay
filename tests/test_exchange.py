"""Security properties of `keyrelay exchange`, tested against a local Immich stub with made-up values."""

import base64
import html
import json
import os
import re
import select
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO, TextIOWrapper
from pathlib import Path
from unittest.mock import patch

import keyrelay

ROOT = Path(__file__).resolve().parents[1]
EMAIL = "admin@example.test"
PASSWORD = "fake-Pa55word-for-tests"
API_KEY = "stub-immich-api-key-0001"


class ImmichStub(BaseHTTPRequestHandler):
    """Implements the four Immich endpoints the example uses. Records requests and the process table."""

    state = None

    def log_message(self, format, *args):
        pass

    def send(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/server/config":
            return self.send(200, {"isInitialized": self.state["admin"] is not None})
        self.send(404, {"message": "Not found"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        state = self.state
        state["calls"].append(self.path)
        if self.path == "/api/auth/admin-sign-up":
            if state["admin"]:
                return self.send(400, {"message": "The server already has an admin"})
            state["admin"] = body
            return self.send(201, {"id": "user-1", "email": body["email"]})
        if self.path == "/api/auth/login":
            # The target command is running now: snapshot every process's argv and environment.
            state["ps"] = subprocess.run(["ps", "axeww", "-o", "args="], capture_output=True).stdout
            admin = state["admin"]
            if not admin or (body.get("email"), body.get("password")) != (admin["email"], admin["password"]):
                return self.send(401, {"message": "Incorrect email or password"})
            state["session"] = "stub-session-token"
            return self.send(201, {"accessToken": state["session"], "userId": "user-1"})
        bearer = self.headers.get("Authorization")
        if bearer != "Bearer " + str(state.get("session")):
            return self.send(401, {"message": "Authentication required"})
        if self.path == "/api/api-keys":
            state["key_request"] = body
            return self.send(201, {"secret": API_KEY, "apiKey": {"id": "key-1", "name": body["name"], "permissions": body["permissions"]}})
        if self.path == "/api/auth/logout":
            state["session"] = None
            return self.send(200, {"successful": True})
        self.send(404, {"message": "Not found"})


def stub_server():
    state = {"admin": None, "calls": [], "session": None}
    handler = type("Stub", (ImmichStub,), {"state": state})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, state, "http://127.0.0.1:%d" % server.server_port


def read_link(stream):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if os.name != "nt" and not select.select([stream], [], [], 10)[0]:
            break
        line = stream.readline()
        match = re.match(r"Open (http://127\.0\.0\.1:\d+/r/[\w-]+)", line)
        if match:
            return match.group(1)
    raise AssertionError("No startup link")


def submit(url, values):
    base = url.split("/r/")[0]
    body = json.dumps({"secret": json.dumps(values)}).encode()
    req = urllib.request.Request(url + "/submit", data=body, headers={"Content-Type": "application/json", "Origin": base})
    with urllib.request.urlopen(req, timeout=5) as response:
        return response.status


def encodings(value):
    raw = value.encode()
    return [raw, urllib.parse.quote(value, safe="").encode(), base64.b64encode(raw).rstrip(b"=")]


@unittest.skipIf(os.name == "nt", "exchange needs POSIX file descriptors")
class ExchangeEndToEndTest(unittest.TestCase):
    def setUp(self):
        self.server, self.state, self.immich = stub_server()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def exchange(self, command, extra=(), url=None, field_visible=True):
        args = [sys.executable, str(ROOT / "keyrelay.py"), "exchange",
                "--action", "Create the Immich admin account and an API key",
                "--host", self.immich, "--returns", "A new Immich API key named agent",
                "--field", "email=Admin email", "--field", "password=Admin password", *extra]
        if field_visible:
            args += ["--field-visible", "email"]
        if url:
            args += ["--url", url, "--allow-http"]
        env = dict(os.environ, TMPDIR=self.tmp.name, HOME=self.tmp.name)
        child = subprocess.Popen([*args, "--", *command], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, cwd=self.tmp.name, env=env)
        self.addCleanup(lambda: child.poll() is None and (child.kill(), child.communicate()))
        return child, read_link(child.stderr)

    def immich_command(self):
        return [sys.executable, str(ROOT / "examples/immich_api_key.py"), "--url", self.immich, "--signup", "--key-name", "agent"]

    def assert_no_secret(self, *blobs):
        for blob in blobs:
            blob = blob.encode() if isinstance(blob, str) else blob
            for form in encodings(PASSWORD):
                self.assertNotIn(form, blob)

    def test_immich_signup_returns_only_the_api_key(self):
        command = self.immich_command()
        child, url = self.exchange(command)
        with urllib.request.urlopen(url, timeout=5) as response:
            review = response.read().decode()
        # The review screen shows the real command, host, action, and what comes back.
        self.assertIn(html.escape(shlex.join(command)), review)
        self.assertIn(html.escape(self.immich), review)
        self.assertIn("Create the Immich admin account and an API key", review)
        self.assertIn("A new Immich API key named agent", review)
        self.assertIn("Approve and send once", review)
        self.assertIn('data-name="email" type="text" data-visible="1"', review)
        self.assertIn('data-name="password" type="password"', review)
        self.assertEqual(submit(url, {"email": EMAIL, "password": PASSWORD}), 200)
        output, errors = child.communicate(timeout=20)
        self.assertEqual(child.returncode, 0, errors)
        report = json.loads(output)
        self.assertEqual(report, {"ok": True, "exit_code": 0, "result": {
            "apiKey": API_KEY, "id": "key-1", "name": "agent", "permissions": ["all"], "url": self.immich}})
        self.assertIn("Signed out", errors)
        # The command really used the password; the agent-facing streams never saw it.
        self.assertEqual(self.state["admin"]["password"], PASSWORD)
        self.assertEqual(self.state["calls"], ["/api/auth/admin-sign-up", "/api/auth/login", "/api/api-keys", "/api/auth/logout"])
        self.assertIsNone(self.state["session"])
        self.assert_no_secret(output, errors, url)
        self.assertNotIn(EMAIL, output + errors)
        # No process's argv or environment held the password while the command ran.
        self.assertTrue(self.state["ps"])
        self.assert_no_secret(self.state["ps"])
        # Nothing was written to the temporary directory, home, or working directory.
        for path in Path(self.tmp.name).rglob("*"):
            if path.is_file():
                self.assert_no_secret(path.read_bytes())
        # The local broker is gone with the request.
        with self.assertRaises(urllib.error.URLError):
            urllib.request.urlopen(url, timeout=2)

    def test_wrong_password_reports_failure_without_echo(self):
        self.state["admin"] = {"email": EMAIL, "password": "the-real-one"}
        command = [sys.executable, str(ROOT / "examples/immich_api_key.py"), "--url", self.immich]
        child, url = self.exchange(command)
        submit(url, {"email": EMAIL, "password": PASSWORD})
        output, errors = child.communicate(timeout=20)
        self.assertEqual(child.returncode, 1)
        report = json.loads(output)
        self.assertFalse(report["ok"])
        self.assertNotIn("result", report)
        self.assertIn("HTTP 401", errors)
        self.assert_no_secret(output, errors)

    def test_log_is_redacted_and_leaking_result_is_withheld(self):
        code = ("import base64,json,os,sys,urllib.parse; v=json.loads(sys.stdin.readline()); p=v['password'];"
                "print('raw', p); print('url', urllib.parse.quote(p, safe='')); print('b64', base64.b64encode(p.encode()).decode());"
                "print('basic', base64.b64encode((v['email']+':'+p).encode()).decode());"
                "print('json', json.dumps(v), file=sys.stderr);"
                "os.write(int(os.environ['KEYRELAY_RESULT_FD']), json.dumps({'token': 'derived', 'oops': p}).encode())")
        child, url = self.exchange([sys.executable, "-c", code])
        submit(url, {"email": EMAIL, "password": PASSWORD})
        output, errors = child.communicate(timeout=20)
        self.assertEqual(child.returncode, 1)
        report = json.loads(output)
        self.assertEqual(report["error"], "The result contained a value you typed; withheld")
        self.assertNotIn("result", report)
        self.assertEqual(errors.count("[REDACTED]"), 5, errors)
        self.assert_no_secret(output, errors)
        self.assertNotIn(base64.b64encode((EMAIL + ":" + PASSWORD).encode()).decode().rstrip("="), errors)

    def test_missing_or_invalid_result(self):
        for code, message in (("pass", "wrote no result"),
                              ("import os; os.write(int(os.environ['KEYRELAY_RESULT_FD']), b'not json')", "not valid UTF-8 JSON")):
            with self.subTest(message=message):
                child, url = self.exchange([sys.executable, "-c", code])
                submit(url, {"email": EMAIL, "password": PASSWORD})
                output, _ = child.communicate(timeout=20)
                self.assertEqual(child.returncode, 1)
                self.assertIn(message, json.loads(output)["error"])

    def test_remote_broker_url(self):
        # Stands in for Tailscale Serve, which adds the identity header in front of a localhost broker.
        base = keyrelay.handler_factory("owner@example.com", "serve")

        class Serve(base):
            def parse_request(self):
                ok = super().parse_request()
                if ok:
                    del self.headers["Tailscale-User-Login"]
                    self.headers["Tailscale-User-Login"] = "owner@example.com"
                return ok

        broker = ThreadingHTTPServer(("127.0.0.1", 0), Serve)
        threading.Thread(target=broker.serve_forever, daemon=True).start()
        self.addCleanup(broker.server_close)
        self.addCleanup(broker.shutdown)
        self.addCleanup(keyrelay.requests.clear)
        remote = "http://127.0.0.1:%d" % broker.server_port
        child, url = self.exchange(self.immich_command(), url=remote)
        self.assertTrue(url.startswith(remote + "/r/"))
        submit(url, {"email": EMAIL, "password": PASSWORD})
        output, errors = child.communicate(timeout=20)
        self.assertEqual(json.loads(output)["result"]["apiKey"], API_KEY, errors)
        self.assert_no_secret(output, errors)
        # The persistent broker deleted the claimed request.
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(url, timeout=2)
        self.assertEqual(error.exception.code, 404)


class ExchangeBrokerTest(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), keyrelay.handler_factory(None, "local"))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.server.server_port
        self.addCleanup(keyrelay.requests.clear)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, path, method="GET", body=None, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                content = response.read().decode()
                return response.status, json.loads(content) if response.headers["Content-Type"].startswith("application/json") else content
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def body(self, **changes):
        body = {"command": "tool --login", "target": "standard input (JSON)", "kind": "exchange",
                "action": "Sign in", "host": "https://app.example.test", "returns": "A session token",
                "fields": [{"name": "user", "label": "User", "visible": True}, {"name": "password", "label": "Password"}]}
        body.update(changes)
        return body

    def test_requires_a_complete_description(self):
        for changes in ({"action": ""}, {"host": None}, {"returns": "x" * 501}, {"fields": []},
                        {"kind": "other"}, {"fields": [{"name": "a", "label": "A", "visible": "yes"}]}):
            with self.subTest(changes=changes):
                self.assertEqual(self.request("/api/requests", "POST", self.body(**changes))[0], 400)

    def test_one_time_use(self):
        status, created = self.request("/api/requests", "POST", self.body())
        self.assertEqual(status, 201)
        self.assertTrue(created["supports_exchange"])
        path = "/r/" + created["id"]
        values = json.dumps({"user": "u", "password": PASSWORD})
        self.assertEqual(self.request(path + "/submit", "POST", {"secret": values})[0], 200)
        self.assertEqual(self.request(path + "/submit", "POST", {"secret": values})[0], 400)
        used = self.request(path)[1]
        self.assertNotIn("<form", used)
        self.assertNotIn(PASSWORD, used)
        claim = "/api/requests/" + created["id"]
        self.assertEqual(self.request(claim, "POST", {}, token=created["token"])[1]["secret"], values)
        self.assertEqual(self.request(claim, "POST", {}, token=created["token"])[0], 404)
        self.assertEqual(self.request(path)[0], 404)

    def test_expires(self):
        _, created = self.request("/api/requests", "POST", self.body())
        later = time.monotonic() + keyrelay.TTL + 1
        with patch.object(keyrelay.time, "monotonic", return_value=later):
            self.assertEqual(self.request("/r/" + created["id"])[0], 404)
            values = json.dumps({"user": "u", "password": PASSWORD})
            self.assertEqual(self.request("/r/" + created["id"] + "/submit", "POST", {"secret": values})[0], 404)

    def test_review_escapes_metadata(self):
        _, created = self.request("/api/requests", "POST", self.body(command="<b>x</b>", action="<script>y</script>"))
        page = self.request("/r/" + created["id"])[1]
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", page)
        self.assertIn("&lt;script&gt;y&lt;/script&gt;", page)
        self.assertNotIn("<script>y", page)


@unittest.skipIf(os.name == "nt", "exchange needs POSIX file descriptors")
class ExchangeRunnerTest(unittest.TestCase):
    def args(self, **changes):
        values = dict(url="https://broker.example.ts.net", allow_http=False, command=["--", sys.executable, "-c", "raise SystemExit('must not run')"],
                      action="Sign in", host="https://app.example.test", returns="A token", field=["password=Password"],
                      field_visible=[], field_help=[], note="")
        values.update(changes)
        return Namespace(**values)

    def test_expired_request_never_runs_command(self):
        errors = TextIOWrapper(BytesIO())
        with patch.object(keyrelay, "api", side_effect=[{"id": "i", "token": "t", "expires_in": 0, "field_count": 1, "supports_exchange": True}]), \
                patch.object(keyrelay.subprocess, "Popen") as popen, redirect_stderr(errors):
            with self.assertRaisesRegex(RuntimeError, "Request expired"):
                keyrelay.exchange(self.args())
            popen.assert_not_called()

    def test_refuses_broker_without_exchange(self):
        with patch.object(keyrelay, "api", side_effect=[{"id": "i", "token": "t", "expires_in": 300, "field_count": 1}]) as api, \
                redirect_stderr(TextIOWrapper(BytesIO())):
            with self.assertRaisesRegex(RuntimeError, "update the broker"):
                keyrelay.exchange(self.args())
            self.assertEqual(api.call_count, 1)

    def test_validates_before_contacting_broker(self):
        for changes, message in (({"action": ""}, "--action"), ({"field": []}, "--field"),
                                 ({"field_visible": ["missing"]}, "--field-visible"), ({"command": []}, "command")):
            with self.subTest(message=message), patch.object(keyrelay, "api") as api:
                with self.assertRaisesRegex(RuntimeError, message):
                    keyrelay.exchange(self.args(**changes))
                api.assert_not_called()

    def test_secret_is_not_in_argv_or_environment(self):
        seen = {}

        def popen(command, **kwargs):
            seen.update(command=command, env=kwargs["env"], stdin=kwargs["stdin"])
            raise OSError("stop before running")

        responses = [{"id": "i", "token": "t", "expires_in": 300, "field_count": 1, "supports_exchange": True},
                     {"status": "ready"}, {"secret": json.dumps({"password": PASSWORD})}]
        with patch.object(keyrelay, "api", side_effect=responses), patch.object(keyrelay.subprocess, "Popen", side_effect=popen), \
                redirect_stdout(TextIOWrapper(BytesIO())), redirect_stderr(TextIOWrapper(BytesIO())):
            with self.assertRaises(OSError):
                keyrelay.exchange(self.args(command=["tool", "--flag"]))
        self.assertEqual(seen["command"], ["tool", "--flag"])
        self.assertEqual(seen["stdin"], subprocess.PIPE)
        self.assertNotIn(PASSWORD, json.dumps(seen["env"]))


@unittest.skipIf(os.name == "nt", "exchange needs POSIX file descriptors")
class ExchangePageScriptTest(unittest.TestCase):
    def test_visible_field_stays_visible_and_values_clear(self):
        item = {"status": "waiting", "kind": "exchange", "target": "standard input (JSON)", "command": "tool",
                "action": "Sign in", "host": "https://app.example.test", "returns": "A token",
                "fields": [{"name": "user", "label": "User", "visible": True}, {"name": "password", "label": "Password"}]}
        page = keyrelay.page(item, "fake-request")
        self.assertIn("<title>Review and approve · Keyrelay</title>", page)
        script = page.split("<script>", 1)[1].split("</script>", 1)[0]
        result = subprocess.run(["node", str(ROOT / "tests/exchange_ui.cjs")], input=script, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
