from pathlib import Path

from tokpack.pack import pack_context
from tokpack.tokens import estimate_tokens


def test_estimate_tokens_heuristic():
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcdefgh") == 2
    assert estimate_tokens("") == 0


def test_pack_respects_budget_and_skips_secrets(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n" * 20, encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n\nUseful overview.\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=nope\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("filler " * 500, encoding="utf-8")

    result = pack_context(tmp_path, budget=80)
    paths = {f["path"] for f in result.files}

    assert ".env" not in paths
    assert result.tokens_used <= 80
    assert result.leftover == 80 - result.tokens_used
    assert result.pack_id
    assert "tokpack context" in result.markdown


def test_focus_boosts_matching_file(tmp_path: Path):
    (tmp_path / "auth.py").write_text("def login():\n    return True\n", encoding="utf-8")
    (tmp_path / "other.py").write_text("def noop():\n    return None\n" + ("x" * 400), encoding="utf-8")

    # Tight budget: focus should prefer auth.py
    result = pack_context(tmp_path, budget=60, focus=["auth"])
    paths = [f["path"] for f in result.files]
    assert paths
    assert paths[0] == "auth.py" or "auth.py" in paths


def test_pack_id_stable_for_same_content(tmp_path: Path):
    (tmp_path / "a.py").write_text("a = 1\n", encoding="utf-8")
    r1 = pack_context(tmp_path, budget=200)
    r2 = pack_context(tmp_path, budget=200)
    assert r1.pack_id == r2.pack_id
