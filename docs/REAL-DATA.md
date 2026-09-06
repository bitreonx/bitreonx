# Real GitHub data contract

The profile is regenerated from GitHub GraphQL by `.github/workflows/refresh-profile.yml`.

- `GITHUB_TOKEN` is used automatically for public GitHub profile/repository/contribution data.
- Optional repository secret `PROFILE_TOKEN` takes precedence. Use a token with `read:user` only when you want GitHub-authorized private/internal contribution counts included according to your profile visibility settings.
- Never commit a personal token to this repository.
- The contribution renderer reads `contributionsCollection.contributionCalendar`, including GitHub's canonical `months`, `weeks`, daily `contributionCount`, and `totalContributions`.
- A refresh fails before publishing if the sum of all daily counts does not exactly equal GitHub `totalContributions`.
- Network/API/render/test failures stop the Action; existing published assets remain untouched because the commit step is never reached.
- Mnestis and Rune metadata (stars, forks, language, update date) is refreshed from GitHub GraphQL as part of the same run.

The checked-in test fixture is deterministic test data only. Production refreshes do not read it.
