import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from src.parsers import (
    _resolve_ruby,
    find_line,
    find_version_value_line,
    gradle_dep,
    podspec_dep,
    podspec_version,
)


class TestResolveRuby(unittest.TestCase):
    def test_resolves_interpolation(self):
        content = "BRAZE_VERSION = '13.3'"
        result = _resolve_ruby(content, "~> #{BRAZE_VERSION}")
        self.assertEqual(result, "~> 13.3")

    def test_no_interpolation(self):
        content = ""
        result = _resolve_ruby(content, "~> 13.3")
        self.assertEqual(result, "~> 13.3")

    def test_unknown_variable_left_unchanged(self):
        content = ""
        result = _resolve_ruby(content, "~> #{UNKNOWN_VAR}")
        self.assertEqual(result, "~> #{UNKNOWN_VAR}")

    def test_multiple_interpolations(self):
        content = "MAJOR = '5'\nMINOR = '0'"
        result = _resolve_ruby(content, "#{MAJOR}.#{MINOR}")
        self.assertEqual(result, "5.0")


class TestFindLine(unittest.TestCase):
    def test_finds_matching_line(self):
        content = "line one\nline two\nversion = '1.2.3'\nline four"
        self.assertEqual(find_line(content, r"version"), 3)

    def test_returns_none_when_not_found(self):
        content = "line one\nline two"
        self.assertIsNone(find_line(content, r"version"))

    def test_returns_first_match(self):
        content = "version = '1.0'\nversion = '2.0'"
        self.assertEqual(find_line(content, r"version"), 1)

    def test_one_based_line_numbers(self):
        content = "alpha\nbeta\ngamma"
        self.assertEqual(find_line(content, r"gamma"), 3)


class TestFindVersionValueLine(unittest.TestCase):
    def test_finds_line_with_version_digits(self):
        content = "brazeVersion = '1.2.3'\nimplementation 'com.example:lib:$brazeVersion'"
        result = find_version_value_line(content, "1.2.3")
        self.assertEqual(result, 1)

    def test_returns_none_when_no_digits_in_version_str(self):
        result = find_version_value_line("any content", "no-digits-here")
        self.assertIsNone(result)

    def test_returns_none_when_version_not_in_content(self):
        content = "brazeVersion = '9.9.9'"
        result = find_version_value_line(content, "1.2.3")
        self.assertIsNone(result)

    def test_range_finds_lower_bound_line(self):
        content = "line one\nrange = '[1.0,2.0)'"
        result = find_version_value_line(content, "[1.0,2.0)")
        self.assertEqual(result, 2)


class TestGradleDep(unittest.TestCase):
    def test_plain_quoted_version(self):
        content = 'implementation "com.example:lib:1.2.3"'
        result = gradle_dep(content, "com.example", "lib")
        self.assertEqual(result, "1.2.3")

    def test_maven_range(self):
        content = 'implementation "com.example:lib:[1.0,2.0)"'
        result = gradle_dep(content, "com.example", "lib")
        self.assertEqual(result, "[1.0,2.0)")

    def test_variable_with_def(self):
        content = (
            'def myVer = "1.0.0"\n'
            'implementation "com.example:lib:$myVer"'
        )
        result = gradle_dep(content, "com.example", "lib")
        self.assertEqual(result, "1.0.0")

    def test_variable_with_val_kotlin_dsl(self):
        content = (
            'val brazeVersion = "5.0.0"\n'
            'implementation "com.braze:android-sdk-ui:$brazeVersion"'
        )
        result = gradle_dep(content, "com.braze", "android-sdk-ui")
        self.assertEqual(result, "5.0.0")

    def test_returns_none_when_not_present(self):
        content = 'implementation "com.other:thing:1.0"'
        result = gradle_dep(content, "com.example", "lib")
        self.assertIsNone(result)

    def test_maven_inclusive_range(self):
        content = 'implementation "com.example:lib:[1.0,2.0]"'
        result = gradle_dep(content, "com.example", "lib")
        self.assertEqual(result, "[1.0,2.0]")

    def test_variable_with_curly_braces(self):
        content = (
            'def sdkVer = "3.1.0"\n'
            'implementation "com.example:lib:${sdkVer}"'
        )
        result = gradle_dep(content, "com.example", "lib")
        self.assertEqual(result, "3.1.0")


class TestPodspecDep(unittest.TestCase):
    def test_inline_version(self):
        content = "s.dependency 'BrazeKit', '~> 13.3'"
        result = podspec_dep(content, "BrazeKit")
        self.assertEqual(result, "~> 13.3")

    def test_variable_reference(self):
        content = (
            "pod_ver = '~> 1.0'\n"
            "s.dependency 'BrazeKit', pod_ver"
        )
        result = podspec_dep(content, "BrazeKit")
        self.assertEqual(result, "~> 1.0")

    def test_ruby_interpolation(self):
        content = (
            "BRAZE_VERSION = '13.3'\n"
            "s.dependency 'BrazeKit', \"~> #{BRAZE_VERSION}\""
        )
        result = podspec_dep(content, "BrazeKit")
        self.assertEqual(result, "~> 13.3")

    def test_returns_none_when_pod_not_present(self):
        content = "s.dependency 'SomeOtherPod', '~> 2.0'"
        result = podspec_dep(content, "BrazeKit")
        self.assertIsNone(result)

    def test_double_quoted_pod_name(self):
        content = 's.dependency "BrazeKit", "~> 13.3"'
        result = podspec_dep(content, "BrazeKit")
        self.assertEqual(result, "~> 13.3")


class TestPodspecVersion(unittest.TestCase):
    def test_single_quoted_version(self):
        content = "s.version = '4.3.0'"
        result = podspec_version(content)
        self.assertEqual(result, "4.3.0")

    def test_double_quoted_version_with_spec_prefix(self):
        content = 'spec.version = "2.0.1"'
        result = podspec_version(content)
        self.assertEqual(result, "2.0.1")

    def test_returns_none_when_not_present(self):
        content = "s.name = 'MyPod'"
        result = podspec_version(content)
        self.assertIsNone(result)

    def test_ignores_other_attributes(self):
        content = "s.name = 'MyPod'\ns.version = '1.0.0'\ns.summary = 'A pod'"
        result = podspec_version(content)
        self.assertEqual(result, "1.0.0")


if __name__ == "__main__":
    unittest.main()
