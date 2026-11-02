# Keyrelay initial launch plan

Drafted 2026-11-02. Follows the "distribution without shilling" order in
`~/Dev/headquarters/strategy/priorities.md`: listings first, own-site writing second, one personal share last.

## Starting point (2026-11-02)

- npm `keyrelay` 0.1.5, published 2026-10-14. 82 downloads in the last month.
- GitHub repo public, 0 stars, 5 topics.
- Site live at https://keyrelay.colefoster.ca, homepage only.
- Local `main` is 8 commits ahead of `origin/main`. Unpushed: three guide pages, the analytics-note fix, the
  directory and post drafts, and the redaction-hook draft.
- `keyrelay.py` on `main` differs from the 0.1.5 tarball: the October 17 exact-Host check in serve mode and the
  dropped-connection fix aren't on npm.

## Phase 0: make what people land on current

1. Bump to 0.1.6 and publish to npm. **Cole:** npm login.
2. Push `main`. The Pages workflow deploys `site/`. Check that `/api-key-without-chat/`,
   `/enter-api-key-from-phone/`, `/how-it-works/`, and `/sitemap.xml` return 200.
3. Run the Tailscale phone round trip once with a fake value, or drop the phone flow from launch copy. It's the
   only claim not verified end to end.
4. Add GitHub topics: `claude-code`, `codex`, `ai-agents`, `secrets`, `api-keys`.
5. Submit the sitemap in Search Console (existing access only).
6. Keep the redaction hook out of all launch copy. `NOTES.md` says it can't make the transcript guarantee.

### Phase 0 status (2026-11-02)

- Done: 0.1.6 tagged and pushed; guide pages and sitemap return 200; GitHub topics added.
- Published: npm 0.1.6 (2026-11-02), matching `main`.
- Skipped: the phone round trip. Cole's iPhone resolved no `ts.net` names at all (hil failed too), a phone
  DNS problem rather than a Keyrelay one. The phone flow stays out of launch copy until it's tested; the
  directory entry and the post's FAQ no longer mention it.
- Not done: Search Console sitemap submission.
- Found: the ash broker runs an October 14 build (`--auth whois` behind nginx) without the October 17
  exact-Host check. `main` no longer has whois mode, so updating it means reworking that deployment.

## Phase 1: listings

From `drafts/directory-submissions.md`. Each is a public PR from Cole's account, so each needs his go.

1. `bradAGI/awesome-cli-coding-agents`: PR to Agent infrastructure. Good fit.
2. `scadastrangelove/awesome-ai-security-tools`: PR to `WATCHLIST.md`. Medium fit.
3. Optional: `ottosulin/awesome-ai-security`. Medium-low fit.
4. Skip awesome-claude-code, MCP directories, and skill directories for now: Keyrelay isn't Claude-Code-specific,
   an MCP server, or a skill.

Optional unlock: a small Claude Code skill that wraps the agent-instructions snippet would qualify for
awesome-claude-code and skill directories. Build only if Phase 1 shows signal.

### Phase 1 status (2026-11-02)

- Opened https://github.com/bradAGI/awesome-cli-coding-agents/pull/599 (maintainer merges in batches).
- Opened https://github.com/scadastrangelove/awesome-ai-security-tools/pull/216 (watchlist).
- Not opened: `ottosulin/awesome-ai-security` (optional).

## Phase 2: writing on the project's own site

1. Publish `drafts/posts-agent-api-access-without-keys.md` as a page under `keyrelay.colefoster.ca`, linked
   from the homepage and sitemap.
2. Optional: cross-link from colefoster.ca, where a Keyrelay exhibit already exists.

### Phase 2 status (2026-11-02)

- Published at https://keyrelay.colefoster.ca/agent-api-access-without-keys/, linked from the homepage footer and sitemap. The redaction-hook paragraph was dropped, per Phase 0.

## Phase 3: one personal share

Cole's call, in his voice, drafted from his notes. Pick one, spaced a few days after Phase 2:

- **Show HN**: Cole decided against it for now (2026-11-02).
- An X post with the demo GIF.

### Phase 3 status (2026-11-02)

- Posted on X as a 2-post thread with the demo GIF: https://x.com/cole_0x4A3B7C/status/2117342661921120672

## Measurement

Baseline: 82 npm downloads/month, 0 stars, Search Console empty. Check 14 days after Phase 1:

- npm weekly downloads, GitHub stars and issues, Umami page views per guide, and Search Console queries.
- If nothing moves, park further promotion and keep the listings. Mode is "mostly explore".

## Decisions for Cole

- Publish 0.1.6 to npm (needs his login).
- Push `main`, which deploys the guide pages.
- Which Phase 1 PRs to open.
- Show HN, X, or neither, and when.
