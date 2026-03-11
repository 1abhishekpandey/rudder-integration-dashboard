"""HTTP client utilities for GitHub API and raw content fetching."""

import json
import os
import urllib.request
import urllib.error
from typing import Optional, Any

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
