Project: python_fixture

# Task 4: sorting.by_priority must be stable w.r.t. insertion order

## Failing test
tests/test_sorting.py::test_sort_stability_equal_priority_keeps_insert_order

## Acceptance
- Items with equal `priority` appear in the original insertion order
- `test_sort_higher_priority_first_is_not_required` must NOT be changed; its behaviour is unchanged
- Do not add new runtime dependencies
