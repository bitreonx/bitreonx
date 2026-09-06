#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

GRAPHQL_URL = "https://api.github.com/graphql"
REST_USER_URL = "https://api.github.com/user"
QUERY = r'''
query Profile($login: String!) {
  viewer {
    login
  }
  user(login: $login) {
    login
    name
    bio
    url
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, orderBy: {field: UPDATED_AT, direction: DESC}) {
      totalCount
      nodes {
        name
        url
        description
        stargazerCount
        forkCount
        updatedAt
        isFork
        isArchived
        primaryLanguage { name color }
      }
    }
    contributionsCollection {
      hasAnyRestrictedContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        colors
        months {
          firstDay
          name
          totalWeeks
          year
        }
        weeks {
          firstDay
          contributionDays {
            color
            contributionCount
            contributionLevel
            date
            weekday
          }
        }
      }
    }
  }
}
'''.strip()


def load_profile_config(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("username"):
        raise ValueError("profile config requires username")
    if not isinstance(data.get("featured_repositories"), list):
        raise ValueError("profile config requires featured_repositories")
    return data


def _normalize_repo(repo: dict) -> dict:
    language = repo.get("primaryLanguage") or {}
    return {
        "name": repo.get("name", ""),
        "url": repo.get("url", ""),
        "description": repo.get("description") or "",
        "stars": int(repo.get("stargazerCount") or 0),
        "forks": int(repo.get("forkCount") or 0),
        "updated_at": repo.get("updatedAt") or "",
        "is_fork": bool(repo.get("isFork")),
        "is_archived": bool(repo.get("isArchived")),
        "language": language.get("name") or "",
        "language_color": language.get("color") or "#8b949e",
        "available": True,
    }


def normalize_graphql_payload(payload: dict, config: dict) -> dict:
    if payload.get("errors"):
        raise ValueError(f"GitHub GraphQL errors: {payload['errors']}")
    root = payload.get("data") or {}
    viewer = root.get("viewer") or {}
    viewer_login = viewer.get("login") or ""
    expected_login = config["username"]
    if viewer_login.lower() != expected_login.lower():
        raise ValueError(
            "GitHub authenticated GitHub user mismatch: "
            f"expected {expected_login}, got {viewer_login or 'unknown'}"
        )

    user = root.get("user")
    if not user:
        raise ValueError("GitHub payload is missing user")

    repositories = user.get("repositories") or {}
    nodes = repositories.get("nodes") or []
    by_name = {repo.get("name"): _normalize_repo(repo) for repo in nodes if repo.get("name")}
    featured = []
    for name in config.get("featured_repositories", []):
        repo = by_name.get(name)
        if repo is None:
            repo = {
                "name": name,
                "url": f"https://github.com/{config['username']}/{name}",
                "description": "Repository metadata unavailable during this refresh.",
                "stars": 0,
                "forks": 0,
                "updated_at": "",
                "is_fork": False,
                "is_archived": False,
                "language": "",
                "language_color": "#8b949e",
                "available": False,
            }
        featured.append(repo)

    collection = user.get("contributionsCollection") or {}
    calendar = collection.get("contributionCalendar")
    if not calendar:
        raise ValueError("GitHub payload is missing contribution calendar")

    months = []
    for month in calendar.get("months") or []:
        months.append({
            "first_day": month.get("firstDay", ""),
            "name": month.get("name", ""),
            "total_weeks": int(month.get("totalWeeks") or 0),
            "year": int(month.get("year") or 0),
        })

    weeks = []
    seen_dates: set[str] = set()
    daily_total = 0
    latest_date = ""
    for week in calendar.get("weeks") or []:
        days = []
        for day in week.get("contributionDays") or []:
            value = day.get("date", "")
            if value and value in seen_dates:
                raise ValueError(f"GitHub contribution calendar integrity error: duplicate day {value}")
            if value:
                seen_dates.add(value)
                latest_date = max(latest_date, value)
            count = int(day.get("contributionCount") or 0)
            daily_total += count
            days.append({
                "date": value,
                "weekday": int(day.get("weekday") or 0),
                "count": count,
                "level": day.get("contributionLevel") or "NONE",
                "color": day.get("color") or "#ebedf0",
            })
        weeks.append({"first_day": week.get("firstDay", ""), "days": days})

    github_total = int(calendar.get("totalContributions") or 0)
    if daily_total != github_total:
        raise ValueError(
            "GitHub contribution calendar integrity error: "
            f"daily counts sum to {daily_total}, but GitHub totalContributions is {github_total}"
        )

    return {
        "profile": {
            "login": user.get("login") or config["username"],
            "name": user.get("name") or config.get("display_name") or config["username"],
            "bio": user.get("bio") or config.get("headline") or "",
            "url": user.get("url") or f"https://github.com/{config['username']}",
            "followers": int((user.get("followers") or {}).get("totalCount") or 0),
            "public_repositories": int(repositories.get("totalCount") or len(nodes)),
            "stars": sum(int(repo.get("stargazerCount") or 0) for repo in nodes if not repo.get("isFork")),
        },
        "repositories": featured,
        "calendar": {
            "total": github_total,
            "has_restricted_contributions": bool(collection.get("hasAnyRestrictedContributions")),
            "restricted_contributions_count": int(collection.get("restrictedContributionsCount") or 0),
            "colors": list(calendar.get("colors") or []),
            "months": months,
            "weeks": weeks,
            "through": latest_date,
        },
    }


def validate_token_identity_and_scopes(identity: dict, scopes_header: str, username: str) -> None:
    login = identity.get("login") or ""
    if login.lower() != username.lower():
        raise ValueError(
            "PROFILE_TOKEN authenticated as the wrong GitHub user: "
            f"expected {username}, got {login or 'unknown'}"
        )

    scopes = {scope.strip().lower() for scope in scopes_header.split(",") if scope.strip()}
    if not scopes:
        raise ValueError(
            "PROFILE_TOKEN must be a classic personal access token with read:user. "
            "Fine-grained/repository tokens are rejected because they can silently omit private contribution counts."
        )
    if "read:user" not in scopes and "user" not in scopes:
        raise ValueError(
            "PROFILE_TOKEN is missing the required read:user scope. "
            "Create a classic personal access token with read:user and save it as the PROFILE_TOKEN Actions secret."
        )


def validate_profile_token(username: str, token: str) -> None:
    if not token:
        raise ValueError(
            "PROFILE_TOKEN is required. The profile renderer refuses to fall back to GITHUB_TOKEN "
            "because repository-scoped tokens can omit private contribution counts."
        )
    request = urllib.request.Request(
        REST_USER_URL,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{username}-profile-token-check",
            "X-Github-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            identity = json.loads(response.read().decode("utf-8"))
            scopes_header = response.headers.get("X-OAuth-Scopes", "")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GitHub PROFILE_TOKEN validation failed: {exc}") from exc
    validate_token_identity_and_scopes(identity, scopes_header, username)


def fetch_profile_data(username: str, token: str, config: dict) -> dict:
    validate_profile_token(username, token)
    body = json.dumps({"query": QUERY, "variables": {"login": username}}).encode("utf-8")
    request = urllib.request.Request(
        GRAPHQL_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": f"{username}-profile-renderer",
            "X-Github-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GitHub GraphQL request failed: {exc}") from exc
    return normalize_graphql_payload(payload, config)


def token_from_environment() -> str:
    token = os.environ.get("PROFILE_TOKEN") or ""
    if not token:
        raise ValueError(
            "PROFILE_TOKEN is required; GITHUB_TOKEN fallback is intentionally disabled to protect contribution accuracy."
        )
    return token
