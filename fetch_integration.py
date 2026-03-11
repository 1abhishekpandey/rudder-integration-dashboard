#!/usr/bin/env python3
"""
RudderStack Integration Version Explorer

Usage:
    ./fetch_integration.py [integration]          # e.g. ./fetch_integration.py braze
    ./fetch_integration.py                        # interactive selection

Requires: Python 3.9+, curl-accessible internet (no third-party packages needed).

Set GITHUB_TOKEN env var to raise the GitHub API rate limit from 60 to 5000 req/hr.
"""

import sys, os, json, re, urllib.request, urllib.error, datetime, hashlib
from typing import Optional, Union, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Terminal helpers ───────────────────────────────────────────────────────────

# Detect terminals that render OSC 8 hyperlinks as clickable text.
# In unsupported terminals we print the URL in parentheses instead.
_TERM = os.environ.get("TERM_PROGRAM", "")
_SUPPORTS_HYPERLINKS = (
    _TERM in ("iTerm.app", "WezTerm", "Hyper")
    or os.environ.get("KITTY_WINDOW_ID") is not None
    or os.environ.get("VTE_VERSION") is not None       # GNOME Terminal / Tilix
    or os.environ.get("WT_SESSION") is not None        # Windows Terminal
)

def link(text: str, url: str) -> str:
    """Render a hyperlink.

    - Terminals that support OSC 8: clickable underlined text.
    - Other terminals: plain text followed by the URL in dim parentheses.
    """
    if _SUPPORTS_HYPERLINKS:
        return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"
    return f"{text} {dim(f'({url})')}"

def bold(s: str) -> str: return f"\033[1m{s}\033[0m"
def dim(s: str)  -> str: return f"\033[2m{s}\033[0m"

def status_icon(vendor_range: Optional[str], latest: Optional[str]) -> str:
    """Colour-code latest vendor version against the declared version range."""
    if not vendor_range or not latest:
        return "⚪"
    if vendor_range == latest:
        return "🟢"
    # Pessimistic operator ~> (CocoaPods): ~> 13.3 means >= 13.3, < 14.0
    m = re.match(r'~>\s*(\d+)\.(\d+)', vendor_range)
    if m:
        major, minor = int(m.group(1)), int(m.group(2))
        parts = [int(x) for x in re.split(r'[.\-]', latest) if x.isdigit()]
        if not parts:
            return "⚪"
        if parts[0] != major:
            return "🔴"
        return "🟢" if len(parts) < 2 or parts[1] >= minor else "⚪"
    # Maven range: [x, y) or [x, y]
    m = re.match(r'([\[(])([^,]+),\s*([^)\]]+)([\])])', vendor_range)
    if m:
        lower_inc, lower_s, upper_s, upper_inc = m.group(1), m.group(2).strip(), m.group(3).strip(), m.group(4)
        try:
            to_tuple = lambda v: tuple(int(x) for x in re.split(r'[.\-]', v) if x.isdigit())
            lower, upper, lv = to_tuple(lower_s), to_tuple(upper_s), to_tuple(latest)
            ok_lower = lv >= lower if lower_inc == "[" else lv > lower
            ok_upper = lv <= upper if upper_inc == "]" else lv < upper
            return "🟢" if (ok_lower and ok_upper) else "🔴"
        except (ValueError, TypeError):
            pass
    return "🔴"

# ── HTTP ───────────────────────────────────────────────────────────────────────

_GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

def _headers(is_github: bool = False) -> dict:
    h = {"User-Agent": "rudder-integration-explorer/1.0"}
    if is_github and _GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {_GITHUB_TOKEN}"
    return h

def get_json(url: str) -> Optional[Any]:
    is_gh = "api.github.com" in url or "raw.githubusercontent.com" in url
    try:
        req = urllib.request.Request(url, headers=_headers(is_gh))
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception:
        return None

def get_text(url: str) -> Optional[str]:
    is_gh = "raw.githubusercontent.com" in url
    try:
        req = urllib.request.Request(url, headers=_headers(is_gh))
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode(errors="replace")
    except Exception:
        return None

# ── Package registry helpers ───────────────────────────────────────────────────

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

# ── GitHub helpers ─────────────────────────────────────────────────────────────

def blob_url(repo: str, ref: str, path: str) -> str:
    return f"https://github.com/{repo}/blob/{ref}/{path}"

def cocoapods_specs_url(pod: str, version: str) -> str:
    """Build the CocoaPods/Specs GitHub URL for a given pod and version.
    The shard path is the first 3 hex chars of the MD5 hash of the pod name."""
    digest = hashlib.md5(pod.encode()).hexdigest()
    return (
        f"https://github.com/CocoaPods/Specs/blob/master/Specs"
        f"/{digest[0]}/{digest[1]}/{digest[2]}/{pod}/{version}/{pod}.podspec.json"
    )

def mvnrepository_url(group: str, artifact: str, version: str) -> str:
    return f"https://mvnrepository.com/artifact/{group}/{artifact}/{version}"

def gh_raw(repo: str, ref: str, path: str) -> Optional[str]:
    return get_text(f"https://raw.githubusercontent.com/{repo}/{ref}/{path}")

def gh_raw_at_version(repo: str, version: str, path: str) -> tuple[Optional[str], str]:
    """Fetch a file at the tag matching a version (tries v{version} then {version}).
    Falls back to the default branch. Returns (content, ref_used)."""
    for ref in (f"v{version}", version):
        content = gh_raw(repo, ref, path)
        if content:
            return content, ref
    return gh_raw_default(repo, path)

def gh_raw_default(repo: str, path: str) -> tuple[Optional[str], str]:
    """Fetch a file from the default branch (tries main then master).
    Returns (content, ref_used)."""
    for ref in ("main", "master"):
        content = gh_raw(repo, ref, path)
        if content:
            return content, ref
    return None, "main"

# ── Build-file parsers ─────────────────────────────────────────────────────────

def _resolve_ruby(content: str, value: str) -> str:
    """Expand #{var} Ruby interpolation using definitions found in content."""
    def _sub(m: re.Match) -> str:
        var = m.group(1)
        vm = re.search(rf"""{re.escape(var)}\s*=\s*['"]([^'"]+)['"]""", content)
        return vm.group(1) if vm else m.group(0)
    return re.sub(r'#\{(\w+)\}', _sub, value)

def find_line(content: str, pattern: str) -> Optional[int]:
    """Return the 1-based line number of the first line matching the regex pattern."""
    for i, line in enumerate(content.splitlines(), 1):
        if re.search(pattern, line):
            return i
    return None

def find_version_value_line(content: str, version_str: str) -> Optional[int]:
    """Find the line where the version digits first appear — useful when a version
    is declared in a variable and only referenced in the dependency declaration."""
    numbers = re.findall(r'\d+\.\d+(?:\.\d+)*', version_str)
    if not numbers:
        return None
    return find_line(content, re.escape(numbers[0]))

def gradle_dep(content: str, group: str, artifact: str) -> Optional[str]:
    """Extract version/range for group:artifact from a Gradle file."""
    coord = rf"""{re.escape(group)}:{re.escape(artifact)}:"""
    # Maven range: [1.0,2.0) or (1.0,2.0] — contains ) which plain char class misses
    m = re.search(rf"""['"]?{coord}([\[(][^'"]+[\])])['"]?""", content)
    if m:
        return m.group(1).strip()
    # Variable reference: $var or ${var} — must be checked before plain version
    # to avoid returning the raw "${ ... }" string
    m2 = re.search(rf"""['"]?{coord}\$\{{?(\w+)\}}?['"]?""", content)
    if m2:
        var = m2.group(1)
        # Groovy: def brazeVersion = "x"  /  ext block: brazeVersion = "x"
        # Kotlin: val brazeVersion = "x"
        vm = re.search(rf"""(?:val\s+|def\s+|var\s+)?{re.escape(var)}\s*=\s*['"]([^'"]+)['"]""", content)
        if vm:
            return vm.group(1).strip()
    # Plain version: "group:artifact:1.2.3"  (exclude $ to avoid matching variable refs)
    m = re.search(rf"""['"]?{coord}([^'"()\s$]+)['"]?""", content)
    if m:
        return m.group(1).strip()
    return None

def podspec_dep(content: str, pod: str) -> Optional[str]:
    """Extract version constraint for a pod from a .podspec file."""
    # Direct: s.dependency 'Pod', '~> 1.0'
    m = re.search(
        rf"""dependency\s+['"]?{re.escape(pod)}['"]?\s*,\s*['"]([^'"]+)['"]""",
        content
    )
    if m:
        return _resolve_ruby(content, m.group(1).strip())
    # Variable: pod_ver = '~> 1.0'  /  s.dependency 'Pod', pod_ver
    m2 = re.search(rf"""dependency\s+['"]?{re.escape(pod)}['"]?\s*,\s*(\w+)""", content)
    if m2:
        var = m2.group(1)
        vm = re.search(rf"""{re.escape(var)}\s*=\s*['"]([^'"]+)['"]""", content)
        if vm:
            return _resolve_ruby(content, vm.group(1).strip())
    return None

def podspec_version(content: str) -> Optional[str]:
    # s.version = '4.3.0'  or  spec.version = "4.3.0"
    m = re.search(r"""\w+\.version\s*=\s*['"]([^'"]+)['"]""", content)
    return m.group(1).strip() if m else None

# ── Integration registry ───────────────────────────────────────────────────────

REGISTRY: dict = {
    "braze": {
        "display_name": "Braze",
        "android": {
            "repo":                  "rudderlabs/rudder-integration-braze-android",
            "maven_group":           "com.rudderstack.android.integration",
            "maven_artifact":        "braze",
            "build_file":            "braze/build.gradle",
            "vendor_group":          "com.braze",
            "vendor_artifact":       "android-sdk-ui",
            "vendor_repo":           "braze-inc/braze-android-sdk",
            "vendor_version_file":   "build.gradle",
        },
        "ios": {
            "repo":                  "rudderlabs/rudder-integration-braze-ios",
            "pod":                   "Rudder-Braze",
            "podspec_file":          "Rudder-Braze.podspec",
            "package_json_file":     "package.json",
            "vendor_pod":            "BrazeKit",
            "vendor_gh_repo":        "braze-inc/braze-swift-sdk",
            "vendor_version_file":   "BrazeKit.podspec",
        },
        "rn": {
            "rudder_repo":                  "rudderlabs/rudder-sdk-react-native",
            "rudder_pkg":                   "@rudderstack/rudder-integration-braze-react-native",
            "rudder_android_file":          "libs/rudder-integration-braze-react-native/android/build.gradle",
            "rudder_ios_file":              "libs/rudder-integration-braze-react-native/rudder-integration-braze-react-native.podspec",
            "rudder_android_dep_group":     "com.rudderstack.android.integration",
            "rudder_android_dep_artifact":  "braze",
            "rudder_ios_dep_pod":           "Rudder-Braze",
            "vendor_pkg":                   "@braze/react-native-sdk",
            "vendor_repo":                  "braze-inc/braze-react-native-sdk",
            "vendor_android_file":          "android/build.gradle",
            "vendor_ios_file":              "braze-react-native-sdk.podspec",
            "vendor_android_dep_group":     "com.braze",
            "vendor_android_dep_artifact":  "android-sdk-ui",
            "vendor_ios_dep_pod":           "BrazeKit",
        },
        "flutter": {
            "rudder_repo":                  "rudderlabs/rudder-sdk-flutter",
            "rudder_pkg":                   "rudder_integration_braze_flutter",
            "rudder_android_file":          "packages/integrations/rudder_integration_braze_flutter/android/build.gradle",
            "rudder_ios_file":              "packages/integrations/rudder_integration_braze_flutter/ios/rudder_integration_braze_flutter.podspec",
            "rudder_android_dep_group":     "com.rudderstack.android.integration",
            "rudder_android_dep_artifact":  "braze",
            "rudder_ios_dep_pod":           "Rudder-Braze",
            "vendor_pkg":                   "braze_plugin",
            "vendor_repo":                  "braze-inc/braze-flutter-sdk",
            "vendor_android_file":          "android/build.gradle",
            "vendor_ios_file":              "ios/braze_plugin.podspec",
            "vendor_android_dep_group":     "com.braze",
            "vendor_android_dep_artifact":  "android-sdk-ui",
            "vendor_ios_dep_pod":           "BrazeKit",
        },
    }
}

# ── Data fetch functions ───────────────────────────────────────────────────────

def fetch_android(cfg: dict, version: str) -> dict:
    repo = cfg["repo"]
    out: dict = {
        "repo":     repo,
        "version":  version,
        "repo_url": f"https://github.com/{repo}",
    }
    content, ref = gh_raw_default(repo, cfg["build_file"])
    if content:
        vendor_range          = gradle_dep(content, cfg["vendor_group"], cfg["vendor_artifact"])
        out["vendor_range"]   = vendor_range
        base                  = blob_url(repo, ref, cfg["build_file"])
        line                  = find_version_value_line(content, vendor_range) if vendor_range else None
        out["build_file_url"] = base + (f"#L{line}" if line else "")
    pkg, ref_pkg = gh_raw_default(repo, "package.json")
    if pkg:
        try:
            pkg_version    = json.loads(pkg).get("version") or version
            out["version"] = pkg_version
            out["maven_url"] = mvnrepository_url(cfg["maven_group"], cfg["maven_artifact"], pkg_version)
        except Exception:
            pass
        out["version_url"] = blob_url(repo, ref_pkg, "package.json") + "#L2"
    latest = maven_latest(cfg["vendor_group"], cfg["vendor_artifact"])
    out["latest_vendor"] = latest
    if latest and cfg.get("vendor_repo") and cfg.get("vendor_version_file"):
        vc, ref_vc = gh_raw_at_version(cfg["vendor_repo"], latest, cfg["vendor_version_file"])
        if vc:
            line = find_version_value_line(vc, latest)
            if line:
                out["latest_vendor_url"] = blob_url(cfg["vendor_repo"], ref_vc, cfg["vendor_version_file"]) + f"#L{line}"
    return out

def fetch_ios(cfg: dict) -> dict:
    repo = cfg["repo"]
    out: dict = {"repo": repo, "repo_url": f"https://github.com/{repo}"}
    content, ref = gh_raw_default(repo, cfg["podspec_file"])
    if content:
        # Some podspecs load version from package.json at runtime — try that first
        version = None
        if cfg.get("package_json_file"):
            pkg, ref_pkg = gh_raw_default(repo, cfg["package_json_file"])
            if pkg:
                try:
                    version = json.loads(pkg).get("version")
                except Exception:
                    pass
                out["version_url"] = blob_url(repo, ref_pkg, cfg["package_json_file"]) + "#L2"
        ios_version         = version or podspec_version(content)
        out["version"]      = ios_version
        vendor_range        = podspec_dep(content, cfg["vendor_pod"])
        out["vendor_range"] = vendor_range
        base                = blob_url(repo, ref, cfg["podspec_file"])
        line                = find_version_value_line(content, vendor_range) if vendor_range else None
        out["podspec_url"]  = base + (f"#L{line}" if line else "")
        if ios_version:
            out["cocoapods_specs_url"] = cocoapods_specs_url(cfg["pod"], ios_version)
    # Try CocoaPods trunk first; fall back to GitHub releases
    latest = cocoapods_latest(cfg["vendor_pod"])
    if not latest and cfg.get("vendor_gh_repo"):
        latest = github_release_latest(cfg["vendor_gh_repo"])
    out["latest_vendor"] = latest
    if latest and cfg.get("vendor_gh_repo") and cfg.get("vendor_version_file"):
        vc, ref_vc = gh_raw_at_version(cfg["vendor_gh_repo"], latest, cfg["vendor_version_file"])
        if vc:
            line = find_version_value_line(vc, latest)
            if line:
                out["latest_vendor_url"] = blob_url(cfg["vendor_gh_repo"], ref_vc, cfg["vendor_version_file"]) + f"#L{line}"
    return out

def fetch_rn(cfg: dict) -> dict:
    out: dict = {}

    rudder_repo = cfg["rudder_repo"]
    out["rudder_repo_url"] = f"https://github.com/{rudder_repo}"
    out["rudder_npm_url"]  = f"https://www.npmjs.com/package/{cfg['rudder_pkg']}"

    # Read version from package.json inside the monorepo
    pkg_json_path = "/".join(cfg["rudder_android_file"].split("/")[:-2]) + "/package.json"
    pkg, ref_pkg = gh_raw_default(rudder_repo, pkg_json_path)
    if pkg:
        try:
            rudder_version = json.loads(pkg).get("version")
            out["rudder_version"]         = rudder_version
            out["rudder_pkg_json_url"]    = blob_url(rudder_repo, ref_pkg, pkg_json_path) + "#L4"
            if rudder_version:
                out["rudder_npm_version_url"] = f"https://www.npmjs.com/package/{cfg['rudder_pkg']}/v/{rudder_version}"
        except Exception:
            pass
    if "rudder_version" not in out:
        out["rudder_version"] = npm_latest(cfg["rudder_pkg"])

    ac, ref_ac = gh_raw_default(rudder_repo, cfg["rudder_android_file"])
    if ac:
        out["rudder_android_range"] = gradle_dep(ac, cfg["rudder_android_dep_group"], cfg["rudder_android_dep_artifact"])
        base = blob_url(rudder_repo, ref_ac, cfg["rudder_android_file"])
        line = find_line(ac, rf"{re.escape(cfg['rudder_android_dep_group'])}:{re.escape(cfg['rudder_android_dep_artifact'])}")
        out["rudder_android_url"] = base + (f"#L{line}" if line else "")
    ic, ref_ic = gh_raw_default(rudder_repo, cfg["rudder_ios_file"])
    if ic:
        out["rudder_ios_range"] = podspec_dep(ic, cfg["rudder_ios_dep_pod"])
        base = blob_url(rudder_repo, ref_ic, cfg["rudder_ios_file"])
        line = find_line(ic, rf"dependency\s+['\"]?{re.escape(cfg['rudder_ios_dep_pod'])}")
        out["rudder_ios_url"] = base + (f"#L{line}" if line else "")

    vendor_repo = cfg["vendor_repo"]
    out["vendor_repo_url"] = f"https://github.com/{vendor_repo}"
    out["vendor_npm_url"]  = f"https://www.npmjs.com/package/{cfg['vendor_pkg']}"

    # Read vendor version from package.json so the link points to the source file
    vpkg, ref_vpkg = gh_raw_default(vendor_repo, "package.json")
    if vpkg:
        try:
            vendor_version = json.loads(vpkg).get("version")
            out["vendor_version"]         = vendor_version
            out["vendor_pkg_json_url"]    = blob_url(vendor_repo, ref_vpkg, "package.json") + "#L3"
            if vendor_version:
                out["vendor_npm_version_url"] = f"https://www.npmjs.com/package/{cfg['vendor_pkg']}/v/{vendor_version}"
        except Exception:
            pass
    if "vendor_version" not in out:
        out["vendor_version"] = npm_latest(cfg["vendor_pkg"])

    vac, ref_vac = gh_raw_default(vendor_repo, cfg["vendor_android_file"])
    if vac:
        vendor_android_range = gradle_dep(vac, cfg["vendor_android_dep_group"], cfg["vendor_android_dep_artifact"])
        out["vendor_android_range"] = vendor_android_range
        base = blob_url(vendor_repo, ref_vac, cfg["vendor_android_file"])
        line = find_version_value_line(vac, vendor_android_range) if vendor_android_range else None
        out["vendor_android_url"] = base + (f"#L{line}" if line else "")
    vic, ref_vic = gh_raw_default(vendor_repo, cfg["vendor_ios_file"])
    if vic:
        vendor_ios_range = podspec_dep(vic, cfg["vendor_ios_dep_pod"])
        out["vendor_ios_range"] = vendor_ios_range
        base = blob_url(vendor_repo, ref_vic, cfg["vendor_ios_file"])
        line = find_version_value_line(vic, vendor_ios_range) if vendor_ios_range else None
        out["vendor_ios_url"] = base + (f"#L{line}" if line else "")
    return out

def fetch_flutter(cfg: dict) -> dict:
    out: dict = {}
    out["rudder_pub_url"] = f"https://pub.dev/packages/{cfg['rudder_pkg']}"

    rudder_repo = cfg["rudder_repo"]
    out["rudder_repo_url"] = f"https://github.com/{rudder_repo}"

    # Read version from pubspec.yaml inside the monorepo
    pubspec_path = "/".join(cfg["rudder_android_file"].split("/")[:-2]) + "/pubspec.yaml"
    pubspec, ref_pubspec = gh_raw_default(rudder_repo, pubspec_path)
    if pubspec:
        m = re.search(r'^version:\s*(\S+)', pubspec, re.MULTILINE)
        if m:
            rudder_version = m.group(1)
            out["rudder_version"] = rudder_version
            line = find_line(pubspec, r'^version:')
            out["rudder_pubspec_url"] = blob_url(rudder_repo, ref_pubspec, pubspec_path) + (f"#L{line}" if line else "")
            out["rudder_pub_version_url"] = f"https://pub.dev/packages/{cfg['rudder_pkg']}/versions/{rudder_version}"
    if "rudder_version" not in out:
        out["rudder_version"] = pubdev_latest(cfg["rudder_pkg"])

    ac, ref_ac = gh_raw_default(rudder_repo, cfg["rudder_android_file"])
    if ac:
        rudder_android_range = gradle_dep(ac, cfg["rudder_android_dep_group"], cfg["rudder_android_dep_artifact"])
        out["rudder_android_range"] = rudder_android_range
        base = blob_url(rudder_repo, ref_ac, cfg["rudder_android_file"])
        line = find_line(ac, rf"{re.escape(cfg['rudder_android_dep_group'])}:{re.escape(cfg['rudder_android_dep_artifact'])}")
        out["rudder_android_url"] = base + (f"#L{line}" if line else "")
    ic, ref_ic = gh_raw_default(rudder_repo, cfg["rudder_ios_file"])
    if ic:
        rudder_ios_range = podspec_dep(ic, cfg["rudder_ios_dep_pod"])
        out["rudder_ios_range"] = rudder_ios_range
        base = blob_url(rudder_repo, ref_ic, cfg["rudder_ios_file"])
        line = find_line(ic, rf"dependency\s+['\"]?{re.escape(cfg['rudder_ios_dep_pod'])}")
        out["rudder_ios_url"] = base + (f"#L{line}" if line else "")

    vendor_repo = cfg["vendor_repo"]
    out["vendor_repo_url"] = f"https://github.com/{vendor_repo}"
    out["vendor_pub_url"] = f"https://pub.dev/packages/{cfg['vendor_pkg']}"

    # Read vendor version from pubspec.yaml (root of vendor repo)
    vendor_pubspec_path_parts = "/".join(cfg["vendor_android_file"].split("/")[:-2]).strip("/")
    vendor_pubspec_path = (vendor_pubspec_path_parts + "/pubspec.yaml") if vendor_pubspec_path_parts else "pubspec.yaml"
    vpubspec, ref_vpubspec = gh_raw_default(vendor_repo, vendor_pubspec_path)
    if vpubspec:
        m = re.search(r'^version:\s*(\S+)', vpubspec, re.MULTILINE)
        if m:
            vendor_version = m.group(1)
            out["vendor_version"] = vendor_version
            line = find_line(vpubspec, r'^version:')
            out["vendor_pubspec_url"] = blob_url(vendor_repo, ref_vpubspec, vendor_pubspec_path) + (f"#L{line}" if line else "")
            out["vendor_pub_version_url"] = f"https://pub.dev/packages/{cfg['vendor_pkg']}/versions/{vendor_version}"
    if "vendor_version" not in out:
        out["vendor_version"] = pubdev_latest(cfg["vendor_pkg"])

    vac, ref_vac = gh_raw_default(vendor_repo, cfg["vendor_android_file"])
    if vac:
        vendor_android_range = gradle_dep(vac, cfg["vendor_android_dep_group"], cfg["vendor_android_dep_artifact"])
        out["vendor_android_range"] = vendor_android_range
        base = blob_url(vendor_repo, ref_vac, cfg["vendor_android_file"])
        line = find_version_value_line(vac, vendor_android_range) if vendor_android_range else None
        out["vendor_android_url"] = base + (f"#L{line}" if line else "")
    vic, ref_vic = gh_raw_default(vendor_repo, cfg["vendor_ios_file"])
    if vic:
        vendor_ios_range = podspec_dep(vic, cfg["vendor_ios_dep_pod"])
        out["vendor_ios_range"] = vendor_ios_range
        base = blob_url(vendor_repo, ref_vic, cfg["vendor_ios_file"])
        line = find_version_value_line(vic, vendor_ios_range) if vendor_ios_range else None
        out["vendor_ios_url"] = base + (f"#L{line}" if line else "")
    return out

# ── Display ────────────────────────────────────────────────────────────────────

_LW = 34  # label column width

def _row(label: str, value: str, url: Optional[str] = None) -> None:
    val = link(value, url) if (url and value and value != "—") else value
    print(f"  {dim(label.ljust(_LW))} {val or dim('—')}")

def _section(title: str) -> None:
    print()
    bar = "─" * (62 - len(title))
    print(f"  {bold(title)}  {dim(bar)}")

def _display_android(d: dict) -> None:
    _section("Native — Android")
    repo_name = d["repo"].split("/")[-1]
    _row("Rudder Integration",         link(repo_name, d["repo_url"]))
    _row("Rudder Integration Version", d["version"],                  d.get("version_url") or d["repo_url"])
    _row("Gradle",                     link("Gradle", d["maven_url"]) if d.get("maven_url") else "—")
    _row("Vendor Version Range",       d.get("vendor_range") or "—",  d.get("build_file_url"))
    latest = d.get("latest_vendor") or "—"
    icon   = status_icon(d.get("vendor_range"), d.get("latest_vendor"))
    _row("Latest Vendor Version",      f"{icon} {latest}", d.get("latest_vendor_url"))

def _display_ios(d: dict) -> None:
    _section("Native — iOS")
    repo_name = d["repo"].split("/")[-1]
    _row("Rudder Integration",         link(repo_name, d["repo_url"]))
    _row("Rudder Integration Version", str(d.get("version") or "—"),  d.get("version_url") or d["repo_url"])
    _row("Podspec",                    link("Podspec", d["cocoapods_specs_url"]) if d.get("cocoapods_specs_url") else "—")
    _row("Vendor Version Range",       d.get("vendor_range") or "—",  d.get("podspec_url"))
    latest = d.get("latest_vendor") or "—"
    icon   = status_icon(d.get("vendor_range"), d.get("latest_vendor"))
    _row("Latest Vendor Version",      f"{icon} {latest}", d.get("latest_vendor_url"))

def _display_rn(d: dict, cfg: dict, android_native_ver: Optional[str], ios_native_ver: Optional[str]) -> None:
    def _icon_range(range_val: Optional[str], native_ver: Optional[str]) -> str:
        icon = status_icon(range_val, native_ver)
        return f"{icon} {range_val}" if range_val else "—"

    _section("React Native")
    _row("Rudder RN Integration SDK",    link(cfg["rudder_pkg"], d["rudder_repo_url"]) if d.get("rudder_repo_url") else cfg["rudder_pkg"])
    _row("npm",                          link("npm", d["rudder_npm_version_url"]) if d.get("rudder_npm_version_url") else link("npm", d.get("rudder_npm_url")) if d.get("rudder_npm_url") else "—")
    _row("Rudder RN Version",            str(d.get("rudder_version") or "—"),                                   d.get("rudder_pkg_json_url"))
    _row("Underlying Android SDK Range", _icon_range(d.get("rudder_android_range"), android_native_ver),        d.get("rudder_android_url"))
    _row("Underlying iOS SDK Range",     _icon_range(d.get("rudder_ios_range"), ios_native_ver),                d.get("rudder_ios_url"))
    _row("Vendor RN SDK",                link(cfg["vendor_pkg"], d["vendor_repo_url"]) if d.get("vendor_repo_url") else cfg["vendor_pkg"])
    _row("npm",                          link("npm", d["vendor_npm_version_url"]) if d.get("vendor_npm_version_url") else link("npm", d.get("vendor_npm_url")) if d.get("vendor_npm_url") else "—")
    _row("Vendor RN Latest Version",     str(d.get("vendor_version") or "—"),                                   d.get("vendor_pkg_json_url"))
    _row("Vendor Underlying Android",    d.get("vendor_android_range") or "—",                                  d.get("vendor_android_url"))
    _row("Vendor Underlying iOS",        d.get("vendor_ios_range") or "—",                                      d.get("vendor_ios_url"))

def _display_flutter(d: dict, cfg: dict, android_native_ver: Optional[str], ios_native_ver: Optional[str]) -> None:
    def _icon_range(range_val: Optional[str], native_ver: Optional[str]) -> str:
        icon = status_icon(range_val, native_ver)
        return f"{icon} {range_val}" if range_val else "—"

    _section("Flutter")
    _row("Rudder Flutter Integration SDK",  cfg["rudder_pkg"],                                                      d.get("rudder_pub_url"))
    _row("Rudder Flutter Version",          str(d.get("rudder_version") or "—"))
    _row("Underlying Android SDK Range",    _icon_range(d.get("rudder_android_range"), android_native_ver),         d.get("rudder_android_url"))
    _row("Underlying iOS SDK Range",        _icon_range(d.get("rudder_ios_range"), ios_native_ver),                 d.get("rudder_ios_url"))
    _row("Vendor Flutter SDK",              cfg["vendor_pkg"],                                                      d.get("vendor_pub_url"))
    _row("Vendor Flutter Latest Version",   str(d.get("vendor_version") or "—"))
    _row("Vendor Underlying Android",       d.get("vendor_android_range") or "—",                                   d.get("vendor_android_url"))
    _row("Vendor Underlying iOS",           d.get("vendor_ios_range") or "—",                                       d.get("vendor_ios_url"))

# ── Interactive prompts ────────────────────────────────────────────────────────

def _pick(prompt: str, options: list[str]) -> str:
    print(f"\n  {bold(prompt)}")
    for i, opt in enumerate(options, 1):
        print(f"  {dim(str(i).rjust(3))}  {opt}")
    while True:
        try:
            raw = input("\n  Enter number: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("  Invalid — try again.")

# ── Markdown generation ────────────────────────────────────────────────────────

def _ml(text: str, url: Optional[str]) -> str:
    """Return a Markdown hyperlink, or plain text when there is no URL."""
    if url and text and text not in ("—", ""):
        label = text.replace("[", "\\[", 1) if text.startswith("[") else text
        return f"[{label}]({url})"
    return text or "—"

def generate_markdown(
    integration: str,
    cfg: dict,
    android_data: dict,
    ios_data: dict,
    rn_data: dict,
    flutter_data: dict,
) -> str:
    today = datetime.date.today().isoformat()
    name  = cfg["display_name"]

    # ── helpers ────────────────────────────────────────────────────────────────
    def native_row(platform: str, repo: str, repo_url: str, version: str,
                   version_url: Optional[str],
                   build_file_label: str, build_file_url: Optional[str],
                   vendor_range: Optional[str], vendor_file_url: Optional[str],
                   latest: Optional[str], latest_url: Optional[str]) -> str:
        icon        = status_icon(vendor_range, latest)
        latest_text = f"{icon} {latest}" if latest else "—"
        return (
            f"| {platform} "
            f"| {_ml(repo.split('/')[-1], repo_url)} "
            f"| {_ml(version, version_url or repo_url)} "
            f"| {_ml(build_file_label, build_file_url)} "
            f"| {_ml(vendor_range or '—', vendor_file_url)} "
            f"| {_ml(latest_text, latest_url)} |"
        )

    def cp_row(rudder_pkg: str, rudder_pkg_url: Optional[str],
               rudder_ver: str,
               rudder_range: Optional[str], rudder_range_url: Optional[str],
               vendor_pkg: str, vendor_pkg_url: Optional[str],
               vendor_ver: str,
               vendor_range: Optional[str], vendor_range_url: Optional[str]) -> str:
        return (
            f"| {_ml(rudder_pkg, rudder_pkg_url)} "
            f"| {rudder_ver} "
            f"| {_ml(rudder_range or '—', rudder_range_url)} "
            f"| {_ml(vendor_pkg, vendor_pkg_url)} "
            f"| {vendor_ver} "
            f"| {_ml(vendor_range or '—', vendor_range_url)} |"
        )

    def _range_cell(range_val: Optional[str], range_url: Optional[str], native_ver: Optional[str]) -> str:
        """Format a Rudder underlying SDK range cell with a status icon."""
        icon = status_icon(range_val, native_ver)
        text = f"{icon} {range_val}" if range_val else "—"
        return _ml(text, range_url)

    def rn_combined_row(
        rudder_pkg: str, rudder_repo_url: Optional[str],
        rudder_npm_ver_url: Optional[str],
        rudder_ver: str, rudder_ver_url: Optional[str],
        rudder_android_range: Optional[str], rudder_android_url: Optional[str],
        rudder_ios_range: Optional[str], rudder_ios_url: Optional[str],
        android_native_ver: Optional[str], ios_native_ver: Optional[str],
        vendor_pkg: str, vendor_repo_url: Optional[str],
        vendor_npm_ver_url: Optional[str],
        vendor_ver: str, vendor_ver_url: Optional[str],
        vendor_android_range: Optional[str], vendor_android_url: Optional[str],
        vendor_ios_range: Optional[str], vendor_ios_url: Optional[str],
    ) -> str:
        return (
            f"| {_ml(rudder_pkg, rudder_repo_url)} "
            f"| {_ml('npm', rudder_npm_ver_url)} "
            f"| {_ml(rudder_ver, rudder_ver_url)} "
            f"| {_range_cell(rudder_android_range, rudder_android_url, android_native_ver)} "
            f"| {_range_cell(rudder_ios_range, rudder_ios_url, ios_native_ver)} "
            f"| {_ml(vendor_pkg, vendor_repo_url)} "
            f"| {_ml('npm', vendor_npm_ver_url)} "
            f"| {_ml(vendor_ver, vendor_ver_url)} "
            f"| {_ml(vendor_android_range or '—', vendor_android_url)} "
            f"| {_ml(vendor_ios_range or '—', vendor_ios_url)} |"
        )

    def flutter_combined_row(
        rudder_pkg: str, rudder_repo_url: Optional[str],
        rudder_pub_ver_url: Optional[str],
        rudder_ver: str, rudder_ver_url: Optional[str],
        rudder_android_range: Optional[str], rudder_android_url: Optional[str],
        rudder_ios_range: Optional[str], rudder_ios_url: Optional[str],
        android_native_ver: Optional[str], ios_native_ver: Optional[str],
        vendor_pkg: str, vendor_repo_url: Optional[str],
        vendor_pub_ver_url: Optional[str],
        vendor_ver: str, vendor_ver_url: Optional[str],
        vendor_android_range: Optional[str], vendor_android_url: Optional[str],
        vendor_ios_range: Optional[str], vendor_ios_url: Optional[str],
    ) -> str:
        return (
            f"| {_ml(rudder_pkg, rudder_repo_url)} "
            f"| {_ml('pub', rudder_pub_ver_url)} "
            f"| {_ml(rudder_ver, rudder_ver_url)} "
            f"| {_range_cell(rudder_android_range, rudder_android_url, android_native_ver)} "
            f"| {_range_cell(rudder_ios_range, rudder_ios_url, ios_native_ver)} "
            f"| {_ml(vendor_pkg, vendor_repo_url)} "
            f"| {_ml('pub', vendor_pub_ver_url)} "
            f"| {_ml(vendor_ver, vendor_ver_url)} "
            f"| {_ml(vendor_android_range or '—', vendor_android_url)} "
            f"| {_ml(vendor_ios_range or '—', vendor_ios_url)} |"
        )

    sep     = "| --- | --- | --- | --- | --- | --- |"
    rn_sep  = "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    fl_sep  = "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"

    # ── Native Integration ─────────────────────────────────────────────────────
    android_row = native_row(
        "Android",
        android_data["repo"], android_data["repo_url"],
        android_data["version"],
        android_data.get("version_url"),
        "Gradle", android_data.get("maven_url"),
        android_data.get("vendor_range"), android_data.get("build_file_url"),
        android_data.get("latest_vendor"), android_data.get("latest_vendor_url"),
    )
    ios_row = native_row(
        "iOS",
        ios_data["repo"], ios_data["repo_url"],
        str(ios_data.get("version") or "—"),
        ios_data.get("version_url"),
        "Podspec", ios_data.get("cocoapods_specs_url"),
        ios_data.get("vendor_range"), ios_data.get("podspec_url"),
        ios_data.get("latest_vendor"), ios_data.get("latest_vendor_url"),
    )

    # ── RN ─────────────────────────────────────────────────────────────────────
    rn_pkg            = cfg["rn"]["rudder_pkg"]
    rn_repo_url       = rn_data.get("rudder_repo_url")
    rn_npm_ver_url    = rn_data.get("rudder_npm_version_url")
    rn_ver            = str(rn_data.get("rudder_version") or "—")
    rn_ver_url        = rn_data.get("rudder_pkg_json_url")
    vendor_rn_pkg     = cfg["rn"]["vendor_pkg"]
    vendor_rn_repo_url = rn_data.get("vendor_repo_url")
    vendor_rn_npm_url = rn_data.get("vendor_npm_version_url")
    vendor_rn_ver     = str(rn_data.get("vendor_version") or "—")

    vendor_rn_ver_url = rn_data.get("vendor_pkg_json_url")

    rn_combined = rn_combined_row(
        rn_pkg, rn_repo_url, rn_npm_ver_url, rn_ver, rn_ver_url,
        rn_data.get("rudder_android_range"), rn_data.get("rudder_android_url"),
        rn_data.get("rudder_ios_range"), rn_data.get("rudder_ios_url"),
        android_data["version"], str(ios_data.get("version") or None),
        vendor_rn_pkg, vendor_rn_repo_url, vendor_rn_npm_url, vendor_rn_ver, vendor_rn_ver_url,
        rn_data.get("vendor_android_range"), rn_data.get("vendor_android_url"),
        rn_data.get("vendor_ios_range"), rn_data.get("vendor_ios_url"),
    )

    # ── Flutter ────────────────────────────────────────────────────────────────
    fl_pkg                = cfg["flutter"]["rudder_pkg"]
    fl_repo_url           = flutter_data.get("rudder_repo_url")
    fl_pub_ver_url        = flutter_data.get("rudder_pub_version_url")
    fl_ver                = str(flutter_data.get("rudder_version") or "—")
    fl_ver_url            = flutter_data.get("rudder_pubspec_url")
    vendor_fl_pkg         = cfg["flutter"]["vendor_pkg"]
    vendor_fl_repo_url    = flutter_data.get("vendor_repo_url")
    vendor_fl_pub_ver_url = flutter_data.get("vendor_pub_version_url")
    vendor_fl_ver         = str(flutter_data.get("vendor_version") or "—")
    vendor_fl_ver_url     = flutter_data.get("vendor_pubspec_url")

    fl_combined = flutter_combined_row(
        fl_pkg, fl_repo_url, fl_pub_ver_url, fl_ver, fl_ver_url,
        flutter_data.get("rudder_android_range"), flutter_data.get("rudder_android_url"),
        flutter_data.get("rudder_ios_range"), flutter_data.get("rudder_ios_url"),
        android_data["version"], str(ios_data.get("version") or None),
        vendor_fl_pkg, vendor_fl_repo_url, vendor_fl_pub_ver_url, vendor_fl_ver, vendor_fl_ver_url,
        flutter_data.get("vendor_android_range"), flutter_data.get("vendor_android_url"),
        flutter_data.get("vendor_ios_range"), flutter_data.get("vendor_ios_url"),
    )

    native_header = "| Platform | Rudder Integration | Rudder Integration Version | Build File | Vendor Version Range | Latest Vendor Version |"
    native_sep    = "| --- | --- | --- | --- | --- | --- |"
    rn_header = (
        "| Rudder RN Integration SDK | npm | Version "
        "| Underlying Android SDK Range | Underlying iOS SDK Range "
        "| Vendor RN SDK | npm | Version "
        "| Vendor Underlying Android SDK Range | Vendor Underlying iOS SDK Range |"
    )
    fl_header = (
        "| Rudder Flutter Integration SDK | pub | Version "
        "| Underlying Android SDK Range | Underlying iOS SDK Range "
        "| Vendor Flutter SDK | pub | Version "
        "| Vendor Underlying Android SDK Range | Vendor Underlying iOS SDK Range |"
    )

    sections = [
        f"{name} — Legacy SDK Research",
        "",
        f"Data collected: {today}",
        "",
        "# Native Integration",
        "",
        native_header,
        native_sep,
        android_row,
        ios_row,
        "",
        "---",
        "",
        "# React Native SDK",
        "",
        rn_header,
        rn_sep,
        rn_combined,
        "",
        "---",
        "",
        "# Flutter SDK",
        "",
        fl_header,
        fl_sep,
        fl_combined,
        "",
    ]
    return "\n".join(sections)

def write_markdown(integration: str, content: str) -> str:
    """Write markdown content to {INTEGRATION}_LEGACY.md next to this script."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, f"{integration.upper()}_LEGACY.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path

# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    # 1. Select integration
    names = list(REGISTRY.keys())
    if len(sys.argv) > 1 and sys.argv[1] in REGISTRY:
        integration = sys.argv[1]
    elif len(sys.argv) > 1:
        print(f"Unknown integration '{sys.argv[1]}'. Available: {', '.join(names)}")
        sys.exit(1)
    else:
        integration = _pick("Select integration:", names)

    cfg = REGISTRY[integration]
    acfg = cfg["android"]

    # 2. Fetch available Android native versions
    print(f"\n  Fetching versions from Maven Central…", end="", flush=True)
    versions = maven_versions(acfg["maven_group"], acfg["maven_artifact"])
    print(f" {len(versions)} found.")

    if not versions:
        print("  No versions found — check connectivity or Maven coordinates.")
        sys.exit(1)

    version = _pick(
        f"Select {cfg['display_name']} Android native version ({acfg['maven_group']}:{acfg['maven_artifact']}):",
        versions[:25],
    )

    # 3. Fetch all platform data in parallel
    print(f"\n  Fetching data for {bold(version)}…", end="", flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        fut_android  = pool.submit(fetch_android,  acfg,         version)
        fut_ios      = pool.submit(fetch_ios,       cfg["ios"])
        fut_rn       = pool.submit(fetch_rn,        cfg["rn"])
        fut_flutter  = pool.submit(fetch_flutter,   cfg["flutter"])
        android_data = fut_android.result()
        ios_data     = fut_ios.result()
        rn_data      = fut_rn.result()
        flutter_data = fut_flutter.result()
    print(" done.\n")

    # 4. Render
    border = "═" * 66
    print(border)
    print(bold(f"  RudderStack {cfg['display_name']} — Legacy Integration  (Android v{version})"))
    print(border)

    _display_android(android_data)
    _display_ios(ios_data)
    _display_rn(rn_data, cfg["rn"], android_data["version"], str(ios_data.get("version") or None))
    _display_flutter(flutter_data, cfg["flutter"], android_data["version"], str(ios_data.get("version") or None))

    print()
    print(dim("  " + border))
    print(dim("  🟢 latest within declared range   🔴 outside range   ⚪ unknown"))
    if not _GITHUB_TOKEN:
        print(dim("  Tip: set GITHUB_TOKEN env var to avoid GitHub API rate limits (60 req/hr unauthenticated)"))
    print()

    # 5. Write markdown
    md_content = generate_markdown(integration, cfg, android_data, ios_data, rn_data, flutter_data)
    md_path    = write_markdown(integration, md_content)
    print(f"  Updated {link(md_path, f'file://{md_path}')}")
    print()


if __name__ == "__main__":
    main()
