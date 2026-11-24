"""Immutable acceptance tests for the causal vector clock.

Every test is deterministic and uses only the standard library and pytest.
The fixtures are plain dictionaries so they do not depend on the stubs.  The
ten defect tests exercise the exact semantics that the exercise describes;
the five invariant tests exercise idempotence, associativity, concurrency
symmetry, sparse equivalence and batch independence.

While the eight functions in ``engine/causal/clock.py`` are stubs, every test
must fail with ``NotImplementedError``.  Do not modify this file, add skips or
xfail markers, relax assertions, or monkeypatch the implementation.
"""

from engine.causal.clock import (
    AFTER,
    BEFORE,
    CONCURRENT,
    EQUAL,
    SUMMARY_KEY,
    clock_batch,
    compact,
    compare,
    concurrent,
    happens_before,
    merge,
    tick,
    validate_clock,
)


def test_compare_uses_componentwise_order_not_component_sum():
    left = {"n1": 5, "n2": 0}
    right = {"n1": 4, "n2": 4}
    assert compare(left, right) == CONCURRENT
    assert compare({"n1": 3}, {"n2": 3}) == CONCURRENT
    assert compare({"n1": 1, "n2": 4}, {"n1": 2, "n2": 4}) == BEFORE
    assert compare({"n1": 2, "n2": 4}, {"n1": 1, "n2": 4}) == AFTER


def test_happens_before_requires_a_strictly_smaller_component():
    clock = {"a": 2, "b": 1}
    assert happens_before(clock, clock) is False
    assert happens_before({"a": 1}, {"a": 1, "b": 0}) is False
    assert happens_before({"a": 1, "b": 2}, {"a": 2, "b": 2}) is True
    assert happens_before({"a": 2, "b": 2}, {"a": 2, "b": 1}) is False
    assert happens_before({"a": 2}, {"a": 1}) is False


def test_concurrent_requires_both_component_directions():
    assert concurrent({"a": 2, "b": 1}, {"a": 1, "b": 2}) is True
    assert concurrent({"a": 2}, {"b": 1}) is True
    assert concurrent({"a": 1}, {"a": 2}) is False
    assert concurrent({"a": 1, "b": 1}, {"a": 1, "b": 2}) is False
    assert concurrent({"a": 1}, {"a": 1}) is False


def test_merge_preserves_components_missing_from_one_side():
    assert merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}
    assert merge({"a": 1, "b": 2}, {"b": 3, "c": 4}) == {
        "a": 1,
        "b": 3,
        "c": 4,
    }


def test_merge_treats_a_missing_component_as_zero():
    assert merge({"a": 5, "b": 0}, {"a": 2}) == {"a": 5, "b": 0}
    assert merge({"a": 5}, {"a": 2, "b": 0}) == {"a": 5, "b": 0}
    assert merge({}, {"a": 0}) == {"a": 0}


def test_tick_advances_only_the_local_node():
    clock = {"a": 2, "b": 5}
    assert tick(clock, "a") == {"a": 3, "b": 5}
    assert clock == {"a": 2, "b": 5}
    assert tick(clock, "c") == {"a": 2, "b": 5, "c": 1}
    assert tick({}, "a") == {"a": 1}


def test_compact_folds_omitted_nodes_and_reports_conflict():
    sparse = compact({"a": 3, "b": 2, "c": 1}, ["a"])
    assert sparse == {"a": 3, SUMMARY_KEY: {"b": 2, "c": 1}}
    assert validate_clock(sparse) == []
    assert validate_clock({"a": 3, SUMMARY_KEY: {"a": 2}}) == [
        "summary:conflict:a"
    ]


def test_validate_clock_rejects_negative_and_malformed_counts():
    assert validate_clock({"a": 0}) == []
    assert validate_clock({"a": True}) == ["count:not-int:a"]
    assert validate_clock(
        {"a": -1, "b": "2", "": 3, SUMMARY_KEY: {"c": -2}}
    ) == [
        "count:negative:a",
        "count:not-int:b",
        "node:empty",
        "summary:count:negative:c",
    ]


def test_clock_batch_keeps_events_independent():
    events = [
        {"clock": {"a": 1}, "node": "a"},
        {"clock": {"b": 1}, "node": "b"},
    ]
    report = clock_batch(events, {"merge_results": True})
    assert report["results"] == [{"a": 2}, {"b": 2}]
    assert report["merged"] == {"a": 2, "b": 2}


def test_compare_equal_is_equal_not_concurrent():
    clock = {"a": 2, "b": 1}
    assert compare(clock, clock) == EQUAL
    assert compare({"a": 1}, {"a": 1}) == EQUAL
    assert compare(clock, {"a": 2, "b": 1, "c": 0}) == EQUAL
    assert merge(clock, clock) == clock


def test_same_node_ticks_are_strictly_ordered():
    once = tick({}, "a")
    twice = tick(once, "a")
    assert once == {"a": 1}
    assert twice == {"a": 2}
    assert compare(once, twice) == BEFORE
    assert happens_before(once, twice) is True
    assert happens_before(twice, once) is False


def test_merge_is_idempotent_commutative_and_associative():
    a = {"a": 1, "b": 3}
    b = {"a": 2, "b": 1, "c": 4}
    c = {"b": 2, "c": 0, "d": 5}
    assert merge(a, a) == a
    assert merge(a, b) == merge(b, a)
    assert merge(merge(a, b), c) == merge(a, merge(b, c))


def test_concurrent_clocks_do_not_happen_before_each_other():
    left = {"a": 2, "b": 1}
    right = {"a": 1, "b": 2}
    assert concurrent(left, right) is True
    assert happens_before(left, right) is False
    assert happens_before(right, left) is False
    assert compare(left, right) == CONCURRENT


def test_sparse_merge_compares_like_the_full_clock():
    left = {"a": 1, "b": 2, "c": 0}
    right = {"a": 3, "b": 0, "c": 1}
    probe = {"a": 4, "b": 1, "c": 0}
    keep = ["a"]
    full_merged = merge(left, right)
    assert full_merged == {"a": 3, "b": 2, "c": 1}
    assert compare(full_merged, probe) == CONCURRENT
    sparse_merged = merge(compact(left, keep), compact(right, keep))
    assert sparse_merged == full_merged
    assert compare(sparse_merged, compact(probe, keep)) == CONCURRENT


def test_batch_matches_individual_ticks():
    events = [
        {"clock": {}, "node": "a"},
        {"clock": {"a": 9}, "node": "b"},
        {"clock": {"b": 2}, "node": "b"},
    ]
    first = clock_batch(events, {"merge_results": True})
    second = clock_batch(events, {"merge_results": True})
    manual = [tick(event["clock"], event["node"]) for event in events]
    assert first["results"] == manual
    assert second == first
    expected = merge(merge(manual[0], manual[1]), manual[2])
    assert first["merged"] == expected