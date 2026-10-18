#!/usr/bin/env python3
"""Create the first Immich admin, sign in, and save only a new API key.

Usage: keyrelay run --stdin --field 'email=Admin email' --field 'password=Admin password' \
         -- python3 immich_api_key.py http://immich.example:2283 immich-api-key.txt
"""
import json, os, sys, urllib.request

url, out = sys.argv[1].rstrip("/"), sys.argv[2]
creds = json.loads(sys.stdin.readline())  # secrets arrive on stdin, never in argv


def post(path, body, token=None):
    headers = {"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})}
    req = urllib.request.Request(url + path, json.dumps(body).encode(), headers)
    return json.load(urllib.request.urlopen(req))


post("/api/auth/admin-sign-up", {**creds, "name": "Admin"})
session = post("/api/auth/login", creds)["accessToken"]
key = post("/api/api-keys", {"name": "agent", "permissions": ["all"]}, session)["secret"]
post("/api/auth/logout", {}, session)  # end the sign-in session; keep only the key
with open(os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as f:
    f.write(key)  # persist only the derived key, readable by you alone
print("API key saved to", out)  # print the outcome, not the key or the password
