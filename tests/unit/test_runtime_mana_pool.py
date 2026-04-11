from runtime_mana_pool import RuntimeManaPool


def test_normalizes_sorts_and_deduplicates_values() -> None:
    pool = RuntimeManaPool([3, 1.0, 2.5, 3.0, 1, "bad"])
    assert pool.values() == [1, 2.5, 3]
    assert pool.current() == 1


def test_step_wraps_around() -> None:
    pool = RuntimeManaPool([1, 2, 3])
    assert pool.step(-1) == 3
    assert pool.step(1) == 1
    assert pool.step(4) == 2


def test_set_values_prefers_closest_value() -> None:
    pool = RuntimeManaPool([1, 4, 8])
    pool.set_values([2, 6, 10], preferred_value=7)
    assert pool.current() == 6


def test_set_values_ignores_empty_replacement() -> None:
    pool = RuntimeManaPool([1, 2, 3])
    pool.step(1)
    pool.set_values([])
    assert pool.values() == [1, 2, 3]
    assert pool.current() == 2
