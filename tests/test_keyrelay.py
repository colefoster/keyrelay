import http.client
import io
import json
import os
import signal
import sys
import threading
import time
import unittest
from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
from http.server import ThreadingHTTPServer
from io import BytesIO, TextIOWrapper
from unittest.mock import patch

import keyrelay

HOST = "broker.example.ts.net"
OWNER = "owner@example.com"


def args(**changes):
    values = dict(url="https://" + HOST, env="TOKEN", stdin=False, allow_http=False, command=["tool"],
                  field=[], field_help=[], note="")
    values.update(changes)
    return Namespace(**values)


class BrokerTest(unittest.TestCase):
    """Serve mode, as reached through Tailscale Serve: exact Host plus the identity header."""

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), keyrelay.handler_factory(OWNER, HOST))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def tearDown(self):
        keyrelay.pending.clear()

    def request(self, path, method="GET", body=None, token=None, email=OWNER, host=HOST, origin=None, raw=None, content_type="application/json"):
        headers = {"Host": host}
        if email:
            headers["Tailscale-User-Login"] = email
        if body is not None or raw is not None:
            headers["Content-Type"] = content_type
        if token:
            headers["Authorization"] = "Bearer " + token
        if origin:
            headers["Origin"] = origin
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request(method, path, raw if raw is not None else json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse()
        content = response.read().decode()
        connection.close()
        is_json = response.getheader("Content-Type").startswith("application/json")
        return response.status, json.loads(content) if is_json else content

    def create(self, **body):
        return self.request("/api/requests", "POST", dict({"command": "gh api user", "target": "GITHUB_TOKEN"}, **body))

    def test_exchange_is_one_time_and_authenticated(self):
        status, created = self.create()
        self.assertEqual(status, 201)
        path = "/r/" + created["id"]
        self.assertNotIn(created["token"], path)
        self.assertEqual(self.request(path, email="another@example.com")[0], 403)
        self.assertEqual(self.request(path)[0], 200)
        self.assertEqual(self.request(path + "/submit", "POST", {"secret": "test-secret"}, origin="https://evil.example")[0], 403)
        self.assertEqual(self.request(path + "/submit", "POST", {"secret": "test-secret"}, origin="https://" + HOST)[0], 200)
        self.assertEqual(self.request(path + "/submit", "POST", {"secret": "again"})[0], 400)
        api_path = "/api/requests/" + created["id"]
        self.assertEqual(self.request(api_path, token="wrong")[0], 404)
        self.assertEqual(self.request(api_path, token=created["token"])[1]["status"], "ready")
        self.assertEqual(self.request(api_path, "POST", {}, token=created["token"])[1]["secret"], "test-secret")
        self.assertEqual(self.request(api_path, "POST", {}, token=created["token"])[0], 404)

    def test_serve_mode_requires_exact_host(self):
        # The identity header is trusted only for the configured host, so a request that reached
        # the port another way (another proxy, a rebinding page) is refused.
        for host in ("evil.example", "127.0.0.1:%d" % self.server.server_port, HOST + ".evil.example"):
            self.assertEqual(self.request("/health", host=host)[0], 403)
        self.assertEqual(self.request("/health", email=None)[0], 403)
        self.assertEqual(self.request("/health")[0], 200)

    def test_requests_expire(self):
        _, created = self.create()
        later = time.monotonic() + keyrelay.TTL + 1
        with patch.object(keyrelay.time, "monotonic", return_value=later):
            self.assertEqual(self.request("/r/" + created["id"])[0], 404)
            self.assertEqual(self.request("/api/requests/" + created["id"], token=created["token"])[0], 404)
        self.assertNotIn(created["id"], keyrelay.pending)

    def test_pending_request_cap(self):
        for _ in range(keyrelay.MAX_PENDING):
            self.assertEqual(self.create()[0], 201)
        self.assertEqual(self.create()[0], 429)

    def test_rejects_oversized_and_non_json_bodies(self):
        oversized = json.dumps({"command": "x" * keyrelay.MAX_BODY, "target": "T"})
        self.assertEqual(self.request("/api/requests", "POST", raw=oversized)[0], 400)
        valid = json.dumps({"command": "tool", "target": "T"})
        self.assertEqual(self.request("/api/requests", "POST", raw=valid, content_type="text/plain")[0], 400)
        self.assertEqual(self.request("/api/requests", "POST", raw=valid)[0], 201)

    def test_writes_no_request_lines_to_stderr(self):
        captured = io.StringIO()
        with redirect_stderr(captured):
            _, created = self.create()
            self.request("/r/" + created["id"])
            self.request("/r/" + created["id"] + "/submit", "POST", {"secret": "test-secret"})
            self.request("/missing", host="evil.example")
        self.assertEqual(captured.getvalue(), "")

    def test_multiple_fields_validate_and_deliver_once(self):
        fields = [{"name": "apiKey", "label": "API key"}, {"name": "apiSecret", "label": "API <secret>"}]
        status, created = self.create(target="BUNDLE", fields=fields)
        self.assertEqual((status, created["field_count"]), (201, 2))
        path = "/r/" + created["id"]
        page = self.request(path)[1]
        self.assertIn('data-name="apiKey"', page)
        self.assertIn("API &lt;secret&gt;", page)
        for value in ["plain", "{}", '{"apiKey":"x"}', '{"apiKey":"x","apiSecret":""}']:
            self.assertEqual(self.request(path + "/submit", "POST", {"secret": value})[0], 400)
        secret = json.dumps({"apiKey": "fake-key", "apiSecret": "fake-secret"})
        self.assertEqual(self.request(path + "/submit", "POST", {"secret": secret})[0], 200)
        self.assertEqual(self.request("/api/requests/" + created["id"], "POST", {}, token=created["token"])[1]["secret"], secret)

    def test_invalid_field_specs(self):
        for fields in [None, {}, [None], [{"name": "a", "label": "A"}] * 2, [{"name": "bad-name", "label": "A"}],
                       [{"name": "a", "label": "A", "extra": 1}], [{"name": "a", "label": "A", "help": "x" * 1001}]]:
            self.assertEqual(self.create(fields=fields)[0], 400)

    def test_instructions_are_validated_and_escaped(self):
        fields = [{"name": "key", "label": "Key", "help": "Settings > Keys <b>only</b>"}]
        status, created = self.create(note="Use the app account.\n<script>bad</script>", fields=fields)
        self.assertEqual(status, 201)
        page = self.request("/r/" + created["id"])[1]
        self.assertIn('aria-describedby="hint help-0"', page)
        self.assertIn("Settings &gt; Keys &lt;b&gt;only&lt;/b&gt;", page)
        self.assertIn("Use the app account.\n&lt;script&gt;bad&lt;/script&gt;", page)
        for note in (None, {}, "x" * 2001):
            self.assertEqual(self.create(note=note)[0], 400)

    def test_page_escapes_command(self):
        _, created = self.create(command="<script>alert(1)</script>")
        body = self.request("/r/" + created["id"])[1]
        self.assertIn("&lt;script&gt;", body)
        self.assertNotIn("<script>alert", body)


class RunnerTest(unittest.TestCase):
    def run_with_fake_broker(self, run_args, secret="test-secret"):
        output, errors = TextIOWrapper(BytesIO()), TextIOWrapper(BytesIO())
        fields = len(run_args.field)
        responses = [{"id": "request", "token": "claim", "expires_in": 300, "field_count": fields}, {"status": "ready"}, {"secret": secret}]
        previous_sigterm = signal.getsignal(signal.SIGTERM)
        with patch.object(keyrelay, "api", side_effect=responses), redirect_stdout(output), redirect_stderr(errors):
            code = keyrelay.run(run_args)
        self.assertIs(signal.getsignal(signal.SIGTERM), previous_sigterm)
        output.flush()
        errors.flush()
        return code, output.buffer.getvalue(), errors.buffer.getvalue()

    def python(self, code, **changes):
        return args(command=["--", sys.executable, "-c", code], **changes)

    def test_runner_injects_and_redacts(self):
        code, output, errors = self.run_with_fake_broker(self.python("import os; print('value=' + os.environ['TOKEN'])"))
        self.assertEqual(code, 0)
        self.assertIn(b"value=[REDACTED]", output)
        self.assertNotIn(b"test-secret", output + errors)

    def test_runner_passes_through_non_utf8_output(self):
        code, output, errors = self.run_with_fake_broker(self.python(
            "import os,sys; sys.stdout.buffer.write(b'\\xff ' + os.environ['TOKEN'].encode() + b'\\n'); sys.exit(3)"))
        self.assertEqual(code, 3)
        self.assertIn(b"\xff [REDACTED]\n", output)
        self.assertNotIn(b"test-secret", output + errors)

    @unittest.skipIf(os.name == "nt", "POSIX environments use surrogateescape")
    def test_runner_redacts_secret_with_lone_surrogate(self):
        # JSON permits lone surrogates; POSIX passes them to the command as raw bytes in both modes.
        secret = json.loads('"fake-\\udcff"')
        for mode, code in (({}, "import os,sys; sys.stdout.buffer.write(b'ok ' + os.environb[b'TOKEN'] + b'\\n')"),
                           ({"env": None, "stdin": True}, "import sys; sys.stdout.buffer.write(b'ok ' + sys.stdin.buffer.readline())")):
            with self.subTest(mode=mode):
                _, output, errors = self.run_with_fake_broker(self.python(code, **mode), secret)
                self.assertEqual(output.splitlines()[-1], b"ok [REDACTED]")
                self.assertNotIn(b"fake-\xff", output + errors)

    def test_multi_field_values_are_redacted_in_both_modes(self):
        secret = json.dumps({"apiKey": "fake-key", "apiSecret": "fake-secret", "region": "eu"})
        echo = "import json,os,sys; v=json.loads(os.environ.get('TOKEN') or sys.stdin.readline()); print(v['apiKey']); print(v['apiSecret'], 'eu', file=sys.stderr)"
        for mode in ({}, {"env": None, "stdin": True}):
            with self.subTest(mode=mode):
                fields = ["apiKey=API key", "apiSecret=API secret", "region=Region"]
                code, output, errors = self.run_with_fake_broker(self.python(echo, field=fields, **mode), secret)
                self.assertEqual(code, 0)
                self.assertEqual(output.splitlines()[-1], b"[REDACTED]")
                # Values shorter than MIN_REDACT stay readable rather than redacting every "eu" in the output.
                self.assertEqual(errors, b"[REDACTED] eu\n")

    def test_runner_rejects_unsupported_notes_and_invalid_help(self):
        run_args = args(field=["key=Key"], note="Use the app account", field_help=["key=Settings > Keys"])
        with patch.object(keyrelay, "api", return_value={"field_count": 1}) as api:
            with self.assertRaisesRegex(RuntimeError, "update the broker"):
                keyrelay.run(run_args)
            payload = api.call_args.args[2]
            self.assertEqual(payload["note"], run_args.note)
            self.assertEqual(payload["fields"][0]["help"], "Settings > Keys")
        for help_specs in (["missing=Help"], ["key=Help", "key=Again"], ["key="], ["key"], ["key=" + "x" * 1001]):
            with patch.object(keyrelay, "api") as api:
                with self.assertRaisesRegex(RuntimeError, "Field help"):
                    keyrelay.run(args(field=["key=Key"], field_help=help_specs))
                api.assert_not_called()

    def test_runner_requires_https_broker(self):
        with patch.object(keyrelay, "api") as api:
            with self.assertRaisesRegex(RuntimeError, "HTTPS"):
                keyrelay.run(args(url="http://" + HOST))
            api.assert_not_called()

    @unittest.skipIf(os.name == "nt", "POSIX signals")
    def test_runner_reports_signal_like_a_shell(self):
        code, _, _ = self.run_with_fake_broker(self.python("import os,signal; os.kill(os.getpid(), signal.SIGTERM)"))
        self.assertEqual(code, 128 + signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
