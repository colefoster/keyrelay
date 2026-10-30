# Keyrelay redaction hook — draft specification

Status: prototype, not installed or released. Checked against the
[Claude Code hooks reference](https://code.claude.com/docs/en/hooks.md) on
2026-10-29. See [prior art](../PRIOR_ART.md) and [release gaps](../NOTES.md).

## What can actually be protected

This hook attempts to stop recognizable credentials from reaching **the model**.
It cannot promise that raw values never enter the local transcript, prompt
history, telemetry, or terminal buffers. Never test it with a real credential.

The official contract explicitly documents two limitations:

- [Blocked prompts](https://code.claude.com/docs/en/hooks#what-a-blocked-prompt-leaves-behind)
  do not reach Claude. `suppressOriginalPrompt` hides the original prompt in the
  block message, but the text can still appear in local transcript/history files.
- [PostToolUse replacement](https://code.claude.com/docs/en/hooks#posttooluse-decision-control)
  happens after execution. Telemetry captures the original output before the hook.
  Replacement does not undo files, commands, or requests. Built-in tools ignore
  replacements that fail their output schema and use the original instead.

For the stronger requirement, prevent entry at the source: use Keyrelay's existing
credential form and command runner before any credential is pasted or printed.
This prototype adds defense in depth; it does not repair an earlier disclosure.

## Files and runtime

- `hooks/redact_secrets.py`: Python 3.9+ standard library, synchronous command hook.
- `hooks/claude-settings.example.json`: inert settings fragment, for manual review.
- `tests/secret_corpus.py`: deterministic invented positives and negatives.
- `tests/test_redaction_hook.py`: detector and JSON-contract tests, offline.

Reads exactly one UTF-8 JSON object from stdin. Writes either nothing (clean event)
or one JSON decision to stdout, exiting 0 so Claude Code parses it. It creates no
files, calls no network services, launches no subprocesses, reads no environment
credentials, and never opens `transcript_path`. Input exists transiently in memory;
Python cannot guarantee memory erasure. Diagnostics contain no value fragments,
fingerprints, user text, arbitrary field names, or exception messages.

## Input/output contract

The command requires `--event UserPromptSubmit` or `--event PostToolUse`, matching
the input's `hook_event_name`. Common host fields include `session_id`,
`transcript_path`, `cwd`, and `permission_mode`; the prototype ignores them.

### UserPromptSubmit

Input needs `hook_event_name` and a string `prompt`. Scan only `prompt`.
On detection, reject the entire prompt; this event cannot replace prompt text.

```json
{
  "decision": "block",
  "reason": "Possible credential detected. Remove it and use Keyrelay's form.",
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "suppressOriginalPrompt": true
  }
}
```

The actual reason includes fixed handoff instructions. No sanitized copy of the
prompt is emitted, since snippets could leak undetected credentials. A clean
prompt emits nothing and proceeds normally.

### PostToolUse

Input needs `hook_event_name`, a string `tool_name`, and `tool_response`.
`tool_input` may also be present but is not replayed or altered: the tool has
already run. Walk all strings, object keys, lists, and nested objects in
`tool_response`. Also detect high-entropy string values under secret-named object
properties. Preserve surrounding text, non-secret properties, numbers, booleans,
nulls, arrays, and error/exit-status flags.

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "updatedToolOutput": {
      "stdout": "[KEYRELAY:github; re-enter via Keyrelay]",
      "stderr": "",
      "interrupted": false,
      "isImage": false
    },
    "additionalContext": "Credentials replaced; request them through Keyrelay."
  }
}
```

The actual replacement has the original tool response's structure, rather than
wrapping every result in the example's Bash shape. This uses documented
`updatedToolOutput` for both built-in and MCP tools, not the older MCP-only field.
An added warning, exit 2, or `decision: "block"` alone cannot redact tool output.
String types and structure are preserved, but that does not prove every built-in
schema accepts every possible replacement. Arbitrary secret-bearing MCP property
names are also replaced; collisions stop processing rather than silently losing
data. No response is emitted at all for clean results.

### Error policy

Malformed UTF-8/JSON, duplicate keys, NaN/infinity (including exponent overflow),
mismatched events, missing required fields, inputs larger than 4 MiB, nesting over
64 levels within a result, and redacted-key collisions produce fixed diagnostics.
Prompt errors block and suppress the original prompt in the block message.
PostToolUse errors return `continue: false`, `stopReason`, and a blocking reason.
This stops the agent loop but **cannot guarantee suppression of an uninspectable
result**. The hook never truncates an input and then declares it clean.

The example sets a five-second timeout and `onFailure: "block"` for process
failures. On PostToolUse, failure blocking still cannot undo execution or redact
the original result. It is not a substitute for a working replacement. Unsupported
client versions, hook disabling, and host-level errors can bypass protection.

## Detection and false-positive policy

| Rule | Shape / context |
| --- | --- |
| AWS | `AKIA`/`ASIA` plus 16 uppercase alphanumeric characters; secret access keys need a secret-named assignment |
| GitHub | `ghp`, `gho`, `ghu`, `ghs`, `ghr` plus 36 characters; `github_pat_` plus 82 characters |
| OpenAI | Legacy `sk-` plus 48 alphanumeric characters; `sk-proj-` / `sk-svcacct-` plus 40–240 characters |
| Anthropic | `sk-ant-apiNN-` / `sk-ant-adminNN-` plus 40–160 characters |
| Stripe | `sk`/`rk`, `live`/`test`, plus 24–200 alphanumeric characters; publishable `pk` keys pass |
| Slack | Common `xox*` token and `xapp` app-token layouts |
| PEM | PKCS#8, RSA, EC, DSA, OpenSSH, encrypted private-key blocks; unmatched begin consumes the rest of the string |
| Generic | Explicit secret-named assignment/property, 24–512 token characters, Shannon entropy ≥4 bits/character |

Provider rules require token boundaries. Generic matching requires names such as
`API_KEY`, `SERVICE_AUTH_TOKEN`, `CLIENT_SECRET`, `AWS_SECRET_ACCESS_KEY`, or
`password`. Unlabelled entropy is deliberately insufficient. Generic hex strings
and canonical UUIDs pass even under secret-like names, reducing hash/commit-SHA
false positives at the cost of missing actual hex/UUID credentials. Public PEM
keys and certificates pass. Structurally valid provider tokens in examples still
trigger: there is no checksum validation, remote validation, or allowlist.

This is a conservative set of common shapes, not an exhaustive provider catalog.
It does not decode base64/escaped inner payloads or scan binary/image attachments,
referenced files, tool failures, tool inputs, shell history, or already-persisted
messages. Provider format changes require corpus updates. Short, low-entropy,
unknown-format, encoded, or split credentials can pass undetected. Thresholds are
heuristics, not a measured production false-positive rate.

## Keyrelay handoff

Replacements are **instructions, not handles**. There is no secret registry or
retrieval API in this prototype. The hook does not launch Keyrelay automatically,
pass the detected value to it, or retain a mapping.

The user removes the value and asks the agent to invoke the existing runner:

```sh
node /ABSOLUTE/PATH/TO/keyrelay/bin/keyrelay.cjs run --env SERVICE_TOKEN -- your-command
```

Then the user re-enters the credential exclusively through the printed one-time
browser form. Read the command first. Existing runner output redaction protects
exact echoes of submitted values; transformed values remain outside that promise.

## Manual installation — user action only

Nothing in this change installs a hook. For a later synthetic-only evaluation:

1. Run `python3 -m unittest discover -s tests -p 'test_redaction_hook.py'` from
   this checkout. Python 3.9+ is enough; no dependencies or provider access.
2. Confirm the target Claude Code build documents and implements
   `updatedToolOutput`, `suppressOriginalPrompt`, and `onFailure`. Do not assume
   an older build recognizes them; no minimum supported build is verified here.
3. Review `hooks/claude-settings.example.json`. Replace both absolute-path
   placeholders. Quote the interpreter/script paths inside each JSON command if
   they contain spaces. Use a trusted absolute Python path if needed.
4. Manually merge the `hooks` entries into the desired project's
   `.claude/settings.local.json` (or user settings), preserving existing hooks.
   Keep the commands synchronous. Do not put this example in an auto-loaded
   settings path until those checks are complete.
5. Start a new Claude Code session and inspect `/hooks`. In an isolated disposable
   session, use invented fixtures only. Confirm prompt blocking, no prompt echo,
   Bash and MCP result replacement, clean-result pass-through, and failure behavior.
   Inspect local transcript/history/telemetry to establish their actual behavior.
6. To remove, delete only these two command entries from the settings file and
   start a new session. Retain unrelated hooks.

Until the release checks in `NOTES.md` are completed, do not rely on this draft for
real credentials. The stronger no-transcript guarantee requires source-side
prevention or a host change, not a more aggressive regular expression.
