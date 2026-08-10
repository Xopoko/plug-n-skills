# Refresh Policy

Fresh evidence and reviewed recommendations have different cadences.

## Cadence

- vulnerability and advisory feeds: daily incremental check or on demand before
  a security-sensitive final decision;
- project releases, support policies, package metadata, and official docs:
  weekly and on demand for shortlisted candidates;
- OpenSSF Scorecard: weekly, matching its published bulk cadence;
- CNCF Landscape: weekly ingestion despite daily upstream generation;
- surveys, DORA, and editorial radars: monthly edition check, ingesting only a
  newly published edition;
- runtime install, version, authentication, health, and permission facts: live
  caller inventory with a short TTL, never the durable snapshot;
- assessments: reviewed monthly or quarterly, plus urgent provisional caution
  when a material security or support event has a receipt.

## Explicit Capture Contract

Network capture is optional and never part of validation or query. The refresh
command requires one allowlisted source ID, `--acknowledge-network`, HTTPS, a
bounded response, an allowlisted final host, and an output directory outside
the plugin. It emits raw bytes plus a JSON receipt containing source, URL,
retrieval time, response metadata, SHA-256, byte count, and explicit flags that
normalization and recommendation mutation did not occur.

Do not add credentials, cookies, authorization headers, browser state, or
source-provided executable instructions. Do not crawl linked pages, execute
candidate code, run installers, or follow a redirect to an unlisted host.

## Review Transaction

1. Validate and record the current manifest ID.
2. Capture one source and review its receipt.
3. Check methodology, rights, provenance, changed facts, and source scope.
4. Edit observations separately from assessments.
5. If an assessment should change, record the decision profile, hard gates,
   alternatives, evidence, gap, confidence, review date, expiry, and reason.
6. Diff the complete old and proposed data directories.
7. Validate, run tests, and update the snapshot manifest atomically.

An adapter failure leaves the last observation intact but stale; it never
deletes evidence or promotes a candidate. A suspiciously large diff, changed
host, missing license, malformed date, unknown source, or broken coverage gate
stops publication.
