import re
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
_NEWER_VENDOR_BUILD_GRADLE = "ext {\n    coreVersionName = '6.0.0'\n}\n"
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
_NEWER_VENDOR_PODSPEC = "Pod::Spec.new do |s|\n  s.version = '6.0.0'\nend\n"

# Matches blob/<something-that-looks-like-a-semver-tag>/
# e.g. blob/5.4.1/ or blob/v5.4.1/ but NOT blob/main/ or blob/master/
_TAG_IN_BLOB_URL = re.compile(r"/blob/v?\d+\.\d+[\d.]*(-\S+)?/")


def _is_github_blob_with_anchor(url: str) -> bool:
    return (
        url.startswith(GITHUB_BLOB_PREFIX)
        and GITHUB_BLOB_MARKER in url
        and "#L" in url
    )


def _uses_default_branch(url: str) -> bool:
    """Return True when the blob URL uses main or master, not a version tag."""
    return "/blob/main/" in url or "/blob/master/" in url


def _uses_version_tag(url: str) -> bool:
    """Return True when the blob URL contains a semver-like tag segment."""
    return bool(_TAG_IN_BLOB_URL.search(url))


# ── Android ────────────────────────────────────────────────────────────────────

class TestFetchAndroidLatestVendorUrl(unittest.TestCase):

    def _default_side_effect(self, vendor_content=_VENDOR_BUILD_GRADLE, vendor_ref="main"):
        return [
            (_RUDDER_BUILD_GRADLE, "master"),   # build_file fetch
            (_PACKAGE_JSON, "master"),           # package.json fetch
            (vendor_content, vendor_ref),        # vendor_version_file fetch
        ]

    @patch("src.fetchers.maven_latest", return_value="5.4.1")
    @patch("src.fetchers.gh_raw_default")
    def test_latest_vendor_url_is_github_blob_with_line_anchor(
        self, mock_default, _mock_maven
    ):
        mock_default.side_effect = self._default_side_effect()
        result = fetch_android(_ANDROID_CFG, "2.1.0")
        url = result.get("latest_vendor_url")
        self.assertIsNotNone(url, "latest_vendor_url must be set when vendor file is fetched")
        self.assertTrue(
            _is_github_blob_with_anchor(url),
            f"latest_vendor_url must be a GitHub blob URL with #L anchor, got: {url}",
        )

    @patch("src.fetchers.maven_latest", return_value="5.4.1")
    @patch("src.fetchers.gh_raw_default")
    def test_latest_vendor_url_not_a_registry_url(
        self, mock_default, _mock_maven
    ):
        mock_default.side_effect = self._default_side_effect()
        result = fetch_android(_ANDROID_CFG, "2.1.0")
        url = result.get("latest_vendor_url", "")
        self.assertNotIn("mvnrepository.com", url, "latest_vendor_url must not point to Maven repository")
        self.assertNotIn("search.maven.org", url, "latest_vendor_url must not point to Maven search")
        self.assertNotIn("npmjs.com", url, "latest_vendor_url must not point to npm")
        self.assertNotIn("pub.dev", url, "latest_vendor_url must not point to pub.dev")

    @patch("src.fetchers.maven_latest", return_value="5.4.1")
    @patch("src.fetchers.gh_raw_default")
    def test_latest_vendor_url_absent_when_vendor_file_not_found(
        self, mock_default, _mock_maven
    ):
        """When the vendor version file cannot be fetched at all, no URL should be set."""
        mock_default.side_effect = self._default_side_effect(vendor_content=None)
        result = fetch_android(_ANDROID_CFG, "2.1.0")
        self.assertNotIn(
            "latest_vendor_url", result,
            "latest_vendor_url must not be set when vendor file fetch fails",
        )

    @patch("src.fetchers.maven_latest", return_value="5.4.1")
    @patch("src.fetchers.gh_raw_default")
    def test_latest_vendor_url_contains_vendor_repo(
        self, mock_default, _mock_maven
    ):
        mock_default.side_effect = self._default_side_effect()
        result = fetch_android(_ANDROID_CFG, "2.1.0")
        url = result.get("latest_vendor_url", "")
        self.assertIn(
            _ANDROID_CFG["vendor_repo"], url,
            "latest_vendor_url must reference the vendor_repo from config",
        )

    @patch("src.fetchers.maven_latest", return_value="5.4.1")
    @patch("src.fetchers.gh_raw_default")
    def test_latest_vendor_url_contains_vendor_version_file(
        self, mock_default, _mock_maven
    ):
        mock_default.side_effect = self._default_side_effect()
        result = fetch_android(_ANDROID_CFG, "2.1.0")
        url = result.get("latest_vendor_url", "")
        self.assertIn(
            _ANDROID_CFG["vendor_version_file"], url,
            "latest_vendor_url must reference the vendor_version_file path from config",
        )

    @patch("src.fetchers.maven_latest", return_value="5.4.1")
    @patch("src.fetchers.gh_raw_default")
    def test_default_branch_url_uses_default_branch_not_version_tag(
        self, mock_default, _mock_maven
    ):
        """When version is found on default branch, URL must use main/master."""
        mock_default.side_effect = self._default_side_effect()
        result = fetch_android(_ANDROID_CFG, "2.1.0")
        url = result.get("latest_vendor_url", "")
        self.assertTrue(
            _uses_default_branch(url),
            f"latest_vendor_url must use main or master branch, got: {url}",
        )
        self.assertFalse(
            _uses_version_tag(url),
            f"latest_vendor_url must not embed a semver tag in the blob path, got: {url}",
        )
        self.assertNotIn("latest_vendor_url_is_tag", result)

    @patch("src.fetchers.maven_latest", return_value="5.4.1")
    @patch("src.fetchers._gh_raw_at_version", return_value=(_VENDOR_BUILD_GRADLE, "v5.4.1"))
    @patch("src.fetchers.gh_raw_default")
    def test_tag_fallback_when_default_branch_is_ahead(
        self, mock_default, _mock_at_ver, _mock_maven
    ):
        """When default branch has moved past the latest published version,
        the tag fallback provides the URL with #L anchor and sets the is_tag flag."""
        mock_default.side_effect = self._default_side_effect(
            vendor_content=_NEWER_VENDOR_BUILD_GRADLE,
        )
        result = fetch_android(_ANDROID_CFG, "2.1.0")
        url = result.get("latest_vendor_url", "")
        self.assertTrue(
            _is_github_blob_with_anchor(url),
            f"latest_vendor_url must have #L anchor from tag fallback, got: {url}",
        )
        self.assertTrue(
            _uses_version_tag(url),
            f"tag fallback URL should contain a version tag, got: {url}",
        )
        self.assertTrue(result.get("latest_vendor_url_is_tag"),
                        "latest_vendor_url_is_tag must be True when tag fallback is used")

    @patch("src.fetchers.maven_latest", return_value="5.4.1")
    @patch("src.fetchers._gh_raw_at_version", return_value=(None, None))
    @patch("src.fetchers.gh_raw_default")
    def test_no_url_when_version_not_found_anywhere(
        self, mock_default, _mock_at_ver, _mock_maven
    ):
        """When neither default branch nor tag has the version, no URL should be set."""
        mock_default.side_effect = self._default_side_effect(
            vendor_content=_NEWER_VENDOR_BUILD_GRADLE,
        )
        result = fetch_android(_ANDROID_CFG, "2.1.0")
        self.assertNotIn("latest_vendor_url", result,
                         "latest_vendor_url must not be set when version is absent everywhere")


# ── iOS ────────────────────────────────────────────────────────────────────────

class TestFetchIosLatestVendorUrl(unittest.TestCase):

    def _default_side_effect(self, vendor_content=_VENDOR_PODSPEC, vendor_ref="main"):
        return [
            (_PODSPEC, "master"),        # podspec_file fetch
            (_PACKAGE_JSON, "master"),   # package_json_file fetch
            (vendor_content, vendor_ref),  # vendor_version_file fetch
        ]

    @patch("src.fetchers.cocoapods_latest", return_value="5.5.3")
    @patch("src.fetchers.gh_raw_default")
    def test_latest_vendor_url_is_github_blob_with_line_anchor(
        self, mock_default, _mock_cocoapods
    ):
        mock_default.side_effect = self._default_side_effect()
        result = fetch_ios(_IOS_CFG)
        url = result.get("latest_vendor_url")
        self.assertIsNotNone(url, "latest_vendor_url must be set when vendor podspec is fetched")
        self.assertTrue(
            _is_github_blob_with_anchor(url),
            f"latest_vendor_url must be a GitHub blob URL with #L anchor, got: {url}",
        )

    @patch("src.fetchers.cocoapods_latest", return_value="5.5.3")
    @patch("src.fetchers.gh_raw_default")
    def test_latest_vendor_url_not_a_registry_url(
        self, mock_default, _mock_cocoapods
    ):
        mock_default.side_effect = self._default_side_effect()
        result = fetch_ios(_IOS_CFG)
        url = result.get("latest_vendor_url", "")
        self.assertNotIn("cocoapods.org", url, "latest_vendor_url must not point to CocoaPods trunk")
        self.assertNotIn("mvnrepository.com", url, "latest_vendor_url must not point to Maven")
        self.assertNotIn("pub.dev", url, "latest_vendor_url must not point to pub.dev")

    @patch("src.fetchers.cocoapods_latest", return_value="5.5.3")
    @patch("src.fetchers.gh_raw_default")
    def test_latest_vendor_url_absent_when_vendor_podspec_not_found(
        self, mock_default, _mock_cocoapods
    ):
        mock_default.side_effect = self._default_side_effect(vendor_content=None)
        result = fetch_ios(_IOS_CFG)
        self.assertNotIn(
            "latest_vendor_url", result,
            "latest_vendor_url must not be set when vendor podspec fetch fails",
        )

    @patch("src.fetchers.cocoapods_latest", return_value="5.5.3")
    @patch("src.fetchers.gh_raw_default")
    def test_default_branch_url_uses_default_branch_not_version_tag(
        self, mock_default, _mock_cocoapods
    ):
        """When version is found on default branch, URL must use main/master."""
        mock_default.side_effect = self._default_side_effect()
        result = fetch_ios(_IOS_CFG)
        url = result.get("latest_vendor_url", "")
        self.assertTrue(
            _uses_default_branch(url),
            f"latest_vendor_url must use main or master branch, got: {url}",
        )
        self.assertFalse(
            _uses_version_tag(url),
            f"latest_vendor_url must not embed a semver tag in the blob path, got: {url}",
        )
        self.assertNotIn("latest_vendor_url_is_tag", result)

    @patch("src.fetchers.cocoapods_latest", return_value="5.5.3")
    @patch("src.fetchers._gh_raw_at_version", return_value=(_VENDOR_PODSPEC, "v5.5.3"))
    @patch("src.fetchers.gh_raw_default")
    def test_tag_fallback_when_default_branch_is_ahead(
        self, mock_default, _mock_at_ver, _mock_cocoapods
    ):
        """When default branch has moved past the latest published version
        (e.g. Firebase main ahead of CocoaPods), the tag fallback provides
        the URL with #L anchor and sets the is_tag flag."""
        mock_default.side_effect = self._default_side_effect(
            vendor_content=_NEWER_VENDOR_PODSPEC,
        )
        result = fetch_ios(_IOS_CFG)
        url = result.get("latest_vendor_url", "")
        self.assertTrue(
            _is_github_blob_with_anchor(url),
            f"latest_vendor_url must have #L anchor from tag fallback, got: {url}",
        )
        self.assertTrue(
            _uses_version_tag(url),
            f"tag fallback URL should contain a version tag, got: {url}",
        )
        self.assertTrue(result.get("latest_vendor_url_is_tag"),
                        "latest_vendor_url_is_tag must be True when tag fallback is used")

    @patch("src.fetchers.cocoapods_latest", return_value="5.5.3")
    @patch("src.fetchers._gh_raw_at_version", return_value=(None, None))
    @patch("src.fetchers.gh_raw_default")
    def test_no_url_when_version_not_found_anywhere(
        self, mock_default, _mock_at_ver, _mock_cocoapods
    ):
        """When neither default branch nor tag has the version, no URL should be set."""
        mock_default.side_effect = self._default_side_effect(
            vendor_content=_NEWER_VENDOR_PODSPEC,
        )
        result = fetch_ios(_IOS_CFG)
        self.assertNotIn("latest_vendor_url", result,
                         "latest_vendor_url must not be set when version is absent everywhere")


if __name__ == "__main__":
    unittest.main()
