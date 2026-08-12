#!/usr/bin/env python3
"""Render the public-event signal used by the @bitreonx GitHub profile.

Data boundary:
- https://api.github.com/users/{username}/events/public

No private contribution calendar is queried.
No third-party profile-card service is used.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

BG = "#070A0F"
SURFACE = "#0B1118"
SURFACE_2 = "#0E1620"
GRID = "#17222D"
MUTED = "#7F8B99"
TEXT = "#E6EDF3"
GREEN = "#72F1B8"
CYAN = "#86D7FF"
VIOLET = "#B794F4"
AMBER = "#F6C177"
RED = "#FF7B72"
FONT = 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace'

EVENT_WEIGHTS = {
    "PushEvent": 3,
    "PullRequestEvent": 2,
    "PullRequestReviewEvent": 1,
    "IssuesEvent": 1,
    "IssueCommentEvent": 1,
    "CreateEvent": 1,
    "ReleaseEvent": 3,
}


def request_bytes(url: str, user_agent: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": user_agent,
        },
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read()


def fetch_public_events(username: str) -> list[dict]:
    events: list[dict] = []
    for page in range(1, 4):
        url = f"https://api.github.com/users/{username}/events/public?per_page=100&page={page}"
        batch = json.loads(request_bytes(url, f"{username}-profile-renderer").decode("utf-8"))
        if not batch:
            break
        events.extend(batch)
    return events


def esc(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def aligned_start(today: dt.date) -> dt.date:
    return today - dt.timedelta(days=today.weekday() + 12 * 7)


def activity(events: Iterable[dict], start: dt.date, end: dt.date):
    score: defaultdict[dt.date, int] = defaultdict(int)
    raw_days: Counter[dt.date] = Counter()
    kinds: Counter[str] = Counter()

    for event in events:
        created_at = event.get("created_at")
        if not created_at:
            continue
        try:
            day = dt.datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
        except ValueError:
            continue
        if not start <= day <= end:
            continue

        kind = event.get("type", "OtherEvent")
        kinds[kind] += 1
        raw_days[day] += 1

        weight = EVENT_WEIGHTS.get(kind, 1)
        if kind == "PushEvent":
            payload = event.get("payload") or {}
            size = payload.get("size") or 1
            try:
                weight = max(1, min(int(size), 5))
            except (TypeError, ValueError):
                weight = 1
        score[day] += weight

    return score, raw_days, kinds


def render_signal(username: str, events: list[dict], out: Path, now: dt.datetime | None = None) -> None:
    now = now or dt.datetime.now(dt.timezone.utc)
    today = now.date()
    start = aligned_start(today)
    end = start + dt.timedelta(days=90)
    score, raw_days, kinds = activity(events, start, end)

    values = [value for value in score.values() if value > 0]
    maximum = max(values) if values else 0

    def level(value: int) -> int:
        if value <= 0 or maximum <= 0:
            return 0
        ratio = value / maximum
        if ratio <= 0.25:
            return 1
        if ratio <= 0.50:
            return 2
        if ratio <= 0.75:
            return 3
        return 4

    colors = [SURFACE_2, "#183528", "#1E5B42", "#2F9267", GREEN]
    cells: list[str] = []

    x0, y0, dx, dy = 555, 110, 40, 37
    for week in range(13):
        for day_index in range(7):
            day = start + dt.timedelta(days=week * 7 + day_index)
            lvl = level(score.get(day, 0))
            x = x0 + week * dx
            y = y0 + day_index * dy
            stroke = GRID if lvl == 0 else colors[lvl]
            cells.append(
                f'<rect x="{x}" y="{y}" width="26" height="26" rx="6" '
                f'fill="{colors[lvl]}" stroke="{stroke}">'
                f"<title>{day.isoformat()}: {raw_days.get(day, 0)} public events</title>"
                "</rect>"
            )

    total = sum(raw_days.values())
    active_days = sum(1 for count in raw_days.values() if count)
    pushes = kinds.get("PushEvent", 0)
    pull_requests = kinds.get("PullRequestEvent", 0)
    releases = kinds.get("ReleaseEvent", 0)
    sync = now.strftime("%Y-%m-%d %H:%M UTC")

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="410" viewBox="0 0 1200 410" role="img" aria-labelledby="title desc">
<title id="title">{esc(username)} public build pulse</title>
<desc id="desc">Thirteen-week visualization of visible public GitHub events for {esc(username)}.</desc>
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BG}"/><stop offset="1" stop-color="#091018"/></linearGradient>
</defs>
<style>
.mono{{font-family:{FONT}}}
.live{{animation:pulse 2s ease-in-out infinite}}
@keyframes pulse{{0%,100%{{opacity:.45}}50%{{opacity:1}}}}
@media (prefers-reduced-motion:reduce){{.live{{animation:none}}}}
</style>
<rect width="1200" height="410" rx="22" fill="url(#bg)"/>
<rect x="1" y="1" width="1198" height="408" rx="21" fill="none" stroke="{GRID}"/>
<text x="44" y="48" class="mono" font-size="13" letter-spacing="2" fill="{GREEN}">PUBLIC BUILD PULSE // 13 WEEKS</text>
<circle cx="963" cy="43" r="4" fill="{GREEN}" class="live"/>
<text x="1156" y="48" text-anchor="end" class="mono" font-size="11" fill="{GREEN}">LIVE // PUBLIC EVENTS ONLY</text>
<path d="M44 66H1156" stroke="{GRID}"/>

<g transform="translate(44 104)">
  <text y="20" class="mono" font-size="12" fill="{MUTED}">visible_events</text>
  <text x="190" y="20" class="mono" font-size="12" fill="{TEXT}">{total}</text>
  <text y="58" class="mono" font-size="12" fill="{MUTED}">active_days</text>
  <text x="190" y="58" class="mono" font-size="12" fill="{GREEN}">{active_days}</text>
  <text y="96" class="mono" font-size="12" fill="{MUTED}">push_events</text>
  <text x="190" y="96" class="mono" font-size="12" fill="{TEXT}">{pushes}</text>
  <text y="134" class="mono" font-size="12" fill="{MUTED}">pull_requests</text>
  <text x="190" y="134" class="mono" font-size="12" fill="{CYAN}">{pull_requests}</text>
  <text y="172" class="mono" font-size="12" fill="{MUTED}">releases</text>
  <text x="190" y="172" class="mono" font-size="12" fill="{VIOLET}">{releases}</text>
  <path d="M0 198H430" stroke="{GRID}"/>
  <text y="225" class="mono" font-size="10.5" fill="{MUTED}">signal ≠ contribution total // privacy boundary: public events</text>
</g>

{''.join(cells)}

<text x="555" y="385" class="mono" font-size="10.5" fill="{MUTED}">quiet</text>
<g transform="translate(605 373)">
  <rect width="13" height="13" rx="3" fill="{SURFACE_2}"/>
  <rect x="19" width="13" height="13" rx="3" fill="#183528"/>
  <rect x="38" width="13" height="13" rx="3" fill="#1E5B42"/>
  <rect x="57" width="13" height="13" rx="3" fill="#2F9267"/>
  <rect x="76" width="13" height="13" rx="3" fill="{GREEN}"/>
</g>
<text x="700" y="385" class="mono" font-size="10.5" fill="{MUTED}">loud</text>
<text x="1156" y="385" text-anchor="end" class="mono" font-size="10.5" fill="{MUTED}">sync: {esc(sync)}</text>
</svg>'''
    out.write_text(svg, encoding="utf-8")



def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="bitreonx")
    parser.add_argument("--output", default="assets/signal.svg")
    parser.add_argument("--events-json")
    parser.add_argument("--now", help="ISO timestamp for deterministic testing")
    args = parser.parse_args()

    if args.events_json:
        events = json.loads(Path(args.events_json).read_text(encoding="utf-8"))
    else:
        events = fetch_public_events(args.username)

    now = (
        dt.datetime.fromisoformat(args.now.replace("Z", "+00:00"))
        if args.now
        else dt.datetime.now(dt.timezone.utc)
    )
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    render_signal(args.username, events, output, now=now)
    print(f"rendered {output} for @{args.username} from {len(events)} public events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
