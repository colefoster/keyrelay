# Keyrelay

**Give a coding agent a credential without pasting it into chat.**

[Product page](https://getkeyrelay.colefoster.ca) · [Setup](#setup) · [Security model](#security-model)

The agent starts a command and receives a one-time link. Open it on a Tailnet device, review the command, and enter your token. Keyrelay delivers it once to the waiting runner through an environment variable or standard input.

- One Python file; standard library only.
- Private broker authenticated with Tailscale identity.
- Requests live in memory and expire after five minutes.
- Plain-text echoes of the credential are redacted from captured command output.

## Setup

You need Python 3.9+ and Tailscale on the broker and client devices. Enable HTTPS in your Tailnet for Tailscale Serve. Run the broker on a trusted machine.

```sh
git clone https://github.com/colefoster/keyrelay.git
cd keyrelay
python3 keyrelay.py serve --email you@example.com
```

In another terminal, expose the localhost broker to your Tailnet:

```sh
tailscale serve --bg http://127.0.0.1:8765
```

Use the HTTPS URL printed by Tailscale as your broker URL. Keep the backend on localhost; only the trusted Tailscale Serve proxy should supply identity headers. **Do not use Tailscale Funnel or a public reverse proxy.**

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

Replace the example URL with your broker's HTTPS URL:

```sh
python3 keyrelay.py run \
  --url https://your-broker.your-tailnet.ts.net \
  --env GITHUB_TOKEN -- gh api user
```

For a command that accepts its credential on standard input:

```sh
python3 keyrelay.py run \
  --url https://your-broker.your-tailnet.ts.net \
  --stdin -- gh auth login --with-token
```

Ask your agent to show you the printed link. Open it, verify the command, enter the credential, and select **Send once**. The waiting command runs and returns its exit status and redacted output. Interactive commands that need a terminal are not supported.

An example instruction for your agent:

> When a command needs a credential, use Keyrelay's `run` command and show me the one-time link. Never ask me to paste credentials into the conversation.

## Security model

Keyrelay keeps credentials out of the normal chat handoff. **It is not a sandbox or a defense against a malicious agent or command.** Review the displayed command and use it only on trusted machines with agents you trust.

The broker holds requests and submitted secrets in process memory. Expired entries are removed on the next request; expiry is not guaranteed memory erasure. A successful claim deletes the entry. Restarting the broker discards pending requests. Keyrelay does not write credentials to a database or log HTTP requests.

The runner captures stdout and stderr, replacing exact copies of the secret before displaying them. Encoded, transformed, or deliberately transmitted credentials are not covered. The command receives the real credential and can store it; authenticated CLIs may persist sessions. Other software with sufficient access to the broker or runner can read process memory or environments. Use narrowly scoped, short-lived credentials where possible.

Only the configured Tailscale user is allowed to access the broker. All requests by that identity share the same trust boundary; this is a personal handoff tool, not a multi-tenant secret manager.

## Development

```sh
python3 -m unittest discover -s tests
python3 -m http.server 8080 --directory site
```

The public product page is static and collects no credentials. It is deployed to Cloudflare Pages separately from the private broker. See [site deployment](docs/site-deployment.md).
