"""Offline, invented fixtures. No credentials copied from accounts or the web.

Provider-shaped strings are generated deterministically so there are no complete
credential-shaped literals in the repository. Never authenticate with this corpus.
Each case is (label, text, expected rule, synthetic value that must disappear).
"""

import random
import string


def invented(length, alphabet=string.ascii_letters + string.digits, seed=54):
    rng = random.Random(seed)
    return "".join(rng.choice(alphabet) for _ in range(length))


def positive(label, value, rule, template="value: {}"):
    return label, template.format(value), rule, value


CASES = [
    positive("aws-long-lived", "AKIA" + invented(16, string.ascii_uppercase + string.digits), "aws-access-id"),
    positive("aws-session", "ASIA" + invented(16, string.ascii_uppercase + string.digits), "aws-access-id"),
    positive("github-classic", "ghp_" + invented(36), "github"),
    positive("github-oauth", "gho_" + invented(36), "github"),
    positive("github-user", "ghu_" + invented(36), "github"),
    positive("github-server", "ghs_" + invented(36), "github"),
    positive("github-refresh", "ghr_" + invented(36), "github"),
    positive("github-fine-grained", "github_pat_" + invented(82), "github"),
    positive("openai-legacy", "sk-" + invented(48), "openai"),
    positive("openai-project", "sk-proj-" + invented(156), "openai"),
    positive("openai-service", "sk-svcacct-" + invented(156), "openai"),
    positive("anthropic-api", "sk-ant-api03-" + invented(95), "anthropic"),
    positive("anthropic-admin", "sk-ant-admin01-" + invented(95), "anthropic"),
    positive("stripe-live", "sk_live_" + invented(24), "stripe"),
    positive("stripe-test", "sk_test_" + invented(98), "stripe"),
    positive("stripe-restricted", "rk_live_" + invented(24), "stripe"),
    positive("slack-bot", "xoxb-" + "123456789012-987654321098-" + invented(32), "slack"),
    positive("slack-user", "xoxp-" + "123456789012-987654321098-112233445566-" + invented(32), "slack"),
    positive("slack-app", "xapp-1-" + "A1234567890-1234567890123-" + invented(48, string.ascii_lowercase + string.digits), "slack-app"),
    positive("generic-api-key", invented(40), "secret-assignment", "API_KEY={}"),
    positive("generic-password", invented(40), "secret-assignment", "password: '{}'"),
    positive("generic-json", invented(40), "secret-assignment", '{{"client_secret":"{}"}}'),
    positive("generic-export", invented(40), "secret-assignment", 'export SERVICE_AUTH_TOKEN="{}"'),
    positive("aws-secret-context", invented(40, string.ascii_letters + string.digits + "/+"), "secret-assignment", "AWS_SECRET_ACCESS_KEY={}"),
    positive("punctuated-key", "ghp_" + invented(36), "github", "({}),"),
    positive("url-key", "ghp_" + invented(36), "github", "https://example.invalid/{}/info"),
]
for key_type in ("PRIVATE KEY", "RSA PRIVATE KEY", "EC PRIVATE KEY", "DSA PRIVATE KEY", "OPENSSH PRIVATE KEY", "ENCRYPTED PRIVATE KEY"):
    value = "-----BEGIN " + key_type + "-----\n" + invented(80) + "\n-----END " + key_type + "-----"
    CASES.append(positive("pem-" + key_type, value, "pem-private-key"))
CASES.append(positive("pem-truncated", "-----BEGIN PRIVATE KEY-----\n" + invented(80), "pem-private-key"))

NEGATIVES = [
    ("ordinary-prose", "Fix the token parser and rotate keys later."),
    ("uuid", "token=550e8400-e29b-41d4-a716-446655440000"),
    ("commit-sha", "secret=" + invented(40, string.hexdigits[:16])),
    ("sha256", "API_KEY=" + invented(64, string.hexdigits[:16])),
    ("sha512", "password=" + invented(128, string.hexdigits[:16])),
    ("bare-entropy", invented(96)),
    ("checksum-assignment", "checksum=" + invented(44)),
    ("non-secret-id", "request_id=" + invented(40)),
    ("public-key-assignment", "public_key=" + invented(40)),
    ("token-count", "token_count=24000"),
    ("short-password", "password=abc123"),
    ("placeholder", "API_KEY=your-api-key-goes-here"),
    ("repeated-placeholder", "API_KEY=" + "x" * 48),
    ("env-reference", "API_KEY=${SERVICE_API_KEY}"),
    ("template", "TOKEN={{ secrets.API_KEY }}"),
    ("keyrelay-marker", "[KEYRELAY:github; re-enter via Keyrelay]"),
    ("pem-public", "-----BEGIN PUBLIC KEY-----\n" + invented(80) + "\n-----END PUBLIC KEY-----"),
    ("pem-cert", "-----BEGIN CERTIFICATE-----\n" + invented(80) + "\n-----END CERTIFICATE-----"),
    ("stripe-publishable", "pk_live_" + invented(32)),
    ("github-short", "ghp_" + invented(35)),
    ("github-long", "ghp_" + invented(37)),
    ("embedded-github", "prefixghp_" + invented(36)),
    ("aws-wrong-case", "akia" + invented(16, string.ascii_uppercase)),
    ("aws-short", "AKIA" + invented(15, string.ascii_uppercase)),
    ("provider-names", "AWS GitHub OpenAI Anthropic Stripe Slack"),
    ("prefix-example", "sk-proj-EXAMPLE ghp_EXAMPLE sk-ant-api03-EXAMPLE"),
]
CASES.extend((label, text, None, None) for label, text in NEGATIVES)
