---
name: kmp-security-privacy
description: Review Kotlin Multiplatform security and privacy across secure storage, tokens, Ktor auth, TLS, certificate pinning, logging redaction, runtime protection, platform APIs, and commonMain boundaries.
---

# KMP Security And Privacy

Use this skill for secrets, tokens, authentication, secure storage, logging redaction, networking security, privacy-sensitive data, runtime app protection, and platform security boundaries in KMP projects.

## Review Flow

1. Search for secret-like names and literals in shared code, tests, configs, and logs.
2. Identify where tokens, refresh tokens, device identifiers, PII, and encryption keys live.
3. Verify common code exposes interfaces and policies, while platform source sets own storage implementation.
4. Review Ktor auth, refresh-token loops, retries, TLS/certificate pinning, and redaction.
5. Check CI/release examples do not contain signing, keystore, App Store, Maven Central, or token material.

## Rules

- `commonMain` should not hardcode secrets or own platform storage implementation.
- Android sensitive key-value storage should use Android-backed secure storage.
- iOS sensitive key-value storage should use Keychain-backed storage.
- Shared logging APIs must redact tokens, auth headers, refresh responses, PII, and request bodies unless explicitly safe.
- Refresh-token requests must avoid recursive auth interception.
- Certificate pinning and runtime app protection are risk-based choices; do not add them as universal defaults.
- Hardware-backed encrypted storage libraries and runtime app protection SDKs are optional. Verify threat model, target support, maintenance, incident response, and policy before adoption.

## Output

Lead with:

- security verdict
- exact files and flows reviewed
- hard blockers
- platform-boundary issues
- redaction gaps
- network/auth risks
- tests or manual checks needed
