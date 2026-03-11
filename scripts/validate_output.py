"""Validate generated markdown report files for link integrity and formatting."""

import glob
import os
import re
import sys


# Markdown link pattern: [text](url)
LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)]*)\)')
# Broken link: bare \[ at start of a cell (not inside a proper link)
BROKEN_BRACKET_RE = re.compile(r'(?<!\[)\\?\[(?!\[)')
# Status icons that should appear before brackets in range cells
STATUS_ICON_RE = re.compile(r'[🟢🔴⚪]')
# Table separator
TABLE_SEP_RE = re.compile(r'^\|(\s*---\s*\|)+$')
# Table row
TABLE_ROW_RE = re.compile(r'^\|.*\|$')
# Valid URL domains for this project
VALID_DOMAINS = [
    'github.com',
    'mvnrepository.com',
    'www.npmjs.com',
    'pub.dev',
]


def validate_file(filepath: str) -> list[str]:
    """Validate a single markdown report file. Returns a list of error strings."""
    errors = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    if not lines:
        errors.append(f"{filepath}: file is empty")
        return errors

    filename = os.path.basename(filepath)

    # Check 1: Title line exists (first non-empty line)
    first_line = lines[0].strip()
    if not first_line or first_line.startswith('#'):
        errors.append(f"{filename}:1: title should be plain text, not a heading")

    # Check 2: Required sections
    content = ''.join(lines)
    if '# Native Integration' not in content:
        errors.append(f"{filename}: missing '# Native Integration' section")
    if '# Flutter SDK' not in content:
        errors.append(f"{filename}: missing '# Flutter SDK' section")

    # Check 3: Validate each line
    in_table = False
    expected_cols = 0

    for i, line in enumerate(lines, start=1):
        stripped = line.rstrip('\n')

        # Check table structure
        if TABLE_SEP_RE.match(stripped):
            in_table = True
            expected_cols = stripped.count('|') - 1
            continue

        if in_table and TABLE_ROW_RE.match(stripped):
            col_count = stripped.count('|') - 1
            if col_count != expected_cols:
                errors.append(
                    f"{filename}:{i}: table column mismatch — "
                    f"expected {expected_cols}, got {col_count}"
                )
        elif in_table and not stripped.strip():
            in_table = False
            expected_cols = 0

        # Check links in this line
        for match in LINK_RE.finditer(stripped):
            label, url = match.group(1), match.group(2)

            # Empty URL
            if not url or url.isspace():
                errors.append(f"{filename}:{i}: empty URL in link [{label}]()")

            # URL must start with https://
            if url and not url.startswith('https://'):
                errors.append(
                    f"{filename}:{i}: non-HTTPS URL: {url}"
                )

            # URL domain check
            if url.startswith('https://'):
                domain = url.split('/')[2] if len(url.split('/')) > 2 else ''
                if domain and not any(d in domain for d in VALID_DOMAINS):
                    errors.append(
                        f"{filename}:{i}: unexpected domain in URL: {domain}"
                    )

            # Label should not start with a bare unescaped bracket
            # (escaped \[ is fine inside a link label)
            if label.startswith('[') and not label.startswith('\\['):
                errors.append(
                    f"{filename}:{i}: link label starts with unescaped '[': [{label}]"
                )

        # Check status icons in range cells
        # Range cells contain Maven ranges like [2.1.0,3.0.0) or CocoaPods ~> 4.3
        # Status icons must appear BEFORE the range text inside a link
        range_links = re.findall(r'\[((?:[🟢🔴⚪]\s)?\\?\[[\d.,)+\s]*)\]\(', stripped)
        for rl in range_links:
            if '\\[' in rl and not STATUS_ICON_RE.search(rl):
                errors.append(
                    f"{filename}:{i}: range cell missing status icon: {rl}"
                )

    # Check 4: Every table row in Native section has platform label
    native_section = False
    for i, line in enumerate(lines, start=1):
        stripped = line.rstrip('\n')
        if '# Native Integration' in stripped:
            native_section = True
            continue
        if native_section and stripped.startswith('#'):
            native_section = False
        if native_section and TABLE_ROW_RE.match(stripped) and not TABLE_SEP_RE.match(stripped):
            if stripped.startswith('| Platform'):
                continue
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if cells and cells[0] not in ('Android', 'iOS'):
                errors.append(
                    f"{filename}:{i}: unexpected platform in Native table: '{cells[0]}'"
                )

    # Check 5: No dash-only data cells (indicates missing data)
    # We allow "—" (em-dash) as intentional placeholder but flag bare "—" in
    # version/URL columns (columns 3+ in native table)
    # This is a soft check — just warn, don't fail

    return errors


def main() -> int:
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'output',
    )

    if not os.path.isdir(output_dir):
        print(f"ERROR: output directory not found: {output_dir}")
        return 1

    files = glob.glob(os.path.join(output_dir, '*_LEGACY.md'))
    if not files:
        print(f"ERROR: no *_LEGACY.md files found in {output_dir}")
        return 1

    all_errors = []
    for filepath in sorted(files):
        print(f"Validating {os.path.basename(filepath)} ...")
        file_errors = validate_file(filepath)
        all_errors.extend(file_errors)

    if all_errors:
        print(f"\n{len(all_errors)} validation error(s) found:\n")
        for err in all_errors:
            print(f"  - {err}")
        return 1

    print(f"\nAll {len(files)} report(s) passed validation.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
