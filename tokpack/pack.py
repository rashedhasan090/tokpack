"""Core packing logic."""

from __future__ import annotations

import fnmatch
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from .ignore import (
    is_binary_path,
    is_ignored,
    is_secretish,
    load_gitignore,
    should_skip_dir,
)
from .tokens import estimate_tokens

SOURCE_EXTS = {
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".go", ".rs", ".java", ".kt", ".c", ".h", ".cpp", ".hpp", ".cs",
    ".rb", ".php", ".swift", ".scala", ".sh", ".bash", ".zsh", ".sql",
    ".r", ".jl",
}
DOC_EXTS = {".md", ".rst", ".txt", ".adoc"}
CONFIG_EXTS = {".toml", ".yaml", ".yml", ".json", ".ini", ".cfg", ".lock"}
LOW_VALUE_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Cargo.lock", "composer.lock",
}


@dataclass
class FileCandidate:
    path: Path
    rel: str
    score: float
    tokens: int
    sha256: str
    text: str


@dataclass
class PackResult:
    pack_id: str
    budget: int
    tokens_used: int
    files: list[dict]
    markdown: str
    leftover: int


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _score_file(rel: str, path: Path, text: str, focus: list[str]) -> float:
    score = 10.0
    ext = path.suffix.lower()
    name = path.name

    if name in LOW_VALUE_NAMES or ext == ".lock":
        score -= 20
    elif ext in SOURCE_EXTS:
        score += 40
    elif ext in DOC_EXTS:
        score += 20
    elif ext in CONFIG_EXTS:
        score += 12
    elif name in {"Dockerfile", "Makefile", "Justfile"}:
        score += 25
    else:
        score += 5

    score -= rel.count("/") * 1.5

    lowered = rel.lower()
    if "/test" in f"/{lowered}" or lowered.startswith("tests/") or lowered.startswith("test/"):
        score -= 8
    if "/vendor/" in f"/{lowered}" or "/third_party/" in f"/{lowered}":
        score -= 15

    for keyword in focus:
        k = keyword.lower()
        if k in lowered:
            score += 25
        if k in text.lower():
            score += 15

    if rel.lower() in {"readme.md", "readme.rst", "readme.txt"}:
        score += 18

    return score


def iter_candidates(
    root: Path,
    focus: list[str] | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    use_tiktoken: bool = False,
    max_file_bytes: int = 256_000,
) -> list[FileCandidate]:
    focus = focus or []
    include = include or []
    exclude = exclude or []
    root = root.resolve()
    gitignore = load_gitignore(root)
    out: list[FileCandidate] = []

    for dirpath, dirnames, filenames in os.walk(root):
        kept = []
        for d in dirnames:
            if should_skip_dir(d):
                continue
            rel_dir = str((Path(dirpath) / d).relative_to(root)).replace("\\", "/")
            if is_ignored(rel_dir, gitignore, exclude) or is_ignored(rel_dir + "/", gitignore, exclude):
                continue
            kept.append(d)
        dirnames[:] = kept

        for name in filenames:
            path = Path(dirpath) / name
            rel = str(path.relative_to(root)).replace("\\", "/")
            if is_secretish(path) or is_binary_path(path):
                continue
            if is_ignored(rel, gitignore, exclude):
                continue
            if include and not any(
                fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(name, g) for g in include
            ):
                continue
            try:
                if path.stat().st_size > max_file_bytes:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "\x00" in text:
                continue
            tokens = estimate_tokens(text, use_tiktoken=use_tiktoken)
            tokens += estimate_tokens(f"\n\n## {rel}\n\n```\n```\n", use_tiktoken=use_tiktoken)
            score = _score_file(rel, path, text, focus)
            out.append(
                FileCandidate(
                    path=path,
                    rel=rel,
                    score=score,
                    tokens=tokens,
                    sha256=_sha256_text(text),
                    text=text,
                )
            )
    out.sort(key=lambda c: (-c.score, c.rel))
    return out


def pack_context(
    root: Path,
    budget: int,
    focus: list[str] | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    use_tiktoken: bool = False,
) -> PackResult:
    if budget < 1:
        raise ValueError("budget must be >= 1")
    candidates = iter_candidates(
        root, focus=focus, include=include, exclude=exclude, use_tiktoken=use_tiktoken
    )
    chosen: list[FileCandidate] = []
    used = 0
    for c in candidates:
        if used + c.tokens > budget:
            continue
        chosen.append(c)
        used += c.tokens

    digest = hashlib.sha256()
    for c in sorted(chosen, key=lambda x: x.rel):
        digest.update(c.rel.encode("utf-8"))
        digest.update(b":")
        digest.update(c.sha256.encode("utf-8"))
        digest.update(b"\n")
    pack_id = digest.hexdigest()[:16]

    parts = [
        "# tokpack context\n",
        f"\n- pack_id: `{pack_id}`\n",
        f"- root: `{root.resolve()}`\n",
        f"- budget: {budget}\n",
        f"- tokens_used: {used}\n",
        f"- files: {len(chosen)}\n",
    ]
    files_meta: list[dict] = []
    for c in chosen:
        lang = c.path.suffix.lstrip(".") or "text"
        parts.append(f"\n## {c.rel}\n\n```{lang}\n{c.text.rstrip()}\n```\n")
        files_meta.append(
            {
                "path": c.rel,
                "score": round(c.score, 2),
                "tokens": c.tokens,
                "sha256": c.sha256,
            }
        )

    return PackResult(
        pack_id=pack_id,
        budget=budget,
        tokens_used=used,
        files=files_meta,
        markdown="".join(parts),
        leftover=max(0, budget - used),
    )


def manifest_dict(result: PackResult, root: Path) -> dict:
    return {
        "tool": "tokpack",
        "version": "0.1.0",
        "pack_id": result.pack_id,
        "root": str(root.resolve()),
        "budget": result.budget,
        "tokens_used": result.tokens_used,
        "leftover": result.leftover,
        "files": result.files,
    }
