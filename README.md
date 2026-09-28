# Keyrelay

**Give a coding agent a credential without pasting it into chat.**

[Product page](https://getkeyrelay.colefoster.ca) · [Setup](#setup) · [Security model](#security-model)

The agent starts a command and receives a one-time link. Open it on the same computer, review the command, and enter your token. Keyrelay delivers it once to the waiting command through an environment variable or standard input.

- Runs locally by default. No account, server setup, or Tailscale required.
- Starts a temporary loopback-only broker and closes it when the command finishes.
- Requests live in memory and expire after five minutes.
- Plain-text echoes of the credential are redacted from captured command output.
- Optional Tailscale broker for handoffs from another device.

## Setup

Install **Node.js 18+** (includes `npx`) and **Python 3.9+**, then run:

```sh
npx github:colefoster/keyrelay run --env GITHUB_TOKEN -- gh api user
```

`npx` downloads the launcher and bundled Python implementation. You do not need to clone this repository, start a server, or configure networking. The tool you run (`gh` in this example) must already be installed.

Open the printed `http://127.0.0.1:…/r/…` link **on the same computer**. Review the command, enter your token, and select **Send once**. The command runs, then the local broker shuts down. The link expires after five minutes; Ctrl+C cancels it.

To install a persistent CLI instead:

```sh
npm install -g github:colefoster/keyrelay
keyrelay run --env GITHUB_TOKEN -- gh api user
```

For a command that accepts its credential on standard input:

```sh
npx github:colefoster/keyrelay run --stdin -- gh auth login --with-token
```

The runner returns the command's exit status and redacted output. Interactive commands that need a terminal are not supported.

Without Node.js, clone the repository and use `python3 keyrelay.py run --env GITHUB_TOKEN -- gh api user` instead.

## Optional: use another device with Tailscale

Local links work only on the machine running the command. To enter credentials from your phone or another computer, run a persistent broker behind Tailscale. You need Tailscale on the broker and client devices and HTTPS enabled in your Tailnet.

```sh
npx github:colefoster/keyrelay serve --email you@example.com
```

In another terminal:

```sh
tailscale serve --bg http://127.0.0.1:8765
```

Use the HTTPS URL printed by Tailscale:

```sh
npx github:colefoster/keyrelay run \
  --url https://your-broker.your-tailnet.ts.net \
  --env GITHUB_TOKEN -- gh api user
```

Keep the backend on localhost; only the trusted Tailscale Serve proxy should supply identity headers. **Do not use Tailscale Funnel or a public reverse proxy.**

For a persistent Linux service, edit `keyrelay.service` to use your Tailscale login, then:

```sh
sudo install -d /opt/keyrelay
sudo install -m 644 keyrelay.py /opt/keyrelay/keyrelay.py
sudo install -m 644 keyrelay.service /etc/systemd/system/keyrelay.service
sudo systemctl daemon-reload
sudo systemctl enable --now keyrelay.service
```

The optional `--auth whois` mode is for the maintainer's existing private nginx deployment. It expects a trusted `X-Real-IP` header and the `keyrelay.colefoster.ca` Host header. Use the default Tailscale Serve mode for your own installation.

## Use with a coding agent

Add this to your agent instructions:

> When a command needs a credential, run it with `npx github:colefoster/keyrelay run --env VARIABLE -- COMMAND` (or `--stdin`) and show me the printed one-time link. Leave the runner waiting while I enter the credential in my browser. Never ask me to paste credentials into the conversation. The link opens on the computer running the command; use a configured Tailscale broker with `--url` for remote agents.

## Security model

Keyrelay keeps credentials out of the normal chat handoff. **It is not a sandbox or a defense against a malicious agent or command.** Review the displayed command and use it only on trusted machines with agents you trust.

The broker holds requests and submitted secrets in process memory. Expired entries are removed on the next request; expiry is not guaranteed memory erasure. A successful claim deletes the entry. Restarting the broker discards pending requests. Keyrelay does not write credentials to a database or log HTTP requests.

The runner captures stdout and stderr, replacing exact copies of the secret before displaying them. Encoded, transformed, or deliberately transmitted credentials are not covered. The command receives the real credential and can store it; authenticated CLIs may persist sessions. Other software with sufficient access to the broker or runner can read process memory or environments. Use narrowly scoped, short-lived credentials where possible.

In local mode, the broker binds only to `127.0.0.1` on a randomly assigned port. It checks the exact Host header to reject DNS rebinding and rejects cross-origin POSTs. Local programs and users on the same machine remain trusted: this is not OS-user authentication. Do not forward the port or expose it through a proxy.

In Tailscale mode, only the configured Tailscale identity is allowed to access the broker. All requests by that identity share the same trust boundary; this is a personal handoff tool, not a multi-tenant secret manager.

## Development

```sh
python3 -m unittest discover -s tests
python3 -m http.server 8080 --directory site
```

The public product page is static and collects no credentials. It is deployed to Cloudflare Pages separately from the private broker. See [site deployment](docs/site-deployment.md).
