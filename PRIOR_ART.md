# Prior art — 2026-10-29

Verdict: continue with a small **Keyrelay-specific draft**, not a new general
secret scanner. No reviewed tool establishes the requested guarantee that raw
credentials never enter a Claude Code transcript. The host's persistence behavior
prevents this hook pair from establishing that guarantee, too.

- [secret-guard](https://github.com/WSeubring/secret-guard) already implements
  prompt blocking, tool-result replacement with `updatedToolOutput`, provider
  regexes, contextual rules, and false-positive evaluation. Its published README
  describes substantially broader coverage than this prototype. It does not
  document Keyrelay handoff instructions or a guarantee against local prompt
  persistence. Evaluate it before turning this draft into a maintained scanner.
  Reviewed its README only; did not install, build, or validate its claims.
- [Gitleaks](https://github.com/gitleaks/gitleaks) is an established free scanner
  with provider rules and entropy checks. It needs an adapter for Claude Code
  event JSON and Keyrelay instructions; scanning alone cannot change the host's
  transcript behavior.
- [Redaction-hook gist](https://gist.github.com/ruvnet/332336ad5e0516daa810d98f8f0ddca9)
  describes a similar approach. Its claims about transcripts should be checked
  against the current first-party contract, not treated as a guarantee.

The [official hooks reference](https://code.claude.com/docs/en/hooks.md) explicitly
says blocked prompt text may remain in local files, and tool telemetry captures
original output before `PostToolUse`. `decision: "block"` on `PostToolUse` merely
adds feedback: only `updatedToolOutput` replaces what the model sees. Those are
constraints on both existing tools and this prototype. No third-party code was
copied into this implementation.
