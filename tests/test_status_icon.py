import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from src.url_builders import status_icon


class TestStatusIcon(unittest.TestCase):
    def test_both_none_returns_grey(self):
        self.assertEqual(status_icon(None, None), "⚪")

    def test_vendor_range_none_returns_grey(self):
        self.assertEqual(status_icon(None, "1.2.3"), "⚪")

    def test_latest_none_returns_grey(self):
        self.assertEqual(status_icon("1.2.3", None), "⚪")

    def test_exact_match_returns_green(self):
        self.assertEqual(status_icon("1.2.3", "1.2.3"), "🟢")

    def test_different_exact_returns_red(self):
        self.assertEqual(status_icon("1.2.3", "1.2.4"), "🔴")

    def test_cocoapods_pessimistic_same_major_returns_green(self):
        # ~> 13.3 means >= 13.3, < 14.0; 13.5 is within range
        self.assertEqual(status_icon("~> 13.3", "13.5"), "🟢")

    def test_cocoapods_pessimistic_different_major_returns_red(self):
        # ~> 13.3 means >= 13.3, < 14.0; 14.0 is outside range
        self.assertEqual(status_icon("~> 13.3", "14.0"), "🔴")

    def test_cocoapods_pessimistic_exact_minor_returns_green(self):
        # 13.3 itself satisfies >= 13.3
        self.assertEqual(status_icon("~> 13.3", "13.3"), "🟢")

    def test_cocoapods_pessimistic_lower_minor_returns_grey_or_red(self):
        # 13.2 is below 13.3, so not in range; function returns ⚪ for parts[1] < minor
        result = status_icon("~> 13.3", "13.2")
        self.assertIn(result, ("⚪", "🔴"))

    def test_maven_inclusive_range_within_returns_green(self):
        # [1.0,2.0] inclusive both ends; 1.5 is within
        self.assertEqual(status_icon("[1.0,2.0]", "1.5"), "🟢")

    def test_maven_exclusive_upper_at_boundary_returns_red(self):
        # [1.0,2.0) exclusive upper; 2.0 is NOT in range
        self.assertEqual(status_icon("[1.0,2.0)", "2.0"), "🔴")

    def test_maven_range_out_of_range_returns_red(self):
        # [1.0,2.0) exclusive upper; 3.0 is way out of range
        self.assertEqual(status_icon("[1.0,2.0)", "3.0"), "🔴")

    def test_maven_inclusive_range_at_lower_bound_returns_green(self):
        self.assertEqual(status_icon("[1.0,2.0]", "1.0"), "🟢")

    def test_maven_inclusive_range_at_upper_bound_returns_green(self):
        self.assertEqual(status_icon("[1.0,2.0]", "2.0"), "🟢")

    def test_vendor_range_provided_but_latest_none_returns_grey(self):
        self.assertEqual(status_icon("~> 5.0", None), "⚪")

    def test_maven_exclusive_lower_boundary_returns_red(self):
        # (1.0,2.0] exclusive lower; 1.0 is NOT in range
        self.assertEqual(status_icon("(1.0,2.0]", "1.0"), "🔴")

    def test_unrecognized_range_returns_red(self):
        # An unrecognized format that is not equal to latest
        self.assertEqual(status_icon(">=1.0", "1.5"), "🔴")


if __name__ == "__main__":
    unittest.main()
