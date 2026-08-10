# Source And Licensing Ledger

The machine-readable ledger is `data/source-registry.v1.json`. This reference
explains how to use it; it does not replace source-specific terms.

## Admission

Admit a source only when it is an official project, standards body, foundation,
survey publisher, platform telemetry publisher, security service, registry, or
repository controlled by the responsible publisher. Record direct URL,
edition/version, publication and retrieval dates, cadence, limitations,
evidence role, refresh policy, and usage mode.

First-party material is authoritative for what a project promises, supports,
licenses, and releases, but is not independent comparative evidence. Surveys,
telemetry, landscapes, and automated security systems provide different
signals; each retains its methodology and scope.

## Seed Ledger Boundaries

- Thoughtworks Technology Radar is twice-yearly, opinionated, based on client
  work, and explicitly not comprehensive. Cite; do not copy its blip corpus.
- Stack Overflow survey data is ODbL and recruitment favors engaged Stack
  Overflow users. Attribution and database-license obligations require review
  before redistribution.
- JetBrains states that its 2025 public report content is for non-commercial
  use. The seed snapshot stores only a citation and methodology note; do not
  ingest or redistribute the dataset without a separate rights decision.
- State of JavaScript describes a specific developer subset and trend-oriented
  survey. Preserve that scope.
- GitHub Octoverse measures GitHub activity and labels observed AI associations
  as correlations, not causal proof.
- CNCF Landscape is generated daily but is a categorized map, not an
  endorsement. Its Crunchbase-derived content has separate restrictions.
- OpenSSF Scorecard is a security-practice signal, not overall product quality;
  bulk weekly scans omit some expensive checks.
- deps.dev and OSV aggregate official registries and advisory sources. Coverage
  and freshness vary by ecosystem and upstream source.
- MCP Registry is preview discovery metadata and may reset. Presence does not
  prove trust, installation, authentication, or health.

## Usage Modes

- `citation-only`: store URL and a short original paraphrase; do not mirror the
  source body.
- `open-data-with-attribution`: reuse only under the recorded license and
  attribution conditions.
- `standard-reference`: cite the normative document; avoid republishing it.
- `license-review-required`: no ingestion or redistribution until reviewed.

Raw refresh artifacts are temporary evidence receipts, not plugin source. Keep
them outside the tracked plugin directory and never commit them by default.
