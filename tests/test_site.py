"""Static checks for the public product site: metadata, sitemap, links, and no private broker details."""

import os
import re
import unittest
from html.parser import HTMLParser

SITE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")
ORIGIN = "https://keyrelay.colefoster.ca"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr", "path"}
GUIDES = ["api-key-without-chat", "enter-api-key-from-phone", "how-it-works"]


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title, self.meta, self.links, self.ids, self.inline = "", {}, [], set(), []
        self.canonical, self._in_title = None, False
        self.stack, self.errors = [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag not in VOID:
            self.stack.append(tag)
        if "id" in a and a["id"] in self.ids:
            self.errors.append("duplicate id " + a["id"])
        if "id" in a:
            self.ids.add(a["id"])
        if "style" in a:
            self.inline.append("style attribute on <%s>" % tag)
        if tag == "title":
            self._in_title = True
        elif tag == "meta" and "name" in a:
            self.meta[a["name"]] = a.get("content", "")
        elif tag == "link" and a.get("rel") == "canonical":
            self.canonical = a["href"]
        elif tag == "style":
            self.inline.append("<style> element")
        elif tag == "script" and "src" not in a and a.get("type") != "application/ld+json":
            self.inline.append("inline <script>")
        if tag == "link" and a.get("rel") not in ("stylesheet", "icon"):
            return
        self.links += [a[key] for key in ("href", "src") if key in a]

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append("unexpected </%s> inside %s" % (tag, self.stack[-1:] or "nothing"))
        else:
            self.stack.pop()
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def parse(rel):
    page = Page()
    with open(os.path.join(SITE, rel), encoding="utf-8") as f:
        page.raw = f.read()
    page.feed(page.raw)
    return page


def local_target(href, page_dir):
    """Map an internal href to a file in site/, or None for external links."""
    if re.match(r"^[a-z]+:", href) or href.startswith("//"):
        return None
    path = href.split("#", 1)[0]
    if not path:
        return ""
    full = os.path.normpath(path.lstrip("/") if path.startswith("/") else os.path.join(page_dir, path))
    return os.path.join(full, "index.html") if path.endswith("/") else full


class SiteTest(unittest.TestCase):
    pages = ["index.html"] + [g + "/index.html" for g in GUIDES]

    def test_unique_titles_descriptions_and_canonicals(self):
        seen = {"title": set(), "description": set(), "canonical": set()}
        for rel in self.pages:
            page = parse(rel)
            for key, value in (("title", page.title.strip()), ("description", page.meta.get("description")),
                               ("canonical", page.canonical)):
                self.assertTrue(value, "%s: missing %s" % (rel, key))
                self.assertNotIn(value, seen[key], "%s: duplicate %s" % (rel, key))
                seen[key].add(value)
            expected = ORIGIN + "/" + (rel[: -len("index.html")])
            self.assertEqual(page.canonical, expected, rel)

    def test_sitemap_lists_exactly_the_public_pages(self):
        with open(os.path.join(SITE, "sitemap.xml"), encoding="utf-8") as f:
            locs = re.findall(r"<loc>([^<]+)</loc>", f.read())
        self.assertEqual(sorted(locs), sorted(parse(rel).canonical for rel in self.pages))

    def test_internal_links_resolve(self):
        for rel in self.pages:
            page = parse(rel)
            for href in page.links:
                target = local_target(href, os.path.dirname(rel))
                if target is None:
                    continue
                if target == "":
                    self.assertIn(href[1:], page.ids, "%s: missing anchor %s" % (rel, href))
                    continue
                self.assertTrue(os.path.isfile(os.path.join(SITE, target)), "%s: broken link %s" % (rel, href))

    def test_guides_are_well_formed(self):
        for guide in GUIDES:
            page = parse(guide + "/index.html")
            self.assertEqual(page.errors + page.stack, [], guide)

    def test_guides_are_csp_safe(self):
        # _headers allows only same-origin styles and scripts, so inline ones would silently not apply.
        for guide in GUIDES:
            self.assertEqual(parse(guide + "/index.html").inline, [], guide)

    def test_guides_leak_no_broker_details(self):
        for guide in GUIDES:
            raw = parse(guide + "/index.html").raw
            self.assertNotIn("/r/", raw, guide)
            self.assertNotIn("127.0.0.1:8765/", raw, guide)
            for host in re.findall(r"[\w.-]+\.ts\.net", raw):
                self.assertEqual(host, "your-broker.your-tailnet.ts.net", guide)
            for email in re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", raw):
                self.assertEqual(email, "you@example.com", guide)


if __name__ == "__main__":
    unittest.main()
