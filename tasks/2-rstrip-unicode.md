Project: python_fixture

# Task 2: Strip trailing Unicode whitespace in strings.clean

## Failing test
tests/test_strings.py::test_clean_nbsp

## Acceptance
- `clean("hi\u00a0\u00a0")` returns `"hi"`
- All existing tests in `tests/` still pass
- Do not change the signature of `clean`
