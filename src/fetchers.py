"""Data fetch functions for Android, iOS, React Native, and Flutter integrations."""

import json
import re
import sys
from typing import Optional

from src.http_client import get_text
from src.parsers import find_line, find_version_value_line, gradle_dep, podspec_dep, podspec_version
from src.url_builders import blob_url, cocoapods_specs_url, mvnrepository_url
from src.packages import maven_latest, google_maven_latest, npm_latest, pubdev_latest, cocoapods_latest, github_release_latest


def _json_dotpath(data: dict, path: str):
    """Extract a value from a nested dict using a dot-separated key path."""
    for key in path.split("."):
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def gh_raw(repo: str, ref: str, path: str) -> Optional[str]:
    return get_text(f"https://raw.githubusercontent.com/{repo}/{ref}/{path}")




def _gh_raw_at_version(repo: str, version: str, path: str) -> tuple[Optional[str], str]:
    """Fetch a file at the tag matching a version (tries v{version} then {version}).
    Returns (content, ref_used) or (None, None) if not found."""
    for ref in (f"v{version}", version):
        content = gh_raw(repo, ref, path)
        if content:
            return content, ref
    return None, None


def gh_raw_default(repo: str, path: str) -> tuple[Optional[str], str]:
    """Fetch a file from the default branch (tries main then master).
    Returns (content, ref_used)."""
    for ref in ("main", "master"):
        content = gh_raw(repo, ref, path)
        if content:
            return content, ref
    return None, "main"


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
        if vendor_range:
            line = find_version_value_line(content, vendor_range)
            if not line:
                print(f"\n  ERROR: Could not find vendor range '{vendor_range}' in {repo}/{cfg['build_file']}", file=sys.stderr)
                sys.exit(1)
            out["build_file_url"] = base + f"#L{line}"
        else:
            out["build_file_url"] = base
    pkg, ref_pkg = gh_raw_default(repo, "package.json")
    if pkg:
        try:
            pkg_version    = json.loads(pkg).get("version") or version
            out["version"] = pkg_version
            out["maven_url"] = mvnrepository_url(cfg["maven_group"], cfg["maven_artifact"], pkg_version)
        except Exception:
            pass
        line = find_line(pkg, r'"version"')
        if not line:
            print(f"\n  ERROR: Could not find 'version' field in {repo}/package.json", file=sys.stderr)
            sys.exit(1)
        out["version_url"] = blob_url(repo, ref_pkg, "package.json") + f"#L{line}"
    latest = maven_latest(cfg["vendor_group"], cfg["vendor_artifact"])
    out["latest_vendor"] = latest
    if not latest and cfg.get("vendor_maven_repo") == "google":
        latest = google_maven_latest(cfg["vendor_group"], cfg["vendor_artifact"])
        out["latest_vendor"] = latest
    if latest and cfg.get("vendor_repo") and cfg.get("vendor_version_file"):
        vc, ref_vc = gh_raw_default(cfg["vendor_repo"], cfg["vendor_version_file"])
        if vc:
            line = find_version_value_line(vc, latest)
            if line:
                out["latest_vendor_url"] = blob_url(cfg["vendor_repo"], ref_vc, cfg["vendor_version_file"]) + f"#L{line}"
            else:
                tag_vc, tag_ref = _gh_raw_at_version(cfg["vendor_repo"], latest, cfg["vendor_version_file"])
                if tag_vc and tag_ref:
                    tag_line = find_version_value_line(tag_vc, latest)
                    if tag_line:
                        out["latest_vendor_url"] = blob_url(cfg["vendor_repo"], tag_ref, cfg["vendor_version_file"]) + f"#L{tag_line}"
                        out["latest_vendor_url_is_tag"] = True
    elif latest and cfg.get("vendor_latest_url"):
        out["latest_vendor_url"] = cfg["vendor_latest_url"]
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
                line = find_line(pkg, r'"version"')
                if not line:
                    print(f"\n  ERROR: Could not find 'version' field in {repo}/{cfg['package_json_file']}", file=sys.stderr)
                    sys.exit(1)
                out["version_url"] = blob_url(repo, ref_pkg, cfg["package_json_file"]) + f"#L{line}"
        ios_version         = version or podspec_version(content)
        out["version"]      = ios_version
        vendor_range        = podspec_dep(content, cfg["vendor_pod"])
        out["vendor_range"] = vendor_range
        base                = blob_url(repo, ref, cfg["podspec_file"])
        if vendor_range:
            line = find_version_value_line(content, vendor_range)
            if not line:
                print(f"\n  ERROR: Could not find vendor range '{vendor_range}' in {repo}/{cfg['podspec_file']}", file=sys.stderr)
                sys.exit(1)
            out["podspec_url"] = base + f"#L{line}"
        else:
            out["podspec_url"] = base
        if ios_version:
            out["cocoapods_specs_url"] = cocoapods_specs_url(cfg["pod"], ios_version)
    # Try CocoaPods trunk first; fall back to GitHub releases
    latest = cocoapods_latest(cfg["vendor_pod"])
    if not latest and cfg.get("vendor_gh_repo"):
        latest = github_release_latest(cfg["vendor_gh_repo"])
    out["latest_vendor"] = latest
    if latest and cfg.get("vendor_gh_repo") and cfg.get("vendor_version_file"):
        vc, ref_vc = gh_raw_default(cfg["vendor_gh_repo"], cfg["vendor_version_file"])
        if vc:
            line = find_version_value_line(vc, latest)
            if line:
                out["latest_vendor_url"] = blob_url(cfg["vendor_gh_repo"], ref_vc, cfg["vendor_version_file"]) + f"#L{line}"
            else:
                tag_vc, tag_ref = _gh_raw_at_version(cfg["vendor_gh_repo"], latest, cfg["vendor_version_file"])
                if tag_vc and tag_ref:
                    tag_line = find_version_value_line(tag_vc, latest)
                    if tag_line:
                        out["latest_vendor_url"] = blob_url(cfg["vendor_gh_repo"], tag_ref, cfg["vendor_version_file"]) + f"#L{tag_line}"
                        out["latest_vendor_url_is_tag"] = True
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
            out["rudder_version"] = rudder_version
            line = find_line(pkg, r'"version"')
            if not line:
                print(f"\n  ERROR: Could not find 'version' field in {rudder_repo}/{pkg_json_path}", file=sys.stderr)
                sys.exit(1)
            out["rudder_pkg_json_url"] = blob_url(rudder_repo, ref_pkg, pkg_json_path) + f"#L{line}"
            if rudder_version:
                out["rudder_npm_version_url"] = f"https://www.npmjs.com/package/{cfg['rudder_pkg']}/v/{rudder_version}"
        except Exception:
            pass
    if "rudder_version" not in out:
        out["rudder_version"] = npm_latest(cfg["rudder_pkg"])

    ac, ref_ac = gh_raw_default(rudder_repo, cfg["rudder_android_file"])
    if ac:
        rudder_android_range = gradle_dep(ac, cfg["rudder_android_dep_group"], cfg["rudder_android_dep_artifact"])
        out["rudder_android_range"] = rudder_android_range
        base = blob_url(rudder_repo, ref_ac, cfg["rudder_android_file"])
        if rudder_android_range:
            line = find_line(ac, rf"{re.escape(cfg['rudder_android_dep_group'])}:{re.escape(cfg['rudder_android_dep_artifact'])}")
            if not line:
                print(f"\n  ERROR: Could not find '{cfg['rudder_android_dep_group']}:{cfg['rudder_android_dep_artifact']}' in {rudder_repo}/{cfg['rudder_android_file']}", file=sys.stderr)
                sys.exit(1)
            out["rudder_android_url"] = base + f"#L{line}"
        else:
            out["rudder_android_url"] = base
    ic, ref_ic = gh_raw_default(rudder_repo, cfg["rudder_ios_file"])
    if ic:
        rudder_ios_range = podspec_dep(ic, cfg["rudder_ios_dep_pod"])
        out["rudder_ios_range"] = rudder_ios_range
        base = blob_url(rudder_repo, ref_ic, cfg["rudder_ios_file"])
        if rudder_ios_range:
            line = find_line(ic, rf"dependency\s+['\"]?{re.escape(cfg['rudder_ios_dep_pod'])}")
            if not line:
                print(f"\n  ERROR: Could not find dependency '{cfg['rudder_ios_dep_pod']}' in {rudder_repo}/{cfg['rudder_ios_file']}", file=sys.stderr)
                sys.exit(1)
            out["rudder_ios_url"] = base + f"#L{line}"
        else:
            out["rudder_ios_url"] = base

    vendor_repo = cfg["vendor_repo"]
    out["vendor_repo_url"] = f"https://github.com/{vendor_repo}"
    out["vendor_npm_url"]  = f"https://www.npmjs.com/package/{cfg['vendor_pkg']}"

    # Read vendor version from package.json so the link points to the source file
    vendor_pkg_json_path = cfg.get("vendor_package_json_path", "package.json")
    vpkg, ref_vpkg = gh_raw_default(vendor_repo, vendor_pkg_json_path)
    if vpkg:
        try:
            vendor_version = json.loads(vpkg).get("version")
            out["vendor_version"] = vendor_version
            line = find_line(vpkg, r'"version"')
            if not line:
                print(f"\n  ERROR: Could not find 'version' field in {vendor_repo}/{vendor_pkg_json_path}", file=sys.stderr)
                sys.exit(1)
            out["vendor_pkg_json_url"] = blob_url(vendor_repo, ref_vpkg, vendor_pkg_json_path) + f"#L{line}"
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
        if vendor_android_range:
            line = find_version_value_line(vac, vendor_android_range)
            if not line:
                print(f"\n  ERROR: Could not find vendor range '{vendor_android_range}' in {vendor_repo}/{cfg['vendor_android_file']}", file=sys.stderr)
                sys.exit(1)
            out["vendor_android_url"] = base + f"#L{line}"
        else:
            out["vendor_android_url"] = base
    vic, ref_vic = gh_raw_default(vendor_repo, cfg["vendor_ios_file"])
    if vic:
        vendor_ios_range = podspec_dep(vic, cfg["vendor_ios_dep_pod"])
        out["vendor_ios_range"] = vendor_ios_range
        base = blob_url(vendor_repo, ref_vic, cfg["vendor_ios_file"])
        if vendor_ios_range:
            line = find_version_value_line(vic, vendor_ios_range)
            if not line:
                print(f"\n  ERROR: Could not find vendor range '{vendor_ios_range}' in {vendor_repo}/{cfg['vendor_ios_file']}", file=sys.stderr)
                sys.exit(1)
            out["vendor_ios_url"] = base + f"#L{line}"
        else:
            out["vendor_ios_url"] = base

    # Monorepo fallback: read SDK versions from a central JSON file
    if cfg.get("vendor_versions_json_file") and (
        not out.get("vendor_android_range") or not out.get("vendor_ios_range")
    ):
        vjson, ref_vjson = gh_raw_default(vendor_repo, cfg["vendor_versions_json_file"])
        if vjson:
            try:
                data = json.loads(vjson)
                base_url = blob_url(vendor_repo, ref_vjson, cfg["vendor_versions_json_file"])
                if not out.get("vendor_android_range") and cfg.get("vendor_android_sdk_version_key"):
                    ver = _json_dotpath(data, cfg["vendor_android_sdk_version_key"])
                    if ver:
                        out["vendor_android_range"] = str(ver)
                        line = find_line(vjson, re.escape(str(ver)))
                        if line:
                            out["vendor_android_url"] = base_url + f"#L{line}"
                if not out.get("vendor_ios_range") and cfg.get("vendor_ios_sdk_version_key"):
                    ver = _json_dotpath(data, cfg["vendor_ios_sdk_version_key"])
                    if ver:
                        out["vendor_ios_range"] = str(ver)
                        line = find_line(vjson, re.escape(str(ver)))
                        if line:
                            out["vendor_ios_url"] = base_url + f"#L{line}"
            except json.JSONDecodeError:
                pass
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
            if not line:
                print(f"\n  ERROR: Could not find 'version:' in {rudder_repo}/{pubspec_path}", file=sys.stderr)
                sys.exit(1)
            out["rudder_pubspec_url"] = blob_url(rudder_repo, ref_pubspec, pubspec_path) + f"#L{line}"
            out["rudder_pub_version_url"] = f"https://pub.dev/packages/{cfg['rudder_pkg']}/versions/{rudder_version}"
    if "rudder_version" not in out:
        out["rudder_version"] = pubdev_latest(cfg["rudder_pkg"])

    ac, ref_ac = gh_raw_default(rudder_repo, cfg["rudder_android_file"])
    if ac:
        rudder_android_range = gradle_dep(ac, cfg["rudder_android_dep_group"], cfg["rudder_android_dep_artifact"])
        out["rudder_android_range"] = rudder_android_range
        base = blob_url(rudder_repo, ref_ac, cfg["rudder_android_file"])
        if rudder_android_range:
            line = find_line(ac, rf"{re.escape(cfg['rudder_android_dep_group'])}:{re.escape(cfg['rudder_android_dep_artifact'])}")
            if not line:
                print(f"\n  ERROR: Could not find '{cfg['rudder_android_dep_group']}:{cfg['rudder_android_dep_artifact']}' in {rudder_repo}/{cfg['rudder_android_file']}", file=sys.stderr)
                sys.exit(1)
            out["rudder_android_url"] = base + f"#L{line}"
        else:
            out["rudder_android_url"] = base
    ic, ref_ic = gh_raw_default(rudder_repo, cfg["rudder_ios_file"])
    if ic:
        rudder_ios_range = podspec_dep(ic, cfg["rudder_ios_dep_pod"])
        out["rudder_ios_range"] = rudder_ios_range
        base = blob_url(rudder_repo, ref_ic, cfg["rudder_ios_file"])
        if rudder_ios_range:
            line = find_line(ic, rf"dependency\s+['\"]?{re.escape(cfg['rudder_ios_dep_pod'])}")
            if not line:
                print(f"\n  ERROR: Could not find dependency '{cfg['rudder_ios_dep_pod']}' in {rudder_repo}/{cfg['rudder_ios_file']}", file=sys.stderr)
                sys.exit(1)
            out["rudder_ios_url"] = base + f"#L{line}"
        else:
            out["rudder_ios_url"] = base

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
            if not line:
                print(f"\n  ERROR: Could not find 'version:' in {vendor_repo}/{vendor_pubspec_path}", file=sys.stderr)
                sys.exit(1)
            out["vendor_pubspec_url"] = blob_url(vendor_repo, ref_vpubspec, vendor_pubspec_path) + f"#L{line}"
            out["vendor_pub_version_url"] = f"https://pub.dev/packages/{cfg['vendor_pkg']}/versions/{vendor_version}"
    if "vendor_version" not in out:
        out["vendor_version"] = pubdev_latest(cfg["vendor_pkg"])

    vac, ref_vac = gh_raw_default(vendor_repo, cfg["vendor_android_file"])
    if vac:
        vendor_android_range = gradle_dep(vac, cfg["vendor_android_dep_group"], cfg["vendor_android_dep_artifact"])
        out["vendor_android_range"] = vendor_android_range
        base = blob_url(vendor_repo, ref_vac, cfg["vendor_android_file"])
        if vendor_android_range:
            line = find_version_value_line(vac, vendor_android_range)
            if not line:
                print(f"\n  ERROR: Could not find vendor range '{vendor_android_range}' in {vendor_repo}/{cfg['vendor_android_file']}", file=sys.stderr)
                sys.exit(1)
            out["vendor_android_url"] = base + f"#L{line}"
        else:
            out["vendor_android_url"] = base
    vic, ref_vic = gh_raw_default(vendor_repo, cfg["vendor_ios_file"])
    if vic:
        vendor_ios_range = podspec_dep(vic, cfg["vendor_ios_dep_pod"])
        out["vendor_ios_range"] = vendor_ios_range
        base = blob_url(vendor_repo, ref_vic, cfg["vendor_ios_file"])
        if vendor_ios_range:
            line = find_version_value_line(vic, vendor_ios_range)
            if not line:
                print(f"\n  ERROR: Could not find vendor range '{vendor_ios_range}' in {vendor_repo}/{cfg['vendor_ios_file']}", file=sys.stderr)
                sys.exit(1)
            out["vendor_ios_url"] = base + f"#L{line}"
        else:
            out["vendor_ios_url"] = base
    return out
