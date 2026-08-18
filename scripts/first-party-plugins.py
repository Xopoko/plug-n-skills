#!/usr/bin/env python3
"""Operate the standalone first-party plugin catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import plugin_catalog as catalog
from plugin_registry import repo_root


def parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", type=Path, default=argparse.SUPPRESS)
    result = argparse.ArgumentParser(description=__doc__, parents=[common])
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("list", parents=[common])
    sub.add_parser("validate", parents=[common])
    verify = sub.add_parser("verify-source", parents=[common]); verify.add_argument("names", nargs="*")
    status = sub.add_parser("status", parents=[common]); status.add_argument("names", nargs="*"); status.add_argument("--cache-root", type=Path)
    materialize = sub.add_parser("materialize", parents=[common]); materialize.add_argument("name"); materialize.add_argument("--offline", action="store_true"); materialize.add_argument("--cache-root", type=Path)
    checkout = sub.add_parser("checkout", parents=[common]); checkout.add_argument("name"); checkout.add_argument("--dest", type=Path, required=True); checkout.add_argument("--cache-root", type=Path)
    receipt = sub.add_parser("receipt", parents=[common]); receipt.add_argument("name"); receipt.add_argument("--source", type=Path, required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = getattr(args, "root", repo_root())
    try:
        payload = None if args.command == "receipt" else catalog.validate_catalog(root)
        if args.command == "validate": print(f"first-party catalog valid: {len(payload['publishers'])} publishers, {len(payload['plugins'])} plugins")
        elif args.command == "list":
            for item in payload["plugins"]: print(f"{item['name']}\t{item['manifest']['version']}\t{item['source']['repository']}@{item['source']['commit']}\tdefault={str(item['selection']['default']).lower()}")
        elif args.command == "verify-source":
            for item in catalog.select_plugins(payload, args.names): print(json.dumps(catalog.verify_remote(item, catalog_root=root), sort_keys=True))
        elif args.command == "materialize": print(catalog.materialize(root, args.name, offline=args.offline, cache_root=args.cache_root))
        elif args.command == "checkout": print(catalog.checkout(root, args.name, args.dest, cache_root=args.cache_root))
        elif args.command == "receipt": print(catalog.generate_receipt(root, args.name, args.source))
        elif args.command == "status":
            base = args.cache_root.resolve() if args.cache_root else root.resolve() / ".agents" / "first-party-sources"
            for item in catalog.select_plugins(payload, args.names):
                target = base / item["name"] / item["source"]["commit"]
                state = "absent"
                if target.exists():
                    try: catalog.verify_plugin_tree(target, item, catalog.receipt_for(root, item)); state = "verified"
                    except catalog.CatalogError: state = "invalid"
                print(f"{item['name']}\t{state}\t{target}")
        return 0
    except catalog.CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
