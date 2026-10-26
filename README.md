# Keyrelay

**Give your agent the key, keep it out of the chat.**

Keyrelay prints a single-use link. You open it, check the command, and type the key. It goes straight to that one
command and never into the conversation.

[Product page](https://keyrelay.colefoster.ca) · [Usage](https://github.com/colefoster/keyrelay/blob/main/docs/usage.md) · [Security](#security)

![Keyrelay demo: an agent requests a key, you enter it in the browser](https://raw.githubusercontent.com/colefoster/keyrelay/main/docs/keyrelay-demo.gif)

## Quickstart

Needs Node.js 18+ and Python 3.9+. Try it with a made-up value:

```sh
npx keyrelay run --env DEMO_TOKEN -- printenv DEMO_TOKEN
```

Open the printed link, enter anything, and select **Send once**. `printenv` prints the value, and you see
`[REDACTED]`. Afterwards `$DEMO_TOKEN` isn't set in your shell: only that one command got it.

`keyrelay run --env NAME` asks you for the secret, then `-- your command` runs with it as `$NAME`.
Use `--stdin` instead for tools that read the secret from standard input.

## Use with a coding agent

Add this to your agent instructions:

> When a command needs a credential, run it with `npx keyrelay run --env VARIABLE -- COMMAND` (or `--stdin` if the tool reads it from standard input) and show me the printed link. Leave the runner waiting while I enter the credential. For several credentials, repeat `--field NAME=Label`; the command receives them as one JSON object. Never ask me to paste credentials into the conversation.

## How it works

1. The agent runs the command through Keyrelay. It starts a broker on `127.0.0.1` and prints a one-time link.
2. You open the link, check the exact command, and type the key.
3. Keyrelay hands the key to that command once and returns its exit status and output, with the key replaced by
   `[REDACTED]`.

One standard-library Python file (under 450 lines, no dependencies) plus a small npm launcher. Runs locally, no
account. Multiple fields, sign-in flows, and a Tailscale broker for entering keys from your phone are in
[Usage](https://github.com/colefoster/keyrelay/blob/main/docs/usage.md).

## Security

Keyrelay keeps the secret out of the conversation, shell history, and command arguments. The broker accepts only
its exact loopback `Host` and same-origin posts, each link works once and expires after five minutes, and any echo
of the secret in the output is redacted.

### What it doesn't protect against

- **A malicious command.** The command you approve gets the real secret and can store, send, or transform it
  (base64 slips past redaction). Read the command before you send. Keyrelay isn't a sandbox.
- **Other processes running as you.** They can read a process's environment and memory; use `--stdin` if that
  matters. Python can't scrub secrets from memory.
- **What the target tool keeps.** A CLI may save its own session or token to disk.
- **Your other devices on your Tailnet**, in Tailscale mode: any device signed in as you can open a pending link.

Prefer scoped, short-lived credentials. Report vulnerabilities via [SECURITY.md](SECURITY.md).

## Development

```sh
python3 -m unittest discover -s tests
```

## License

[MIT](LICENSE) © 2026 Cole Foster
