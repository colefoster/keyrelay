# Security

## Reporting a vulnerability

Report vulnerabilities privately through
[GitHub's private vulnerability reporting](https://github.com/colefoster/keyrelay/security/advisories/new).
Please don't open a public issue for anything that could expose someone's credentials.

Include the Keyrelay version (`npm view keyrelay version` or the commit), the mode you used (local, or a Tailscale
broker with `--url`), and the steps to reproduce. Use made-up values. Never include a real credential.

## Scope

In scope are ways for something other than the approved command to obtain a submitted secret. Examples:

- another web page or local network peer reading or submitting a request
- a request being claimed twice, or after it expired
- a secret appearing in broker logs, the agent-facing output, or command arguments

Out of scope are the limits listed in the README under
[What it doesn't protect against](README.md#what-it-doesnt-protect-against). These include a malicious command,
same-user processes, and secrets that a command transforms before printing.

Only the latest release gets fixes.
