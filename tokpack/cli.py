"""Command-line interface for tokpack."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .pack import manifest_dict, pack_context


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tokpack",
        description="Pack a project into a token-budgeted context bundle for LLM agents.",
    )
    p.add_argument("path", type=Path, help="Project directory to pack")
    p.add_argument("--budget", type=int, required=True, help="Max estimated tokens for the pack")
    p.add_argument("--out", type=Path, default=Path("context.md"), help="Markdown pack output path")
    p.add_argument(
        "--manifest",
        type=Path,
        default=Path("manifest.json"),
        help="JSON manifest output path",
    )
    p.add_argument(
        "--focus",
        action="append",
        default=[],
        help="Keyword to boost (path/content); repeatable",
    )
    p.add_argument(
        "--include",
        action="append",
        default=[],
        help="Only include paths matching this glob; repeatable",
    )
    p.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Extra exclude globs; repeatable",
    )
    p.add_argument(
        "--tiktoken",
        action="store_true",
        help="Use tiktoken cl100k_base if installed; else heuristic",
    )
    p.add_argument("--version", action="version", version=f"tokpack {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.path
    if not root.exists() or not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    try:
        result = pack_context(
            root,
            budget=args.budget,
            focus=args.focus,
            include=args.include,
            exclude=args.exclude,
            use_tiktoken=args.tiktoken,
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    args.out.write_text(result.markdown, encoding="utf-8")
    man = manifest_dict(result, root)
    args.manifest.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")

    print(
        f"tokpack {result.pack_id}: packed {len(result.files)} files, "
        f"{result.tokens_used}/{result.budget} tokens "
        f"({result.leftover} leftover) -> {args.out} + {args.manifest}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
