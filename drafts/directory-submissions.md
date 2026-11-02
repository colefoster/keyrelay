# Keyrelay directory submissions (draft)

Drafted 2026-10-31 for bead xp-4x4o. **Nothing here has been submitted.** Cole submits; recommendations on
awesome-claude-code must come from a human by its rules.

Facts used below (checked 2026-10-31): repo `colefoster/keyrelay`, public, MIT, created 2026-09-24, last commit
2026-10-26, 0 stars; npm `keyrelay` 0.1.5; site https://keyrelay.colefoster.ca. Rules were read from each list's
repo with `gh api` (read-only) or cole-mcp `web_fetch`.

Re-check the star count and the list's latest rules on the day you submit.

## Summary

| # | Target | Method | Fit |
| --- | --- | --- | --- |
| 1 | bradAGI/awesome-cli-coding-agents | PR to README | **Good**: submit |
| 2 | scadastrangelove/awesome-ai-security-tools | PR to WATCHLIST.md | **Medium**: submit to watchlist |
| 3 | ottosulin/awesome-ai-security | PR to README | **Medium-low**: optional |
| 4 | hesreallyhim/awesome-claude-code | Web issue form only | **Not yet**: fails the "specific to Claude Code" box |
| 5 | RoggeOhta/awesome-codex-cli | Issue or PR | **Weak**: no Codex-specific integration |
| 6 | bureado/awesome-agent-runtime-security | PR | **Poor**: list excludes same-privilege isolation |
| 7 | tailscale-dev/awesome-tailscale | PR | **Skip**: no merges since 2024 |
| 8 | AlternativeTo | Web form, account | **Low**: rules not verifiable |
| 9 | MCP and skill directories | — | **No fit**: Keyrelay is neither |
| 10 | Own metadata (GitHub topics, npm keywords) | Cole's repo | **Do**: free, no review |

## 1. bradAGI/awesome-cli-coding-agents — good fit

- List: https://github.com/bradAGI/awesome-cli-coding-agents (1.4k stars). Last commit 2026-10-26.
- Rules (README "Contributing"): "PRs welcome". Entries must be valid, active projects. The format is name and
  link, a star count for GitHub repos, and a 1 to 2 line description of what it does and who it's for. A
  license and a "why it's interesting" note are optional. **Entries are sorted by stars within each
  section**, so place yours by count.
- How PRs land: the maintainer batches them. On 2026-10-17 a commit added 76 entries from the open PR queue.
  PRs stay "open" until then. 100+ PRs are open now, so expect a wait.
- Section: `### Agent infrastructure` ("Sandboxes, routers, browser/terminal automation, and extension tools").
  OneCLI, a credential vault, is already listed there.
- Placement: with 0 stars, add it at the end of the starred entries, directly after the `SAKO` line (the last
  `⭐ 0` entry) and before the unstarred `Agent Fleet` / `podway` entries.
- PR title: `Add Keyrelay to Agent infrastructure`
- Diff:

```diff
 - **[SAKO](https://github.com/Thakay/sako)** `⭐ 0` — Task ledger and finish gate for coding agents: …
+- **[Keyrelay](https://github.com/colefoster/keyrelay)** `⭐ 0` — One-time credential handoff for coding agents: `npx keyrelay run --env NAME -- command` prints a local link, you type the key in a browser form, and only that command receives it, with echoes redacted from the output the agent reads. MIT.
```

- PR body:

> Adds Keyrelay to Agent infrastructure. It is a CLI (one Python file plus an npm launcher) that a coding
> agent runs when a command needs a credential, so the key goes to that command instead of the chat. Placed
> by star count. MIT, active (last commit 2026-10-26).

## 2. scadastrangelove/awesome-ai-security-tools — medium fit, watchlist

- List: https://github.com/scadastrangelove/awesome-ai-security-tools (1.7k stars). Active, merges PRs weekly.
- Rules (CONTRIBUTING.md): the main list is generated. Edit `data/sections.json`, not `README.md`, and run
  `gen_readme.py`. Descriptions must be factual, one sentence. **Very new and zero-star projects may be tracked
  in `WATCHLIST.md` first**, then graduate on license, adoption, and maintenance signals. Recent PRs were
  reviewed into the watchlist this way (PRs #180–199).
- Fit: the list covers coding-agent security, and Keyrelay is a credential-isolation tool for coding agents.
  With 0 stars it belongs in `WATCHLIST.md`, under `## Candidates`.
- PR title: `Watchlist: add Keyrelay (credential handoff for coding agents)`
- Diff (append to the `## Candidates` list in `WATCHLIST.md`):

```diff
+- [Keyrelay](https://github.com/colefoster/keyrelay) - MIT single-file Python CLI (npm launcher) that hands a credential to one command a coding agent runs: the user types it into a one-time loopback browser form, the command receives it by environment variable or stdin, and exact echoes are redacted from the output returned to the agent. Watch because it is new (September 2026) with no independent adoption yet; it does not sandbox the command, which receives the real secret.
```

## 3. ottosulin/awesome-ai-security — medium-low fit

- List: https://github.com/ottosulin/awesome-ai-security (1.6k stars). Merging PRs as of 2026-10-31.
- Rules (README line 5): "create a PR or contact me". There is no CONTRIBUTING file. Entry format in the
  section: `* [Name](url) - _Description_`.
- Section: `### Agent Runtime Security & Sandboxing`. The neighbours are sandboxes (OpenShell, nono). Keyrelay
  is a narrower secret-handling tool, so it may be declined.
- Diff (append at the end of that section):

```diff
+* [Keyrelay](https://github.com/colefoster/keyrelay) - _One-time credential handoff for coding agents: the user types a key into a single-use local browser form and only the approved command receives it, so it never enters the model's context._
```

## 4. hesreallyhim/awesome-claude-code — not yet

- List: https://github.com/hesreallyhim/awesome-claude-code (57k stars).
- Rules (CONTRIBUTING.md, `.github/ISSUE_TEMPLATE/recommend-resource.yml`):
  - **Only the web UI issue form. No PRs, no `gh` CLI.** Breaking this risks a temporary ban.
  - Must be a human recommendation. One resource at a time.
  - Must be at least 14 days old with continued commits, or have 100+ stars. Keyrelay passes on age.
  - Descriptions are descriptive, not promotional: one line, no emojis, don't address the reader.
  - The maintainer warns that getting listed shouldn't be a promotion strategy.
- Required fields: Display Name; Category (dropdown, here `Security`); Link (https); Author Name;
  Author Link; Description (10 to 500 characters). Five required checkboxes, including **"This resource is
  specific to Claude Code"**. A sixth "do not check" box must stay unticked.
- Verdict: **don't submit now.** Keyrelay works with any agent, so the Claude Code checkbox would not be
  honest. It becomes a fit if a Claude Code-specific piece ships, such as the draft redaction hook on branch
  `harvest/xp-54q`. Draft for that day:
  - Display Name: `Keyrelay`
  - Category: `Security`
  - Link: `https://github.com/colefoster/keyrelay`
  - Author Name: `colefoster`
  - Author Link: `https://github.com/colefoster`
  - Description: `CLI that lets Claude Code run a command needing a credential without the credential entering the conversation. The user types the key into a one-time local browser form, only that command receives it, and echoes are redacted from the output Claude reads.`

## 5. RoggeOhta/awesome-codex-cli — weak

- List: https://github.com/RoggeOhta/awesome-codex-cli (560 stars). Last change 2026-09-06; submissions are
  batched ("resolve verified submissions").
- Rules (CONTRIBUTING.md): open an issue with the link and a short description, or open a PR editing
  `README.md`. Entries must be **directly related to Codex CLI**: "general AI/LLM tools don't belong unless
  they have specific Codex integration". They must be maintained and have a one-sentence description, with a
  star badge in `flat-square` style. No self-promotion without real users or clear unique value.
- Verdict: **skip for Keyrelay.** It has no Codex-specific integration. If submitted anyway, use the
  `## Cross-Agent Tools` section:

```diff
+- [colefoster/keyrelay](https://github.com/colefoster/keyrelay) - Hand Codex a credential for one command through a single-use local browser form, so the key never enters the session. ![GitHub stars](https://img.shields.io/github/stars/colefoster/keyrelay?style=flat-square)
```

## 6. bureado/awesome-agent-runtime-security — poor fit

- List: https://github.com/bureado/awesome-agent-runtime-security (131 stars). Section
  `## Secrets Management & Isolation` is a table: `| Name | Keywords | Description |`.
- Rule (README "What this list is not"): it excludes entries whose isolation "relies on a shared kernel or a
  parent process supervisor in the same privilege level". Keyrelay's command runs as the same user. The list
  wants the agent never to hold the secret. Keyrelay's guarantee is narrower: the secret stays out of the
  model context.
- Verdict: **skip.** At most it could sit in the "Other secret management tools of potential interest"
  sentence, which the maintainer curates.

## 7. tailscale-dev/awesome-tailscale — skip

- List: https://github.com/tailscale-dev/awesome-tailscale (27 stars). Only commits are from 2024-10-02. No
  PR merged among 14 opened since.
- Rules (contributing.md): PR from a new branch. Add the item at the bottom of an existing section, in the
  format `- [item name](https link): Description beginning with capital, ending in period.`
- If Cole wants it anyway (section `## Other`):

```diff
+- [colefoster/keyrelay](https://github.com/colefoster/keyrelay): A credential handoff for coding agents that can run its broker behind Tailscale Serve, so you enter a key from your phone and only the allowed Tailscale login can open the form.
```

## 8. AlternativeTo — low

- Adding an app needs an AlternativeTo account and goes through their moderation. Their pages refused
  automated fetches on 2026-10-31 (bot protection), so **current rules are unverified**.
- Plausible listing: "Keyrelay", category Security & Privacy / Developer Tools, platforms macOS and Linux,
  license Open Source (MIT), free. It would be an alternative to 1Password CLI (`op run`). It is not a real
  replacement, and the site's own usage docs say a password manager CLI can be the better fit. Low value until
  people search for it by name.
- Description (if used): `Single-use browser form for handing an API key to one command a coding agent runs, without pasting it into the chat. Free, MIT, runs locally.`

## 9. MCP and skill directories — no fit

Keyrelay ships neither an MCP server nor an agent skill. MCP directories (awesome-mcp-servers, mcp.so, Smithery)
and skill catalogs don't apply. Revisit if a Keyrelay skill (the agent-instruction snippet packaged as a
`SKILL.md`) is published.

## 10. Own metadata — do first

GitHub topics: there are five today (coding-agents, credentials, developer-tools, python, tailscale). Add the
terms people search lists for. This changes Cole's public repo, so it is listed here and not applied:

```sh
gh repo edit colefoster/keyrelay --add-topic claude-code --add-topic codex --add-topic secrets \
  --add-topic api-keys --add-topic ai-agents --add-topic security
```

npm keywords (`package.json`, takes effect on the next publish):

```diff
   "keywords": [
     "credentials",
     "coding-agents",
     "tailscale",
-    "cli"
+    "cli",
+    "claude-code",
+    "codex",
+    "api-key",
+    "secrets",
+    "ai-agents"
   ],
```
