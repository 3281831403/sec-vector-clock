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
the standard library, never mutate their arguments, and currently raise
``NotImplementedError`` until the defects are fixed.

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

SUMMARY_KEY = "__summary__"
BEFORE = "before"
AFTER = "after"
EQUAL = "equal"
CONCURRENT = "concurrent"


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

    Raises ``NotImplementedError`` until implemented.
    """
    raise NotImplementedError


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

    Raises ``NotImplementedError`` until implemented.
    """
    raise NotImplementedError


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

    Raises ``NotImplementedError`` until implemented.
    """
    raise NotImplementedError


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

    Raises ``NotImplementedError`` until implemented.
    """
    raise NotImplementedError


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

    Raises ``NotImplementedError`` until implemented.
    """
    raise NotImplementedError


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

    Raises ``NotImplementedError`` until implemented.
    """
    raise NotImplementedError


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

    Raises ``NotImplementedError`` until implemented.
    """
    raise NotImplementedError


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

    Raises ``NotImplementedError`` until implemented.
    """
    raise NotImplementedError