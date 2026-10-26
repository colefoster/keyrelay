# Keyrelay usage

Reference for everything beyond the [README](../README.md) quickstart.

## `--env NAME` or `--stdin`

`--env NAME` sets the secret as an environment variable for the command. `--stdin` writes the secret, followed by
a newline, to the command's standard input. Use `--stdin` for tools that read the secret from input, such as
`gh auth login --with-token`.

## Several credentials: `--field NAME=Label`

```sh
npx keyrelay run --env X_CREDENTIALS_JSON \
  --field 'apiKey=API Key' --field 'apiSecret=API Key Secret' \
  --field 'accessToken=Access Token' --field 'accessTokenSecret=Access Token Secret' \
  -- your-command
```

The form shows one password field per `--field`. The command receives one JSON object keyed by field name, through
`--env` or `--stdin`. You can use up to 16 fields, each name must be a unique identifier, and every field is required.
The whole submission can be up to 16,384 characters.

## Instructions: `--note` and `--field-help NAME=Text`

`--note` adds plain text above the form, up to 2,000 characters. `--field-help` adds help under one field, up to
1,000 characters. **Never put credentials in labels, notes, help, or the command.** That text is shown on the form,
not kept secret.

Every form has **Show values** for checking what you pasted. The fields are cleared and hidden again when you submit.

## Sign in or exchange credentials for a token

Fields also cover sign-ins and first-run account setup. You type the username and password, and the command trades
them for something narrower, such as an API key:

```sh
npx keyrelay run --stdin \
  --field 'email=Admin email' --field 'password=Admin password' \
  -- python3 examples/immich_api_key.py http://immich.example:2283 immich-api-key.txt
```

[`examples/immich_api_key.py`](../examples/immich_api_key.py) creates the first Immich admin, signs in, creates an API
key, and signs out. A command like it should follow three rules:

- **Send secrets to the target on stdin, never in argv.** Arguments show up in the process list. Use
  `curl --data @-`, not `curl -d "$PASSWORD"`.
- **Print only the outcome**, such as "API key saved". Don't print the password, the key, or a raw response.
- **Save only the token**, in a file only you can read (mode `0600`). Never save the password.

Keyrelay can't handle sign-ins that need a person at the page, such as 2FA, CAPTCHAs, passkeys, or SSO. Use your
agent's own browser tool for those. The agent opens the sign-in page, stops reading it while you sign in, and carries
on once you say you're done.

## Another device: `--url` with a Tailscale broker

A local link works only on the computer running the command. To enter a secret from your phone, run a persistent
broker behind [Tailscale Serve](https://tailscale.com/kb/1312/serve). It must be HTTPS and reachable only on your
Tailnet.

```sh
npx keyrelay serve --email you@example.com --host your-broker.your-tailnet.ts.net
tailscale serve --bg http://127.0.0.1:8765
```

Then pass the broker to the runner:

```sh
npx keyrelay run --url https://your-broker.your-tailnet.ts.net --env DEMO_TOKEN -- printenv DEMO_TOKEN
```

The broker accepts a request only when `Host` matches `--host` exactly and Tailscale Serve identifies the user as
`--email`. Keep it bound to localhost so the identity header can only come from Tailscale Serve. **Don't use Tailscale
Funnel or a public reverse proxy.** The secret still goes to the command on the machine that runs `keyrelay run`.

To run the broker as a Linux service, edit the email and host in [`keyrelay.service`](../keyrelay.service), then run:

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
