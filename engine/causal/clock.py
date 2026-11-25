"""Vector clocks for audit events: executable specification (stubs only).

A *flat clock* is a mapping from node names to non-negative integer counters::

    {"api": 3, "worker": 1}

A missing component counts as zero.  Absence is not evidence of causality: a
node that is absent from both clocks contributes nothing to the ordering, and
an explicitly stored zero is exactly the same as an absent node.

A *sparse clock* keeps some components at the top level and folds every other
component into the reserved summary key::

    {"api": 3, "__summary__": {"worker": 1, "cron": 2}}

The summary value is a mapping, not a scalar: collapsing several different
nodes into one number loses their identities and makes a later merge and
comparison disagree with the full clock.  The top-level entries and the
summary entries together form one logical vector.  A node must not occur in
both places; :func:`validate_clock` reports that conflict and operations that
need an unambiguous vector raise ``ValueError``.  :func:`compact` moves every
non-kept node into the summary instead of discarding it, and :func:`merge`,
:func:`compare`, :func:`happens_before`, :func:`concurrent` and
:func:`clock_batch` flatten a sparse clock before doing any arithmetic.

The four comparison outcomes are exact lowercase strings: ``"before"``,
``"after"``, ``"equal"`` and ``"concurrent"``.  No tolerance, rounding or
heuristic is permitted anywhere.  All functions are deterministic, use only
the standard library, never mutate their arguments, and never mutate their arguments.

Validation problem codes are returned in lexicographic order:

  * ``clock:not-dict`` for a non-mapping clock;
  * ``node:not-str`` and ``node:empty`` for a bad top-level node name;
  * ``count:not-int:<node>`` and ``count:negative:<node>`` for a bad
    top-level count;
  * ``summary:not-dict`` when the reserved summary value is not a mapping;
  * ``summary:node:not-str`` and ``summary:node:empty`` for a bad summary
    node name;
  * ``summary:count:not-int:<node>`` and
    ``summary:count:negative:<node>`` for a bad summary count;
  * ``summary:conflict:<node>`` when a node occurs both at the top level and
    in the summary.
"""

from collections.abc import Mapping

SUMMARY_KEY = "__summary__"
BEFORE = "before"
AFTER = "after"
EQUAL = "equal"
CONCURRENT = "concurrent"


def _is_count(value) -> bool:
    """Return ``True`` for a legitimate non-negative integer count.

    ``bool`` subclasses ``int`` but is not a legitimate counter value.
    """
    return isinstance(value, int) and not isinstance(value, bool)


def _count_problems(value, prefix: str, label: str) -> list[str]:
    """Return the problem codes for one counter ``value``."""
    if not _is_count(value):
        return [f"{prefix}count:not-int:{label}"]
    if value < 0:
        return [f"{prefix}count:negative:{label}"]
    return []


def _flatten(clock: dict) -> dict:
    """Return a flat copy of ``clock``, expanding its summary, or raise.

    A malformed clock raises ``ValueError``.  Explicit zeros are preserved so
    that merges keep every component that either side spells out.
    """
    problems = validate_clock(clock)
    if problems:
        raise ValueError("malformed clock: " + ", ".join(problems))
    flat = {}
    for node, count in clock.items():
        if node == SUMMARY_KEY:
            continue
        flat[node] = count
    if SUMMARY_KEY in clock:
        flat.update(clock[SUMMARY_KEY])
    return flat


def tick(clock: dict, node: str) -> dict:
    """Advance a local event at ``node`` by one and return a new flat clock.

    ``clock`` is a flat vector clock and ``node`` is a non-empty string.  The
    returned mapping contains the same components as ``clock`` plus ``node``
    if it was absent.  Exactly one counter changes: ``node`` is incremented by
    one.  Every other counter keeps its value.  Incrementing all nodes would
    turn a local event into a global event and destroy the causal distinction
    between nodes, so it is forbidden.

    The input is not modified.  Malformed clocks, including a sparse summary
    in this function, raise ``ValueError``.  A missing node starts at zero and
    therefore becomes one.
    """
    if not isinstance(node, str) or not node:
        raise ValueError("node must be a non-empty string")
    if isinstance(clock, Mapping) and SUMMARY_KEY in clock:
        raise ValueError("tick expects a flat clock, got a sparse summary")
    flat = _flatten(clock)
    flat[node] = flat.get(node, 0) + 1
    return flat


def merge(a: dict, b: dict) -> dict:
    """Merge two clocks componentwise and return a new flat clock.

    Both arguments may be flat or sparse; summaries are flattened first.  The
    result contains every node present in either clock, including nodes whose
    count is zero.  For each node the result is ``max(a_count, b_count)``,
    with an absent component participating as zero, not as one.  Treating a
    missing component as one inflates the result; treating it as anything
    other than zero also breaks commutativity and idempotence.

    The result never contains the reserved summary key: it is a fully expanded
    clock.  Neither argument is modified.  A malformed clock raises
    ``ValueError``.
    """
    left = _flatten(a)
    right = _flatten(b)
    merged = {}
    for node in left.keys() | right.keys():
        merged[node] = max(left.get(node, 0), right.get(node, 0))
    return merged


def compare(a: dict, b: dict) -> str:
    """Return the exact causal relation between two clocks.

    The arguments may be flat or sparse.  Compare them component by component
    after flattening; do not compare the sum of the counters.  Two clocks with
    equal sums can be concurrent, and a clock with the smaller sum can contain
    a component that is ahead of the other clock.

    The result is exactly one of:

      * ``"before"`` when every component of ``a`` is less than or equal to
        the corresponding component of ``b`` and at least one is strictly
        smaller;
      * ``"after"`` when the same holds with the arguments exchanged;
      * ``"equal"`` when every component is equal, including absent and
        explicit zero components;
      * ``"concurrent"`` when each clock has at least one component strictly
        greater than the other clock.

    An absent component and an explicit zero are identical.  A node absent
    from both clocks cannot create a causal relation.  Neither argument is
    modified.  A malformed clock raises ``ValueError``.
    """
    left = _flatten(a)
    right = _flatten(b)
    a_ahead = False
    b_ahead = False
    for node in left.keys() | right.keys():
        left_count = left.get(node, 0)
        right_count = right.get(node, 0)
        if left_count > right_count:
            a_ahead = True
        elif left_count < right_count:
            b_ahead = True
    if a_ahead and b_ahead:
        return CONCURRENT
    if a_ahead:
        return AFTER
    if b_ahead:
        return BEFORE
    return EQUAL


def happens_before(a: dict, b: dict) -> bool:
    """Return ``True`` only for the strict causal order ``a`` before ``b``.

    This is exactly ``compare(a, b) == "before"``.  Every component of ``a``
    must be less than or equal to the corresponding component of ``b``, and at
    least one component must be strictly smaller.  Merely requiring that no
    component of ``a`` is greater than ``b`` is insufficient: it makes equal
    clocks happen before themselves and breaks irreflexivity.

    Missing and explicit zero components are equivalent, and a missing node
    does not count as a causal difference.  The arguments are not modified.
    A malformed clock raises ``ValueError``.
    """
    return compare(a, b) == BEFORE


def concurrent(a: dict, b: dict) -> bool:
    """Return ``True`` only when two clocks are causally concurrent.

    Concurrency requires both directions: there must be at least one component
    where ``a`` is strictly greater than ``b`` and at least one component where
    ``b`` is strictly greater than ``a``.  Using ``or`` instead of ``and``
    turns every ordered pair, and every equal pair, into a false concurrency
    report.

    Equal clocks are not concurrent, and a clock that happens before another
    is not concurrent with it.  Missing and explicit zero components are
    equivalent.  The arguments are not modified.  A malformed clock raises
    ``ValueError``.
    """
    left = _flatten(a)
    right = _flatten(b)
    a_ahead = False
    b_ahead = False
    for node in left.keys() | right.keys():
        left_count = left.get(node, 0)
        right_count = right.get(node, 0)
        if left_count > right_count:
            a_ahead = True
        elif left_count < right_count:
            b_ahead = True
    return a_ahead and b_ahead


def compact(clock: dict, keep) -> dict:
    """Fold all non-kept components of a clock into the reserved summary map.

    ``keep`` is an iterable of node names.  The returned sparse clock contains
    every kept node at the top level, using count zero when the node was not
    present, and puts every other node and its count into the mapping stored
    under :data:`SUMMARY_KEY`.  The summary is always present, possibly as an
    empty mapping, and explicit zero components are folded rather than
    silently dropped.

    The folded values must not be discarded: ``merge`` and ``compare`` use
    them as full components.  If a node occurs both as a kept top-level entry
    and inside an existing summary, the input is ambiguous and ``ValueError``
    is raised; :func:`validate_clock` reports the same condition as
    ``summary:conflict:<node>``.  The reserved key itself may not appear in
    ``keep``.  The input and ``keep`` are not modified.
    """
    if isinstance(keep, str):
        raise ValueError("keep must be an iterable of node names, not a string")
    try:
        kept_nodes = list(keep)
    except TypeError as exc:
        raise ValueError("keep must be an iterable of node names") from exc
    for node in kept_nodes:
        if not isinstance(node, str) or not node:
            raise ValueError("kept node names must be non-empty strings")
        if node == SUMMARY_KEY:
            raise ValueError(f"reserved key {SUMMARY_KEY!r} may not be kept")
    flat = _flatten(clock)
    kept_set = set(kept_nodes)
    folded = {node: count for node, count in flat.items() if node not in kept_set}
    compacted = {node: flat.get(node, 0) for node in kept_nodes}
    compacted[SUMMARY_KEY] = folded
    return compacted


def validate_clock(clock: dict) -> list[str]:
    """Return a sorted list of structural problems; an empty list means valid.

    The check covers negative counts, non-integer counts (``bool`` is not an
    integer count even though it subclasses ``int``), empty or non-string node
    names, malformed summaries, and summary conflicts.  A clock that rolls a
    counter backwards must be rejected rather than silently accepted.  A node
    that appears both at the top level and in the summary is a conflict because
    it would otherwise have two different values in one vector.

    The exact problem codes are documented at module level.  A clean flat
    clock and a clean sparse clock both return ``[]``.  The input is not
    modified and this function does not raise for structural damage; it
    reports every problem it can find.
    """
    if not isinstance(clock, Mapping):
        return ["clock:not-dict"]
    problems = []
    summary = None
    if SUMMARY_KEY in clock:
        summary = clock[SUMMARY_KEY]
        if not isinstance(summary, Mapping):
            problems.append("summary:not-dict")
            summary = None
    for node, count in clock.items():
        if node == SUMMARY_KEY:
            continue
        if not isinstance(node, str):
            problems.append("node:not-str")
        elif not node:
            problems.append("node:empty")
        label = node if isinstance(node, str) else str(node)
        problems.extend(_count_problems(count, "", label))
    if summary is not None:
        for node, count in summary.items():
            if not isinstance(node, str):
                problems.append("summary:node:not-str")
            elif not node:
                problems.append("summary:node:empty")
            label = node if isinstance(node, str) else str(node)
            problems.extend(_count_problems(count, "summary:", label))
            if isinstance(node, str) and node in clock and node != SUMMARY_KEY:
                problems.append(f"summary:conflict:{node}")
    return sorted(set(problems))


def clock_batch(events: list, policy: dict) -> dict:
    """Advance a batch of events independently and optionally merge the results.

    ``events`` is a list of mappings, each shaped like::

        {"clock": <flat or sparse clock>, "node": "<non-empty name>"}

    Each event is processed from its own ``clock``.  No result may become the
    starting clock of the next event: reusing the previous clock serialises
    independent events, leaks one node's progress into another event, and
    makes a batch differ from ticking each event separately.

    ``policy`` is a mapping with a boolean ``"merge_results"``.  The returned
    mapping is::

        {
            "results": [<flat clock for each event, in input order>],
            "merged": <merge of all results, or {} when merging is off>,
        }

    The input events and policy are not modified.  Malformed events, nodes or
    policies raise ``ValueError``.
    """
    if not isinstance(policy, Mapping) or "merge_results" not in policy:
        raise ValueError("policy must be a mapping with 'merge_results'")
    merge_results = policy["merge_results"]
    if not isinstance(merge_results, bool):
        raise ValueError("policy['merge_results'] must be a boolean")
    if not isinstance(events, list):
        raise ValueError("events must be a list")
    results = []
    for event in events:
        if not isinstance(event, Mapping):
            raise ValueError("each event must be a mapping")
        if "clock" not in event or "node" not in event:
            raise ValueError("each event needs 'clock' and 'node'")
        start = event["clock"]
        if isinstance(start, Mapping) and SUMMARY_KEY in start:
            start = _flatten(start)
        results.append(tick(start, event["node"]))
    merged = {}
    if merge_results:
        for result in results:
            merged = merge(merged, result)
    return {"results": results, "merged": merged}
