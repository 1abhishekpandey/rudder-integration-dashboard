import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import hashlib
import unittest
from src.url_builders import blob_url, cocoapods_specs_url, mvnrepository_url


class TestBlobUrl(unittest.TestCase):
    def test_basic_url(self):
        result = blob_url(
            "rudderlabs/rudder-integration-braze-android",
            "master",
            "build.gradle",
        )
        self.assertEqual(
            result,
            "https://github.com/rudderlabs/rudder-integration-braze-android/blob/master/build.gradle",
        )

    def test_no_line_anchor_in_result(self):
        result = blob_url("owner/repo", "main", "src/file.py")
        self.assertNotIn("#L", result)

    def test_nested_path(self):
        result = blob_url("org/repo", "develop", "src/main/build.gradle")
        self.assertEqual(
            result,
            "https://github.com/org/repo/blob/develop/src/main/build.gradle",
        )

    def test_line_anchor_appended_externally(self):
        base = blob_url("owner/repo", "master", "file.txt")
        with_anchor = f"{base}#L42"
        self.assertTrue(with_anchor.endswith("#L42"))


class TestCocoapodsSpecsUrl(unittest.TestCase):
    def _expected_shard(self, pod: str) -> tuple:
        digest = hashlib.md5(pod.encode()).hexdigest()
        return digest[0], digest[1], digest[2]

    def test_rudder_braze_url(self):
        pod = "Rudder-Braze"
        version = "4.3.0"
        result = cocoapods_specs_url(pod, version)
        d = hashlib.md5(pod.encode()).hexdigest()
        expected = (
            f"https://github.com/CocoaPods/Specs/blob/master/Specs"
            f"/{d[0]}/{d[1]}/{d[2]}/{pod}/{version}/{pod}.podspec.json"
        )
        self.assertEqual(result, expected)

    def test_shard_uses_first_three_hex_chars(self):
        pod = "Rudder-Braze"
        version = "4.3.0"
        result = cocoapods_specs_url(pod, version)
        d = hashlib.md5(pod.encode()).hexdigest()
        # The URL should contain /Specs/{d[0]}/{d[1]}/{d[2]}/
        shard_path = f"/Specs/{d[0]}/{d[1]}/{d[2]}/"
        self.assertIn(shard_path, result)

    def test_url_contains_pod_and_version(self):
        pod = "SomePod"
        version = "1.0.0"
        result = cocoapods_specs_url(pod, version)
        self.assertIn(pod, result)
        self.assertIn(version, result)
        self.assertTrue(result.endswith(f"{pod}.podspec.json"))

    def test_different_pods_produce_different_shards(self):
        url1 = cocoapods_specs_url("PodA", "1.0.0")
        url2 = cocoapods_specs_url("PodB", "1.0.0")
        # Strip out the common prefix to compare shard segments
        prefix = "https://github.com/CocoaPods/Specs/blob/master/Specs/"
        shard1 = url1[len(prefix):].split("/")[:3]
        shard2 = url2[len(prefix):].split("/")[:3]
        d1 = hashlib.md5(b"PodA").hexdigest()
        d2 = hashlib.md5(b"PodB").hexdigest()
        self.assertEqual(shard1, [d1[0], d1[1], d1[2]])
        self.assertEqual(shard2, [d2[0], d2[1], d2[2]])


class TestMvnrepositoryUrl(unittest.TestCase):
    def test_braze_url(self):
        result = mvnrepository_url(
            "com.rudderstack.android.integration", "braze", "2.1.1"
        )
        self.assertEqual(
            result,
            "https://mvnrepository.com/artifact/com.rudderstack.android.integration/braze/2.1.1",
        )

    def test_generic_url(self):
        result = mvnrepository_url("com.example", "my-lib", "3.0.0")
        self.assertEqual(
            result,
            "https://mvnrepository.com/artifact/com.example/my-lib/3.0.0",
        )

    def test_url_structure(self):
        result = mvnrepository_url("org.example", "artifact", "1.0")
        self.assertTrue(result.startswith("https://mvnrepository.com/artifact/"))
        self.assertTrue(result.endswith("/1.0"))


if __name__ == "__main__":
    unittest.main()
