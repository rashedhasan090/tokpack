# tokpack

**Token-budgeted context packer for LLM agents.**

Dumping a whole repo into a prompt wastes context and hides the files that matter. `tokpack` ranks project files, packs the highest-value ones until a token budget is exhausted, and emits:

1. A single markdown context pack you can paste into an agent / chat
2. A JSON manifest with per-file `sha256` hashes and a content-addressed `pack_id` for reproducibility

## Why this is novel

Most “repo to prompt” helpers either concatenate everything or rely on embeddings / a hosted indexer. `tokpack` is a tiny offline CLI that treats **token budget as a hard constraint**, scores files with transparent heuristics (source > docs > lockfiles, path depth, optional `--focus` keywords), skips secret-ish paths by default, and fingerprints the exact pack so you can re-run experiments with the same context receipt.

It is original small-scale tooling — not a fork or thin wrapper of a famous project.

## Install

```bash
pip install -e ".[dev]"
```

Optional better token counts:

```bash
pip install -e ".[tiktoken]"
```

## Usage

```bash
tokpack examples/demo_project --budget 500 --out context.md --manifest manifest.json
```

Boost paths/content matching keywords:

```bash
tokpack . --budget 8000 --focus auth --focus api
```

Include / exclude globs:

```bash
tokpack . --budget 4000 --include "src/**/*.py" --exclude "**/generated/**"
```

Use tiktoken when installed:

```bash
tokpack . --budget 4000 --tiktoken
```

Stderr prints a one-line summary, including the `pack_id`.

## Scoring (short)

- Source extensions score highest; docs next; lockfiles are deprioritized
- Shallower paths preferred; `tests/` slightly downranked
- `--focus` keywords boost matching paths and file contents
- Skips `.git`, `node_modules`, venvs, binaries, and secret-ish names (`.env`, `*.pem`, `id_rsa*`, `credentials.json`, …)
- Respects `.gitignore` (common patterns)

Default token estimate is `ceil(chars / 4)`. With `--tiktoken`, uses `cl100k_base` when the optional dependency is present.

## Demo

```bash
pip install -e .
tokpack examples/demo_project --budget 400 --out /tmp/demo.md --manifest /tmp/demo.json
cat /tmp/demo.json | head
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
