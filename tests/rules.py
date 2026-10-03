"""Pure, importable helpers encoding the skill's static research rules.

``rules`` is intentionally free of I/O: no network access, no file reads, no
datetime "now". Every function is deterministic and side-effect free so it can
be exercised by importable pytest tests without a live flight site.
"""

from __future__ import annotations

from typing import Iterable, Iterator, Sequence, Tuple

# A strict per-direction journey cap: reject totals of 20:00:00 or longer.
STRICT_DURATION_CAP_SECONDS = 20 * 60 * 60  # 20:00:00


def duration_to_seconds(hhmmss: str) -> int:
    """Convert a strict ``HH:MM:SS`` duration to integer seconds.

    >>> duration_to_seconds("19:59:59")
    71999
    """
    parts = hhmmss.split(":")
    if len(parts) != 3 or any(
        len(part) != 2 or not part.isascii() or not part.isdigit() for part in parts
    ):
        raise ValueError("duration must use HH:MM:SS format")
    hours, minutes, seconds = map(int, parts)
    if minutes >= 60 or seconds >= 60:
        raise ValueError("minutes and seconds must be between 00 and 59")
    return hours * 3600 + minutes * 60 + seconds


def passes_strict_duration_cap(hhmmss: str) -> bool:
    """Return whether a journey's total duration passes the strict under-20 cap.

    Exactly ``20:00:00`` is REJECTED (>= the cap); ``19:59:59`` passes.
    """
    return duration_to_seconds(hhmmss) < STRICT_DURATION_CAP_SECONDS


def enumerate_rolling_windows(
    first_outbound: int,
    last_outbound: int,
    length_days: int,
) -> list[tuple[int, int]]:
    """Enumerate an exact fixed-length rolling matched-date window.

    Every pair is preserved as its own (outbound, return) tuple — never
    collapsed into one ±N-day placeholder. For example a "10 days, anywhere
    from 5-15 through 10-20 March" request (length 10, outbounds 5..10):

    >>> enumerate_rolling_windows(5, 10, 10)
    [(5, 15), (6, 16), (7, 17), (8, 18), (9, 19), (10, 20)]
    """
    if first_outbound > last_outbound:
        raise ValueError("first_outbound must be <= last_outbound")
    if length_days < 1:
        raise ValueError("length_days must be >= 1")
    return [
        (outbound, outbound + length_days)
        for outbound in range(first_outbound, last_outbound + 1)
    ]


def classify_baggage(row: dict) -> str:
    """Map a result row to exactly one baggage bucket.

    Returns one of ``"included"`` | ``"fee required"`` | ``"unverified"``.
    """
    marker = str(row.get("baggage", "")).strip().lower()
    if marker in {"included", "check-in", "checked"}:
        return "included"
    if "fee" in marker or "extra" in marker or marker in {"optional"}:
        return "fee required"
    return "unverified"


def sources_independent(source_a: dict, source_b: dict) -> bool:
    """Return whether two retrieved sources are evidence-independent.

    Two frontends that share a single inventory backend (or a redirect chain
    into the same inventory) are NOT independent. Independence requires both a
    distinct frontend and a distinct inventory backend.
    """
    for field in ("frontend", "inventory_backend"):
        a, b = source_a.get(field), source_b.get(field)
        if not isinstance(a, str) or not isinstance(b, str):
            return False
        if not a.strip() or not b.strip() or a == b:
            return False
    return True


def blocked_source_once(attempts: Sequence[dict]) -> list[dict]:
    """Return attempts with each blocked source recorded exactly once.

    A source that produced an explicit block (bot page / CAPTCHA / HTTP 403 /
    provider guard) is recorded on its first blocked attempt and is NOT
    retried; later blocked attempts for the same source are dropped.
    """
    recorded: dict[str, dict] = {}
    for attempt in attempts:
        if attempt.get("blocked"):
            source = str(attempt.get("source"))
            recorded.setdefault(source, attempt)
    # Deterministic ordering by first appearance for the non-blocked summary.
    return list(recorded.values())


def all_unique(names: Iterable[object]) -> bool:
    """Return whether every supplied name is distinct (helper for assertions)."""
    seen: set[object] = set()
    for name in names:
        if name in seen:
            return False
        seen.add(name)
    return True


def _amount(value: object) -> float:
    """Validate one non-negative money amount; ``None`` (unknown) counts as 0."""
    if value is None:
        return 0.0
    amount = float(value)  # type: ignore[arg-type]
    if amount != amount or amount < 0:  # NaN or negative
        raise ValueError("amounts must be non-negative numbers")
    return amount


def route_hack_lower_bound(
    fare: float,
    bag_fee: float | None = None,
    positioning: float | None = None,
    hotel: float | None = None,
) -> float:
    """Lowest possible all-in total for a route-hack candidate.

    Unknown components count as 0 *in the bound only*, so pruning on this
    bound can never discard a candidate that might still win. Never report
    the bound as a price.

    >>> route_hack_lower_bound(300, bag_fee=None, positioning=45)
    345.0
    """
    return _amount(fare) + _amount(bag_fee) + _amount(positioning) + _amount(hotel)


def prune_by_lower_bound(
    candidates: Sequence[dict], best_total: float | None
) -> Tuple[list[dict], list[dict]]:
    """Split candidates into (kept, pruned) against the best qualified total.

    A candidate is pruned when its lower bound is >= ``best_total``: it cannot
    strictly beat the current best, so slow airline-direct repricing is
    skipped. Both lists are ordered cheapest bound first and carry
    ``lower_bound``; pruned rows also carry ``best_total`` for the log line.
    Inputs are not mutated. Re-run with the next qualified best when the
    current best is disqualified, which re-admits candidates automatically.
    """
    scored = sorted(
        (
            dict(
                candidate,
                lower_bound=route_hack_lower_bound(
                    candidate["fare"],
                    candidate.get("bag_fee"),
                    candidate.get("positioning"),
                    candidate.get("hotel"),
                ),
            )
            for candidate in candidates
        ),
        key=lambda row: row["lower_bound"],
    )
    if best_total is None:
        return scored, []
    best = _amount(best_total)
    kept = [row for row in scored if row["lower_bound"] < best]
    pruned = [dict(row, best_total=best) for row in scored if row["lower_bound"] >= best]
    return kept, pruned
