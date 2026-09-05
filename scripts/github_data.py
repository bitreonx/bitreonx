#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

GRAPHQL_URL = "https://api.github.com/graphql"
QUERY = r'''
query Profile($login: String!) {
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
      contributionCalendar {
        totalContributions
        colors
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
    user = (payload.get("data") or {}).get("user")
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

    weeks = []
    for week in calendar.get("weeks") or []:
        days = []
        for day in week.get("contributionDays") or []:
            days.append({
                "date": day.get("date", ""),
                "weekday": int(day.get("weekday") or 0),
                "count": int(day.get("contributionCount") or 0),
                "level": day.get("contributionLevel") or "NONE",
                "color": day.get("color") or "#ebedf0",
            })
        weeks.append({"first_day": week.get("firstDay", ""), "days": days})

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
            "total": int(calendar.get("totalContributions") or 0),
            "colors": list(calendar.get("colors") or []),
            "weeks": weeks,
        },
    }


def fetch_profile_data(username: str, token: str, config: dict) -> dict:
    if not token:
        raise ValueError("GitHub token is required; set PROFILE_TOKEN or GITHUB_TOKEN")
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
    return os.environ.get("PROFILE_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
