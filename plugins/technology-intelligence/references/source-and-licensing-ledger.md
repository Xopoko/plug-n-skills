# Source And Licensing Ledger

The machine-readable ledger is `data/source-registry.v1.json`. This reference
explains how to use it; it does not replace source-specific terms.

## Admission

Admit a source only when it is an official project, standards body, foundation,
survey or telemetry publisher, security service, registry, responsible
repository, or attributable scholarly primary study. Record direct URL,
edition/version, publication and retrieval dates, the measurement window when
the source samples or benchmarks a period, cadence, limitations, evidence role,
refresh policy, and usage mode. Mark preprints explicitly and keep them
provisional.

First-party material is authoritative for what a project promises, supports,
licenses, and releases, but is not independent comparative evidence. Surveys,
telemetry, landscapes, and automated security systems provide different
signals; each retains its methodology and scope.

Independence is candidate-relative. Use `affiliated_technology_ids` when a
foundation, registry, steward, or publisher has a direct relationship to a
candidate. Such material can still be useful context but does not satisfy the
candidate's independent-evidence gate by itself.

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
- AnyDoc v0.1.8 documentation and benchmark material are immutable, first-party
  Firecrawl evidence. The benchmark excludes PDF and excludes CSV from quality
  judging; its corpus is private, the LLM judge sees only the first six rendered
  pages, each document receives one warm run, dependency versions are not fully
  pinned, process timing differs by tool, and the measurement window is
  undisclosed. Retain it as an affiliated vendor benchmark, not an independent
  ranking. Package manifests document Node.js 20+, Python 3.10+, Rust 1.88, and
  no published Windows ARM64 native target; actual runtime compatibility remains
  caller-supplied. Text-based PDF support uses a separate path and does not imply
  OCR for scanned or image-only PDFs.

## Usage Modes

- `citation-only`: store URL and a short original paraphrase; do not mirror the
  source body.
- `open-data-with-attribution`: reuse only under the recorded license and
  attribution conditions.
- `standard-reference`: cite the normative document; avoid republishing it.
- `license-review-required`: no ingestion or redistribution until reviewed.

Raw refresh artifacts are temporary evidence receipts, not plugin source. Keep
them outside the tracked plugin directory and never commit them by default.
