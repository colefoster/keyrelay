# Product
<!-- impeccable:product-schema 1 -->

## Platform
web

## Users
Developers working with coding agents that need credentials for CLI commands.

## Product Purpose
Address the moment a coding agent needs an API key but warns the user not to paste it into chat. Give the user a local form that hands the key to the waiting command, so work can continue without putting the key in the conversation.

## Operating Context
A Python standard-library broker runs on localhost by default, with optional Tailscale access. A browser form displays the pending command. A runner injects the submitted secret through an environment variable or stdin.

## Capabilities and Constraints
Requests expire after five minutes, live in memory, and are consumed once. Plain-text secret echoes are redacted. This is not a sandbox: trusted commands can transmit or transform credentials. No hosted public broker is offered. The npm launcher requires Node.js and Python 3.9+; Tailscale is not required for local use.

## Evidence on Hand
keyrelay.py, tests/test_keyrelay.py, and an existing private deployment.

## Stack
Public marketing surface: static HTML/CSS/JavaScript on Cloudflare Pages, inferred from the requested lightweight product page. No package or build dependencies needed for the site.

## Brand Commitments
Name: Keyrelay. Existing broker uses a dark blue surface and cyan accents. User-confirmed positioning: the agent needs a key but tells the user not to put it in chat; no testimonials, adoption figures, or security certification claims.
