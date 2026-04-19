Project: python_fixture

# http_client.get must forward its timeout argument

## Failing test
tests/test_http_client.py::test_get_forwards_timeout_to_urlopen

## Acceptance
- `get("http://x", timeout=7.5)` passes `timeout=7.5` to `urllib.request.urlopen`
- All existing tests in `tests/` still pass
