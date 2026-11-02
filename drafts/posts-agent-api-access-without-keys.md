---
title: "Giving AI coding agents API access without giving them the keys"
description: "Why env vars, pasted keys, and readable config files leak credentials to coding agents, and how brokers, scoped tokens, and a one-time handoff like Keyrelay keep the key out of the transcript."
slug: agent-api-access-without-keys
date: 2026-10-29
status: draft
tags: [coding-agents, security, credentials, keyrelay]
og_summary: >-
  Coding agents need API keys to do real work, but the usual ways of handing
  them over (shell env vars, pasting into the prompt, config files on disk) put
  the key where the model can read it, and so into the transcript. This guide
  explains the failure in each, the patterns that avoid it (a broker that
  injects the credential at the boundary, scoped short-lived tokens, and a
  human handoff that never touches the conversation), and where Keyrelay, a
  small open-source one-time credential handoff, fits and where it doesn't.
---

# Giving AI coding agents API access without giving them the keys

A coding agent that can run commands will eventually need a credential: an API key to call a service, a token to
publish a package, a password to set up a self-hosted app. This guide explains how to give the agent's command
that credential without putting the value into the conversation, where the model reads it, logs keep it, and
anything the model later writes can repeat it.

This guide is for developers who run coding agents such as Claude Code or Codex against real accounts. It assumes
that you trust the agent to run commands, but don't want a long-lived secret in its context.

## The goal

Separate two things that are easy to conflate:

- **Authority**: the agent's command is allowed to call the API.
- **Knowledge**: the model has seen the key's value.

The agent needs the first. It almost never needs the second. Every pattern below is a way to grant authority while
withholding knowledge.

## Three common approaches that leak the key

### Exporting the key in the agent's shell

You run `export OPENAI_API_KEY=...` in the terminal where the agent works, or put it in a shell profile.

**What goes wrong:** the agent's shell is the model's shell. The model can run `env`, `printenv`, or `echo
$OPENAI_API_KEY`, and the output comes straight back into its context. A routine debugging step is enough;
no malice is required. The key also reaches every
command the agent runs in that session, not only the one that needs it.

### Pasting the key into the prompt

You paste the key into the chat and ask the agent to use it.

**What goes wrong:** the value is now part of the conversation. It's sent to the model provider, stored in the
local transcript and history, and available to the model for the rest of the session. The model may also put it
somewhere permanent, such as a command line (visible in the process list and shell history), a config file, or a
commit.

### A config file the agent can read

You put the key in `.env`, `~/.config/tool/credentials`, or a similar file, and point the tool at it.

**What goes wrong:** if the agent can read files, it can read that one. A `cat .env` or a broad search over the
project brings the value into context just as `printenv` does. This approach is acceptable only for keys that you would be comfortable letting the agent see.

## Patterns that keep the key out of the model's context

### Inject at the boundary with a credential proxy or broker

The command never holds the key. It sends requests to a local proxy or broker, and the broker adds the credential
on the way out. The model can see the proxy's address but never the key. This is the strongest pattern for repeated API
calls. It takes more setup: the proxy must understand the API's authentication and decide which requests to sign.

### Use scoped, short-lived tokens

Whatever reaches the command should be worth as little as possible if it leaks. Prefer a token limited to one
repository, one project, or read-only access, with an expiry measured in hours or days rather than never. Many
providers support this through fine-grained personal access tokens or OAuth token exchange. Scoping doesn't keep
the value out of the transcript, but it limits the damage when it gets there.

### Hand off through a person, outside the transcript

When a person holds the key and a waiting command needs it once, the person can enter it directly into that
command's environment through a channel the model can't read. The model knows that a credential was supplied, but
not what it was. This works well for one-off setup tasks, such as logging a CLI in or creating the first admin
account on a self-hosted service.

A password manager CLI covers the case where the key is already in a vault: `op run` from 1Password, for example,
resolves secret references when the command starts. A human handoff covers the case where it isn't.

## Where Keyrelay fits

[Keyrelay](https://github.com/colefoster/keyrelay) is a small, MIT-licensed tool that implements the human handoff.
It's one standard-library Python file and a short npm launcher, it runs locally, and it needs no account.

The agent runs the command through `keyrelay run`. Keyrelay starts a broker on `127.0.0.1`, prints a one-time link,
and waits. You open the link, check the exact command that will receive the secret, type the value, and select
**Send once**. Keyrelay runs that one command with the value as an environment variable (`--env NAME`) or on
standard input (`--stdin`), then prints the command's output with any exact copy of the value replaced by
`[REDACTED]`.

Each link works once and expires after five minutes. The broker accepts only its exact loopback `Host` header and
same-origin form posts. The value isn't put in command arguments or shell history, and it isn't set in the agent's
shell afterward.

### What it doesn't do

Keyrelay is a handoff, not a sandbox or a proxy. Be clear about its limits before you rely on it:

- **The command gets the real key.** A command that you approve can store, send, or transform the value. Redaction
  only catches exact copies, so an encoded value such as base64 passes through. Read the command before you send.
- **Other processes running as you** can read a process's environment and memory. Use `--stdin` if that matters.
- **The target tool may keep its own copy.** For example, a CLI that you log in may save a token to disk where
  the agent can later read it.
- **Output is buffered.** Keyrelay captures the command's output until it exits so that it can redact it. Long or
  interactive commands don't show progress.
- **It handles one run at a time.** For repeated API calls, a broker that injects credentials at the boundary is the
  better pattern.
- **It can't handle sign-ins that need a person on the page**, such as 2FA prompts, CAPTCHAs, passkeys, or SSO.

A redaction hook for Claude Code, which would block prompts and tool output that look like credentials, is in
progress as a draft specification. It isn't released. Even once it is, it's a second line of defense: by its own
description it can't remove a value from local transcripts after the value was pasted.

## Worked example: log in the GitHub CLI without pasting a token

This example uses a fine-grained GitHub token, which follows the scoped-token pattern, and Keyrelay for the
handoff. It needs Node.js 18 or later and Python 3.9 or later.

1. Try the handoff first with a made-up value:

   ```sh
   npx keyrelay run --env DEMO_TOKEN -- printenv DEMO_TOKEN
   ```

   Open the printed link, enter any text, and select **Send once**. The command prints the value, and the output
   shows `[REDACTED]` instead. `$DEMO_TOKEN` isn't set in your shell afterward.

2. Add this instruction to your agent's instructions file, so that it uses the same route for real credentials:

   > When a command needs a credential, run it with `npx keyrelay run --env VARIABLE -- COMMAND` (or `--stdin` if
   > the tool reads it from standard input) and show me the printed link. Leave the runner waiting while I enter the
   > credential. For several credentials, repeat `--field NAME=Label`; the command receives them as one JSON object.
   > Never ask me to paste credentials into the conversation.

3. In GitHub, create a fine-grained personal access token limited to the repositories and permissions the task
   needs, with a short expiry.

4. Ask the agent to log in the GitHub CLI. It runs:

   ```sh
   npx keyrelay run --stdin -- gh auth login --with-token
   ```

   `gh auth login --with-token` reads the token from standard input, so `--stdin` is the right mode.

5. Open the link the agent shows you, confirm that the command is `gh auth login --with-token`, paste the token, and
   select **Send once**. The agent sees the command's exit status and redacted output.

Note what this example doesn't protect: `gh` stores the token in its own credential store, and the agent can use
`gh` afterward. That's the point of logging in, and it's why the token should be scoped and short-lived.

## FAQ

**Doesn't the agent still control which command gets the key?**
Yes. Keyrelay shows you the exact command before you send, and that review is the control. If you don't trust the
agent to choose commands, a credential handoff won't help. Use a proxy that enforces a request policy instead.

**Can I enter the key from my phone?**
Yes. Keyrelay can run a persistent broker behind Tailscale Serve, restricted to one Tailscale identity, with
`keyrelay serve` on the host and `keyrelay run --url` from the agent. Don't expose it through Tailscale Funnel or a
public reverse proxy. Any of your own devices on the tailnet can open a pending link.

**Is `.env` with direnv ever fine?**
Yes, for development keys that you'd be comfortable letting the agent read. The value sits in plain text on disk,
so treat it as visible to the agent.

**Does Keyrelay store or log the key?**
Pending requests are held in the broker's memory and removed when the runner claims the value or the request
expires. Python can't guarantee that memory is scrubbed, and the command you run may save its own copy.

**What if I already pasted a key into the chat?**
Revoke it and issue a new one. Redacting the transcript later doesn't recall what was already sent to the model or
written to local history.
