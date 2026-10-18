# Browser handoff: you sign in, the agent continues

Use this pattern when a sign-in can't be scripted: 2FA prompts, CAPTCHAs, passkeys, SSO redirects, or a site
with no API for logging in. The agent opens the page in a browser you can both see. You sign in yourself. The agent
takes over again once you're done. Your password never passes through the agent or Keyrelay.

**Why this isn't a Keyrelay command:** the browser session belongs to the agent's browser tool, such as the Claude
desktop app's browser pane, Claude in Chrome, or a headed Playwright window. Keyrelay never sees the page, so it can't
check when you're done or keep the agent from reading the page. The safety comes from the rules below, which the
agent has to follow.
Keyrelay is still useful at the end of the flow, when the site shows a new token that should go to a tool and not to
the chat (step 6 of the example).

## Rules for the agent

While you sign in:

- **Don't look.** No screenshots, page reads, accessibility snapshots, or JavaScript on that tab until you say
  you're done. This applies even when the agent is "just checking whether it loaded."
- **Don't fill.** Never type, paste, or autofill a password, one-time code, or recovery code, even one the user
  provides. Clicking "Sign in with Google" or similar is fine. Typing into the identity provider's form isn't.
- **Don't solve challenges.** CAPTCHAs and bot checks are yours.

After you sign in:

- **Don't take the session.** Never read or export cookies, `localStorage`, or session tokens. Never save Playwright
  `storage_state`, HAR files, or network logs that contain them.
- **Stop at approvals.** Fill in the form for an action, then let you press the button that creates a credential,
  grants OAuth access, or accepts terms.
- **Clean up.** When the task is done, sign out or close a temporary browser profile. A browser pane that keeps
  sign-ins between sessions keeps this one too, until you sign out.

## How control comes back

Pick one:

1. **You say so (default).** The agent opens the page, says "Sign in in the browser, then tell me when you're done,"
   and ends its turn. You reply "done."
2. **A postcondition, for scripted flows.** A headed Playwright script waits for the URL to leave the sign-in page.
   It doesn't read the page while waiting:

   ```python
   from playwright.sync_api import sync_playwright

   with sync_playwright() as p:
       browser = p.chromium.launch(headless=False)
       context = browser.new_context()          # fresh profile; never pass or save storage_state
       page = context.new_page()
       page.goto("https://dash.cloudflare.com/login")
       print("Sign in in the browser window. Waiting up to 5 minutes...")
       page.wait_for_url(lambda url: "/login" not in url and "/two-factor" not in url, timeout=300_000)
       page.goto("https://dash.cloudflare.com/profile/api-tokens")
       # ... continue with the steps you approved ...
   ```

   A URL change only shows that the site moved on. It doesn't show that the right account signed in, so check the
   account name on the next page before you continue.

## Worked example: a scoped Cloudflare API token

The task: "Set up DNS automation for `example.com`." It needs a Cloudflare API token limited to that zone. Cloudflare
sign-in has 2FA and sometimes a Turnstile challenge, so it can't be scripted.

1. **The agent opens the page.** It navigates its browser to `https://dash.cloudflare.com/profile/api-tokens` and
   says: *"Sign in in the browser pane (2FA included). I won't read the page until you tell me you're done."* Then it
   stops.
2. **You sign in** with your password, 2FA code, and any challenge. Then you reply "done."
3. **The agent checks where it is.** It reads the page once and confirms the account email in the header. If the
   wrong account is signed in, it stops and says so.
4. **The agent drafts the token.** It selects **Create Token > Edit zone DNS**, limits **Zone Resources** to
   `example.com`, and sets an expiry. Then it stops before **Create Token** and lists the permissions it chose.
5. **You approve** by checking the summary and selecting **Create Token** yourself.
6. **The token goes to the tool, not the chat.** Cloudflare shows the token once. Before you copy it, the agent
   starts a Keyrelay handoff into the place that needs it. If the automation runs as a Cloudflare Worker, that's:

   ```sh
   npx keyrelay run --stdin -- wrangler secret put CLOUDFLARE_API_TOKEN
   ```

   You paste the token into the Keyrelay form, not into the chat. The agent sees only Wrangler's redacted output.
7. **Clean up.** The agent closes the tab. If the browser profile keeps sign-ins, it asks whether you want to sign
   out of Cloudflare.

If the agent really needs the token itself, for example to make API calls in this session, it may read the token from
the page in step 6. That's the same trade as an `exchange` result: a scoped, revocable credential reaches the agent,
and your password and 2FA don't.

## When to use `exchange` instead

If the site has a plain username-and-password API, such as a self-hosted app's `/api/auth/login`, use
[`keyrelay exchange`](../README.md#sign-ins-and-account-creation-keyrelay-exchange). It runs without a browser, works
from your phone over Tailscale, and returns only a derived result. Use the browser handoff when a human has to be
there for the sign-in itself.
