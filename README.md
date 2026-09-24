# Keyrelay

Give a coding agent a credential **without pasting it into chat**. The agent runs a command with `keyrelay.py run`, receives a link, and waits. Open the link on a Tailnet device, review the command, and enter the credential. Keyrelay sends it once to the waiting runner, which passes it to the command through an environment variable or standard input.

The broker keeps requests in memory for at most five minutes. It does not persist credentials, use a database, or log HTTP requests. The runner redacts plain-text echoes of the secret from command output. A command can still deliberately transmit or transform a credential, so review the displayed command and use this only with agents you trust to run commands on your machine.

## Live broker

The broker runs as `keyrelay.service` on ash. Tailscale Serve exposes it at `https://ash.tailf89aba.ts.net:8443`. Only `cole@thefostersonline.com` is accepted. The systemd service and Serve configuration survive reboots.

## Install or update on ash

Use a free localhost port. The example uses 8765. Set the email to **your own Tailscale login**.

```sh
sudo install -d /opt/keyrelay
sudo install -m 644 keyrelay.py /opt/keyrelay/keyrelay.py
sudo install -m 644 keyrelay.service /etc/systemd/system/keyrelay.service
sudo systemctl daemon-reload
sudo systemctl enable --now keyrelay.service
```

In another shell on the same machine:

```sh
sudo tailscale serve --bg --https=8443 http://127.0.0.1:8765
sudo tailscale serve status
```

Use **Serve**, never Funnel. Serve supplies the `Tailscale-User-Login` identity header. The backend binds only to localhost and refuses requests without the exact allowed login. Grant only your devices access to the Serve port in the Tailnet ACL if the tailnet has other members.

For a persistent service, run the broker with systemd using a dedicated user and the `ExecStart` equivalent of the first command. It must stay running while a request is pending. The client can run on any Tailnet device that can reach the Serve URL.

## Use from Codex or Claude Code

Give the agent a command like this, with the actual Serve URL:

```sh
python3 /Users/cole/Dev/keyrelay/keyrelay.py run --url https://ash.tailf89aba.ts.net:8443 --env GITHUB_TOKEN -- gh api user
```

Or for tools that read a token from standard input:

```sh
python3 /Users/cole/Dev/keyrelay/keyrelay.py run --url https://ash.tailf89aba.ts.net:8443 --stdin -- gh auth login --with-token
```

The agent should show you the printed link. Open it, verify the command, enter the credential, and press **Send once**. The runner then executes the command and returns its output with plain-text copies of the secret removed.

The agent never needs to read, paste, or store the raw credential. If a CLI must persist an authenticated session, that CLI controls its own storage after the handoff. Keyrelay itself stores no reusable key.

## Local smoke test

`python3 -m unittest discover -s tests` tests the one-time exchange. The server requires a Tailscale identity header, so direct browser access to `localhost:8765` is intentionally denied.
