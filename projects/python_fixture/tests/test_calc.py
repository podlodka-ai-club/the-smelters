from calc import divide


def test_divide_normal() -> None:
    assert divide(10, 2) == 5


def test_divide_by_zero_returns_none() -> None:
    assert divide(10, 0) is None
