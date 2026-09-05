# Motion-First GitHub Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a GitHub-native animated profile whose motion assets are deterministically regenerated from real GitHub profile, repository, and contribution data.

**Architecture:** Keep the existing GitHub GraphQL normalization boundary. Add a focused Pillow animation renderer that consumes normalized data and emits paired light/dark GIF + PNG assets, then simplify the README renderer around those assets. The workflow installs Pillow, verifies tests first, refreshes data, renders motion, and commits only generated output changes.

**Tech Stack:** Python 3.12, Pillow, GitHub GraphQL API, GitHub Actions, Markdown/HTML `<picture>`.

**Spec:** `docs/superpowers/specs/2026-09-05-motion-profile-design.md`

## Global Constraints
- GitHub contribution cells must preserve exact `contributionCount` values.
- GitHub repository metadata must remain sourced from GraphQL.
- No terminal UI, badge walls, visitor counters, streak cards, fake “live” labels, neon, or generic skill lists.
- Motion assets must have static PNG fallback frames.
- Identical data/config must render byte-identical assets.
- GitHub API failure must not replace existing generated assets.

---

### Task 1: Motion renderer contract
**Files:** Create `scripts/motion_profile.py`; create `tests/test_motion_profile.py`; create `requirements.txt`.

**Interfaces:**
- Consumes normalized data from `scripts.github_data.normalize_graphql_payload`.
- Produces `render_motion_assets(data: dict, config: dict, output_dir: Path) -> list[Path]`.

- [ ] Write tests asserting deterministic bytes, paired GIF/PNG output, required dimensions, animation frame count, exact contribution total in the contribution final frame metadata, and banned visual-copy absence.
- [ ] Run `python -m unittest tests.test_motion_profile -v` and verify RED.
- [ ] Implement deterministic canvas, font loading, easing, palette-safe GIF output, hero/project/contribution loops.
- [ ] Run the test and verify GREEN.

### Task 2: Motion-first README
**Files:** Modify `scripts/render_profile.py`; modify `tests/test_readme.py`; modify `profile.json`.

**Interfaces:**
- `render_readme(config: dict) -> str` references `assets/motion/*-{light,dark}.gif` and static fallback PNGs.

- [ ] Write failing tests for the five-beat structure and removal of “How I build”.
- [ ] Run tests and verify RED.
- [ ] Implement compact motion-first README composition and sharper copy.
- [ ] Regenerate `README.md` and verify GREEN.

### Task 3: Workflow regeneration
**Files:** Modify `.github/workflows/refresh-profile.yml`; modify `tests/test_workflow.py`.

**Interfaces:** GitHub Action installs `requirements.txt`, tests before network rendering, and commits README plus `assets/motion`.

- [ ] Write workflow contract tests for Pillow install and generated asset commit paths.
- [ ] Verify RED.
- [ ] Update workflow and verify GREEN.

### Task 4: Visual and release verification
**Files:** Generated `assets/motion/*`; final archive.

- [ ] Render from the checked-in GitHub fixture and inspect representative light/dark frames.
- [ ] Run full unit suite.
- [ ] Validate GIF animation/frame counts and PNG dimensions.
- [ ] Scan README/generated text for banned profile clichés.
- [ ] Package repository and verify ZIP integrity.
