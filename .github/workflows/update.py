#!/usr/bin/env python3
"""Fetch the shadcn registry directory and every registry's index.

Source of truth: https://ui.shadcn.com/r/registries.json — an array of
``{ name, homepage, url, description }``. The ``url`` is a per-item template
containing a ``{name}`` placeholder (e.g. ``https://7ovr.com/r/{name}.json``).
A registry's full index ("the registry information") is obtained by substituting
``{name}`` with ``registry`` (with ``index`` as a fallback), which returns the
registry definition: ``{ $schema, name, homepage, items[] }``.

Each registry index is written to the repo root as ``<name>.json`` (the leading
``@`` is stripped). The directory itself is saved as ``registries.json``.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

DIRECTORY_URL = "https://ui.shadcn.com/r/registries.json"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
USER_AGENT = "shadcn-registry-props/1.0 (+https://github.com)"
TIMEOUT = 30
WORKERS = 16
RETRIES = 2


def fetch(url: str) -> bytes:
    last_err: Exception | None = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read()
        except Exception as err:  # noqa: BLE001 - retry on anything transient
            last_err = err
    raise last_err if last_err else RuntimeError(f"failed to fetch {url}")


def safe_filename(name: str) -> str:
    """`@ai-elements` -> `ai-elements.json`; sanitize anything unexpected."""
    stem = name.lstrip("@").strip()
    stem = re.sub(r"[^A-Za-z0-9._-]", "-", stem) or "registry"
    return f"{stem}.json"


def index_candidates(url_template: str) -> list[str]:
    """Candidate index URLs for a registry, in priority order."""
    cands = []
    for token in ("registry", "index"):
        if "{name}" in url_template:
            cands.append(url_template.replace("{name}", token))
    return cands


def fetch_registry(entry: dict) -> tuple[str, dict | None, str]:
    name = entry.get("name", "")
    url_template = entry.get("url", "")
    if not name or "{name}" not in url_template:
        return name, None, "missing name/url template"

    last_reason = "no candidate URLs"
    for candidate in index_candidates(url_template):
        try:
            raw = fetch(candidate)
            data = json.loads(raw)
            return name, data, candidate
        except urllib.error.HTTPError as err:
            last_reason = f"HTTP {err.code} @ {candidate}"
        except json.JSONDecodeError as err:
            last_reason = f"invalid JSON @ {candidate}: {err}"
        except Exception as err:  # noqa: BLE001
            last_reason = f"{type(err).__name__} @ {candidate}: {err}"
    return name, None, last_reason


def main() -> int:
    print(f"Fetching directory: {DIRECTORY_URL}")
    directory = json.loads(fetch(DIRECTORY_URL))
    if not isinstance(directory, list):
        print("ERROR: registries.json is not a JSON array", file=sys.stderr)
        return 1

    # Persist the directory itself at the repo root.
    with open(os.path.join(ROOT, "registries.json"), "w", encoding="utf-8") as fh:
        json.dump(directory, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"{len(directory)} registries listed. Fetching indexes with {WORKERS} workers...")
    ok, failed = 0, []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(fetch_registry, entry): entry for entry in directory}
        for future in as_completed(futures):
            name, data, info = future.result()
            if data is None:
                failed.append((name, info))
                print(f"  ✗ {name}: {info}")
                continue
            path = os.path.join(ROOT, safe_filename(name))
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            ok += 1
            print(f"  ✓ {name} -> {os.path.basename(path)}")

    print(f"\nDone: {ok} saved, {len(failed)} failed (of {len(directory)}).")

    # Surface a summary in the GitHub Actions run, if available.
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"## Registry update\n\n")
            fh.write(f"- **{ok}** registries saved\n")
            fh.write(f"- **{len(failed)}** failed (of {len(directory)})\n")
            if failed:
                fh.write("\n<details><summary>Failures</summary>\n\n")
                for name, info in sorted(failed):
                    fh.write(f"- `{name}`: {info}\n")
                fh.write("\n</details>\n")

    # Don't fail the job just because some third-party registries are down.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
