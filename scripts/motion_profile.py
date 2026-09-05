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
FPS_MS = 140


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


def render_hero_frames(data: dict, config: dict, theme: MotionTheme, frame_count: int = 40) -> list[Image.Image]:
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


def render_contribution_frames(data: dict, config: dict, theme: MotionTheme, frame_count: int = 48) -> list[Image.Image]:
    height = 360
    weeks = data["calendar"]["weeks"]
    all_days = [day for week in weeks for day in week["days"]]
    max_count = max((int(day.get("count", 0)) for day in all_days), default=1) or 1
    peak = max(all_days, key=lambda day: int(day.get("count", 0)), default={"count": 0, "date": ""})
    frames: list[Image.Image] = []
    grid_x, grid_y = 52, 124
    cell, gap = 14, 3

    for i in range(frame_count):
        t = i / (frame_count - 1)
        fade = _fade_loop(t)
        frame = _new_frame(height, theme)
        reveal = _window(t, 0.04, 0.20) * fade

        _alpha_text(frame, (48, 34), "BUILD ACTIVITY / GITHUB", size=10, color=theme.quiet, alpha=int(210 * fade), bold=True, mono=True, tracking=1.5)
        resolved = _window(t, 0.55, 0.74)
        total_display = round(data["calendar"]["total"] * resolved)
        _alpha_text(frame, (48, 70), f"{total_display}", size=38, color=theme.fg, alpha=int(255 * reveal), bold=True)
        _alpha_text(frame, (128, 80), "CONTRIBUTIONS / LAST 12 MONTHS", size=10, color=theme.muted, alpha=int(210 * reveal), bold=True, mono=True, tracking=0.8)
        peak_label = peak.get("date", "")
        if peak_label:
            try:
                peak_label = dt.date.fromisoformat(peak_label).strftime("%b %d").upper()
            except ValueError:
                pass
        _alpha_text(frame, (1152, 80), f"PEAK {peak.get('count', 0)} / {peak_label}", size=9, color=theme.quiet, alpha=int(205 * reveal), bold=True, mono=True, anchor="ra", tracking=0.6)

        # weekday labels only where useful
        _alpha_text(frame, (14, grid_y + 1 * (cell + gap) - 4), "M", size=8, color=theme.quiet, alpha=int(155 * reveal), bold=True, mono=True)
        _alpha_text(frame, (14, grid_y + 3 * (cell + gap) - 4), "W", size=8, color=theme.quiet, alpha=int(155 * reveal), bold=True, mono=True)
        _alpha_text(frame, (14, grid_y + 5 * (cell + gap) - 4), "F", size=8, color=theme.quiet, alpha=int(155 * reveal), bold=True, mono=True)

        weeks_revealed = _ease(max(0.0, min(1.0, (t - 0.14) / 0.48))) * max(1, len(weeks))
        for wi, week in enumerate(weeks):
            x = grid_x + wi * (cell + gap)
            week_alpha = max(0.0, min(1.0, weeks_revealed - wi)) * fade
            for day in week["days"]:
                weekday = int(day.get("weekday", 0))
                y = grid_y + weekday * (cell + gap)
                count = int(day.get("count", 0))
                if count <= 0:
                    color = theme.empty
                else:
                    intensity = min(1.0, math.sqrt(count / max_count))
                    color = _mix(theme.accent_soft, theme.accent, 0.28 + intensity * 0.72)
                    color = "#%02x%02x%02x" % color
                layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
                d = ImageDraw.Draw(layer)
                d.rounded_rectangle((x, y, x + cell, y + cell), radius=3, fill=_rgba(color, int(230 * week_alpha)))
                frame.alpha_composite(layer)

                # one-frame wake pulse when a week arrives; count controls radius.
                age = weeks_revealed - wi
                if count > 0 and 0.15 < age < 0.75:
                    pulse = 1 - abs(0.45 - age) / 0.30
                    radius = cell / 2 + 2 + min(8, math.sqrt(count)) * max(0, pulse)
                    _circle(frame, (x + cell / 2, y + cell / 2), radius, theme.accent, int(34 * max(0, pulse) * fade), outline=theme.accent, outline_alpha=int(45 * max(0, pulse) * fade))

        # scan marker makes chronology legible without inventing activity
        if 0.22 <= t <= 0.67:
            scan = (t - 0.22) / 0.45
            sx = grid_x + scan * ((len(weeks) - 1) * (cell + gap) + cell)
            _line(frame, [(sx, grid_y - 8), (sx, grid_y + 7 * (cell + gap) - gap + 8)], theme.accent, int(78 * fade), 1)

        _draw_footer_rule(frame, theme, 296, int(255 * fade))
        _alpha_text(frame, (48, 314), "EXACT DAILY COUNTS / GITHUB GRAPHQL", size=9, color=theme.quiet, alpha=int(205 * fade), bold=True, mono=True, tracking=0.65)
        _alpha_text(frame, (1152, 314), "NO EVENT WEIGHTING", size=9, color=theme.quiet, alpha=int(205 * fade), bold=True, mono=True, anchor="ra", tracking=0.65)
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
    palette_frames = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
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


def render_motion_assets(data: dict, config: dict, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    renderers = [
        ("hero", render_hero_frames, "identity topology derived from active GitHub contribution days"),
        ("mnestis", render_mnestis_frames, "Mnestis repository system flow"),
        ("rune", render_rune_frames, "Rune orchestration system flow"),
        ("contributions", render_contribution_frames, "GitHub contributionCalendar exact daily counts"),
    ]
    for theme_name, theme in THEMES.items():
        for asset_name, renderer, source in renderers:
            frames = renderer(data, config, theme)
            gif_path = output_dir / f"{asset_name}-{theme_name}.gif"
            png_path = output_dir / f"{asset_name}-{theme_name}.png"
            comment = f"bitreonx profile; source={source}; totalContributions={data['calendar']['total']}"
            _save_animation(frames, gif_path, png_path, comment=comment)
            written.extend([gif_path, png_path])
    return sorted(written, key=lambda p: p.name)
