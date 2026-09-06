import json
import unittest
from pathlib import Path

from scripts.github_data import load_profile_config, normalize_graphql_payload

ROOT = Path(__file__).resolve().parents[1]


class GitHubDataTests(unittest.TestCase):
    def setUp(self):
        self.config = load_profile_config(ROOT / "profile.json")
        self.payload = json.loads((ROOT / "tests/fixtures/github_profile_graphql.json").read_text())

    def test_normalizes_profile_metrics_and_featured_repositories(self):
        data = normalize_graphql_payload(self.payload, self.config)
        self.assertEqual(data["profile"]["login"], "bitreonx")
        self.assertEqual(data["profile"]["followers"], 55)
        self.assertEqual(data["profile"]["public_repositories"], 5)
        self.assertEqual([repo["name"] for repo in data["repositories"]], ["Mnestis", "Rune"])
        self.assertEqual(data["repositories"][0]["stars"], 50)
        self.assertEqual(data["repositories"][0]["forks"], 6)

    def test_preserves_exact_contribution_counts(self):
        data = normalize_graphql_payload(self.payload, self.config)
        days = {day["date"]: day for week in data["calendar"]["weeks"] for day in week["days"]}
        self.assertEqual(data["calendar"]["total"], 181)
        self.assertEqual(days["2026-08-29"]["count"], 50)
        self.assertEqual(days["2026-08-27"]["count"], 21)
        self.assertEqual(days["2026-03-22"]["count"], 4)

    def test_preserves_canonical_github_month_metadata(self):
        data = normalize_graphql_payload(self.payload, self.config)
        months = data["calendar"]["months"]
        self.assertGreaterEqual(len(months), 12)
        self.assertEqual(months[0]["name"], "September")
        self.assertEqual(months[0]["year"], 2025)
        self.assertEqual(months[-1]["name"], "September")
        self.assertEqual(months[-1]["year"], 2026)

    def test_rejects_calendar_when_daily_sum_does_not_match_github_total(self):
        payload = json.loads(json.dumps(self.payload))
        payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"] += 1
        with self.assertRaisesRegex(ValueError, "integrity"):
            normalize_graphql_payload(payload, self.config)

    def test_graphql_query_requests_canonical_month_metadata(self):
        from scripts.github_data import QUERY
        self.assertIn("months {", QUERY)
        self.assertIn("totalWeeks", QUERY)

    def test_missing_curated_repository_is_explicit(self):
        payload = json.loads(json.dumps(self.payload))
        payload["data"]["user"]["repositories"]["nodes"] = [
            r for r in payload["data"]["user"]["repositories"]["nodes"] if r["name"] != "Rune"
        ]
        data = normalize_graphql_payload(payload, self.config)
        rune = data["repositories"][1]
        self.assertEqual(rune["name"], "Rune")
        self.assertFalse(rune["available"])

    def test_rejects_missing_user(self):
        with self.assertRaisesRegex(ValueError, "user"):
            normalize_graphql_payload({"data": {"user": None}}, self.config)


if __name__ == "__main__":
    unittest.main()
