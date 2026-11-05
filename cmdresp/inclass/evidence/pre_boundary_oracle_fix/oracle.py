"""Independent binary32 oracle using exact rational arithmetic and integer RNE.

No numpy arithmetic and no call to the DUT/Python model. Numeric inputs/outputs
are raw IEEE 754 binary32 patterns; supported values are normals and signed zero.
"""
from fractions import Fraction


def rational(word):
    sign, exponent, fraction = word >> 31, (word >> 23) & 255, word & 0x7FFFFF
    if exponent == 0:
        if fraction:
            raise ValueError("subnormal outside supported domain")
        return Fraction(0)
    if exponent == 255:
        raise ValueError("nonfinite outside supported domain")
    mantissa = (1 << 23) + fraction
    power = exponent - 150
    v = Fraction(mantissa * (1 << max(power, 0)), 1 << max(-power, 0))
    return -v if sign else v


def round32(value, zero_sign=0):
    if not value:
        return zero_sign << 31
    sign = int(value < 0)
    value = abs(value)
    p, q = value.numerator, value.denominator
    exponent = p.bit_length() - q.bit_length()
    if value < (Fraction(1 << exponent) if exponent >= 0 else Fraction(1, 1 << -exponent)):
        exponent -= 1
    shift = 23 - exponent
    scaled = value * (1 << shift) if shift >= 0 else value / (1 << -shift)
    mantissa, remainder = divmod(scaled.numerator, scaled.denominator)
    twice = 2 * remainder
    if twice > scaled.denominator or (twice == scaled.denominator and mantissa % 2):
        mantissa += 1
    if mantissa == (1 << 24):
        mantissa >>= 1
        exponent += 1
    if not -126 <= exponent <= 127:
        raise ValueError("rounded result outside supported domain")
    return (sign << 31) | ((exponent + 127) << 23) | (mantissa - (1 << 23))


def evaluate_bits(a, b, x):
    product = round32(rational(a) * rational(x), (a ^ x) >> 31)
    exact_sum = rational(product) + rational(b)
    # Under RNE exact cancellation is +0, except -0 + -0 = -0.
    zero_sign = int(product == 0x80000000 and b == 0x80000000)
    return product, round32(exact_sum, zero_sign)
