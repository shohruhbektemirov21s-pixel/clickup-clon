"""Lexicographic fractional indexing over a base-62 alphabet.

BINDING contract (docs/DATA_MODEL.md section 8):
1. prev < midstring(prev, nxt) < nxt for all valid inputs (plain string compare).
2. midstring(None, None) == "n".
3. No returned key ends with "0".
"""

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
BASE = len(ALPHABET)  # 62
MIN_CHAR = ALPHABET[0]  # "0"
MID_CHAR = ALPHABET[BASE // 2]  # "V"
FIRST_POSITION = "n"  # midpoint-ish start for an empty scope
MAX_LEN_BEFORE_REBALANCE = 48  # position column is 64 -> plenty of headroom

_INDEX = {c: i for i, c in enumerate(ALPHABET)}


class PositionError(ValueError):
    """prev >= next, or otherwise unorderable input."""


def _guard(key: str) -> str:
    """A key must never end in the minimum character, otherwise nothing can be
    inserted between it and its own prefix."""
    return key + MID_CHAR if key.endswith(MIN_CHAR) else key


def midstring(prev: str | None, nxt: str | None) -> str:
    """Return a key K with prev < K < nxt (either bound may be None = open end)."""
    prev = prev or ""
    nxt = nxt or ""
    if prev and nxt and prev >= nxt:
        raise PositionError(f"prev {prev!r} must sort before next {nxt!r}")
    if not prev and not nxt:
        return FIRST_POSITION

    out: list[str] = []
    i = 0
    upper_open = not nxt
    while True:
        a = _INDEX[prev[i]] if i < len(prev) else 0
        if upper_open or i >= len(nxt):
            b = BASE
        else:
            b = _INDEX[nxt[i]]

        if b - a > 1:  # room for a strict midpoint digit
            out.append(ALPHABET[(a + b) // 2])
            return _guard("".join(out))
        if a == b:  # walk the common prefix
            out.append(ALPHABET[a])
            i += 1
            continue
        # adjacent digits: keep the lower one, then the upper bound opens up
        out.append(ALPHABET[a])
        i += 1
        upper_open = True


def evenly_spaced(n: int) -> list[str]:
    """n keys spread across the alphabet; falls back to 2 chars when n is large."""
    if n <= 0:
        return []
    if n <= BASE - 2:
        return [ALPHABET[round((i + 1) * (BASE - 1) / (n + 1))] for i in range(n)]
    step = (BASE * BASE) / (n + 1)
    out = []
    for i in range(n):
        v = round((i + 1) * step)
        out.append(_guard(ALPHABET[v // BASE] + ALPHABET[v % BASE]))
    return out


def position_after(last: str | None) -> str:
    """Key for appending at the end of a scope."""
    return midstring(last, None)
