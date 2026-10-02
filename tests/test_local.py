import http.client
import json
import os
import re
import select
import signal
import subprocess
import sys
import threading
import unittest
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer

import keyrelay

ROOT = Path(__file__).resolve().parents[1]


class LocalSecurityTest(unittest.TestCase):
    def test_rejects_rebinding_and_cross_origin_submission(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), keyrelay.handler_factory(None, 'local'))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        authority = '127.0.0.1:%d' % server.server_port

        def request(path, method='GET', data=None, host=authority, origin=None):
            headers = {'Host': host, 'Content-Type': 'application/json'}
            if origin:
                headers['Origin'] = origin
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            connection.request(method, path, json.dumps(data) if data is not None else None, headers)
            response = connection.getresponse()
            status, body = response.status, response.read()
            connection.close()
            return status, json.loads(body)

        try:
            self.assertEqual(request('/health')[0], 200)
            self.assertEqual(request('/health', host='evil.example')[0], 403)
            self.assertEqual(request('/api/requests', 'POST', {'command': 'echo ok', 'target': 'TOKEN'}, origin='https://evil.example')[0], 403)
            status, created = request('/api/requests', 'POST', {'command': 'echo ok', 'target': 'TOKEN'})
            self.assertEqual(status, 201)
            path = '/r/' + created['id'] + '/submit'
            self.assertEqual(request(path, 'POST', {'secret': 'fake'}, origin='null')[0], 403)
            self.assertEqual(request(path, 'POST', {'secret': 'fake'}, origin='http://' + authority)[0], 200)
        finally:
            server.shutdown()
            server.server_close()
            keyrelay.requests.clear()


class LocalRunnerTest(unittest.TestCase):
    @unittest.skipIf(os.name == 'nt', 'POSIX signal delivery')
    def test_cancel_shuts_down_local_broker(self):
        child = subprocess.Popen(['node', str(ROOT / 'bin/keyrelay.cjs'), 'run', '--env', 'TEST_KEY', '--', sys.executable, '-c', 'raise SystemExit("must not run")'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(select.select([child.stdout], [], [], 10)[0], 'No startup link')
            line = child.stdout.readline()
            base = re.search(r'http://127\.0\.0\.1:\d+', line).group(0)
            child.send_signal(signal.SIGINT)
            output, errors = child.communicate(timeout=5)
            self.assertEqual(child.returncode, 130, errors)
            self.assertNotIn('Traceback', errors)
            self.assertNotIn('must not run', output + errors)
            with self.assertRaises(urllib.error.URLError):
                urllib.request.urlopen(base + '/health', timeout=2)
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate()

    @unittest.skipIf(os.name == 'nt', 'POSIX signal delivery')
    def test_launcher_reports_forwarded_sigterm(self):
        child = subprocess.Popen(['node', str(ROOT / 'bin/keyrelay.cjs'), 'run', '--env', 'TEST_KEY', '--', sys.executable, '-c', 'raise SystemExit("must not run")'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(select.select([child.stdout], [], [], 10)[0], 'No startup link')
            child.stdout.readline()
            child.send_signal(signal.SIGTERM)
            output, errors = child.communicate(timeout=5)
            self.assertEqual(child.returncode, 128 + signal.SIGTERM, errors)
            self.assertNotIn('must not run', output + errors)
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate()

    def test_npx_launcher_local_exchange_and_shutdown(self):
        for mode in ('env', 'stdin'):
            with self.subTest(mode=mode):
                flags = ['--env', 'TEST_KEY'] if mode == 'env' else ['--stdin']
                code = 'import os,sys; print(os.environ["TEST_KEY"] if "TEST_KEY" in os.environ else sys.stdin.read().strip()); sys.exit(7)'
                child = subprocess.Popen(['node', str(ROOT / 'bin/keyrelay.cjs'), 'run', *flags, '--', sys.executable, '-c', code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    # A missing startup link should fail promptly, not hang the suite.
                    if os.name != 'nt':
                        self.assertTrue(select.select([child.stdout], [], [], 10)[0], 'No startup link')
                    line = child.stdout.readline()
                    match = re.match(r'Open (http://127\.0\.0\.1:\d+/r/[\w-]+)', line)
                    self.assertIsNotNone(match, line)
                    url = match.group(1)
                    base = url.split('/r/')[0]
                    with urllib.request.urlopen(url, timeout=5) as response:
                        self.assertIn(b'Ready for a secret', response.read())
                    req = urllib.request.Request(url + '/submit', data=json.dumps({'secret': 'local-test-secret'}).encode(), headers={'Content-Type': 'application/json', 'Origin': base})
                    with urllib.request.urlopen(req, timeout=5) as response:
                        self.assertEqual(response.status, 200)
                    output, errors = child.communicate(timeout=10)
                    self.assertEqual(child.returncode, 7, errors)
                    self.assertIn('[REDACTED]', output)
                    self.assertNotIn('local-test-secret', line + output + errors)
                    with self.assertRaises(urllib.error.URLError):
                        urllib.request.urlopen(base + '/health', timeout=2)
                finally:
                    if child.poll() is None:
                        child.terminate()
                        try:
                            child.communicate(timeout=5)
                        except subprocess.TimeoutExpired:
                            child.kill()
                            child.communicate()


if __name__ == '__main__':
    unittest.main()
