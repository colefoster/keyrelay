import re
import subprocess
import unittest
from pathlib import Path

import keyrelay

ROOT = Path(__file__).resolve().parents[1]


def item(status="waiting"):
    return {"status": status, "target": "DEMO_TOKEN", "command": "node -e 'x'"}


class BrokerPageTest(unittest.TestCase):
    def test_private_pages_ask_not_to_be_indexed(self):
        for body in (keyrelay.page(item(), "abc"), keyrelay.page(item("ready"), "abc"), keyrelay.home_page()):
            self.assertIn('<meta name="robots" content="noindex,nofollow">', body)

    def test_home_page_does_not_claim_tailnet_in_local_mode(self):
        self.assertNotIn("Tailnet only", keyrelay.home_page())

    def test_form_is_labelled_and_described(self):
        body = keyrelay.page(item(), "abc")
        self.assertIn('<label for="secret">', body)
        self.assertIn('aria-describedby="hint"', body)
        self.assertIn('id="hint"', body)
        self.assertIn('role="status"', body)
        self.assertIn('<p id="intro">', body)

    def test_submit_script_behaviour(self):
        # Executes the real inline script against a mocked DOM, fetch, and timers.
        body = keyrelay.page(item(), "fake-request")
        script = body.split("<script>", 1)[1].split("</script>", 1)[0]
        result = subprocess.run(["node", str(ROOT / "tests/broker_ui.cjs")], input=script, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("ok"), result.stdout)

    def test_used_request_has_no_form_or_stale_instructions(self):
        body = keyrelay.page(item("ready"), "abc")
        self.assertNotIn("<form", body)
        self.assertNotIn("<script>", body)
        self.assertNotIn("before supplying the secret", body)
        self.assertIn("already sent", body)


class PublicSiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "site/index.html").read_text()

    def test_social_and_search_metadata(self):
        self.assertIn('<meta name="description"', self.html)
        self.assertIn('<link rel="canonical"', self.html)
        self.assertIn('<meta name="twitter:card" content="summary">', self.html)
        self.assertNotIn("twitter:image", self.html)
        self.assertNotIn("og:image", self.html)

    def test_static_demo_uses_fake_value_and_collects_nothing(self):
        self.assertIn('id="try"', self.html)
        self.assertIn('href="#try"', self.html)
        self.assertIn("DEMO_TOKEN", self.html)
        self.assertIn("<code>demo-value</code>", self.html)
        self.assertNotRegex(self.html, r"<(input|form|textarea)\b")

    def test_no_inline_scripts_under_csp(self):
        for tag in re.findall(r"<script\b[^>]*>", self.html):
            self.assertIn("src=", tag)
        self.assertNotIn("application/ld+json", self.html)

    def test_fragment_links_resolve(self):
        ids = set(re.findall(r'\bid="([^"]+)"', self.html))
        for target in re.findall(r'href="#([^"]+)"', self.html):
            self.assertIn(target, ids)


if __name__ == "__main__":
    unittest.main()
