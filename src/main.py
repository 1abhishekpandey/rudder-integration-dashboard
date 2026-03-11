"""Main entry point logic for the RudderStack Integration Version Explorer."""

import sys
import os
from concurrent.futures import ThreadPoolExecutor

from src.config import load_dotenv
from src.registry import REGISTRY
from src.packages import maven_versions
from src.fetchers import fetch_android, fetch_ios, fetch_rn, fetch_flutter
from src.display import _pick, _display_android, _display_ios, _display_rn, _display_flutter
from src.terminal import bold, dim
from src.markdown import generate_markdown, write_markdown
from src.url_builders import status_icon
from src.http_client import _GITHUB_TOKEN


def main() -> None:
    load_dotenv()
    # 1. Select integration
    names = list(REGISTRY.keys())
    env_integration = os.environ.get("INTEGRATION", "").strip().lower()
    if len(sys.argv) > 1 and sys.argv[1] in REGISTRY:
        integration = sys.argv[1]
    elif len(sys.argv) > 1:
        print(f"Unknown integration '{sys.argv[1]}'. Available: {', '.join(names)}")
        sys.exit(1)
    elif env_integration in REGISTRY:
        integration = env_integration
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
    from src.terminal import link
    md_content = generate_markdown(integration, cfg, android_data, ios_data, rn_data, flutter_data)
    md_path    = write_markdown(integration, md_content)
    print(f"  Updated {link(md_path, f'file://{md_path}')}")
    print()
