# xp-54q draft notes

No hook was installed; no settings, credentials, or existing transcripts were
read or modified. No release, push, upload, paid API call, or public service.

## Unverified / limitations

- Offline tests exercise our JSON contract, not an installed Claude Code host.
  There is no verified minimum supported Claude Code version. The official docs
  checked 2026-10-29 support all-tool `updatedToolOutput`, prompt echo suppression,
  and `onFailure`, but older builds may ignore them.
- **The requested guarantee that raw values never enter a transcript is not
  achievable with this hook pair.** Official docs say blocked prompt text can
  remain in local storage, and tool telemetry captures original results before
  the post hook. This prototype never rewrites existing transcripts.
- `PostToolUse` only covers successful calls. Failures, inputs, file references,
  binary payloads, encoded/split values, unknown formats, and bypassed hooks are
  outside scope. A failed post hook can stop the loop but cannot safely remove
  the original output. Invalid built-in replacement schemas are ignored by Claude
  Code. Arbitrary key-name replacement could invalidate an uncommon tool schema.
- Regexes and the 4-bit entropy threshold need field evaluation with synthetic or
  independently de-identified data. The fixture corpus is a regression check,
  not evidence of production precision/recall. Hex/UUID credentials deliberately
  pass generic rules; provider-shaped documentation examples can trigger.
- Redaction markers are not usable Keyrelay handles. Users must re-enter the
  value in Keyrelay's form. Python does not erase transient process memory.
- The npm package's existing `files` list excludes this draft's hooks. README
  instructions use a source checkout; packaging is a separate release decision.

## Release would need

1. Evaluate existing secret-guard before committing to a second maintained
   scanner; see `PRIOR_ART.md`.
2. Agree on a feasible protection claim. For strict no-transcript storage, keep
   credentials out at the source using Keyrelay, or change the host's persistence
   boundary. Hooks alone cannot satisfy that claim.
3. Pin and test an actual Claude Code version, without live credentials or LLM
   charges: validate Bash, Read, other built-ins, MCP text/structured results,
   output schemas, parallel hooks, invalid/oversized inputs, timeout/crash paths,
   and the on-disk artifacts. Establish an explicit version compatibility gate.
4. Expand synthetic adversarial/negative coverage, measure false positives and
   false negatives on independent data, and measure latency at the 4 MiB limit.
5. Security review for retention, host failure behavior, and replacement-schema
   edge cases. Decide whether source-side wrappers or an SDK boundary are needed.
6. Review packaging/install UX and obtain separate release authorization. This
   draft does not authorize installation or distribution.

## Reproducible checks

```sh
python3 -m unittest discover -s tests -p 'test_redaction_hook.py'
python3 -m unittest discover -s tests
```

The focused check has no network calls or listeners. The existing full suite uses
temporary loopback HTTP brokers and mocked browser code; teardown stops them.
Neither command uses an LLM or real provider credentials.

Observed on this Mac: all 42 tests passed with Python 3.9.6, including 17 hook
tests. Those 17 also passed with Python 3.12.14. The corpus contains 33 positive
cases, 26 named negative cases, and 400 additional generated hex/hash negatives.
The sandbox denied existing loopback test brokers; the successful full run used
`nice -n 15 lockf /tmp/sp_heavy.lock python3 -m unittest discover -s tests` with
loopback permissions. No production Claude Code session was exercised.
