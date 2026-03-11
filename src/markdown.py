"""Markdown report generation and file writing."""

import datetime
import os
from typing import Optional

from src.url_builders import status_icon


def _ml(text: str, url: Optional[str]) -> str:
    """Return a Markdown hyperlink, or plain text when there is no URL."""
    if url and text and text not in ("—", ""):
        label = text.replace("[", "\\[")
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
    rn_combined = None
    if cfg.get("rn") is not None:
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
    fl_combined = None
    if cfg.get("flutter") is not None:
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
    ]

    if rn_combined is not None:
        sections += [
            "# React Native SDK",
            "",
            rn_header,
            rn_sep,
            rn_combined,
            "",
            "---",
            "",
        ]

    if fl_combined is not None:
        sections += [
            "# Flutter SDK",
            "",
            fl_header,
            fl_sep,
            fl_combined,
            "",
        ]
    return "\n".join(sections)


def write_markdown(integration: str, content: str) -> str:
    """Write markdown content to the path defined by OUTPUT_PATH env var.

    Falls back to output/{INTEGRATION}_LEGACY.md in the project root when
    OUTPUT_PATH is not set. Creates the output directory if it does not exist.
    """
    output_path = os.environ.get("OUTPUT_PATH", "").strip()
    if output_path:
        path = output_path
    else:
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(project_dir, "output", f"{integration.upper()}_LEGACY.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
