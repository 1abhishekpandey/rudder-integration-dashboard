"""Terminal display functions for rendering integration data sections."""

import sys
from typing import Optional

from src.terminal import link, bold, dim
from src.url_builders import status_icon

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
