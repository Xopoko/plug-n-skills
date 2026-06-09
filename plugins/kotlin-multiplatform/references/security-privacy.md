# Security And Privacy

## Shared Boundary

Common code can define interfaces, policies, typed errors, and redaction contracts. Platform source sets should own the storage implementation for sensitive material.

## Secure Storage

- Android sensitive key-value storage should be Android-backed.
- iOS sensitive key-value storage should be Keychain-backed.
- Do not store token literals, API keys, encryption keys, or signing material in common source, tests, fixtures, or generated examples.

## Networking

- Token refresh requests must avoid recursive auth interception.
- Retries should have caps, jitter/backoff, and status-specific behavior.
- Certificate pinning is a product/security decision. Add it only when threat model and update process justify it.

## Logging

Redact:

- authorization headers
- access and refresh tokens
- cookies/session IDs
- PII
- request and response bodies unless explicitly safe
- device identifiers where privacy policy requires it

## Optional Security Tooling

Encrypted-storage libraries, runtime app protection, debugger/root checks, and certificate pinning are threat-model decisions. They should not be added as generic hardening unless there is product, compliance, or abuse-risk evidence.

## Output Standard

A security review must name exact files reviewed, data classes or storage APIs involved, redaction points, platform boundaries, and tests/manual checks still needed.
