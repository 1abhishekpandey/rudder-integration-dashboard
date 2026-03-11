"""URL construction helpers for GitHub, CocoaPods, and Maven registries."""

import hashlib
import re
from typing import Optional


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
