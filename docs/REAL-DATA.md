# Real GitHub data contract

The profile is regenerated from GitHub GraphQL by `.github/workflows/refresh-profile.yml`.

## Contribution truth

- Production contribution data **requires** the repository Actions secret `PROFILE_TOKEN`.
- There is deliberately **no `GITHUB_TOKEN` fallback** for contribution rendering. The automatic repository token can return a public-only contribution view and therefore produce totals that do not match the profile owner's signed-in GitHub graph.
- `PROFILE_TOKEN` must be a **classic GitHub personal access token** with the `read:user` scope. GitHub documents `read:user` as required for including contributions from private/internal repositories in `ContributionsCollection`.
- Before GraphQL runs, the generator calls GitHub's authenticated-user endpoint and verifies that the token authenticates as `bitreonx` and that its OAuth scopes include `read:user` (or the broader `user` scope).
- The GraphQL query also requests `viewer.login`; normalization rejects the response unless `viewer.login == bitreonx`.
- The contribution renderer reads `contributionsCollection.contributionCalendar`, including GitHub's canonical `months`, `weeks`, daily `contributionCount`, and `totalContributions`.
- The query also requests `hasAnyRestrictedContributions` and `restrictedContributionsCount` for audit context.
- A refresh fails before publishing if the sum of all daily counts does not exactly equal GitHub `totalContributions`.
- The headline contribution total is the exact GitHub total from frame one. It never animates from a fake zero.

## Failure behavior

Missing token, wrong GitHub user, wrong token type/scope, GraphQL errors, calendar-integrity failures, rendering errors, and test failures all stop the workflow before the commit step. The previous valid README/assets remain published.

## Other live metadata

Mnestis and Rune stars, forks, language, description, and update timestamps are refreshed from GitHub GraphQL in the same run.

## Privacy

A profile README is public. Using an owner-authenticated token can cause aggregated private/internal contribution counts and dates to be rendered into public profile assets. Repository names, commit contents, and private code are not rendered by this profile generator.

The checked-in GraphQL fixture under `tests/fixtures/` is deterministic test data only. Production refreshes never read it.
