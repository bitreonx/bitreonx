# GitHub Profile Rebuild Design

## Goal

Rebuild the `bitreonx/bitreonx` profile repository as a premium editorial engineering portfolio that uses real GitHub data, highlights authored work, and avoids terminal-theme/profile-README clichés.

## Product direction

The profile should feel closer to an excellent product landing surface than a generated developer README. It is restrained, high-contrast, information-dense without being busy, and designed around proof rather than decoration.

### Anti-goals

- No fake contribution heatmap, weighted event score, streak-card service, visitor counter, badge wall, fake terminal process table, or novelty CLI copy.
- No dependency on third-party profile-card services.
- No duplicated GitHub chrome such as a second large avatar block.
- No generic “passionate developer” language or exhaustive technology-logo grid.
- No animation whose only purpose is decoration.

## Information architecture

1. **Hero** — BITREON wordmark, one concise positioning statement, focus areas, and a restrained strip of real profile metrics.
2. **Selected work** — curated authored repositories (`Mnestis`, `Rune`) with metadata refreshed from GitHub.
3. **Contribution record** — the real GitHub contribution calendar for the account, not a reconstruction from events.
4. **Principles** — four short engineering/product principles in normal prose.
5. **Elsewhere** — concise links to repositories and the social profiles already present on the GitHub account.

## Visual system

- Two explicit SVG themes selected by README `<picture>` media queries.
- Light theme: warm near-white canvas, charcoal text, hairline graphite borders, a single cool accent.
- Dark theme: near-black canvas, warm-white text, low-contrast borders, the same accent family.
- Large editorial type hierarchy and generous whitespace; rounded rectangles are used sparingly.
- No gradients unless nearly imperceptible; no neon; no glowing borders; no glassmorphism.
- Contribution cells retain GitHub's five semantic intensity levels while being redrawn to match the profile visual system.
- Assets must remain readable on mobile when GitHub scales the README to a narrow column.

## Data architecture

`profile.json` is the only hand-edited profile configuration. It stores positioning copy, curated repository names, principles, and outbound links.

`scripts/github_data.py` owns GitHub data retrieval and normalization:

- Primary source: GitHub GraphQL API `user(login)`, repository metadata, and `contributionsCollection.contributionCalendar`.
- Auth precedence: `PROFILE_TOKEN`, then `GITHUB_TOKEN`.
- Optional `PROFILE_TOKEN` allows the owner's contribution data available under `read:user`; normal Actions refreshes can use `GITHUB_TOKEN` for public data.
- The code exposes normalized typed dictionaries rather than leaking raw GraphQL response shapes into renderers.
- Offline fixture input is supported for deterministic tests and local rendering.

`scripts/render_profile.py` owns pure SVG/README generation from normalized data. It must not perform network calls.

## Generated assets

- `assets/hero-light.svg`
- `assets/hero-dark.svg`
- `assets/contributions-light.svg`
- `assets/contributions-dark.svg`
- `assets/project-mnestis-light.svg`
- `assets/project-mnestis-dark.svg`
- `assets/project-rune-light.svg`
- `assets/project-rune-dark.svg`

The README references these assets with `<picture>` tags and wraps each project card in its canonical GitHub repository link.

## Refresh workflow

`.github/workflows/refresh-profile.yml` runs daily and on manual dispatch. It:

1. checks out the repository;
2. sets up Python 3.12;
3. runs the unit test suite;
4. fetches GitHub data and regenerates assets/README;
5. commits only when generated files changed.

The workflow receives `PROFILE_TOKEN` if configured; otherwise it falls back to `${{ github.token }}`.

## Failure behavior

A network/API failure must fail the refresh job before overwriting known-good generated assets. Local fixture rendering remains available for tests. Missing curated repositories are rendered as an explicit unavailable state rather than silently replaced by unrelated repositories.

## Testing

Use the standard-library `unittest` module only. Tests cover:

- GraphQL normalization and exact contribution counts;
- curated-repository matching;
- HTML/SVG escaping;
- derived calendar metrics;
- deterministic asset generation;
- README structure and absence of banned legacy patterns.

## Acceptance criteria

- `README.md` contains no fake-terminal sections and no reference to public-events scoring.
- The contribution asset is generated from GitHub's contribution calendar data and preserves exact day counts.
- The default fixture produces a 53-week calendar with tooltips for exact dates/counts.
- Mnestis and Rune cards use live repository metadata when the workflow runs.
- Light and dark SVG variants render without external fonts, scripts, or third-party assets.
- `python -m unittest discover -s tests -v` passes.
- A full offline render from the fixture is deterministic.
