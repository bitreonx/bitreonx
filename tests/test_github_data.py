import json
import os
import unittest
from unittest.mock import patch
from pathlib import Path

from scripts.github_data import QUERY, load_profile_config, normalize_graphql_payload, token_from_environment

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


    def test_graphql_query_authenticates_viewer_and_requests_restricted_contribution_metadata(self):
        self.assertIn("viewer {", QUERY)
        self.assertIn("hasAnyRestrictedContributions", QUERY)
        self.assertIn("restrictedContributionsCount", QUERY)

    def test_rejects_payload_authenticated_as_a_different_github_user(self):
        payload = json.loads(json.dumps(self.payload))
        payload["data"]["viewer"] = {"login": "someone-else"}
        with self.assertRaisesRegex(ValueError, "authenticated GitHub user"):
            normalize_graphql_payload(payload, self.config)

    def test_profile_token_never_falls_back_to_github_token(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "repo-scoped-token"}, clear=True):
            with self.assertRaisesRegex(ValueError, "PROFILE_TOKEN"):
                token_from_environment()

    def test_profile_token_is_used_when_present(self):
        with patch.dict(os.environ, {"PROFILE_TOKEN": "profile-token", "GITHUB_TOKEN": "repo-token"}, clear=True):
            self.assertEqual(token_from_environment(), "profile-token")


    def test_classic_token_scope_validator_requires_read_user(self):
        from scripts.github_data import validate_token_identity_and_scopes
        with self.assertRaisesRegex(ValueError, "read:user"):
            validate_token_identity_and_scopes({"login": "bitreonx"}, "repo", "bitreonx")

    def test_classic_token_scope_validator_accepts_owner_with_read_user(self):
        from scripts.github_data import validate_token_identity_and_scopes
        validate_token_identity_and_scopes({"login": "bitreonx"}, "read:user, user:email", "bitreonx")

    def test_classic_token_scope_validator_rejects_fine_grained_or_missing_scope_header(self):
        from scripts.github_data import validate_token_identity_and_scopes
        with self.assertRaisesRegex(ValueError, "classic personal access token"):
            validate_token_identity_and_scopes({"login": "bitreonx"}, "", "bitreonx")

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
