#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from scripts.github_data import (
        fetch_profile_data,
        load_profile_config,
        normalize_graphql_payload,
        token_from_environment,
    )
except ModuleNotFoundError:  # direct execution from scripts/
    from github_data import (  # type: ignore
        fetch_profile_data,
        load_profile_config,
        normalize_graphql_payload,
        token_from_environment,
    )


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    surface: str
    text: str
    muted: str
    quiet: str
    border: str
    accent: str
    accent_soft: str
    contribution_levels: tuple[str, str, str, str, str]


THEMES = {
    "light": Theme(
        name="light",
        bg="#F6F6F3",
        surface="#FFFFFF",
        text="#151619",
        muted="#696D74",
        quiet="#9A9DA3",
        border="#DADAD4",
        accent="#5957E8",
        accent_soft="#ECEBFF",
        contribution_levels=("#E8E8E3", "#D9D8FF", "#B7B5FF", "#8582F4", "#5957E8"),
    ),
    "dark": Theme(
        name="dark",
        bg="#0C0D0F",
        surface="#111316",
        text="#F3F3EE",
        muted="#A0A3AA",
        quiet="#6F737A",
        border="#2A2C31",
        accent="#AAA8FF",
        accent_soft="#1B1B31",
        contribution_levels=("#202226", "#313151", "#4D4B7A", "#7774B8", "#AAA8FF"),
    ),
}

SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"


def esc(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _svg_open(width: int, height: int, title: str, desc: str, theme: Theme) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{esc(title)}</title>
<desc id="desc">{esc(desc)}</desc>
<rect width="{width}" height="{height}" rx="24" fill="{theme.bg}"/>
<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="23.5" fill="none" stroke="{theme.border}"/>
'''


def _text(x: float, y: float, value: object, *, size: float, fill: str, weight: int = 400,
          family: str = SANS, anchor: str = "start", tracking: float | None = None) -> str:
    attrs = [
        f'x="{x}"', f'y="{y}"', f'fill="{fill}"', f'font-family="{family}"',
        f'font-size="{size}"', f'font-weight="{weight}"', f'text-anchor="{anchor}"',
    ]
    if tracking is not None:
        attrs.append(f'letter-spacing="{tracking}"')
    return f'<text {" ".join(attrs)}>{esc(value)}</text>'


def _wrap(text: str, max_chars: int, max_lines: int) -> list[str]:
    words = (text or "").split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        proposal = word if not current else f"{current} {word}"
        if len(proposal) <= max_chars:
            current = proposal
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines - 1:
            break
    if current and len(lines) < max_lines:
        lines.append(current)

    consumed = " ".join(lines)
    if len(consumed) < len(text.strip()) and lines:
        last = lines[-1]
        if len(last) >= max_chars - 1:
            last = last[: max_chars - 2].rstrip()
        lines[-1] = last.rstrip(" .") + "…"
    return lines[:max_lines]


def _calendar_stats(data: dict) -> dict:
    days = [day for week in data["calendar"]["weeks"] for day in week["days"]]
    active = [day for day in days if day["count"] > 0]
    peak = max((day["count"] for day in active), default=0)
    longest = 0
    running = 0
    for day in days:
        if day["count"] > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0
    return {"active_days": len(active), "peak": peak, "longest_streak": longest}


def render_hero(data: dict, config: dict, theme: Theme) -> str:
    profile = data["profile"]
    focus = config.get("focus") or []
    width, height = 1200, 360
    parts = [_svg_open(width, height, f"{profile['name']} profile", "Editorial GitHub profile header with live account metrics.", theme)]

    parts.append(_text(54, 55, "BITREON / SOFTWARE & SYSTEMS", size=12, fill=theme.muted, weight=650, family=MONO, tracking=1.8))
    parts.append(f'<circle cx="1135" cy="51" r="5" fill="{theme.accent}"/>')
    parts.append(_text(1117, 55, "GITHUB", size=11, fill=theme.muted, weight=600, family=MONO, anchor="end", tracking=1.4))

    parts.append(_text(54, 144, "BITREON", size=72, fill=theme.text, weight=760, tracking=-2.4))
    parts.append(_text(58, 188, config.get("headline") or profile.get("bio") or "", size=20, fill=theme.muted, weight=430))

    chip_x = 58
    for label in focus[:3]:
        chip_w = max(128, 22 + len(label) * 8.4)
        parts.append(f'<rect x="{chip_x}" y="225" width="{chip_w:.0f}" height="34" rx="17" fill="{theme.surface}" stroke="{theme.border}"/>')
        parts.append(_text(chip_x + chip_w / 2, 247, label, size=11.5, fill=theme.text, weight=600, family=MONO, anchor="middle"))
        chip_x += chip_w + 10

    parts.append(f'<path d="M58 300H1142" stroke="{theme.border}"/>')
    metrics = [
        ("FOLLOWERS", profile["followers"]),
        ("PUBLIC REPOS", profile["public_repositories"]),
        ("REPO STARS", profile["stars"]),
    ]
    for idx, (label, value) in enumerate(metrics):
        x = 58 + idx * 212
        parts.append(_text(x, 327, label, size=10.5, fill=theme.quiet, weight=650, family=MONO, tracking=1.1))
        parts.append(_text(x + 124, 329, value, size=18, fill=theme.text, weight=700, family=MONO, anchor="end"))

    parts.append(_text(1142, 329, f"@{profile['login']}", size=12, fill=theme.accent, weight=650, family=MONO, anchor="end"))
    parts.append("</svg>")
    return "".join(parts)


def _level_index(level: str) -> int:
    return {
        "NONE": 0,
        "FIRST_QUARTILE": 1,
        "SECOND_QUARTILE": 2,
        "THIRD_QUARTILE": 3,
        "FOURTH_QUARTILE": 4,
    }.get(level, 0)


def render_contributions(data: dict, theme: Theme) -> str:
    calendar = data["calendar"]
    stats = _calendar_stats(data)
    width, height = 1200, 370
    parts = [_svg_open(width, height, "GitHub contribution record", "Real contribution calendar returned by GitHub for this profile.", theme)]

    parts.append(_text(52, 54, "CONTRIBUTION RECORD", size=12, fill=theme.muted, weight=650, family=MONO, tracking=1.7))
    parts.append(_text(52, 101, calendar["total"], size=42, fill=theme.text, weight=760, family=MONO, tracking=-1.5))
    parts.append(_text(52, 126, "GitHub contributions", size=13, fill=theme.muted, weight=500))

    metric_rows = [
        ("ACTIVE DAYS", stats["active_days"]),
        ("PEAK DAY", stats["peak"]),
        ("LONGEST RUN", f"{stats['longest_streak']}d"),
    ]
    for i, (label, value) in enumerate(metric_rows):
        y = 180 + i * 45
        parts.append(_text(52, y, label, size=10.5, fill=theme.quiet, weight=650, family=MONO, tracking=1.0))
        parts.append(_text(220, y + 1, value, size=14, fill=theme.text, weight=680, family=MONO, anchor="end"))

    grid_x, grid_y = 330, 105
    cell, gap = 12, 4
    weeks = calendar["weeks"]
    for week_index, week in enumerate(weeks):
        x = grid_x + week_index * (cell + gap)
        parts.append(f'<g data-week="{week_index}">')
        for day_index, day in enumerate(week["days"]):
            y = grid_y + day_index * (cell + gap)
            level = _level_index(day["level"])
            color = theme.contribution_levels[level]
            count = day["count"]
            noun = "contribution" if count == 1 else "contributions"
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{color}">'
                f'<title>{esc(day["date"])} · {count} {noun}</title></rect>'
            )
        parts.append("</g>")

    month_positions: list[tuple[int, str]] = []
    last_month = None
    for i, week in enumerate(weeks):
        if not week["days"]:
            continue
        try:
            date = dt.date.fromisoformat(week["days"][0]["date"])
        except ValueError:
            continue
        key = (date.year, date.month)
        if key != last_month:
            month_positions.append((i, date.strftime("%b").upper()))
            last_month = key
    last_month_x = -10_000
    for week_index, label in month_positions:
        x = grid_x + week_index * (cell + gap)
        if x < 1110 and x - last_month_x >= 40:
            parts.append(_text(x, 83, label, size=9.5, fill=theme.quiet, weight=650, family=MONO, tracking=0.8))
            last_month_x = x

    legend_x = 945
    parts.append(_text(legend_x - 58, 326, "LESS", size=9.5, fill=theme.quiet, weight=600, family=MONO, anchor="end", tracking=0.7))
    for i, color in enumerate(theme.contribution_levels):
        parts.append(f'<rect x="{legend_x + i * 20}" y="316" width="12" height="12" rx="3" fill="{color}"/>')
    parts.append(_text(legend_x + 111, 326, "MORE", size=9.5, fill=theme.quiet, weight=600, family=MONO, tracking=0.7))
    parts.append(_text(52, 336, "Exact daily counts · GitHub contribution calendar", size=10.5, fill=theme.quiet, weight=500, family=MONO))

    parts.append("</svg>")
    return "".join(parts)


def _format_updated(value: str) -> str:
    if not value:
        return "metadata unavailable"
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value[:10]
    return parsed.strftime("%b %d, %Y").replace(" 0", " ")


def render_project_card(repo: dict, theme: Theme) -> str:
    width, height = 1200, 220
    available = repo.get("available", True)
    title = repo.get("name") or "Repository"
    parts = [_svg_open(width, height, f"{title} repository", f"GitHub repository metadata for {title}.", theme)]

    parts.append(_text(40, 42, "SELECTED WORK", size=10.5, fill=theme.muted, weight=650, family=MONO, tracking=1.5))
    status = "GITHUB / PUBLIC" if available else "METADATA UNAVAILABLE"
    parts.append(_text(1160, 42, status, size=9.5, fill=theme.quiet, weight=650, family=MONO, anchor="end", tracking=1.0))

    parts.append(_text(40, 92, title, size=34, fill=theme.text, weight=740, tracking=-0.9))
    description_lines = _wrap(repo.get("description") or "", 82, 2)
    for i, line in enumerate(description_lines):
        parts.append(_text(40, 126 + i * 22, line, size=14.5, fill=theme.muted, weight=430))

    parts.append(f'<path d="M860 64V166" stroke="{theme.border}"/>')
    language = repo.get("language") or "—"
    parts.append(f'<circle cx="46" cy="180" r="5" fill="{repo.get("language_color") or theme.quiet}"/>')
    parts.append(_text(60, 184, language, size=11.5, fill=theme.text, weight=620, family=MONO))
    parts.append(_text(240, 184, f"UPDATED {_format_updated(repo.get('updated_at') or '').upper()}", size=10, fill=theme.quiet, weight=620, family=MONO, tracking=0.7))

    parts.append(_text(900, 93, "STARS", size=9.5, fill=theme.quiet, weight=650, family=MONO, tracking=1.0))
    parts.append(_text(900, 122, repo.get("stars", 0), size=22, fill=theme.text, weight=720, family=MONO))
    parts.append(_text(1010, 93, "FORKS", size=9.5, fill=theme.quiet, weight=650, family=MONO, tracking=1.0))
    parts.append(_text(1010, 122, repo.get("forks", 0), size=22, fill=theme.text, weight=720, family=MONO))
    parts.append(_text(1160, 184, "OPEN REPOSITORY ↗", size=10, fill=theme.accent, weight=700, family=MONO, anchor="end", tracking=0.8))

    parts.append("</svg>")
    return "".join(parts)

def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "repository"


def render_all(data: dict, config: dict, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for theme_name in ("light", "dark"):
        theme = THEMES[theme_name]
        hero_path = output_dir / f"hero-{theme_name}.svg"
        hero_path.write_text(render_hero(data, config, theme), encoding="utf-8")
        paths.append(hero_path)

        contribution_path = output_dir / f"contributions-{theme_name}.svg"
        contribution_path.write_text(render_contributions(data, theme), encoding="utf-8")
        paths.append(contribution_path)

    for repo in data["repositories"]:
        slug = _slug(repo["name"])
        for theme_name in ("light", "dark"):
            theme = THEMES[theme_name]
            path = output_dir / f"project-{slug}-{theme_name}.svg"
            path.write_text(render_project_card(repo, theme), encoding="utf-8")
            paths.append(path)
    return paths



def _picture(base_name: str, alt: str) -> str:
    return (
        '<picture>\n'
        f'  <source media="(prefers-color-scheme: dark)" srcset="./assets/{base_name}-dark.svg">\n'
        f'  <source media="(prefers-color-scheme: light)" srcset="./assets/{base_name}-light.svg">\n'
        f'  <img alt="{esc(alt)}" src="./assets/{base_name}-light.svg" width="100%">\n'
        '</picture>'
    )


def render_readme(config: dict) -> str:
    username = config["username"]
    lines: list[str] = [
        '<!-- Generated from profile.json by scripts/render_profile.py. Edit profile.json, not this file. -->',
        '',
        _picture('hero', f"{config.get('display_name') or username} — GitHub profile"),
        '',
        config.get('intro') or '',
        '',
        '## Selected work',
        '',
    ]

    for name in config.get('featured_repositories', []):
        slug = _slug(name)
        repo_url = f'https://github.com/{username}/{name}'
        lines.extend([
            f'<a href="{esc(repo_url)}">',
            _picture(f'project-{slug}', f'{name} — selected repository'),
            '</a>',
            '',
        ])

    lines.extend([
        '## Contribution record',
        '',
        _picture('contributions', f'@{username} GitHub contribution record'),
        '',
        f'<sub>Generated from GitHub\'s own contribution calendar for <code>@{esc(username)}</code>. '
        'Every cell preserves the exact daily contribution count returned by GitHub; no event weighting or third-party stats service.</sub>',
        '',
        '## How I build',
        '',
    ])

    for principle in config.get('principles', []):
        if not isinstance(principle, list) or len(principle) != 2:
            continue
        title, body = principle
        lines.append(f'- **{title}.** {body}')

    lines.extend(['', '## Elsewhere', ''])
    link_parts = []
    for item in config.get('links', []):
        if not isinstance(item, list) or len(item) != 2:
            continue
        label, url = item
        link_parts.append(f'[{label}]({url})')
    lines.append(' · '.join(link_parts))
    lines.extend(['', '<!-- profile refreshes automatically from GitHub data -->', ''])
    return '\n'.join(lines)

def _load_data_json(path: Path, config: dict) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "profile" in payload and "calendar" in payload:
        return payload
    return normalize_graphql_payload(payload, config)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the @bitreonx GitHub profile assets from GitHub data.")
    parser.add_argument("--username")
    parser.add_argument("--config", default="profile.json")
    parser.add_argument("--output-dir", default="assets")
    parser.add_argument("--readme", default="README.md")
    parser.add_argument("--data-json", help="Offline GraphQL payload or normalized data for deterministic rendering")
    args = parser.parse_args()

    config = load_profile_config(Path(args.config))
    username = args.username or config["username"]
    if args.data_json:
        data = _load_data_json(Path(args.data_json), config)
    else:
        data = fetch_profile_data(username, token_from_environment(), config)

    paths = render_all(data, config, Path(args.output_dir))
    Path(args.readme).write_text(render_readme(config), encoding="utf-8")
    print(f"rendered {len(paths)} profile assets and {args.readme} for @{username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
