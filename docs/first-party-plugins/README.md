# First-Party Plugin Receipts

This directory contains machine-readable review receipts referenced by
`first-party-plugins.lock.json`. A receipt is part of the trust boundary, not a
generated cache record.

Each receipt uses exactly these top-level keys:

- `schemaVersion`, `name`, `source`, `version`, `manifest`, `license`;
- `verifiedAt` in `YYYY-MM-DD` form;
- `skills` with an exact `count` and ordered `items` (`name`, `path`,
  `description`, `startupTokens`, and `bodyTokens`); `startupTokens` preserves
  the publication snapshot that used the immutable GitHub blob URL as the file
  locator;
- `counts` with recursive regular-file counts for `references` and `scripts`;
- `tokens` with the publication-time `o200k_base` startup/body totals;
- `icons` with `composerIcon`, `logo`, and `brandColor` values copied from the
  Codex manifest, plus `sha256` and `catalogAsset` for the root-owned offline
  dashboard snapshot.

The source, version, manifest digests, and license must exactly match the lock.
Skill names/paths, support-file counts, icon metadata, and the plugin icon hash
are checked against a materialized pinned tree. Token values are publication
snapshots; the root token report carries them forward as receipt-provided URL
locator totals. JSON objects reject duplicate and unknown keys.

The root token report keeps those published URL-locator values intact and
shows them separately. Its comparable routing estimate is recomputed from each
skill name, description, and source-relative `skills/.../SKILL.md` path for
both local and standalone plugins. These are static source measurements, not
proof of what an agent host injects into a prompt or exposes to a model at
runtime.
