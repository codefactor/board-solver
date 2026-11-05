"""Synthetic tests for frac_inches, including negatives.

Negative sixteenths must read as sign + magnitude (-1/16, not
-1 15/16): Python divmod on a negative gives a positive remainder,
so a naive whole + fraction rendering misreads by almost 2 inches.
"""

from boardsolver.format import frac_inches


def test_positive_and_zero():
    assert frac_inches(0) == '0″'
    assert frac_inches(16) == '1″'
    assert frac_inches(118) == '7⅜″'
    assert frac_inches(1) == '¹⁄₁₆″'


def test_negative_is_sign_plus_magnitude():
    assert frac_inches(-1) == '-¹⁄₁₆″'
    assert frac_inches(-16) == '-1″'
    assert frac_inches(-17) == '-1¹⁄₁₆″'
    assert frac_inches(-31) == '-1¹⁵⁄₁₆″'


def test_negative_ascii():
    assert frac_inches(-1, ascii=True) == '-1/16"'
    assert frac_inches(-17, ascii=True) == '-1 1/16"'
