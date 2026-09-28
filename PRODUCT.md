# Product
<!-- impeccable:product-schema 1 -->

## Platform
web

## Users
Developers working with coding agents that need credentials for CLI commands.

## Product Purpose
Hand a credential to a waiting command without pasting it into an agent conversation.

## Operating Context
A Python standard-library broker runs privately behind Tailscale. A browser form displays the pending command. A runner injects the submitted secret through an environment variable or stdin.

## Capabilities and Constraints
Requests expire after five minutes, live in memory, and are consumed once. Plain-text secret echoes are redacted. This is not a sandbox: trusted commands can transmit or transform credentials. No hosted public broker is offered.

## Evidence on Hand
keyrelay.py, tests/test_keyrelay.py, and an existing private deployment.

## Stack
Public marketing surface: static HTML/CSS/JavaScript on Cloudflare Pages, inferred from the requested lightweight product page. No package or build dependencies needed for the site.

## Brand Commitments
Name: Keyrelay. Existing broker uses a dark blue surface and cyan accents. Public positioning inferred from README and request; no testimonials, adoption figures, or security certification claims.
