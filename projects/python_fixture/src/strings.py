def clean(s: str) -> str:
    """Strip trailing ASCII whitespace. (Unicode trailing spaces should also go.)"""
    return s.rstrip(" \t\n\r")
