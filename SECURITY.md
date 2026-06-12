# Security

These plugins are workflow and instruction packs. They should not contain API keys, credentials, private certificates, tokens, or personal machine paths.

## Reporting

Report issues through GitHub private vulnerability reporting on this repository when enabled, or directly to the repository owner.

## Handling Sensitive Data

- Do not commit `.env` files, signing material, credentials, API tokens, or generated auth output.
- Do not add scripts that exfiltrate local files or send telemetry without a clear opt-in.
- Keep install scripts deterministic and explicit about every location they modify.
- Run `python3 scripts/validate-repository.py` before publishing changes.

