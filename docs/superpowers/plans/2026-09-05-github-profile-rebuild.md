# GitHub Profile Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current terminal-themed GitHub profile with a premium editorial profile powered by GitHub's real contribution calendar and live repository metadata.

**Architecture:** Keep network retrieval isolated in `scripts/github_data.py`, keep rendering pure in `scripts/render_profile.py`, and keep intentional profile copy in `profile.json`. A daily GitHub Action tests, fetches, renders, and commits only changed generated assets.

**Tech Stack:** Python 3.12 standard library, GitHub GraphQL API, SVG, GitHub Actions, Markdown/HTML supported by GitHub profile READMEs.

**Spec:** `docs/superpowers/specs/2026-09-05-github-profile-rebuild-design.md`

## Global Constraints

- No third-party profile-card services or fake telemetry.
- Contribution cells must originate from `contributionsCollection.contributionCalendar` and preserve exact `contributionCount` values.
- Auth precedence is `PROFILE_TOKEN`, then `GITHUB_TOKEN`.
- The profile has explicit light/dark generated SVG assets and no external font dependency.
- Curated authored repositories are `Mnestis` and `Rune`.
- Tests use Python standard-library `unittest` only.

---

### Task 1: Normalize real GitHub profile data

**Files:**
- Create: `profile.json`
- Create: `scripts/github_data.py`
- Create: `tests/fixtures/github_profile_graphql.json`
- Create: `tests/test_github_data.py`

**Interfaces:**
- Produces: `load_profile_config(path: Path) -> dict`
- Produces: `normalize_graphql_payload(payload: dict, config: dict) -> dict`
- Produces: `fetch_profile_data(username: str, token: str, config: dict) -> dict`
- Normalized data contains `profile`, `repositories`, and `calendar` keys.

- [ ] **Step 1: Write failing normalization tests** covering profile metrics, curated repository lookup, and exact contribution day counts.
- [ ] **Step 2: Run `python -m unittest tests.test_github_data -v`** and confirm failures because the data module does not exist.
- [ ] **Step 3: Implement the GraphQL query, HTTP request, validation, config loading, and normalization functions** with explicit errors for missing user/calendar/repositories.
- [ ] **Step 4: Re-run `python -m unittest tests.test_github_data -v`** and confirm all Task 1 tests pass.
- [ ] **Step 5: Commit the self-contained data layer changes.**

### Task 2: Render the editorial visual system

**Files:**
- Replace: `scripts/render_profile.py`
- Create: `tests/test_render_profile.py`
- Generate: `assets/hero-light.svg`
- Generate: `assets/hero-dark.svg`
- Generate: `assets/contributions-light.svg`
- Generate: `assets/contributions-dark.svg`
- Generate: `assets/project-mnestis-light.svg`
- Generate: `assets/project-mnestis-dark.svg`
- Generate: `assets/project-rune-light.svg`
- Generate: `assets/project-rune-dark.svg`

**Interfaces:**
- Consumes normalized data returned by `normalize_graphql_payload`.
- Produces: `render_hero(data: dict, theme: Theme) -> str`
- Produces: `render_contributions(data: dict, theme: Theme) -> str`
- Produces: `render_project_card(repo: dict, theme: Theme) -> str`
- Produces: `render_all(data: dict, config: dict, output_dir: Path) -> list[Path]`
- CLI accepts `--data-json` for deterministic offline fixture generation and network mode otherwise.

- [ ] **Step 1: Write failing renderer tests** for escaping, exact contribution titles/counts, 53-week layout, theme outputs, and deterministic bytes.
- [ ] **Step 2: Run `python -m unittest tests.test_render_profile -v`** and confirm the renderer tests fail against the legacy implementation.
- [ ] **Step 3: Implement the new theme tokens and pure SVG renderers** with no fake terminal/telemetry language and no external resources.
- [ ] **Step 4: Generate all eight fixture-backed assets** using `python scripts/render_profile.py --data-json tests/fixtures/github_profile_graphql.json --config profile.json`.
- [ ] **Step 5: Re-run renderer tests** and confirm they pass.
- [ ] **Step 6: Commit the rendering system and generated assets.**

### Task 3: Replace the README information architecture

**Files:**
- Replace: `README.md`
- Create: `tests/test_readme.py`
- Delete: `assets/footer.svg`
- Delete: `assets/hero.svg`
- Delete: `assets/operator.svg`
- Delete: `assets/signal.svg`

**Interfaces:**
- README consumes only generated local assets and canonical GitHub/social links from `profile.json`.

- [ ] **Step 1: Write failing README tests** asserting required sections and rejecting legacy strings such as `ps aux`, `PUBLIC BUILD PULSE`, `sudo rm -rf`, visitor counters, and badge-wall patterns.
- [ ] **Step 2: Run `python -m unittest tests.test_readme -v`** and verify the legacy README fails the tests.
- [ ] **Step 3: Replace README with the approved five-part editorial structure** using `<picture>` light/dark assets, two linked project cards, concise principles, and plain outbound links.
- [ ] **Step 4: Remove the four obsolete legacy SVGs.**
- [ ] **Step 5: Re-run README tests** and confirm they pass.
- [ ] **Step 6: Commit the README rebuild.**

### Task 4: Automate verified refreshes

**Files:**
- Create: `.github/workflows/refresh-profile.yml`
- Create: `tests/test_workflow.py`

**Interfaces:**
- Workflow runs `python -m unittest discover -s tests -v` then `python scripts/render_profile.py --username bitreonx --config profile.json`.
- Environment token expression passes `PROFILE_TOKEN` when configured and otherwise `github.token` through `GITHUB_TOKEN`.

- [ ] **Step 1: Write a failing workflow contract test** checking schedule/manual triggers, Python 3.12, tests-before-render, contents write permission, and change-only commit behavior.
- [ ] **Step 2: Run `python -m unittest tests.test_workflow -v`** and confirm failure because the workflow is absent.
- [ ] **Step 3: Implement the workflow** with daily cron, manual dispatch, concurrency protection, test gate, render step, and guarded commit/push.
- [ ] **Step 4: Re-run workflow tests** and confirm they pass.
- [ ] **Step 5: Commit workflow automation.**

### Task 5: Final verification and packaging

**Files:**
- Modify only if verification reveals defects.
- Create final archive outside the repository: `/mnt/data/bitreonx-profile-rebuilt.zip`.

**Interfaces:**
- Verification command: `python -m unittest discover -s tests -v`.
- Offline deterministic render command: `python scripts/render_profile.py --data-json tests/fixtures/github_profile_graphql.json --config profile.json`.

- [ ] **Step 1: Run the complete unit suite** and require zero failures/errors.
- [ ] **Step 2: Run offline rendering twice and compare SHA-256 hashes** of all generated SVGs to prove deterministic output.
- [ ] **Step 3: Scan README/generated SVGs for banned legacy patterns and third-party card URLs.**
- [ ] **Step 4: Validate all generated SVGs as XML.**
- [ ] **Step 5: Zip the repository while excluding `.git`, caches, and bytecode.**
