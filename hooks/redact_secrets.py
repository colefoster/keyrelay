#!/usr/bin/env python3
"""Draft Claude Code command hook. No network, credential storage, or logging."""

import argparse
from collections import Counter
import json
import math
import re
import sys


MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_DEPTH = 64
EVENTS = ("UserPromptSubmit", "PostToolUse")
INSTRUCTION = (
    "Remove the credential and resubmit using its environment variable name. "
    "Ask the agent to run Keyrelay with --env NAME -- COMMAND, then enter the "
    "credential only in Keyrelay's one-time browser form. No credential was saved "
    "or registered by this hook; redaction markers are not retrievable handles."
)
ERROR = "Keyrelay hook could not safely inspect this event. Stop and inspect the hook locally."


def token_rule(expression):
    # Avoid matching a prefix embedded in a longer identifier or a truncated value.
    return re.compile(r"(?<![A-Za-z0-9_-])(?:" + expression + r")(?![A-Za-z0-9_-])")


RULES = (
    ("aws-access-id", token_rule(r"(?:AKIA|ASIA)[A-Z0-9]{16}")),
    ("github", token_rule(r"(?:gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82})")),
    ("anthropic", token_rule(r"sk-ant-(?:api\d{2}|admin\d{2})-[A-Za-z0-9_-]{40,160}")),
    ("openai", token_rule(r"sk-(?:(?:proj|svcacct)-[A-Za-z0-9_-]{40,240}|[A-Za-z0-9]{48})")),
    ("stripe", token_rule(r"(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{24,200}")),
    ("slack", token_rule(r"xox[baprs]-[0-9]{10,13}-(?:[0-9]{10,13}-){1,2}[A-Za-z0-9]{24,64}")),
    ("slack-app", token_rule(r"xapp-[0-9]-[A-Z0-9]{10,16}-[0-9]{10,16}-[a-z0-9]{32,64}")),
    ("pem-private-key", re.compile(
        r"-----BEGIN (?P<label>(?:(?:RSA|EC|DSA|OPENSSH|ENCRYPTED) )?PRIVATE KEY)-----"
        r"[\s\S]*?(?:-----END (?P=label)-----|\Z)"
    )),
)
ASSIGNMENT = re.compile(
    r"(?<![\w.-])(?P<name>[A-Za-z_][A-Za-z0-9_.-]{0,80})[\"']?\s*[:=]\s*"
    r"[\"']?(?P<value>[A-Za-z0-9_+/=.\-]{24,512})(?![A-Za-z0-9_+/=.\-])"
)
SECRET_NAME = re.compile(
    r"(?:^|[_.-])(?:api[_-]?key|(?:access|auth|api|client)[_-]?(?:token|secret)|"
    r"secret(?:_access_key)?|token|password|passwd|private[_-]?key)$", re.I
)
HEX = re.compile(r"[0-9a-fA-F]+\Z")
UUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\Z")
TOKEN_VALUE = re.compile(r"[A-Za-z0-9_+/=.\-]{24,512}\Z")


def entropy(value):
    return -sum((n / len(value)) * math.log2(n / len(value)) for n in Counter(value).values())


def secret_assignment(name, value):
    return (bool(SECRET_NAME.search(name)) and bool(TOKEN_VALUE.fullmatch(value))
            and not HEX.fullmatch(value) and not UUID.fullmatch(value)
            and entropy(value) >= 4.0)


def findings(text):
    """Return offsets and fixed rule names, never copies or fingerprints of secrets."""
    found = [(m.start(), m.end(), kind) for kind, rule in RULES for m in rule.finditer(text)]
    for match in ASSIGNMENT.finditer(text):
        value = match.group("value")
        if secret_assignment(match.group("name"), value):
            found.append((*match.span("value"), "secret-assignment"))
    # Prefer the enclosing PEM block/provider token over nested assignment matches.
    selected = []
    for start, end, kind in sorted(found, key=lambda item: (item[0], -item[1])):
        if selected and start < selected[-1][1]:
            continue
        selected.append((start, end, kind))
    return selected


def redact_text(text):
    matches = findings(text)
    if not matches:
        return text, False
    pieces, cursor = [], 0
    for start, end, kind in matches:
        pieces.extend((text[cursor:start], "[KEYRELAY:" + kind + "; re-enter via Keyrelay]"))
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces), True


def redact_json(value, depth=0):
    """Keep tool output types/structure, including arbitrary MCP content blocks."""
    if depth > MAX_DEPTH:
        raise ValueError("nested input")
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        items = [redact_json(item, depth + 1) for item in value]
        return [item for item, _ in items], any(changed for _, changed in items)
    if isinstance(value, dict):
        result, changed = {}, False
        for key, item in value.items():
            safe_key, key_changed = redact_text(key)
            safe_item, item_changed = redact_json(item, depth + 1)
            if isinstance(item, str) and secret_assignment(key, item):
                safe_item = "[KEYRELAY:secret-assignment; re-enter via Keyrelay]"
                item_changed = True
            # Never silently drop data if two secret-bearing MCP keys collide.
            if safe_key in result:
                raise ValueError("redacted key collision")
            result[safe_key] = safe_item
            changed |= key_changed or item_changed
        return result, changed
    return value, False


def reject(event, reason):
    output = {"decision": "block", "reason": reason}
    if event == "UserPromptSubmit":
        output["hookSpecificOutput"] = {
            "hookEventName": event, "suppressOriginalPrompt": True,
        }
    else:
        # PostToolUse 'block' alone only annotates; it does not suppress a result.
        output.update({"continue": False, "stopReason": reason})
    return output


def process(payload, event):
    if not isinstance(payload, dict) or payload.get("hook_event_name") != event:
        raise ValueError("invalid event")
    if event == "UserPromptSubmit":
        prompt = payload.get("prompt")
        if not isinstance(prompt, str):
            raise ValueError("invalid prompt")
        if findings(prompt):
            return reject(event, "Possible credential detected. " + INSTRUCTION)
    else:
        if not isinstance(payload.get("tool_name"), str) or "tool_response" not in payload:
            raise ValueError("invalid tool result")
        safe, changed = redact_json(payload["tool_response"])
        if changed:
            return {"hookSpecificOutput": {
                "hookEventName": event,
                "updatedToolOutput": safe,
                "additionalContext": "Possible credentials replaced by Keyrelay instructions. " + INSTRUCTION,
            }}
    return {}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def invalid_constant(_value):
    raise ValueError("non-finite JSON number")


def finite_float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON number")
    return parsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", choices=EVENTS, required=True)
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError("oversized input")
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                             parse_constant=invalid_constant, parse_float=finite_float)
        output = process(payload, args.event)
    except (ValueError, RecursionError, OSError):
        # Exception messages and tracebacks can contain untrusted input. Never echo them.
        output = reject(args.event, ERROR)
    if output:
        sys.stdout.write(json.dumps(output, ensure_ascii=True, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
