"""Static rule tests for upper-bound pruning of route-hack candidates."""
import pytest

from tests.rules import prune_by_lower_bound, route_hack_lower_bound


def test_unknown_components_count_as_zero_in_bound():
    assert route_hack_lower_bound(fare=300) == 300
    assert route_hack_lower_bound(fare=300, bag_fee=None, positioning=45, hotel=None) == 345


def test_known_components_are_summed():
    assert route_hack_lower_bound(fare=300, bag_fee=40, positioning=45, hotel=90) == 475


@pytest.mark.parametrize("bad", [-1, float("nan")])
def test_rejects_invalid_amounts(bad):
    with pytest.raises(ValueError):
        route_hack_lower_bound(fare=bad)


def candidates():
    return [
        {"id": "open-jaw", "fare": 420, "positioning": 60},          # LB 480
        {"id": "split", "fare": 390},                                # LB 390
        {"id": "nearby", "fare": 350, "bag_fee": 50, "hotel": 100},  # LB 500
    ]


def test_prunes_candidates_whose_bound_reaches_best():
    kept, pruned = prune_by_lower_bound(candidates(), best_total=480)
    assert [c["id"] for c in kept] == ["split"]
    # equality prunes: a bound equal to the best cannot strictly beat it
    assert [p["id"] for p in pruned] == ["open-jaw", "nearby"]
    assert pruned[0]["lower_bound"] == 480 and pruned[0]["best_total"] == 480


def test_kept_candidates_are_ordered_cheapest_bound_first():
    kept, pruned = prune_by_lower_bound(candidates(), best_total=1000)
    assert [c["id"] for c in kept] == ["split", "open-jaw", "nearby"]
    assert pruned == []


def test_no_best_yet_prunes_nothing():
    kept, pruned = prune_by_lower_bound(candidates(), best_total=None)
    assert len(kept) == 3 and pruned == []


def test_rerun_with_a_worse_best_readmits_pruned_candidates():
    # If the current best is later disqualified (bag or duration-cap failure),
    # re-running against the next qualified best must re-admit candidates.
    _, pruned = prune_by_lower_bound(candidates(), best_total=400)
    assert {p["id"] for p in pruned} == {"open-jaw", "nearby"}
    kept, _ = prune_by_lower_bound(candidates(), best_total=600)
    assert {c["id"] for c in kept} == {"split", "open-jaw", "nearby"}


def test_inputs_are_not_mutated():
    items = candidates()
    prune_by_lower_bound(items, best_total=400)
    assert items == candidates()
