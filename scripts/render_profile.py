#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

try:
    from scripts.github_data import (
        fetch_profile_data,
        load_profile_config,
        normalize_graphql_payload,
        token_from_environment,
    )
    from scripts.motion_profile import _calendar_summary, render_motion_assets
except ModuleNotFoundError:
    from github_data import (  # type: ignore
        fetch_profile_data,
        load_profile_config,
        normalize_graphql_payload,
        token_from_environment,
    )
    from motion_profile import _calendar_summary, render_motion_assets  # type: ignore


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


def _static_picture(name: str, alt: str) -> str:
    base = f"./assets/motion/{name}"
    return "\n".join([
        "<picture>",
        f'  <source media="(prefers-color-scheme: dark)" srcset="{base}-dark.png">',
        f'  <img alt="{esc(alt)}" src="{base}-light.png" width="100%">',
        "</picture>",
    ])


def _month_totals(calendar: dict) -> list[dict]:
    counts: dict[tuple[int, int], int] = {}
    for week in calendar.get("weeks") or []:
        for day in week.get("days") or []:
            value = day.get("date", "")
            try:
                parsed = dt.date.fromisoformat(value)
            except ValueError:
                continue
            key = (parsed.year, parsed.month)
            counts[key] = counts.get(key, 0) + int(day.get("count", 0))

    ordered: list[dict] = []
    seen: set[tuple[int, int]] = set()
    through = calendar.get("through", "")
    try:
        through_date = dt.date.fromisoformat(through)
    except ValueError:
        through_date = None

    for month in calendar.get("months") or []:
        year = int(month.get("year") or 0)
        try:
            month_number = dt.datetime.strptime(month.get("name", ""), "%B").month
        except ValueError:
            continue
        key = (year, month_number)
        if key in seen:
            continue
        seen.add(key)
        start_date = dt.date(year, month_number, 1)
        if month_number == 12:
            next_month = dt.date(year + 1, 1, 1)
        else:
            next_month = dt.date(year, month_number + 1, 1)
        end_date = next_month - dt.timedelta(days=1)
        if through_date and start_date <= through_date < end_date:
            end_date = through_date
        ordered.append({
            "label": f"{month.get('name', '')[:3].upper()} {year}",
            "count": counts.get(key, 0),
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        })
    return ordered


def _activity_details(data: dict, username: str) -> str:
    calendar = data["calendar"]
    summary = _calendar_summary(calendar.get("weeks") or [])
    month_totals = _month_totals(calendar)
    through = calendar.get("through", "")
    try:
        through_label = dt.date.fromisoformat(through).strftime("%b %d, %Y")
    except ValueError:
        through_label = through or "latest GitHub calendar day"

    month_cells = " · ".join(
        f'<a href="https://github.com/{esc(username)}?tab=overview&amp;from={item["start"]}&amp;to={item["end"]}">'
        f'<code>{esc(item["label"])} {item["count"]}</code></a>'
        for item in month_totals
    )
    return "\n".join([
        "<details>",
        f"<summary><strong>Activity details</strong> · {calendar['total']} exact contributions · Calendar through {esc(through_label)}</summary>",
        "",
        f"<p><strong>Best week</strong> {summary['best_week_count']} &nbsp;·&nbsp; "
        f"<strong>Best month</strong> {summary['best_month_count']} / {esc(summary['best_month_label'])} &nbsp;·&nbsp; "
        f"<strong>Active</strong> {summary['active_days']} days / {summary['active_weeks']} weeks</p>",
        f"<p>{month_cells}</p>",
        '<p><sub>Source: GitHub GraphQL <code>contributionsCollection.contributionCalendar</code>. '
        'The refresh is rejected if the sum of daily counts differs from GitHub <code>totalContributions</code>.</sub></p>',
        "</details>",
    ])


def render_readme(config: dict, data: dict) -> str:
    username = config["username"]
    display = config.get("display_name") or username
    featured = config.get("featured_repositories") or []
    official_profile = f"https://github.com/{username}?tab=overview"

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
            _static_picture(slug, f"{name} — system overview backed by GitHub repository metadata"),
            "</a>",
            "",
        ])

    lines.extend([
        '<p><sub>BUILD ACTIVITY</sub></p>',
        "",
        f'<a href="{esc(official_profile)}" title="Open the official interactive GitHub contribution graph">',
        _motion_picture("contributions", f"@{username} — exact GitHub contribution calendar"),
        "</a>",
        "",
        f'<p align="right"><sub><a href="{esc(official_profile)}">Open the official interactive graph →</a></sub></p>',
        "",
        _activity_details(data, username),
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
    Path(args.readme).write_text(render_readme(config, data), encoding="utf-8")
    print(f"rendered {len(paths)} profile assets and {args.readme} for @{username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
