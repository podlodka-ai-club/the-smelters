from strings import clean


def test_clean_ascii() -> None:
    assert clean("hi   \n\t") == "hi"


def test_clean_nbsp() -> None:
    assert clean("hi\u00a0\u00a0") == "hi"
