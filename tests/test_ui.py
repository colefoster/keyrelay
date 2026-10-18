import subprocess
import unittest
from pathlib import Path

import keyrelay

ROOT = Path(__file__).resolve().parents[1]


def item(status="waiting"):
    return {"status": status, "target": "DEMO_TOKEN", "command": "node -e 'x'", "fields": [], "note": ""}


class BrokerPageTest(unittest.TestCase):
    def test_submit_script_behaviour(self):
        # Executes the real inline script against a mocked DOM, fetch, and timers.
        body = keyrelay.page(item(), "fake-request")
        script = body.split("<script>", 1)[1].split("</script>", 1)[0]
        result = subprocess.run(["node", str(ROOT / "tests/broker_ui.cjs")], input=script, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("ok"), result.stdout)

    def test_single_and_multi_field_forms_share_one_layout(self):
        single = keyrelay.page(item(), "abc")
        self.assertIn('data-bundle=""', single)
        self.assertEqual(single.count("<input"), 1)
        request = dict(item(), fields=[{"name": "apiKey", "label": "API key"}, {"name": "apiSecret", "label": "API secret"}])
        multi = keyrelay.page(request, "abc")
        self.assertIn('data-bundle="1"', multi)
        self.assertEqual(multi.count("<input"), 2)

    def test_used_request_has_no_form(self):
        body = keyrelay.page(item("ready"), "abc")
        self.assertNotIn("<form", body)
        self.assertNotIn("<script>", body)


if __name__ == "__main__":
    unittest.main()
