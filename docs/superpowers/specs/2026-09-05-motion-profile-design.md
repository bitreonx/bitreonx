# Bitreon Motion-First GitHub Profile Design

## Goal
Replace the static editorial profile with a GitHub-native motion portfolio that feels like a living software system while keeping every displayed GitHub metric factual.

## Experience
The README has five beats only: cinematic identity hero, Mnestis, Rune, contribution record, current/links. No terminal UI, badges, streak cards, visitor counters, pseudo-live labels, or generic skill walls.

### Hero
A seamless 8-second loop. Real active contribution days seed a sparse constellation. Their topology connects and resolves around the BITREON wordmark and the line “I build systems that make software easier to understand.” Motion is restrained: node wake-up, edge flow, mask reveal, then a long calm hold.

### Mnestis
A 6-second system diagram loop showing repository → parse → graph → evidence → answer. Repository metadata (stars, forks, language, update) comes from GitHub GraphQL. The animation communicates the product model rather than decorating a card.

### Rune
A 6-second orchestration loop showing several model/provider inputs converging through a harness and resolving to one controlled execution lane. Metadata remains factual and GitHub-backed.

### Contributions
A 7-second loop built only from `contributionsCollection.contributionCalendar`: weeks reveal left-to-right, active cells illuminate using their exact daily counts, and the exact total resolves at the end. No synthetic events or weighted approximations.

## Rendering Architecture
- `scripts/github_data.py`: fetches and normalizes GitHub GraphQL data.
- `scripts/motion_profile.py`: deterministic Pillow renderer for GitHub-safe animated GIFs plus static PNG fallback frames.
- `scripts/render_profile.py`: composes README from `profile.json` and motion asset paths.
- `assets/motion/`: light/dark GIFs and static PNG fallbacks.
- GitHub Action installs Pillow, runs tests, fetches data, regenerates assets, and commits only changes.

## Visual Language
- Monochrome canvas: warm near-white and graphite black.
- One restrained violet accent; contribution intensity may use monochrome-to-violet levels, not GitHub green.
- Strong typography, hairline geometry, generous empty space.
- No gradients, glassmorphism, neon, terminal chrome, or emoji decoration.
- Motion should be calm and purposeful: 8–10 fps, easing, long resting states, no bouncing.

## Reliability
- GIF is the primary animated asset for GitHub README playback.
- PNG final-frame fallback is generated beside every GIF.
- Rendering is deterministic for identical data/config.
- If GitHub data retrieval fails, the workflow fails without overwriting existing assets.

## Accessibility
Every image receives meaningful alt text in README. Final frames retain all essential labels and metrics so information remains understandable when motion is disabled or paused.
