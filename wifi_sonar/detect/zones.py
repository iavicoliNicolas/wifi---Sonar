"""Fuse per-node states into rooms. OR and majority vote, nothing fancier."""

from collections.abc import Mapping, Sequence

_RANK = {"empty": 0, "presence": 1, "motion": 2}


def fuse_states(states: Sequence[str], mode: str = "or") -> str:
    """Combine node states. ``or`` picks the most active. ``vote`` picks the majority.

    A tie goes to the more active state, so one walk is not erased by a tie.
    """
    known = [item for item in states if item in _RANK]
    if not known:
        return "empty"
    if mode == "vote":
        counts: dict[str, int] = {}
        for item in known:
            counts[item] = counts.get(item, 0) + 1
        return max(counts, key=lambda name: (counts[name], _RANK[name]))
    if mode != "or":
        raise ValueError("mode must be 'or' or 'vote'")
    return max(known, key=lambda name: _RANK[name])


def zone_states(
    node_states: Mapping[str, str],
    zones: Sequence[tuple[str, Sequence[str]]],
    mode: str = "or",
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name, node_ids in zones:
        present = [node_states[node] for node in node_ids if node in node_states]
        rows.append({"name": name, "state": fuse_states(present, mode)})
    return rows
