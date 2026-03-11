import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import datetime
import unittest
from unittest.mock import patch
from src.markdown import _ml, generate_markdown


class TestMl(unittest.TestCase):
    def test_with_url_returns_markdown_link(self):
        self.assertEqual(_ml("hello", "https://example.com"), "[hello](https://example.com)")

    def test_dash_text_returns_dash(self):
        self.assertEqual(_ml("—", "https://example.com"), "—")

    def test_url_none_returns_plain_text(self):
        self.assertEqual(_ml("hello", None), "hello")

    def test_text_starting_with_bracket_escapes_bracket(self):
        result = _ml("[text]", "https://example.com")
        self.assertEqual(result, "[\\[text]](https://example.com)")

    def test_empty_text_returns_dash(self):
        self.assertEqual(_ml("", "https://example.com"), "—")

    def test_empty_text_no_url_returns_dash(self):
        self.assertEqual(_ml("", None), "—")

    def test_regular_text_no_url(self):
        self.assertEqual(_ml("1.2.3", None), "1.2.3")

    def test_text_with_url_no_bracket(self):
        result = _ml("my-repo", "https://github.com/org/my-repo")
        self.assertEqual(result, "[my-repo](https://github.com/org/my-repo)")


class TestGenerateMarkdown(unittest.TestCase):
    def _make_android_data(self):
        return {
            "repo": "rudderlabs/rudder-integration-braze-android",
            "repo_url": "https://github.com/rudderlabs/rudder-integration-braze-android",
            "version": "2.1.1",
            "version_url": "https://github.com/rudderlabs/rudder-integration-braze-android/blob/master/build.gradle#L2",
            "maven_url": "https://mvnrepository.com/artifact/com.rudderstack.android.integration/braze/2.1.1",
            "vendor_range": "[29.0,30.0)",
            "build_file_url": "https://github.com/rudderlabs/rudder-integration-braze-android/blob/master/build.gradle#L10",
            "latest_vendor": "29.5.0",
            "latest_vendor_url": "https://github.com/braze-inc/braze-android-sdk/blob/v29.5.0/build.gradle#L5",
        }

    def _make_ios_data(self):
        return {
            "repo": "rudderlabs/rudder-integration-braze-swift",
            "repo_url": "https://github.com/rudderlabs/rudder-integration-braze-swift",
            "version": "4.3.0",
            "version_url": "https://github.com/rudderlabs/rudder-integration-braze-swift/blob/master/Rudder-Braze.podspec#L3",
            "cocoapods_specs_url": "https://github.com/CocoaPods/Specs/blob/master/Specs/e/1/2/Rudder-Braze/4.3.0/Rudder-Braze.podspec.json",
            "vendor_range": "~> 13.3",
            "podspec_url": "https://github.com/rudderlabs/rudder-integration-braze-swift/blob/master/Rudder-Braze.podspec#L20",
            "latest_vendor": "13.5.0",
            "latest_vendor_url": "https://github.com/CocoaPods/Specs/blob/master/Specs/x/y/z/BrazeKit/13.5.0/BrazeKit.podspec.json",
        }

    def _make_rn_data(self):
        return {
            "rudder_repo_url": "https://github.com/rudderlabs/rudder-sdk-react-native",
            "rudder_npm_version_url": "https://www.npmjs.com/package/@rudderstack/rudder-integration-braze-react-native/v/2.3.0",
            "rudder_version": "2.3.0",
            "rudder_pkg_json_url": "https://github.com/rudderlabs/rudder-sdk-react-native/blob/develop/libs/rudder-integration-braze-react-native/package.json#L3",
            "rudder_android_range": "[2.0,3.0)",
            "rudder_android_url": "https://example.com/android-range",
            "rudder_ios_range": "~> 4.0",
            "rudder_ios_url": "https://example.com/ios-range",
            "vendor_repo_url": "https://github.com/braze-inc/braze-react-native-sdk",
            "vendor_npm_version_url": "https://www.npmjs.com/package/@braze/react-native-sdk/v/8.0.0",
            "vendor_version": "8.0.0",
            "vendor_pkg_json_url": "https://github.com/braze-inc/braze-react-native-sdk/blob/master/package.json#L3",
            "vendor_android_range": "[29.0,30.0)",
            "vendor_android_url": "https://example.com/vendor-android",
            "vendor_ios_range": "~> 13.3",
            "vendor_ios_url": "https://example.com/vendor-ios",
        }

    def _make_flutter_data(self):
        return {
            "rudder_repo_url": "https://github.com/rudderlabs/rudder-sdk-flutter",
            "rudder_pub_version_url": "https://pub.dev/packages/rudder_integration_braze_flutter",
            "rudder_version": "1.0.0",
            "rudder_pubspec_url": "https://github.com/rudderlabs/rudder-sdk-flutter/blob/main/packages/integrations/rudder_integration_braze_flutter/pubspec.yaml#L3",
            "rudder_android_range": "[2.0,3.0)",
            "rudder_android_url": "https://example.com/fl-android-range",
            "rudder_ios_range": "~> 4.0",
            "rudder_ios_url": "https://example.com/fl-ios-range",
            "vendor_repo_url": "https://github.com/braze-inc/braze-flutter-sdk",
            "vendor_pub_version_url": "https://pub.dev/packages/braze_plugin",
            "vendor_version": "3.0.0",
            "vendor_pubspec_url": "https://github.com/braze-inc/braze-flutter-sdk/blob/master/pubspec.yaml#L3",
            "vendor_android_range": "[29.0,30.0)",
            "vendor_android_url": "https://example.com/vendor-fl-android",
            "vendor_ios_range": "~> 13.3",
            "vendor_ios_url": "https://example.com/vendor-fl-ios",
        }

    def _make_cfg(self):
        return {
            "display_name": "Braze",
            "rn": {
                "rudder_pkg": "@rudderstack/rudder-integration-braze-react-native",
                "vendor_pkg": "@braze/react-native-sdk",
            },
            "flutter": {
                "rudder_pkg": "rudder_integration_braze_flutter",
                "vendor_pkg": "braze_plugin",
            },
        }

    @patch("src.markdown.datetime")
    def test_contains_native_integration_section(self, mock_datetime):
        mock_datetime.date.today.return_value = datetime.date(2024, 6, 15)
        result = generate_markdown(
            "braze",
            self._make_cfg(),
            self._make_android_data(),
            self._make_ios_data(),
            self._make_rn_data(),
            self._make_flutter_data(),
        )
        self.assertIn("# Native Integration", result)

    @patch("src.markdown.datetime")
    def test_contains_react_native_sdk_section(self, mock_datetime):
        mock_datetime.date.today.return_value = datetime.date(2024, 6, 15)
        result = generate_markdown(
            "braze",
            self._make_cfg(),
            self._make_android_data(),
            self._make_ios_data(),
            self._make_rn_data(),
            self._make_flutter_data(),
        )
        self.assertIn("# React Native SDK", result)

    @patch("src.markdown.datetime")
    def test_contains_flutter_sdk_section(self, mock_datetime):
        mock_datetime.date.today.return_value = datetime.date(2024, 6, 15)
        result = generate_markdown(
            "braze",
            self._make_cfg(),
            self._make_android_data(),
            self._make_ios_data(),
            self._make_rn_data(),
            self._make_flutter_data(),
        )
        self.assertIn("# Flutter SDK", result)

    @patch("src.markdown.datetime")
    def test_contains_fixed_date(self, mock_datetime):
        mock_datetime.date.today.return_value = datetime.date(2024, 6, 15)
        result = generate_markdown(
            "braze",
            self._make_cfg(),
            self._make_android_data(),
            self._make_ios_data(),
            self._make_rn_data(),
            self._make_flutter_data(),
        )
        self.assertIn("2024-06-15", result)

    @patch("src.markdown.datetime")
    def test_contains_display_name(self, mock_datetime):
        mock_datetime.date.today.return_value = datetime.date(2024, 6, 15)
        result = generate_markdown(
            "braze",
            self._make_cfg(),
            self._make_android_data(),
            self._make_ios_data(),
            self._make_rn_data(),
            self._make_flutter_data(),
        )
        self.assertIn("Braze", result)

    @patch("src.markdown.datetime")
    def test_contains_android_version(self, mock_datetime):
        mock_datetime.date.today.return_value = datetime.date(2024, 6, 15)
        result = generate_markdown(
            "braze",
            self._make_cfg(),
            self._make_android_data(),
            self._make_ios_data(),
            self._make_rn_data(),
            self._make_flutter_data(),
        )
        self.assertIn("2.1.1", result)

    @patch("src.markdown.datetime")
    def test_contains_ios_version(self, mock_datetime):
        mock_datetime.date.today.return_value = datetime.date(2024, 6, 15)
        result = generate_markdown(
            "braze",
            self._make_cfg(),
            self._make_android_data(),
            self._make_ios_data(),
            self._make_rn_data(),
            self._make_flutter_data(),
        )
        self.assertIn("4.3.0", result)

    @patch("src.markdown.datetime")
    def test_output_is_string(self, mock_datetime):
        mock_datetime.date.today.return_value = datetime.date(2024, 6, 15)
        result = generate_markdown(
            "braze",
            self._make_cfg(),
            self._make_android_data(),
            self._make_ios_data(),
            self._make_rn_data(),
            self._make_flutter_data(),
        )
        self.assertIsInstance(result, str)

    @patch("src.markdown.datetime")
    def test_sections_in_correct_order(self, mock_datetime):
        mock_datetime.date.today.return_value = datetime.date(2024, 6, 15)
        result = generate_markdown(
            "braze",
            self._make_cfg(),
            self._make_android_data(),
            self._make_ios_data(),
            self._make_rn_data(),
            self._make_flutter_data(),
        )
        native_pos = result.index("# Native Integration")
        rn_pos = result.index("# React Native SDK")
        flutter_pos = result.index("# Flutter SDK")
        self.assertLess(native_pos, rn_pos)
        self.assertLess(rn_pos, flutter_pos)


if __name__ == "__main__":
    unittest.main()
