#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.github_data import (
        fetch_profile_data,
        load_profile_config,
        normalize_graphql_payload,
        token_from_environment,
    )
    from scripts.motion_profile import render_motion_assets
except ModuleNotFoundError:
    from github_data import (  # type: ignore
        fetch_profile_data,
        load_profile_config,
        normalize_graphql_payload,
        token_from_environment,
    )
    from motion_profile import render_motion_assets  # type: ignore


def esc(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _slug(value: str) -> str:
    return "-".join(part for part in value.lower().replace("_", "-").split("-") if part)


def _motion_picture(name: str, alt: str) -> str:
    base = f"./assets/motion/{name}"
    return "\n".join([
        "<picture>",
        f'  <source media="(prefers-reduced-motion: reduce) and (prefers-color-scheme: dark)" srcset="{base}-dark.png">',
        f'  <source media="(prefers-reduced-motion: reduce)" srcset="{base}-light.png">',
        f'  <source media="(prefers-color-scheme: dark)" srcset="{base}-dark.gif">',
        f'  <source media="(prefers-color-scheme: light)" srcset="{base}-light.gif">',
        f'  <img alt="{esc(alt)}" src="{base}-light.gif" width="100%">',
        "</picture>",
    ])


def render_readme(config: dict) -> str:
    username = config["username"]
    display = config.get("display_name") or username
    featured = config.get("featured_repositories") or []

    lines = [
        "<!-- Generated from profile.json + live GitHub data. Edit profile.json, not README.md. -->",
        "",
        _motion_picture("hero", f"{display} — motion GitHub profile"),
        "",
        '<p><sub>SELECTED SYSTEMS</sub></p>',
        "",
    ]

    for name in featured:
        slug = _slug(name)
        url = f"https://github.com/{username}/{name}"
        lines.extend([
            f'<a href="{esc(url)}">',
            _motion_picture(slug, f"{name} — animated system overview backed by GitHub repository metadata"),
            "</a>",
            "",
        ])

    lines.extend([
        '<p><sub>BUILD ACTIVITY</sub></p>',
        "",
        _motion_picture("contributions", f"@{username} — real GitHub contribution calendar animation"),
        "",
        f'<p><sub>DATA SOURCE</sub><br><code>GitHub GraphQL → contributionsCollection.contributionCalendar</code><br>'
        f'<sub>Every illuminated day comes from the exact contribution count returned for <code>@{esc(username)}</code>. No synthetic events.</sub></p>',
        "",
        '<p><sub>CURRENTLY</sub><br>' + esc(config.get("currently") or "Building developer systems.") + "</p>",
        "",
        '<p><sub>ELSEWHERE</sub><br>',
    ])

    links = []
    for item in config.get("links", []):
        if isinstance(item, list) and len(item) == 2:
            label, url = item
            links.append(f'<a href="{esc(url)}">{esc(label)}</a>')
    lines.append(" · ".join(links) + "</p>")
    lines.extend(["", "<!-- motion assets refresh automatically from GitHub data -->", ""])
    return "\n".join(lines)


def _load_data_json(path: Path, config: dict) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "profile" in payload and "calendar" in payload:
        return payload
    return normalize_graphql_payload(payload, config)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render @bitreonx motion profile assets from GitHub data.")
    parser.add_argument("--username")
    parser.add_argument("--config", default="profile.json")
    parser.add_argument("--output-dir", default="assets/motion")
    parser.add_argument("--readme", default="README.md")
    parser.add_argument("--data-json", help="Offline GraphQL payload or normalized data for deterministic rendering")
    args = parser.parse_args()

    config = load_profile_config(Path(args.config))
    username = args.username or config["username"]
    if args.data_json:
        data = _load_data_json(Path(args.data_json), config)
    else:
        data = fetch_profile_data(username, token_from_environment(), config)

    paths = render_motion_assets(data, config, Path(args.output_dir))
    Path(args.readme).write_text(render_readme(config), encoding="utf-8")
    print(f"rendered {len(paths)} motion assets and {args.readme} for @{username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
