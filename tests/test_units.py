import unittest

from multitool.units import convert


class UnitsTests(unittest.TestCase):
    def test_length_conversion(self) -> None:
        self.assertEqual(convert(1, "km", "m"), 1000)
        self.assertEqual(convert(1, "mi", "ft"), 5280)

    def test_negative_forty_celsius_equals_fahrenheit(self) -> None:
        self.assertEqual(convert(-40, "C", "F"), -40)

    def test_zero_celsius_preserves_kelvin_precision(self) -> None:
        self.assertEqual(convert(0, "C", "K"), 273.15)

    def test_incompatible_units_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            convert(1, "m", "C")

    def test_unknown_units_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            convert(1, "yd", "m")
