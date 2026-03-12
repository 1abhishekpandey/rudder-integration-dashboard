"""Build-file parsers for Gradle and CocoaPods podspec files."""

import re
from typing import Optional


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
    # Variable pod name: var = 'PodName' ... s.dependency var, version_or_var
    m3 = re.search(rf"""(\w+)\s*=\s*['"]?{re.escape(pod)}['"]?""", content)
    if m3:
        pod_var = m3.group(1)
        # Look for dependency using that variable, with literal version
        m4 = re.search(
            rf"""dependency\s+{re.escape(pod_var)}\s*,\s*['"]([^'"]+)['"]""",
            content
        )
        if m4:
            return _resolve_ruby(content, m4.group(1).strip())
        # Look for dependency using that variable, with variable version
        m5 = re.search(
            rf"""dependency\s+{re.escape(pod_var)}\s*,\s*(\w+)""",
            content
        )
        if m5:
            ver_var = m5.group(1)
            vm = re.search(rf"""{re.escape(ver_var)}\s*=\s*['"]([^'"]+)['"]""", content)
            if vm:
                return _resolve_ruby(content, vm.group(1).strip())
    return None


def podspec_version(content: str) -> Optional[str]:
    # s.version = '4.3.0'  or  spec.version = "4.3.0"
    m = re.search(r"""\w+\.version\s*=\s*['"]([^'"]+)['"]""", content)
    return m.group(1).strip() if m else None
