# Keyrelay project PM

Updated 2026-10-07. Owner: Cole. This is the local product/reach backlog; publishing and outreach remain decisions for Cole.

## Product truth and boundaries

Keyrelay helps a trusted coding agent hand a credential to a chosen CLI command without putting it in chat. Local mode needs Node.js 18+ and Python 3.9+, not Tailscale or an account. The public site is static and must never receive credentials. The private broker is separate from the public product site.

This is not a sandbox, a multi-user secret manager, or a defense against a malicious agent/command. A command receives the credential and can store, transform, or transmit it. Local programs share the machine's trust boundary. The broker stores requests in process memory; there is no application-level encryption of that memory. Local loopback HTTP and optional Tailscale HTTPS are different transport contexts. Do not advertise end-to-end encryption or guaranteed memory erasure.

Requests expire after five minutes; expired entries are removed on the next broker request. A successful runner claim deletes the entry. Restarting the broker discards pending entries. Cancellation stops the temporary local broker. A persistent broker may retain an abandoned request until expiry/cleanup. Exact credential echoes in captured output are redacted; transformed output and target-tool storage are outside that protection.

Evidence: [README](README.md), `keyrelay.py` (`page`, `handler_factory`, `cleanup`, `run`), and the existing exchange/local-runner tests. Keep this description aligned with code whenever those behaviors change.

## Prioritized reach backlog

| Priority | Work | Acceptance and scope | Status |
| --- | --- | --- | --- |
| P0 | Keep credential surfaces private | Preserve Host/Origin/bearer/Tailscale checks and CSP. Never place broker hosts, `/r/` URLs, request IDs, tokens, or submitted values in public examples, analytics, sitemaps, logs, or screenshots. Private `noindex` is only defense in depth, never access control. | Ongoing invariant |
| P1 | Public problem/use-case pages | Add useful static pages for “API key without pasting into AI chat,” local credential handoff, and phone-to-Tailnet handoff. Explain who each flow suits, prerequisites, exact command pattern, and limits. Link from the homepage and sitemap; unique titles/descriptions/canonicals. Avoid near-duplicate keyword pages. | Next content pass |
| P1 | Safe fake-credential demo | Show the README's `DEMO_TOKEN` command and literal `demo-value` on the public site. A later interactive illustration must use a fixed fake value and no free-text credential input, backend, persistence, or telemetry of the value. Clearly distinguish an illustration from a real broker. | Bounded static demo in current polish scope; interactive illustration deferred |
| P1 | Public trust/architecture guide | Publish a readable diagram of agent → runner → loopback broker → browser → selected command. Separate optional Tailscale mode. Explain expiration, claim/deletion, cancellation, cleanup, redaction limits, target-tool persistence, malicious commands, local process access, and the personal identity boundary. Include a code-version reference and maintenance owner. | README covers facts; crawlable public guide deferred |
| P1 | Technical crawlability/social metadata | Keep HTML content readable without JavaScript, stable public canonical, crawlable internal links, accurate title/description, and valid sitemap. Add honest Twitter summary metadata. Later create a public-only social image using fixed example values; verify returned production status/headers and URL variants after an explicitly authorized publish. Never put private broker URLs in social tags. | Homepage metadata in current polish scope; image and production verification deferred |
| P2 | Agent integration tutorials | Separate short guides for Claude Code and Codex: agent instruction snippet, trusted command review, runner remains waiting, same-computer link, env vs stdin, cancellation, and temporary broker shutdown. Test with fake values. Keep personal Max/API billing unrelated to installation. | Deferred |
| P2 | CLI integration tutorials | Start with a fake Node command, then optional GitHub CLI and one cloud CLI. State required tools separately, minimum credential scope, target variable, and any target-tool persistence. Existing authentication may make a new key unnecessary. No real login or credential changes during documentation testing. | Deferred |
| P2 | Honest comparisons | Compare chat paste, environment variables, `.env` files, OS keychains/password managers, and dedicated secret managers by storage, handoff friction, revocation, agent visibility, and trust boundary. Describe when an existing mechanism is sufficient. Do not claim universal security superiority or replace a secret manager's capabilities. | Deferred |
| P2 | Discovery and measurement | After permission to publish, check Search Console indexing/canonical/sitemap and page queries using existing access. Establish a baseline before claiming improvement. Refine pages from actual questions; do not collect credential-path or value telemetry. Any new analytics permission, account, or public outreach requires separate authorization. | Needs Cole's publishing/measurement decision |
| P2 | Expired-link recovery | A missing, expired, or claimed request currently renders a JSON 404. A future browser-specific explanatory page should preserve the same status and all auth checks, and help the user request a fresh link. Requires a separate handler/UI review. | Deferred outside HTML-only broker scope |
| P2 | Further accessibility review | Validate announcements with a screen reader, measure smaller footer link targets, and review the incumbent 10px illustrative note. Retain the clear visual identity; no blanket WCAG-conformance claim from this pass. | Deferred |
| P3 | Distribution | Improve public README/npm descriptions and link to finished guides. Later consider useful developer posts or integration directories; draft first, with genuine examples and no invented users, ratings, or endorsements. | Outreach not authorized |

The content-first priority is an inference from the narrow current site and the documented user problem, not a claim about measured keyword demand or ranking. Google emphasizes useful content, crawlable links, descriptive titles, and appropriate public URLs in its [SEO starter guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide). Private-page exclusions follow its [noindex guidance](https://developers.google.com/search/docs/crawling-indexing/block-indexing); exclusions do not protect access to a page. No ranking result is promised.

## Current bounded pass

Claude authors application UI/HTML/CSS changes in an isolated local worktree; Sol independently reviews, tests, and integrates. Scope: broker form states/recovery/accessibility, accurate private-page presentation, HTML indexing exclusions, public fake-value demo, and small metadata/mobile improvements. Authentication, encryption, credential handling on the backend, request expiration/deletion, deployment, and persistent permissions are outside the change. The fake-value walkthrough, FAQ and summary-card metadata are implemented locally in this pass; the public guide pages and an interactive illustration remain backlog items.

## Remaining decisions

- Approve publication separately after reviewing the local result; no deployment or push in this pass.
- Choose the first public problem/use-case page and which agent tutorial to write first.
- Decide whether a fixed-value interactive illustration adds enough value beyond the runnable local fake-value demo.
- Decide whether to use existing Search Console access for a baseline after publication; no new accounts or permissions are assumed.
