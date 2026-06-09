# Safety Vetting

Use this reference when inspecting candidate skills, plugins, scripts, installers, and marketplace packages.

## Risk Classes

- `required`: behavior is needed for the candidate's core workflow.
- `optional`: documented extension, not required for the core workflow.
- `example`: illustrative snippet or sample command.
- `advisory`: warning about what not to do.
- `hidden`: behavior present in code/config but not disclosed.

Only required or hidden high-risk behavior normally rejects a mechanism. Advisory text is a safety signal unless contradicted by code.

## Reject Or Isolate

Reject from the core implementation when a component requires:

- paid API, billing account, or API key;
- external generation service;
- hidden network dependency or telemetry;
- credential, cookie, private key, Keychain, browser-profile, `.env`, SSH, or cloud-config access unrelated to the task;
- `curl | sh`, obfuscated payloads, base64 code execution, `eval`, dynamic shell execution, or broad delete/write behavior;
- project-specific infrastructure that does not improve the requested core capability.

Optional future integrations can be documented as rejected or deferred, but should not be included in the core path.

## Candidate Review Template

```markdown
Candidate:
- Source:
- Version/ref:
- Files reviewed:
- Core capability:
- Useful mechanisms:
- Dependencies/runtime:
- Network/services:
- File/system effects:
- Credential exposure:
- Risk classification:
- Verdict:
- Rationale:
```

## Static Helpers

Run first-pass scans, then verify important findings manually:

```bash
python3 ../../scripts/synthesis/audit_skill_candidate.py <skill-dir> --output candidate-audit.json
python3 ../../scripts/context/context_density_audit.py <paths> --json --top 20
```

The helpers are triage, not final judgment.
