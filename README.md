# Keyrelay

**Your agent needs an API key, then tells you not to paste it into chat. Keyrelay gives you somewhere else to enter it.**

[Product page](https://keyrelay.colefoster.ca) · [Quickstart](#quickstart) · [Security](#what-it-protects-against)

![Keyrelay demo: an agent requests a key, you enter it in the browser](docs/keyrelay-demo.gif)

The agent runs the command through Keyrelay, which prints a one-time link. You open the link, check the command,
and type the key. Keyrelay passes the key to that command once, through an environment variable or standard input,
and shows the agent the command's output with the key removed.

Keyrelay is one standard-library Python file (under 450 lines, no dependencies) plus a small npm launcher.
It runs locally by default and needs no account, server, or Tailscale.

## How it works

```
agent   ── runs ──▶  keyrelay run --env TOKEN -- COMMAND
runner  ── starts a loopback broker on 127.0.0.1 and prints a one-time link
you     ── open ───▶ http://127.0.0.1:PORT/r/ID, check the command, type the secret
broker  ── hands the secret to the runner once, then shuts down
runner  ── runs ──▶  COMMAND with $TOKEN set (or the secret on stdin)
agent   ◀── exit status and output, with the secret replaced by [REDACTED]
```

## What it protects against

- **The secret entering the conversation.** It goes from your browser to the command and never through the
  model's context, the chat transcript, or a pasted message.
- **Shell history and argv.** The secret is never a command-line argument.
- **Other web pages.** The local broker binds to `127.0.0.1` on a random port, accepts only the exact
  `Host` it was started with (which blocks DNS rebinding), and rejects cross-origin POSTs.
- **Reuse.** Each link accepts one submission. The runner claims it once, and unclaimed requests expire after five
  minutes. The broker keeps requests in memory only and doesn't log requests.
- **Accidental echoes.** If the command prints the secret (or any field value of 4 bytes or more), the copy the agent
  sees has it replaced by `[REDACTED]`.

## What it doesn't protect against

- **A malicious agent or command.** The command you approve receives the real secret. It can store it, send it
  anywhere, or print it in a form redaction misses, such as base64. Read the command on the form before you send.
  Keyrelay isn't a sandbox.
- **Other processes running as your user.** They can read the runner's memory. Environment variables are visible to
  same-user tools such as `ps -E` on macOS or `/proc/PID/environ` on Linux. If that matters to you, use `--stdin`.
- **What the target tool keeps.** A CLI that logs in may save a session or token to disk. That's up to the tool.
- **Memory erasure.** Python can't reliably wipe strings. Expired and claimed requests are deleted, not scrubbed.
- **Everyone on your Tailnet who is you.** In Tailscale mode, any device signed in as the allowed user can open a
  pending link.

Use narrowly scoped, short-lived credentials where you can. To report a vulnerability, see [SECURITY.md](SECURITY.md).

## Quickstart

You need **Node.js 18+** (for `npx`) and **Python 3.9+**. Try it with a made-up value:

```sh
npx keyrelay run --env DEMO_TOKEN -- printenv DEMO_TOKEN
```

Open the printed `http://127.0.0.1:…/r/…` link on the same computer. Check the command, enter `demo-value`, and
select **Send once**. `printenv` prints the value, and Keyrelay shows it as `[REDACTED]`; the broker then shuts down. Ctrl+C cancels the handoff.

To install it permanently, run `npm install -g keyrelay`. Without Node.js, clone this repository and run
`python3 keyrelay.py` with the same arguments.

## Use with a coding agent

Add this to your agent instructions:

> When a command needs a credential, run it with `npx keyrelay run --env VARIABLE -- COMMAND` (or `--stdin` if the tool reads it from standard input) and show me the printed link. Leave the runner waiting while I enter the credential. For several credentials, repeat `--field NAME=Label` so I get separate fields; the command receives them as one JSON object. Never ask me to paste credentials into the conversation.

For example, if you want `gh` to use a token you'll paste:

```sh
npx keyrelay run --env GITHUB_TOKEN -- gh api user
```

The runner returns the command's exit status and its redacted output. Commands that need an interactive terminal
aren't supported.

## Options

### `--env NAME` or `--stdin`

`--env NAME` sets the secret as an environment variable for the command. `--stdin` writes the secret, followed by
a newline, to the command's standard input. Use `--stdin` for tools that read the secret from input, such as
`gh auth login --with-token`.

### Several credentials: `--field NAME=Label`

```sh
npx keyrelay run --env X_CREDENTIALS_JSON \
  --field 'apiKey=API Key' --field 'apiSecret=API Key Secret' \
  --field 'accessToken=Access Token' --field 'accessTokenSecret=Access Token Secret' \
  -- your-command
```

The form shows one password field per `--field`. The command receives one JSON object keyed by field name, through
`--env` or `--stdin`. You can use up to 16 fields, each name must be a unique identifier, and every field is required.
The whole submission can be up to 16,384 characters.

### Instructions: `--note` and `--field-help NAME=Text`

`--note` adds plain text above the form, up to 2,000 characters. `--field-help` adds help under one field, up to
1,000 characters. **Never put credentials in labels, notes, help, or the command.** That text is shown on the form,
not kept secret.

Every form has **Show values** for checking what you pasted. The fields are cleared and hidden again when you submit.

### Sign in or exchange credentials for a token

Fields also cover sign-ins and first-run account setup. You type the username and password, and the command trades
them for something narrower, such as an API key:

```sh
npx keyrelay run --stdin \
  --field 'email=Admin email' --field 'password=Admin password' \
  -- python3 examples/immich_api_key.py http://immich.example:2283 immich-api-key.txt
```

[`examples/immich_api_key.py`](examples/immich_api_key.py) creates the first Immich admin, signs in, creates an API
key, and signs out. A command like it should follow three rules:

- **Send secrets to the target on stdin, never in argv.** Arguments show up in the process list. Use
  `curl --data @-`, not `curl -d "$PASSWORD"`.
- **Print only the outcome**, such as "API key saved". Don't print the password, the key, or a raw response.
- **Save only the token**, in a file only you can read (mode `0600`). Never save the password.

Keyrelay can't handle sign-ins that need a person at the page, such as 2FA, CAPTCHAs, passkeys, or SSO. Use your
agent's own browser tool for those. The agent opens the sign-in page, stops reading it while you sign in, and carries
on once you say you're done.

### Another device: `--url` with a Tailscale broker

A local link works only on the computer running the command. To enter a secret from your phone, run a persistent
broker behind [Tailscale Serve](https://tailscale.com/kb/1312/serve). It must be HTTPS and reachable only on your
Tailnet.

```sh
npx keyrelay serve --email you@example.com --host your-broker.your-tailnet.ts.net
tailscale serve --bg http://127.0.0.1:8765
```

Then pass the broker to the runner:

```sh
npx keyrelay run --url https://your-broker.your-tailnet.ts.net --env DEMO_TOKEN -- python3 -c "print('Handoff complete.')"
```

The broker accepts a request only when `Host` matches `--host` exactly and Tailscale Serve identifies the user as
`--email`. Keep it bound to localhost so the identity header can only come from Tailscale Serve. **Don't use Tailscale
Funnel or a public reverse proxy.** The secret still goes to the command on the machine that runs `keyrelay run`.

To run the broker as a Linux service, edit the email and host in [`keyrelay.service`](keyrelay.service), then run:

```sh
sudo install -D -m 644 keyrelay.py /opt/keyrelay/keyrelay.py
sudo install -m 644 keyrelay.service /etc/systemd/system/keyrelay.service
sudo systemctl daemon-reload && sudo systemctl enable --now keyrelay.service
```

## Alternatives

Keyrelay is for when an agent runs the command and you're not at its terminal. Other options can be a better fit:

- **`read -s` in your own terminal.** `read -s TOKEN && TOKEN="$TOKEN" your-command` keeps the value off-screen and
  out of history. This works when you're typing into the shell that runs the command, which an agent's tool calls
  usually aren't.
- **A password manager CLI**, such as `op run` from 1Password. Secrets are referenced by name and injected when the
  command runs. This works well if the secret is already in a vault and you're comfortable with the agent requesting
  it by name.
- **`.env` files with direnv.** These are convenient for long-lived development keys. The value sits in plain text on
  disk, where the agent can read it, so use this only for keys you'd let the agent see.

## Development

```sh
python3 -m unittest discover -s tests
```

The tests need Node.js for the browser-script checks. Tests use made-up values only.

## License

[MIT](LICENSE) © 2026 Cole Foster
