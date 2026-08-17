from app.services.grading import numeric_equivalent


def test_numeric_equivalent_fraction_matches_decimal():
    assert numeric_equivalent("0.5", ["1/2"])
    assert numeric_equivalent("1/2", ["0.5"])


def test_numeric_equivalent_negative():
    assert numeric_equivalent("-3", ["-3", "-3.0"])
    assert not numeric_equivalent("3", ["-3"])


def test_numeric_equivalent_non_numeric_falls_back_to_string():
    assert numeric_equivalent("hello", ["hello", "world"])
    assert not numeric_equivalent("hello", ["world"])


def test_numeric_equivalent_none_input():
    assert not numeric_equivalent(None, ["1"])
