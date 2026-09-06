"""Token estimation helpers."""

from __future__ import annotations

import math
from functools import lru_cache


def estimate_tokens(text: str, use_tiktoken: bool = False) -> int:
    if use_tiktoken:
        enc = _tiktoken_encoder()
        if enc is not None:
            return len(enc.encode(text))
    return max(1, math.ceil(len(text) / 4)) if text else 0


@lru_cache(maxsize=1)
def _tiktoken_encoder():
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None
