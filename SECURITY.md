# Security

These plugins are workflow and instruction packs. They should not contain API keys, credentials, private certificates, tokens, or personal machine paths.

## Reporting

For now, report issues through the repository owner. When this repository becomes public, use GitHub private vulnerability reporting if it is enabled.

## Handling Sensitive Data

- Do not commit `.env` files, signing material, credentials, API tokens, or generated auth output.
- Do not add scripts that exfiltrate local files or send telemetry without a clear opt-in.
- Keep install scripts deterministic and explicit about every location they modify.
- Run `python3 scripts/validate-repository.py` before publishing changes.

