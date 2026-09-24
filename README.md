# Keyrelay

Give a coding agent a credential **without pasting it into chat**. The agent runs a command with `keyrelay.py run`, receives a link, and waits. Open the link on a Tailnet device, review the command, and enter the credential. Keyrelay sends it once to the waiting runner, which passes it to the command through an environment variable or standard input.

The broker keeps requests in memory for at most five minutes. It does not persist credentials, use a database, or log HTTP requests. The runner redacts plain-text echoes of the secret from command output. A command can still deliberately transmit or transform a credential, so review the displayed command and use this only with agents you trust to run commands on your machine.

## Live broker

The broker runs as `keyrelay.service` on ash at **https://keyrelay.colefoster.ca/**. The hostname points to ash's Tailscale IP and nginx listens only there. The broker verifies the connecting Tailscale user with `tailscale whois` and accepts only `cole@thefostersonline.com`.

## Install or update on ash

Use a free localhost port. The example uses 8765. Set the email to **your own Tailscale login**.

```sh
sudo install -d /opt/keyrelay
sudo install -m 644 keyrelay.py /opt/keyrelay/keyrelay.py
sudo install -m 644 keyrelay.service /etc/systemd/system/keyrelay.service
sudo systemctl daemon-reload
sudo systemctl enable --now keyrelay.service
```

The nginx configuration and certificate renewal units are in `/Users/cole/Dev/ash-infra`. Keep the DNS record **DNS-only** and the nginx listener bound to ash's Tailscale IP. The backend binds only to localhost and refuses requests without a verified Tailnet login.

The broker stays running through systemd while a request is pending. The client can run on any Tailnet device that can reach the private hostname.

## Use from Codex or Claude Code

Give the agent a command like this:

```sh
python3 /Users/cole/Dev/keyrelay/keyrelay.py run --url https://keyrelay.colefoster.ca --env GITHUB_TOKEN -- gh api user
```

Or for tools that read a token from standard input:

```sh
python3 /Users/cole/Dev/keyrelay/keyrelay.py run --url https://keyrelay.colefoster.ca --stdin -- gh auth login --with-token
```

The agent should show you the printed link. Open it, verify the command, enter the credential, and press **Send once**. The runner then executes the command and returns its output with plain-text copies of the secret removed.

The agent never needs to read, paste, or store the raw credential. If a CLI must persist an authenticated session, that CLI controls its own storage after the handoff. Keyrelay itself stores no reusable key.

## Local smoke test

`python3 -m unittest discover -s tests` tests the one-time exchange. The server requires a verified Tailnet client IP, so direct browser access to `localhost:8765` is intentionally denied.
