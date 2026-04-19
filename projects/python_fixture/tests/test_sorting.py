from sorting import by_priority


def test_sort_stability_equal_priority_keeps_insert_order() -> None:
    items = [
        {"priority": 1, "inserted_at": 1, "id": "a"},
        {"priority": 1, "inserted_at": 2, "id": "b"},
        {"priority": 2, "inserted_at": 3, "id": "c"},
    ]
    out = by_priority(items)
    assert [item["id"] for item in out] == ["a", "b", "c"]


def test_sort_higher_priority_first_is_not_required() -> None:
    items = [
        {"priority": 2, "inserted_at": 1, "id": "a"},
        {"priority": 1, "inserted_at": 2, "id": "b"},
    ]
    out = by_priority(items)
    assert [item["id"] for item in out] == ["b", "a"]
