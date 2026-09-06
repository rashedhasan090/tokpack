"""Lightweight ignore matching (.gitignore + default denylists)."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

DEFAULT_DENY_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".npmrc",
    ".pypirc",
    "credentials.json",
    "service-account.json",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
}

DEFAULT_DENY_SUFFIXES = (
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".crt",
    ".der",
)

DEFAULT_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
    ".tox",
    ".eggs",
}

BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".bz2",
    ".xz",
    ".7z",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp3",
    ".mp4",
    ".wasm",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".bin",
    ".pyc",
    ".pyo",
    ".class",
}


def load_gitignore(root: Path) -> list[str]:
    path = root / ".gitignore"
    if not path.is_file():
        return []
    patterns: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def _match_git_pattern(rel: str, pattern: str) -> bool:
    """Approximate gitignore matching for common cases."""
    if pattern.startswith("!"):
        pattern = pattern[1:]
    if pattern.endswith("/"):
        pattern = pattern[:-1]
        parts = rel.split("/")
        for i in range(len(parts)):
            prefix = "/".join(parts[: i + 1])
            if (
                fnmatch.fnmatch(prefix, pattern)
                or prefix == pattern
                or fnmatch.fnmatch(parts[i], pattern)
            ):
                return True
        return False
    if "/" in pattern.strip("/"):
        return fnmatch.fnmatch(rel, pattern.lstrip("/"))
    if fnmatch.fnmatch(os.path.basename(rel), pattern) or fnmatch.fnmatch(rel, pattern):
        return True
    return any(fnmatch.fnmatch(part, pattern) for part in rel.split("/"))


def is_secretish(path: Path) -> bool:
    name = path.name
    if name in DEFAULT_DENY_NAMES:
        return True
    if name.startswith("id_rsa") or name.startswith("id_ed25519") or name.startswith("id_ecdsa"):
        return True
    lower = name.lower()
    if lower.endswith(DEFAULT_DENY_SUFFIXES):
        return True
    if lower.endswith(".env") or ".env." in lower:
        return True
    return False


def should_skip_dir(name: str) -> bool:
    if name in DEFAULT_SKIP_DIRS:
        return True
    if name.endswith(".egg-info"):
        return True
    return False


def is_ignored(rel: str, gitignore_patterns: list[str], extra_excludes: list[str]) -> bool:
    for pattern in gitignore_patterns:
        if pattern.startswith("!"):
            continue
        if _match_git_pattern(rel, pattern):
            return True
    for pattern in extra_excludes:
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(os.path.basename(rel), pattern):
            return True
    return False


def is_binary_path(path: Path) -> bool:
    return path.suffix.lower() in BINARY_SUFFIXES
