#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class MotionTheme:
    name: str
    bg: str
    fg: str
    muted: str
    quiet: str
    border: str
    accent: str
    accent_soft: str
    empty: str


THEMES = {
    "light": MotionTheme(
        name="light",
        bg="#F7F7F4",
        fg="#111214",
        muted="#656970",
        quiet="#989BA1",
        border="#D7D8D4",
        accent="#6866F5",
        accent_soft="#E8E8FF",
        empty="#E8E9E5",
    ),
    "dark": MotionTheme(
        name="dark",
        bg="#0A0B0D",
        fg="#F4F4EF",
        muted="#A0A3AA",
        quiet="#696D75",
        border="#292C31",
        accent="#AAA8FF",
        accent_soft="#24243F",
        empty="#1B1D21",
    ),
}

W = 1200
FPS_MS = 100


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    return (*_rgb(value), max(0, min(255, alpha)))


def _mix(a: str, b: str, t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    ar, ag, ab = _rgb(a)
    br, bg, bb = _rgb(b)
    return (
        round(ar + (br - ar) * t),
        round(ag + (bg - ag) * t),
        round(ab + (bb - ab) * t),
    )


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _window(t: float, start: float, end: float) -> float:
    if t <= start:
        return 0.0
    if t >= end:
        return 1.0
    return _ease((t - start) / (end - start))


def _fade_loop(t: float) -> float:
    if t < 0.91:
        return 1.0
    return 1.0 - _ease((t - 0.91) / 0.09)


def _font_candidates(bold: bool = False, mono: bool = False) -> list[str]:
    if mono:
        return [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
        ]
    return [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]


@lru_cache(maxsize=64)
def _font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.ImageFont:
    for path in _font_candidates(bold=bold, mono=mono):
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _new_frame(height: int, theme: MotionTheme) -> Image.Image:
    return Image.new("RGBA", (W, height), _rgba(theme.bg))


def _draw_tracking(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, font: ImageFont.ImageFont,
                   fill, tracking: float = 0) -> None:
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=font, fill=fill, anchor="la")
        bbox = draw.textbbox((0, 0), char, font=font)
        x += (bbox[2] - bbox[0]) + tracking


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, tracking: float = 0) -> float:
    if not text:
        return 0
    width = sum(draw.textlength(char, font=font) for char in text)
    return width + tracking * (len(text) - 1)


def _alpha_text(frame: Image.Image, xy: tuple[int, int], text: str, *, size: int, color: str,
                alpha: int = 255, bold: bool = False, mono: bool = False, tracking: float = 0,
                anchor: str = "la") -> None:
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = _font(size, bold=bold, mono=mono)
    if tracking and anchor == "la":
        _draw_tracking(draw, xy, text, font, _rgba(color, alpha), tracking)
    else:
        draw.text(xy, text, font=font, fill=_rgba(color, alpha), anchor=anchor)
    frame.alpha_composite(layer)


def _line(frame: Image.Image, points: Iterable[tuple[float, float]], color: str, alpha: int, width: int = 1) -> None:
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).line(list(points), fill=_rgba(color, alpha), width=width, joint="curve")
    frame.alpha_composite(layer)


def _circle(frame: Image.Image, center: tuple[float, float], radius: float, color: str, alpha: int = 255,
            outline: str | None = None, outline_alpha: int = 255, width: int = 1) -> None:
    x, y = center
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    box = (x - radius, y - radius, x + radius, y + radius)
    d.ellipse(box, fill=_rgba(color, alpha), outline=_rgba(outline, outline_alpha) if outline else None, width=width)
    frame.alpha_composite(layer)


def _rounded(frame: Image.Image, box: tuple[int, int, int, int], radius: int, fill: str, outline: str | None = None,
             alpha: int = 255, outline_alpha: int = 255, width: int = 1) -> None:
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(
        box,
        radius=radius,
        fill=_rgba(fill, alpha),
        outline=_rgba(outline, outline_alpha) if outline else None,
        width=width,
    )
    frame.alpha_composite(layer)


def _deterministic_point(key: str, x0: int, x1: int, y0: int, y1: int) -> tuple[int, int]:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    x = x0 + int.from_bytes(digest[:4], "big") % max(1, x1 - x0)
    y = y0 + int.from_bytes(digest[4:8], "big") % max(1, y1 - y0)
    return x, y


def _active_days(data: dict) -> list[dict]:
    days = [day for week in data["calendar"]["weeks"] for day in week["days"] if int(day.get("count", 0)) > 0]
    return sorted(days, key=lambda day: day.get("date", ""))



def _weekly_totals(weeks: list[dict]) -> list[dict]:
    totals: list[dict] = []
    for index, week in enumerate(weeks):
        days = week.get("days", [])
        count = sum(int(day.get("count", 0)) for day in days)
        first_day = week.get("first_day") or (days[0].get("date", "") if days else "")
        last_day = days[-1].get("date", "") if days else first_day
        totals.append({"index": index, "first_day": first_day, "last_day": last_day, "count": count})
    return totals


def _calendar_month_labels(calendar: dict) -> list[tuple[int, str]]:
    weeks = calendar.get("weeks") or []
    months = calendar.get("months") or []
    labels: list[tuple[int, str]] = []

    for month in months:
        first_day = month.get("first_day", "")
        name = (month.get("name") or "")[:3].upper()
        year = int(month.get("year") or 0)
        target_index = None

        # Prefer the exact GitHub firstDay anchor when it falls inside the returned calendar.
        for wi, week in enumerate(weeks):
            if any(day.get("date") == first_day for day in week.get("days", [])):
                target_index = wi
                break

        # The first calendar month can begin before the 53-week window. Anchor it to
        # the first returned day that belongs to GitHub's canonical month instead.
        if target_index is None:
            for wi, week in enumerate(weeks):
                for day in week.get("days", []):
                    try:
                        parsed = dt.date.fromisoformat(day.get("date", ""))
                    except ValueError:
                        continue
                    if parsed.year == year and parsed.strftime("%B") == month.get("name"):
                        target_index = wi
                        break
                if target_index is not None:
                    break

        if target_index is not None and name:
            # GitHub can return a one-day partial month at the left edge. If two
            # month anchors land in the same visual week, prefer the later month
            # so labels never collide (for example AUG/SEP on the same column).
            if labels and labels[-1][0] == target_index:
                labels[-1] = (target_index, name)
            else:
                labels.append((target_index, name))

    return labels


def _calendar_summary(weeks: list[dict]) -> dict:
    weekly = _weekly_totals(weeks)
    month_counts: dict[str, int] = {}
    active_days = 0
    for week in weeks:
        for day in week.get("days", []):
            count = int(day.get("count", 0))
            if count > 0:
                active_days += 1
            value = day.get("date", "")
            if len(value) >= 7:
                month_counts[value[:7]] = month_counts.get(value[:7], 0) + count

    best_week = max(weekly, key=lambda item: item["count"], default={"count": 0, "first_day": "", "last_day": ""})
    best_month_key, best_month_count = max(month_counts.items(), key=lambda item: item[1], default=("", 0))
    best_month_label = "—"
    if best_month_key:
        try:
            best_month_label = dt.datetime.strptime(best_month_key, "%Y-%m").strftime("%b %Y").upper()
        except ValueError:
            best_month_label = best_month_key.upper()

    return {
        "best_week_count": int(best_week.get("count", 0)),
        "best_week_first_day": best_week.get("first_day", ""),
        "best_week_last_day": best_week.get("last_day", ""),
        "best_month_count": int(best_month_count),
        "best_month_label": best_month_label,
        "active_days": active_days,
        "active_weeks": sum(1 for item in weekly if item["count"] > 0),
    }

def _repo_lookup(data: dict, name: str) -> dict:
    for repo in data.get("repositories", []):
        if repo.get("name", "").lower() == name.lower():
            return repo
    return {"name": name, "description": "", "stars": 0, "forks": 0, "language": "", "updated_at": ""}


def _format_date(value: str) -> str:
    if not value:
        return "—"
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.strftime("%b %Y").upper()
    except ValueError:
        return "—"


def _draw_footer_rule(frame: Image.Image, theme: MotionTheme, y: int, alpha: int = 255) -> None:
    _line(frame, [(46, y), (1154, y)], theme.border, alpha, 1)


def render_hero_frames(data: dict, config: dict, theme: MotionTheme, frame_count: int = 36) -> list[Image.Image]:
    height = 430
    days = _active_days(data)
    nodes = []
    for day in days[:64]:
        x, y = _deterministic_point(day["date"], 80, 1120, 72, 300)
        nodes.append((x, y, int(day["count"]), day["date"]))
    if not nodes:
        nodes = [(180, 150, 1, "seed"), (520, 100, 1, "seed-2"), (940, 220, 1, "seed-3")]

    frames: list[Image.Image] = []
    for i in range(frame_count):
        t = i / (frame_count - 1)
        master_alpha = _fade_loop(t)
        frame = _new_frame(height, theme)

        _alpha_text(frame, (48, 32), "BITREON / SYSTEMS", size=11, color=theme.muted, alpha=int(220 * master_alpha), bold=True, mono=True, tracking=2)
        _alpha_text(frame, (1152, 32), "GITHUB", size=10, color=theme.quiet, alpha=int(190 * master_alpha), bold=True, mono=True, anchor="ra")

        edge_reveal = _window(t, 0.10, 0.36) * master_alpha
        for idx in range(1, len(nodes)):
            if idx % 2 == 0:
                continue
            a = nodes[idx - 1]
            b = nodes[idx]
            local = _window(t, 0.10 + (idx / max(1, len(nodes))) * 0.15, 0.30 + (idx / max(1, len(nodes))) * 0.16)
            _line(frame, [(a[0], a[1]), (b[0], b[1])], theme.border, int(105 * edge_reveal * local), 1)

        max_count = max(n[2] for n in nodes) or 1
        for idx, (x, y, count, date) in enumerate(nodes):
            start = 0.04 + (idx / max(1, len(nodes))) * 0.19
            reveal = _window(t, start, start + 0.11) * master_alpha
            if reveal <= 0:
                continue
            # 1–2px orbital drift keeps the topology alive without decorative bouncing.
            phase = idx * 0.73
            dx = math.sin(t * math.tau + phase) * 1.7
            dy = math.cos(t * math.tau * 0.8 + phase) * 1.2
            px, py = x + dx, y + dy
            intensity = min(1.0, math.sqrt(count / max_count))
            radius = 2.0 + intensity * 3.8
            _circle(frame, (px, py), radius + 3 * (1 - reveal), theme.accent, int((80 + 155 * intensity) * reveal))
            if count >= max_count * 0.4:
                _circle(frame, (px, py), radius + 8, theme.accent, int(24 * reveal), outline=theme.accent, outline_alpha=int(36 * reveal))

        # A single restrained scan travels through the real-activity topology.
        scan_t = (t - 0.22) / 0.32
        if 0 <= scan_t <= 1 and len(nodes) > 1:
            pos = scan_t * (len(nodes) - 1)
            left = int(pos)
            frac = pos - left
            if left < len(nodes) - 1:
                ax, ay, *_ = nodes[left]
                bx, by, *_ = nodes[left + 1]
                sx = ax + (bx - ax) * frac
                sy = ay + (by - ay) * frac
                _circle(frame, (sx, sy), 5, theme.fg, int(220 * master_alpha))
                _circle(frame, (sx, sy), 14, theme.accent, int(42 * master_alpha), outline=theme.accent, outline_alpha=int(70 * master_alpha))

        title_reveal = _window(t, 0.30, 0.50) * master_alpha
        if title_reveal:
            # quiet backing field so the wordmark remains readable above the topology
            _rounded(frame, (46, 160, 785, 316), 22, theme.bg, alpha=int(225 * title_reveal))
            _alpha_text(frame, (60, 164), "BITREON", size=82, color=theme.fg, alpha=int(255 * title_reveal), bold=True, tracking=-3)
            _alpha_text(
                frame,
                (64, 265),
                "I build systems that make software easier to understand.",
                size=18,
                color=theme.muted,
                alpha=int(235 * title_reveal),
            )
            _alpha_text(frame, (64, 304), "CODE  /  DESIGN  /  AGENT INFRASTRUCTURE", size=10, color=theme.quiet, alpha=int(215 * title_reveal), bold=True, mono=True, tracking=1.2)

        _draw_footer_rule(frame, theme, 382, int(255 * master_alpha))
        _alpha_text(frame, (48, 397), f"@{data['profile']['login']}", size=10, color=theme.quiet, alpha=int(210 * master_alpha), bold=True, mono=True)
        _alpha_text(frame, (1152, 397), f"{data['calendar']['total']} CONTRIBUTIONS / 12 MONTHS", size=10, color=theme.quiet, alpha=int(210 * master_alpha), bold=True, mono=True, anchor="ra", tracking=0.6)
        frames.append(frame.convert("RGB"))
    return frames


def _draw_repo_meta(frame: Image.Image, repo: dict, theme: MotionTheme, y: int, alpha: int) -> None:
    _alpha_text(frame, (48, y), f"{repo.get('language') or '—'}", size=10, color=theme.muted, alpha=alpha, bold=True, mono=True)
    _alpha_text(frame, (210, y), f"STARS {repo.get('stars', 0)}", size=10, color=theme.muted, alpha=alpha, bold=True, mono=True)
    _alpha_text(frame, (330, y), f"FORKS {repo.get('forks', 0)}", size=10, color=theme.muted, alpha=alpha, bold=True, mono=True)
    _alpha_text(frame, (1152, y), f"UPDATED {_format_date(repo.get('updated_at') or '')}", size=10, color=theme.quiet, alpha=alpha, bold=True, mono=True, anchor="ra", tracking=0.6)


def render_mnestis_frames(data: dict, config: dict, theme: MotionTheme, frame_count: int = 40) -> list[Image.Image]:
    repo = _repo_lookup(data, "Mnestis")
    height = 300
    pipeline = [
        (650, 91, "REPOSITORY"),
        (786, 91, "PARSE"),
        (906, 91, "GRAPH"),
        (1018, 91, "EVIDENCE"),
        (1110, 91, "ANSWER"),
    ]
    frames: list[Image.Image] = []
    for i in range(frame_count):
        t = i / (frame_count - 1)
        fade = _fade_loop(t)
        frame = _new_frame(height, theme)
        reveal = _window(t, 0.04, 0.24) * fade

        _alpha_text(frame, (48, 32), "01 / SELECTED SYSTEM", size=10, color=theme.quiet, alpha=int(210 * fade), bold=True, mono=True, tracking=1.4)
        _alpha_text(frame, (48, 74), repo.get("name", "Mnestis"), size=40, color=theme.fg, alpha=int(255 * reveal), bold=True, tracking=-1.3)
        desc = repo.get("description") or "The memory layer for software — AI-ready codebase analysis"
        _alpha_text(frame, (50, 123), desc[:62], size=14, color=theme.muted, alpha=int(230 * reveal))
        _alpha_text(frame, (50, 151), "repository → architecture → evidence → answer", size=11, color=theme.quiet, alpha=int(210 * reveal), bold=True, mono=True, tracking=0.5)

        # pipeline spine
        _line(frame, [(650, 109), (1126, 109)], theme.border, int(170 * reveal), 2)
        for idx, (x, y, label) in enumerate(pipeline):
            local = _window(t, 0.08 + idx * 0.045, 0.24 + idx * 0.045) * fade
            _circle(frame, (x, y), 5.5, theme.bg, int(255 * local), outline=theme.accent if idx in (0, 2, 4) else theme.border, outline_alpha=int(220 * local), width=2)
            _alpha_text(frame, (x, 126), label, size=8, color=theme.quiet, alpha=int(190 * local), bold=True, mono=True, anchor="ma", tracking=0.7)

        # moving evidence packets
        travel = max(0.0, min(1.0, (t - 0.18) / 0.52))
        for lag in (0.0, 0.13, 0.26):
            p = travel - lag
            if 0 <= p <= 1:
                x = 650 + (1126 - 650) * _ease(p)
                _circle(frame, (x, 109), 5, theme.accent, int(235 * fade))
                _circle(frame, (x, 109), 13, theme.accent, int(35 * fade), outline=theme.accent, outline_alpha=int(55 * fade))

        # graph specimen below pipeline
        graph_alpha = _window(t, 0.28, 0.46) * fade
        graph_nodes = [(716, 200), (800, 175), (875, 210), (948, 168), (1030, 206), (1102, 181)]
        for a, b in zip(graph_nodes, graph_nodes[1:]):
            _line(frame, [a, b], theme.border, int(130 * graph_alpha), 1)
        for idx, pt in enumerate(graph_nodes):
            _circle(frame, pt, 4 if idx not in (2, 4) else 6, theme.accent if idx in (2, 4) else theme.bg, int(235 * graph_alpha), outline=theme.accent if idx in (2, 4) else theme.border, outline_alpha=int(200 * graph_alpha), width=1)

        _draw_footer_rule(frame, theme, 250, int(255 * fade))
        _draw_repo_meta(frame, repo, theme, 266, int(220 * fade))
        frames.append(frame.convert("RGB"))
    return frames


def render_rune_frames(data: dict, config: dict, theme: MotionTheme, frame_count: int = 48) -> list[Image.Image]:
    repo = _repo_lookup(data, "Rune")
    height = 300
    sources = [(665, 82, "CODEX"), (665, 133, "CLAUDE"), (665, 184, "OPENROUTER")]
    harness = (897, 133)
    output = (1110, 133)
    frames: list[Image.Image] = []
    for i in range(frame_count):
        t = i / (frame_count - 1)
        fade = _fade_loop(t)
        frame = _new_frame(height, theme)
        reveal = _window(t, 0.04, 0.24) * fade

        _alpha_text(frame, (48, 32), "02 / SELECTED SYSTEM", size=10, color=theme.quiet, alpha=int(210 * fade), bold=True, mono=True, tracking=1.4)
        _alpha_text(frame, (48, 74), repo.get("name", "Rune"), size=40, color=theme.fg, alpha=int(255 * reveal), bold=True, tracking=-1.3)
        _alpha_text(frame, (50, 123), "Bring the model. Keep the harness. Control the execution.", size=14, color=theme.muted, alpha=int(230 * reveal))
        _alpha_text(frame, (50, 151), "providers → one execution contract", size=11, color=theme.quiet, alpha=int(210 * reveal), bold=True, mono=True, tracking=0.5)

        diagram = _window(t, 0.10, 0.30) * fade
        for x, y, label in sources:
            _rounded(frame, (x - 58, y - 17, x + 58, y + 17), 9, theme.bg, outline=theme.border, alpha=int(255 * diagram), outline_alpha=int(190 * diagram))
            _alpha_text(frame, (x, y - 7), label, size=9, color=theme.muted, alpha=int(220 * diagram), bold=True, mono=True, anchor="ma", tracking=0.7)
            _line(frame, [(x + 58, y), (harness[0] - 57, harness[1])], theme.border, int(145 * diagram), 1)

        _rounded(frame, (harness[0] - 57, harness[1] - 33, harness[0] + 57, harness[1] + 33), 14, theme.accent_soft, outline=theme.accent, alpha=int(255 * diagram), outline_alpha=int(210 * diagram), width=2)
        _alpha_text(frame, (harness[0], harness[1] - 10), "RUNE", size=13, color=theme.fg, alpha=int(245 * diagram), bold=True, mono=True, anchor="ma", tracking=1.2)
        _alpha_text(frame, (harness[0], harness[1] + 12), "HARNESS", size=8, color=theme.muted, alpha=int(210 * diagram), bold=True, mono=True, anchor="ma", tracking=0.8)
        _line(frame, [(harness[0] + 57, harness[1]), (output[0] - 54, output[1])], theme.border, int(145 * diagram), 1)
        _rounded(frame, (output[0] - 54, output[1] - 26, output[0] + 54, output[1] + 26), 12, theme.bg, outline=theme.border, alpha=int(255 * diagram), outline_alpha=int(190 * diagram))
        _alpha_text(frame, (output[0], output[1] - 7), "EXECUTE", size=9, color=theme.fg, alpha=int(225 * diagram), bold=True, mono=True, anchor="ma", tracking=0.8)

        # packets converge from providers, then exit as one controlled lane
        travel = max(0.0, min(1.0, (t - 0.22) / 0.46))
        for idx, (x, y, _) in enumerate(sources):
            p = travel - idx * 0.07
            if 0 <= p <= 0.58:
                lp = p / 0.58
                px = x + 58 + (harness[0] - 57 - (x + 58)) * _ease(lp)
                py = y + (harness[1] - y) * _ease(lp)
                _circle(frame, (px, py), 4.5, theme.accent, int(225 * fade))
        out_p = (travel - 0.46) / 0.54
        if 0 <= out_p <= 1:
            px = harness[0] + 57 + (output[0] - 54 - (harness[0] + 57)) * _ease(out_p)
            _circle(frame, (px, harness[1]), 5, theme.fg, int(235 * fade))
            _circle(frame, (px, harness[1]), 12, theme.accent, int(30 * fade), outline=theme.accent, outline_alpha=int(50 * fade))

        _draw_footer_rule(frame, theme, 250, int(255 * fade))
        _draw_repo_meta(frame, repo, theme, 266, int(220 * fade))
        frames.append(frame.convert("RGB"))
    return frames


def render_contribution_frames(data: dict, config: dict, theme: MotionTheme, frame_count: int = 42) -> list[Image.Image]:
    height = 448
    weeks = data["calendar"]["weeks"]
    all_days = [day for week in weeks for day in week["days"]]
    max_count = max((int(day.get("count", 0)) for day in all_days), default=1) or 1
    peak = max(all_days, key=lambda day: int(day.get("count", 0)), default={"count": 0, "date": ""})
    weekly = _weekly_totals(weeks)
    month_labels = _calendar_month_labels(data["calendar"])
    summary = _calendar_summary(weeks)
    max_week = max((item["count"] for item in weekly), default=1) or 1

    frames: list[Image.Image] = []
    grid_x, grid_y = 74, 150
    cell, gap = 16, 4
    step = cell + gap
    grid_right = grid_x + (max(1, len(weeks)) - 1) * step + cell
    grid_bottom = grid_y + 6 * step + cell
    weekly_base_y = 338
    weekly_max_h = 28

    for i in range(frame_count):
        t = i / (frame_count - 1)
        fade = _fade_loop(t)
        frame = _new_frame(height, theme)
        reveal = _window(t, 0.04, 0.20) * fade

        _alpha_text(frame, (48, 30), "BUILD ACTIVITY / GITHUB", size=10, color=theme.quiet, alpha=int(210 * fade), bold=True, mono=True, tracking=1.5)
        # The real GitHub total is visible from frame one. Only the calendar cells animate;
        # the headline number never performs a fake 0 → total count-up.
        total_display = int(data["calendar"]["total"])
        _alpha_text(frame, (48, 64), f"{total_display}", size=38, color=theme.fg, alpha=int(255 * fade), bold=True)
        _alpha_text(frame, (128, 75), "CONTRIBUTIONS / LAST 12 MONTHS", size=10, color=theme.muted, alpha=int(210 * reveal), bold=True, mono=True, tracking=0.8)

        peak_label = peak.get("date", "")
        if peak_label:
            try:
                peak_label = dt.date.fromisoformat(peak_label).strftime("%b %d").upper()
            except ValueError:
                pass
        _alpha_text(frame, (1152, 75), f"PEAK DAY {peak.get('count', 0)} / {peak_label}", size=9, color=theme.quiet, alpha=int(205 * reveal), bold=True, mono=True, anchor="ra", tracking=0.45)

        # Month anchors use the first real day-of-month returned by GitHub.
        month_alpha = _window(t, 0.10, 0.30) * fade
        for wi, label in month_labels:
            x = grid_x + wi * step
            if x > grid_right - 6:
                continue
            _alpha_text(frame, (x, 118), label, size=8, color=theme.quiet, alpha=int(190 * month_alpha), bold=True, mono=True, tracking=0.5)

        # Familiar GitHub rhythm, but with full labels rather than single letters.
        _alpha_text(frame, (20, grid_y + 1 * step + 1), "MON", size=7, color=theme.quiet, alpha=int(160 * reveal), bold=True, mono=True, tracking=0.4)
        _alpha_text(frame, (20, grid_y + 3 * step + 1), "WED", size=7, color=theme.quiet, alpha=int(160 * reveal), bold=True, mono=True, tracking=0.4)
        _alpha_text(frame, (20, grid_y + 5 * step + 1), "FRI", size=7, color=theme.quiet, alpha=int(160 * reveal), bold=True, mono=True, tracking=0.4)

        weeks_revealed = _ease(max(0.0, min(1.0, (t - 0.14) / 0.48))) * max(1, len(weeks))
        for wi, week in enumerate(weeks):
            x = grid_x + wi * step
            week_alpha = max(0.0, min(1.0, weeks_revealed - wi)) * fade
            for day in week["days"]:
                weekday = int(day.get("weekday", 0))
                y = grid_y + weekday * step
                count = int(day.get("count", 0))
                if count <= 0:
                    color = theme.empty
                else:
                    intensity = min(1.0, math.sqrt(count / max_count))
                    color = _mix(theme.accent_soft, theme.accent, 0.25 + intensity * 0.75)
                    color = "#%02x%02x%02x" % color
                layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
                d = ImageDraw.Draw(layer)
                d.rounded_rectangle((x, y, x + cell, y + cell), radius=4, fill=_rgba(color, int(235 * week_alpha)))
                frame.alpha_composite(layer)

                age = weeks_revealed - wi
                if count > 0 and 0.15 < age < 0.75:
                    pulse = 1 - abs(0.45 - age) / 0.30
                    radius = cell / 2 + 2 + min(8, math.sqrt(count)) * max(0, pulse)
                    _circle(frame, (x + cell / 2, y + cell / 2), radius, theme.accent, int(30 * max(0, pulse) * fade), outline=theme.accent, outline_alpha=int(42 * max(0, pulse) * fade))

        # Weekly volume mirrors the 53 calendar columns exactly. It is an aggregation, never synthetic activity.
        weekly_reveal = _window(t, 0.48, 0.72) * fade
        _alpha_text(frame, (20, weekly_base_y - 9), "WK", size=7, color=theme.quiet, alpha=int(150 * weekly_reveal), bold=True, mono=True, tracking=0.4)
        _line(frame, [(grid_x, weekly_base_y), (grid_right, weekly_base_y)], theme.border, int(145 * weekly_reveal), 1)
        for item in weekly:
            wi = int(item["index"])
            count = int(item["count"])
            x = grid_x + wi * step + cell / 2
            if count <= 0:
                bar_h = 2
                bar_color = theme.border
                alpha = int(105 * weekly_reveal)
            else:
                bar_h = 4 + math.sqrt(count / max_week) * (weekly_max_h - 4)
                bar_color = theme.accent
                alpha = int((120 + 115 * math.sqrt(count / max_week)) * weekly_reveal)
            _line(frame, [(x, weekly_base_y), (x, weekly_base_y - bar_h)], bar_color, alpha, 3 if count > 0 else 1)

        # Chronology scan ties the day grid and weekly volume together.
        if 0.22 <= t <= 0.67:
            scan = (t - 0.22) / 0.45
            sx = grid_x + scan * (grid_right - grid_x)
            _line(frame, [(sx, 137), (sx, weekly_base_y + 4)], theme.accent, int(72 * fade), 1)

        stats_reveal = _window(t, 0.58, 0.78) * fade
        best_week_label = "—"
        try:
            start = dt.date.fromisoformat(summary["best_week_first_day"])
            end = dt.date.fromisoformat(summary["best_week_last_day"])
            best_week_label = f"{start.strftime('%b %d').upper()}–{end.strftime('%d')}"
        except ValueError:
            pass

        _draw_footer_rule(frame, theme, 378, int(240 * fade))
        stat_y = 394
        _alpha_text(frame, (48, stat_y), "BEST WEEK", size=8, color=theme.quiet, alpha=int(190 * stats_reveal), bold=True, mono=True, tracking=0.7)
        _alpha_text(frame, (48, stat_y + 17), f"{summary['best_week_count']} / {best_week_label}", size=11, color=theme.fg, alpha=int(235 * stats_reveal), bold=True, mono=True, tracking=0.2)

        _alpha_text(frame, (385, stat_y), "BEST MONTH", size=8, color=theme.quiet, alpha=int(190 * stats_reveal), bold=True, mono=True, tracking=0.7)
        _alpha_text(frame, (385, stat_y + 17), f"{summary['best_month_count']} / {summary['best_month_label']}", size=11, color=theme.fg, alpha=int(235 * stats_reveal), bold=True, mono=True, tracking=0.2)

        _alpha_text(frame, (735, stat_y), "ACTIVE", size=8, color=theme.quiet, alpha=int(190 * stats_reveal), bold=True, mono=True, tracking=0.7)
        _alpha_text(frame, (735, stat_y + 17), f"{summary['active_days']} DAYS / {summary['active_weeks']} WEEKS", size=11, color=theme.fg, alpha=int(235 * stats_reveal), bold=True, mono=True, tracking=0.2)

        _alpha_text(frame, (1152, stat_y + 17), "EXACT GITHUB GRAPHQL", size=8, color=theme.quiet, alpha=int(185 * stats_reveal), bold=True, mono=True, anchor="ra", tracking=0.55)
        frames.append(frame.convert("RGB"))
    return frames


def _save_animation(frames: list[Image.Image], gif_path: Path, png_path: Path, *, comment: str) -> None:
    gif_path.parent.mkdir(parents=True, exist_ok=True)
    # Final-frame fallback uses the calm hold frame, not the loop fade-out.
    hold_index = max(0, min(len(frames) - 1, round((len(frames) - 1) * 0.82)))
    frames[hold_index].save(png_path, format="PNG", optimize=False)

    # One deterministic palette avoids expensive per-frame median-cut quantization
    # and prevents color flicker between GIF frames.
    palette = Image.new("P", (1, 1))
    anchors = [
        (8, 9, 11), (17, 18, 20), (41, 44, 49), (105, 109, 117),
        (160, 163, 170), (244, 244, 239), (247, 247, 244),
        (104, 102, 245), (170, 168, 255), (232, 232, 255),
    ]
    entries = []
    for i in range(256):
        a = anchors[(i * (len(anchors) - 1)) // 255]
        b = anchors[min(len(anchors) - 1, (i * (len(anchors) - 1)) // 255 + 1)]
        local = ((i * (len(anchors) - 1)) % 255) / 255
        entries.extend([
            round(a[0] + (b[0] - a[0]) * local),
            round(a[1] + (b[1] - a[1]) * local),
            round(a[2] + (b[2] - a[2]) * local),
        ])
    palette.putpalette(entries[:768])
    encoded_frames = []
    motion_clock = [_rgb("#6866F5"), _rgb("#AAA8FF"), _rgb("#292C31")]
    for index, frame in enumerate(frames):
        stamped = frame.copy()
        # One corner pixel is a codec heartbeat: visually imperceptible at 1200px wide,
        # but it prevents GIF encoders from collapsing adjacent frames into long pauses.
        stamped.putpixel((stamped.width - 1, stamped.height - 1), motion_clock[index % len(motion_clock)])
        encoded_frames.append(stamped.quantize(palette=palette, dither=Image.Dither.NONE))
    palette_frames = encoded_frames
    palette_frames[0].save(
        gif_path,
        save_all=True,
        append_images=palette_frames[1:],
        duration=FPS_MS,
        loop=0,
        optimize=False,
        disposal=2,
        comment=comment.encode("utf-8"),
    )


def _save_static_frame(frames: list[Image.Image], png_path: Path) -> None:
    png_path.parent.mkdir(parents=True, exist_ok=True)
    hold_index = max(0, min(len(frames) - 1, round((len(frames) - 1) * 0.82)))
    frames[hold_index].save(png_path, format="PNG", optimize=True)


def render_motion_assets(data: dict, config: dict, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Remove legacy project GIFs so a refresh cannot leave heavyweight animations
    # behind after v4 switches those surfaces to static, click-through project art.
    for stale in output_dir.glob("*.gif"):
        if stale.stem.split("-")[0] in {"mnestis", "rune"}:
            stale.unlink()

    written: list[Path] = []
    animated = [
        ("hero", render_hero_frames, "identity topology derived from active GitHub contribution days"),
        ("contributions", render_contribution_frames, "GitHub contributionCalendar exact daily counts"),
    ]
    static = [
        ("mnestis", render_mnestis_frames),
        ("rune", render_rune_frames),
    ]

    for theme_name, theme in THEMES.items():
        for asset_name, renderer, source in animated:
            frames = renderer(data, config, theme)
            gif_path = output_dir / f"{asset_name}-{theme_name}.gif"
            png_path = output_dir / f"{asset_name}-{theme_name}.png"
            comment = (
                f"bitreonx profile; source={source}; "
                f"totalContributions={data['calendar']['total']}; "
                f"calendarThrough={data['calendar'].get('through', '')}"
            )
            _save_animation(frames, gif_path, png_path, comment=comment)
            written.extend([gif_path, png_path])

        for asset_name, renderer in static:
            frames = renderer(data, config, theme)
            png_path = output_dir / f"{asset_name}-{theme_name}.png"
            _save_static_frame(frames, png_path)
            written.append(png_path)

    return sorted(written, key=lambda p: p.name)

