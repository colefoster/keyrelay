import json
import os
import signal
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from argparse import Namespace
from contextlib import redirect_stdout, redirect_stderr
from io import BytesIO, TextIOWrapper
from unittest.mock import patch

import keyrelay


class ExchangeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), keyrelay.handler_factory("owner@example.com"))
        cls.base = "http://127.0.0.1:%d" % cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def request(self, path, method="GET", body=None, token=None, email="owner@example.com", origin=None):
        headers = {"Tailscale-User-Login": email}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = "Bearer " + token
        if origin:
            headers["Origin"] = origin
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as result:
                content = result.read()
                return result.status, json.loads(content) if result.headers["Content-Type"].startswith("application/json") else content.decode()
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_exchange_is_one_time_and_authenticated(self):
        status, created = self.request("/api/requests", "POST", {"command": "gh api user", "target": "GITHUB_TOKEN"})
        self.assertEqual(status, 201)
        path = "/r/" + created["id"]
        self.assertNotIn(created["token"], path)
        self.assertEqual(self.request(path, email="another@example.com")[0], 403)
        self.assertEqual(self.request(path)[0], 200)
        self.assertEqual(self.request(path + "/submit", "POST", {"secret": "test-secret"}, origin="https://evil.example")[0], 403)
        self.assertEqual(self.request(path + "/submit", "POST", {"secret": "test-secret"})[0], 200)
        self.assertEqual(self.request(path + "/submit", "POST", {"secret": "again"})[0], 400)
        api_path = "/api/requests/" + created["id"]
        self.assertEqual(self.request(api_path, token="wrong")[0], 404)
        self.assertEqual(self.request(api_path, token=created["token"])[1]["status"], "ready")
        self.assertEqual(self.request(api_path, "POST", {}, token=created["token"])[1]["secret"], "test-secret")
        self.assertEqual(self.request(api_path, "POST", {}, token=created["token"])[0], 404)

    def test_page_escapes_command(self):
        _, created = self.request("/api/requests", "POST", {"command": "<script>alert(1)</script>", "target": "TOKEN"})
        _, html = self.request("/r/" + created["id"])
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>alert", html)

    def test_homepage_explains_handoff(self):
        status, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("Keyrelay is ready", body)

    def test_whois_auth_checks_tailnet_user(self):
        whois = ThreadingHTTPServer(("127.0.0.1", 0), keyrelay.handler_factory("owner@example.com", "whois"))
        thread = threading.Thread(target=whois.serve_forever, daemon=True)
        thread.start()
        try:
            url = "http://127.0.0.1:%d/health" % whois.server_port
            with patch.object(keyrelay, "tailnet_login", return_value="owner@example.com") as lookup:
                req = urllib.request.Request(url, headers={"Host": "key.colefoster.ca", "X-Real-IP": "100.84.242.24"})
                with urllib.request.urlopen(req) as result:
                    self.assertEqual(result.status, 200)
                lookup.assert_called_once_with("100.84.242.24")
            req = urllib.request.Request(url, headers={"Host": "wrong.example", "X-Real-IP": "100.84.242.24"})
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(req)
            self.assertEqual(error.exception.code, 403)
        finally:
            whois.shutdown()
            whois.server_close()

    def run_with_fake_broker(self, command, secret="test-secret"):
        output, errors = TextIOWrapper(BytesIO()), TextIOWrapper(BytesIO())
        responses = [
            {"id": "request", "token": "claim", "expires_in": 300},
            {"status": "ready"},
            {"secret": secret},
        ]
        args = Namespace(url="https://ash.example.ts.net", env="TOKEN", stdin=False, allow_http=False, command=["--", *command])
        previous_sigterm = signal.getsignal(signal.SIGTERM)
        with patch.object(keyrelay, "api", side_effect=responses), redirect_stdout(output), redirect_stderr(errors):
            code = keyrelay.run(args)
        self.assertIs(signal.getsignal(signal.SIGTERM), previous_sigterm)
        output.flush()
        errors.flush()
        return code, output.buffer.getvalue(), errors.buffer.getvalue()

    def test_runner_injects_and_redacts(self):
        def fake_command(command, **kwargs):
            self.assertEqual(command, ["tool"])
            self.assertEqual(kwargs["env"]["TOKEN"], "test-secret")
            return Namespace(stdout=b"value=test-secret\n", stderr=b"", returncode=0)

        with patch.object(keyrelay.subprocess, "run", side_effect=fake_command):
            code, output, errors = self.run_with_fake_broker(["tool"])
        self.assertEqual(code, 0)
        self.assertIn(b"value=[REDACTED]", output)
        self.assertNotIn(b"test-secret", output + errors)

    def test_runner_passes_through_non_utf8_output(self):
        code, output, errors = self.run_with_fake_broker([sys.executable, "-c", "import os,sys; sys.stdout.buffer.write(b'\\xff ' + os.environ['TOKEN'].encode() + b'\\n'); sys.exit(3)"])
        self.assertEqual(code, 3)
        self.assertIn(b"\xff [REDACTED]\n", output)
        self.assertNotIn(b"test-secret", output + errors)

    @unittest.skipIf(os.name == "nt", "POSIX environments use surrogateescape")
    def test_runner_redacts_env_secret_with_lone_surrogate(self):
        # JSON permits lone surrogates; POSIX injects them into the environment as raw bytes.
        secret = json.loads('"fake-\\udcff"')
        code, output, errors = self.run_with_fake_broker([sys.executable, "-c", "import os,sys; sys.stdout.buffer.write(b'ok ' + os.environb[b'TOKEN'] + b'\\n'); sys.exit(4)"], secret)
        self.assertEqual(code, 4)
        self.assertEqual(output.splitlines()[-1], b"ok [REDACTED]")
        self.assertNotIn(b"fake-\xff", output + errors)

    @unittest.skipIf(os.name == "nt", "POSIX signals")
    def test_runner_reports_signal_like_a_shell(self):
        code, _, _ = self.run_with_fake_broker([sys.executable, "-c", "import os,signal; os.kill(os.getpid(), signal.SIGTERM)"])
        self.assertEqual(code, 128 + signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
