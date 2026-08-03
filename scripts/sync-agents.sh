#!/usr/bin/env bash
# Refresh every locally configured agent from plugin sources:
#   1. this repository's plugins -> Codex local marketplace (every configured CODEX_HOME)
#   2. this repository's plugins -> Claude plugin cache (this repository's marketplace)
#   3. extra local plugin repositories from .sync-local.json -> the same surfaces
#
# Optional machine-local configuration lives OUTSIDE this repository, at
# ${XDG_CONFIG_HOME:-$HOME/.config}/plug-n-skills/sync-local.json:
#   {
#     "codex_homes": ["<extra CODEX_HOME>", ...],
#     "plugin_repos": [{"path": "<plugin repo>", "claude_marketplace": "name"}, ...]
#   }
#
# NOTE: Claude caches plugins by version - bump a plugin's version in both
# manifests to ship content changes to Claude; Codex installs mirror the tree.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT/plugins/capability-workbench/scripts/plugin/ensure_local_plugin_installed.py"
LOCAL_CONFIG="${SYNC_LOCAL_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/plug-n-skills/sync-local.json}"
MARKETPLACE_NAME="${SYNC_CLAUDE_MARKETPLACE:-$(python3 -c '
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
known = Path.home() / ".claude/plugins/known_marketplaces.json"
if known.is_file():
    for name, entry in json.loads(known.read_text()).items():
        paths = {entry.get("installLocation"), entry.get("source", {}).get("path")}
        if any(p and Path(p).expanduser().resolve() == root for p in paths):
            print(name)
            sys.exit(0)
manifest = root / ".claude-plugin" / "marketplace.json"
print(json.loads(manifest.read_text())["name"])
' "$ROOT")}"

codex_homes() {
  LOCAL_CONFIG="$LOCAL_CONFIG" python3 - <<'PY'
import json
import os
from pathlib import Path

homes = []
default = Path.home() / ".codex"
if default.is_dir():
    homes.append(str(default))
cfg = Path(os.environ["LOCAL_CONFIG"])
if cfg.is_file():
    for raw in json.loads(cfg.read_text()).get("codex_homes", []):
        home = str(Path(raw).expanduser())
        if home not in homes:
            homes.append(home)
print("\n".join(homes))
PY
}

plugin_repos() {
  LOCAL_CONFIG="$LOCAL_CONFIG" python3 - <<'PY'
import json
import os
from pathlib import Path

cfg = Path(os.environ["LOCAL_CONFIG"])
if cfg.is_file():
    for entry in json.loads(cfg.read_text()).get("plugin_repos", []):
        print(f'{Path(entry["path"]).expanduser()}\t{entry.get("claude_marketplace", "")}')
PY
}

claude_update_marketplace() {
  local marketplace="$1"
  claude plugin marketplace update "$marketplace" || echo "WARN: marketplace update failed: $marketplace" >&2
  MARKETPLACE_NAME="$marketplace" python3 - <<'PY'
import json
import os
import subprocess
import sys
from pathlib import Path

name = os.environ["MARKETPLACE_NAME"]
manifest = Path.home() / ".claude/plugins/installed_plugins.json"
if not manifest.is_file():
    sys.exit(0)
installed = json.loads(manifest.read_text())
plugins = sorted(
    k.split("@")[0] for k in installed.get("plugins", {}) if k.endswith(f"@{name}")
)
for plugin in plugins:
    r = subprocess.run(["claude", "plugin", "update", f"{plugin}@{name}"])
    if r.returncode:
        print(f"WARN: claude plugin update {plugin} failed", file=sys.stderr)
PY
}

HOMES="$(codex_homes)"

echo "== [1/3] This repository's plugins -> Codex =="
if [[ -z "$HOMES" ]]; then
  echo "No Codex homes found - skipping."
else
  while IFS= read -r home; do
    echo "-- Codex home: $home"
    python3 "$ROOT/scripts/install-codex-plugins.py" \
      --config-path "$home/config.toml" \
      --cache-root "$home/plugins/cache"
  done <<< "$HOMES"
fi

echo "== [2/3] This repository's plugins -> Claude =="
if command -v claude >/dev/null 2>&1 && [[ -d "$HOME/.claude" ]]; then
  claude_update_marketplace "$MARKETPLACE_NAME"
else
  echo "Claude CLI or ~/.claude not found - skipping."
fi

echo "== [3/3] Extra local plugin repositories =="
REPOS="$(plugin_repos)"
if [[ -z "$REPOS" ]]; then
  echo "No extra plugin repositories configured."
else
  while IFS=$'\t' read -r repo_path claude_marketplace; do
    [[ -n "$repo_path" ]] || continue
    echo "-- Repo: $repo_path"
    if [[ -n "$HOMES" ]]; then
      while IFS= read -r home; do
        for plugin_dir in "$repo_path"/plugins/*/; do
          [[ -d "$plugin_dir" ]] || continue
          python3 "$HELPER" "$plugin_dir" --force-manual \
            --marketplace-path "$repo_path/.agents/plugins/marketplace.json" \
            --config-path "$home/config.toml" \
            --cache-root "$home/plugins/cache" >/dev/null \
            || echo "WARN: codex install failed: $plugin_dir -> $home" >&2
        done
        echo "   codex home refreshed: $home"
      done <<< "$HOMES"
    fi
    if [[ -n "$claude_marketplace" ]] && command -v claude >/dev/null 2>&1; then
      claude_update_marketplace "$claude_marketplace"
    fi
  done <<< "$REPOS"
fi

echo "Done. Restart agent sessions to pick up updated plugins."
