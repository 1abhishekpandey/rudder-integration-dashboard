import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
from unittest.mock import patch

from src.fetchers import fetch_android, fetch_ios

GITHUB_BLOB_PREFIX = "https://github.com/"
GITHUB_BLOB_MARKER = "/blob/"

_ANDROID_CFG = {
    "repo":                "rudderlabs/rudder-integration-adjust-android",
    "maven_group":         "com.rudderstack.android.integration",
    "maven_artifact":      "adjust",
    "build_file":          "adjust/build.gradle",
    "vendor_group":        "com.adjust.sdk",
    "vendor_artifact":     "adjust-android",
    "vendor_repo":         "adjust/android_sdk",
    "vendor_version_file": "Adjust/build.gradle",
}

_IOS_CFG = {
    "repo":                "rudderlabs/rudder-integration-adjust-ios",
    "pod":                 "Rudder-Adjust",
    "podspec_file":        "Rudder-Adjust.podspec",
    "package_json_file":   "package.json",
    "vendor_pod":          "Adjust",
    "vendor_gh_repo":      "adjust/ios_sdk",
    "vendor_version_file": "Adjust.podspec",
}

_VENDOR_BUILD_GRADLE = "ext {\n    coreVersionName = '5.4.1'\n}\n"
_RUDDER_BUILD_GRADLE = (
    "ext {\n"
    "    coreVersionName = '5.4.1'\n"
    "}\n"
    "dependencies {\n"
    '    implementation "com.adjust.sdk:adjust-android:5.4.1"\n'
    "}\n"
)
_PACKAGE_JSON = '{"name": "rudder-integration-adjust-android", "version": "2.1.0"}'
_PODSPEC = (
    "Pod::Spec.new do |s|\n"
    "  s.version = '2.2.0'\n"
    "  s.dependency 'Adjust', '~> 5.1.0'\n"
    "end\n"
)
_VENDOR_PODSPEC = "Pod::Spec.new do |s|\n  s.version = '5.5.3'\nend\n"


def _is_github_blob_with_anchor(url: str) -> bool:
    return (
        url.startswith(GITHUB_BLOB_PREFIX)
        and GITHUB_BLOB_MARKER in url
        and "#L" in url
    )


class TestFetchAndroidLatestVendorUrl(unittest.TestCase):

    @patch("src.fetchers.maven_latest", return_value="5.4.1")
    @patch("src.fetchers.gh_raw_at_version", return_value=(_VENDOR_BUILD_GRADLE, "v5.4.1"))
    @patch("src.fetchers.gh_raw_default")
    def test_latest_vendor_url_is_github_blob_with_line_anchor(
        self, mock_default, _mock_at_ver, _mock_maven
    ):
        mock_default.side_effect = [
            (_RUDDER_BUILD_GRADLE, "master"),  # build_file fetch
            (_PACKAGE_JSON, "master"),          # package.json fetch
        ]
        result = fetch_android(_ANDROID_CFG, "2.1.0")
        url = result.get("latest_vendor_url")
        self.assertIsNotNone(url, "latest_vendor_url must be set when vendor file is fetched")
        self.assertTrue(
            _is_github_blob_with_anchor(url),
            f"latest_vendor_url must be a GitHub blob URL with #L anchor, got: {url}",
        )

    @patch("src.fetchers.maven_latest", return_value="5.4.1")
    @patch("src.fetchers.gh_raw_at_version", return_value=(_VENDOR_BUILD_GRADLE, "v5.4.1"))
    @patch("src.fetchers.gh_raw_default")
    def test_latest_vendor_url_not_a_registry_url(
        self, mock_default, _mock_at_ver, _mock_maven
    ):
        mock_default.side_effect = [
            (_RUDDER_BUILD_GRADLE, "master"),
            (_PACKAGE_JSON, "master"),
        ]
        result = fetch_android(_ANDROID_CFG, "2.1.0")
        url = result.get("latest_vendor_url", "")
        self.assertNotIn("mvnrepository.com", url, "latest_vendor_url must not point to Maven repository")
        self.assertNotIn("search.maven.org", url, "latest_vendor_url must not point to Maven search")
        self.assertNotIn("npmjs.com", url, "latest_vendor_url must not point to npm")
        self.assertNotIn("pub.dev", url, "latest_vendor_url must not point to pub.dev")

    @patch("src.fetchers.maven_latest", return_value="5.4.1")
    @patch("src.fetchers.gh_raw_at_version", return_value=(None, "main"))
    @patch("src.fetchers.gh_raw_default")
    def test_latest_vendor_url_absent_when_vendor_file_not_found(
        self, mock_default, _mock_at_ver, _mock_maven
    ):
        """When the vendor version file cannot be fetched, no URL should be set
        (no silent fallback to a registry URL)."""
        mock_default.side_effect = [
            (_RUDDER_BUILD_GRADLE, "master"),
            (_PACKAGE_JSON, "master"),
        ]
        result = fetch_android(_ANDROID_CFG, "2.1.0")
        self.assertNotIn(
            "latest_vendor_url", result,
            "latest_vendor_url must not be set when vendor file fetch fails — "
            "a registry fallback URL would silently mask a wrong vendor_version_file path",
        )

    @patch("src.fetchers.maven_latest", return_value="5.4.1")
    @patch("src.fetchers.gh_raw_at_version", return_value=(_VENDOR_BUILD_GRADLE, "v5.4.1"))
    @patch("src.fetchers.gh_raw_default")
    def test_latest_vendor_url_contains_vendor_repo(
        self, mock_default, _mock_at_ver, _mock_maven
    ):
        mock_default.side_effect = [
            (_RUDDER_BUILD_GRADLE, "master"),
            (_PACKAGE_JSON, "master"),
        ]
        result = fetch_android(_ANDROID_CFG, "2.1.0")
        url = result.get("latest_vendor_url", "")
        self.assertIn(
            _ANDROID_CFG["vendor_repo"], url,
            "latest_vendor_url must reference the vendor_repo from config",
        )

    @patch("src.fetchers.maven_latest", return_value="5.4.1")
    @patch("src.fetchers.gh_raw_at_version", return_value=(_VENDOR_BUILD_GRADLE, "v5.4.1"))
    @patch("src.fetchers.gh_raw_default")
    def test_latest_vendor_url_contains_vendor_version_file(
        self, mock_default, _mock_at_ver, _mock_maven
    ):
        mock_default.side_effect = [
            (_RUDDER_BUILD_GRADLE, "master"),
            (_PACKAGE_JSON, "master"),
        ]
        result = fetch_android(_ANDROID_CFG, "2.1.0")
        url = result.get("latest_vendor_url", "")
        self.assertIn(
            _ANDROID_CFG["vendor_version_file"], url,
            "latest_vendor_url must reference the vendor_version_file path from config",
        )


class TestFetchIosLatestVendorUrl(unittest.TestCase):

    @patch("src.fetchers.cocoapods_latest", return_value="5.5.3")
    @patch("src.fetchers.gh_raw_at_version", return_value=(_VENDOR_PODSPEC, "v5.5.3"))
    @patch("src.fetchers.gh_raw_default")
    def test_latest_vendor_url_is_github_blob_with_line_anchor(
        self, mock_default, _mock_at_ver, _mock_cocoapods
    ):
        mock_default.side_effect = [
            (_PODSPEC, "master"),       # podspec_file fetch
            (_PACKAGE_JSON, "master"),  # package_json_file fetch
        ]
        result = fetch_ios(_IOS_CFG)
        url = result.get("latest_vendor_url")
        self.assertIsNotNone(url, "latest_vendor_url must be set when vendor podspec is fetched")
        self.assertTrue(
            _is_github_blob_with_anchor(url),
            f"latest_vendor_url must be a GitHub blob URL with #L anchor, got: {url}",
        )

    @patch("src.fetchers.cocoapods_latest", return_value="5.5.3")
    @patch("src.fetchers.gh_raw_at_version", return_value=(_VENDOR_PODSPEC, "v5.5.3"))
    @patch("src.fetchers.gh_raw_default")
    def test_latest_vendor_url_not_a_registry_url(
        self, mock_default, _mock_at_ver, _mock_cocoapods
    ):
        mock_default.side_effect = [
            (_PODSPEC, "master"),
            (_PACKAGE_JSON, "master"),
        ]
        result = fetch_ios(_IOS_CFG)
        url = result.get("latest_vendor_url", "")
        self.assertNotIn("cocoapods.org", url, "latest_vendor_url must not point to CocoaPods trunk")
        self.assertNotIn("mvnrepository.com", url, "latest_vendor_url must not point to Maven")
        self.assertNotIn("pub.dev", url, "latest_vendor_url must not point to pub.dev")

    @patch("src.fetchers.cocoapods_latest", return_value="5.5.3")
    @patch("src.fetchers.gh_raw_at_version", return_value=(None, "main"))
    @patch("src.fetchers.gh_raw_default")
    def test_latest_vendor_url_absent_when_vendor_podspec_not_found(
        self, mock_default, _mock_at_ver, _mock_cocoapods
    ):
        mock_default.side_effect = [
            (_PODSPEC, "master"),
            (_PACKAGE_JSON, "master"),
        ]
        result = fetch_ios(_IOS_CFG)
        self.assertNotIn(
            "latest_vendor_url", result,
            "latest_vendor_url must not be set when vendor podspec fetch fails",
        )


if __name__ == "__main__":
    unittest.main()
