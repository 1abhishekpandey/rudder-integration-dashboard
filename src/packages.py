"""Package registry helpers for Maven, npm, pub.dev, CocoaPods, and GitHub releases."""

import re
from typing import Optional

from src.http_client import get_json, get_text


def maven_versions(group: str, artifact: str) -> list[str]:
    url = (f"https://search.maven.org/solrsearch/select"
           f"?q=g:{group}+a:{artifact}&core=gav&rows=50&wt=json")
    d = get_json(url)
    if not d:
        return []
    docs = d.get("response", {}).get("docs", [])
    raw = [doc["v"] for doc in docs if "v" in doc]

    def ver_key(v: str):
        return tuple(int(x) for x in re.split(r'[.\-]', v) if x.isdigit())

    return sorted(set(raw), key=ver_key, reverse=True)


def maven_latest(group: str, artifact: str) -> Optional[str]:
    url = (f"https://search.maven.org/solrsearch/select"
           f"?q=g:{group}+a:{artifact}&rows=1&wt=json")
    d = get_json(url)
    if not d:
        return None
    docs = d.get("response", {}).get("docs", [])
    return docs[0].get("latestVersion") if docs else None


def google_maven_latest(group: str, artifact: str) -> Optional[str]:
    """Fetch latest version from Google's Maven repository (dl.google.com)."""
    group_path = group.replace(".", "/")
    xml = get_text(f"https://dl.google.com/android/maven2/{group_path}/{artifact}/maven-metadata.xml")
    if not xml:
        return None
    m = re.search(r'<latest>([^<]+)</latest>', xml)
    if not m:
        m = re.search(r'<release>([^<]+)</release>', xml)
    return m.group(1).strip() if m else None


def npm_latest(package: str) -> Optional[str]:
    enc = package.replace("@", "%40").replace("/", "%2F")
    d = get_json(f"https://registry.npmjs.org/{enc}/latest")
    return d.get("version") if d else None


def pubdev_latest(package: str) -> Optional[str]:
    d = get_json(f"https://pub.dev/api/packages/{package}")
    return d.get("latest", {}).get("version") if d else None


def cocoapods_latest(pod: str) -> Optional[str]:
    d = get_json(f"https://trunk.cocoapods.org/api/v1/pods/{pod}/versions")
    if not d or not isinstance(d, list):
        return None
    names = [v.get("name", "") for v in d if v.get("name")]
    if not names:
        return None

    def ver_key(v: str):
        return tuple(int(x) for x in re.split(r'[.\-]', v) if x.isdigit())

    return max(names, key=ver_key)


def github_release_latest(repo: str) -> Optional[str]:
    """Get latest release tag from a GitHub repo (for SDKs not on CocoaPods trunk)."""
    d = get_json(f"https://api.github.com/repos/{repo}/releases/latest")
    if not d or not isinstance(d, dict):
        return None
    tag = d.get("tag_name", "")
    return tag.lstrip("v") if tag else None


def github_release_url(repo: str) -> Optional[str]:
    """Get the GitHub releases URL for the latest release of a repo."""
    d = get_json(f"https://api.github.com/repos/{repo}/releases/latest")
    if not d or not isinstance(d, dict):
        return None
    tag = d.get("tag_name")
    return f"https://github.com/{repo}/releases/tag/{tag}" if tag else None
