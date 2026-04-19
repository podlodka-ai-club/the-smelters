Project: python_fixture

# Task 1: Fix divide by zero in calc.divide

## Failing test
tests/test_calc.py::test_divide_by_zero_returns_none

## Acceptance
- `calc.divide(10, 0)` returns `None` instead of raising
- All existing tests in `tests/` still pass
