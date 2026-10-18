#!/usr/bin/env python3
"""Keyrelay exchange target: Immich sign-in (optionally first-run admin signup) that returns only an API key.

Reads {"email": ..., "password": ...} as one JSON line on standard input, as `keyrelay exchange`
delivers it. Writes {"apiKey", "id", "name", "permissions", "url"} to $KEYRELAY_RESULT_FD.
The session token from sign-in is used once to create the key, then logged out.
Standard library only, so it runs anywhere Keyrelay does.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def call(base, path, body=None, token=None, method="POST"):
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read()
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as error:
        try:
            message = json.load(error).get("message", error.reason)
        except ValueError:
            message = error.reason
        # Report the step and status, never the request body.
        raise SystemExit("Immich %s %s returned HTTP %d: %s" % (method, path, error.code, message))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Immich server, for example http://192.168.0.2:2283")
    parser.add_argument("--signup", action="store_true", help="Create the first admin account before signing in")
    parser.add_argument("--name", default="Admin", help="Display name for --signup")
    parser.add_argument("--key-name", default="keyrelay", help="Name of the API key to create")
    parser.add_argument("--permission", action="append", help="API key permission; repeat (default: all)")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    if not base.startswith(("http://", "https://")):
        raise SystemExit("--url must start with http:// or https://")
    fd = os.environ.get("KEYRELAY_RESULT_FD")
    if not fd:
        raise SystemExit("Run this through `keyrelay exchange`; KEYRELAY_RESULT_FD is not set")
    credentials = json.loads(sys.stdin.readline())
    email, password = credentials["email"], credentials["password"]
    permissions = args.permission or ["all"]

    if args.signup:
        if call(base, "/api/server/config", method="GET").get("isInitialized"):
            raise SystemExit("Immich already has an admin account; run again without --signup")
        call(base, "/api/auth/admin-sign-up", {"email": email, "password": password, "name": args.name})
        print("Created the Immich admin account.")
    session = call(base, "/api/auth/login", {"email": email, "password": password})["accessToken"]
    del password, credentials
    print("Signed in.")
    try:
        created = call(base, "/api/api-keys", {"name": args.key_name, "permissions": permissions}, token=session)
        print("Created API key %r." % args.key_name)
    finally:
        call(base, "/api/auth/logout", {}, token=session)
        print("Signed out; the sign-in session is revoked.")
    result = {"apiKey": created["secret"], "id": created["apiKey"]["id"], "name": args.key_name,
              "permissions": permissions, "url": base}
    with os.fdopen(int(fd), "w") as out:
        json.dump(result, out)


if __name__ == "__main__":
    main()
