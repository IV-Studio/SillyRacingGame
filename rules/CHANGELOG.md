# Changelog

## 2026-04-28

- Expanded the unique ability deck with a large new passive card batch covering color rerolls, die tuning and conversion, parity effects, trap tech, reactive movement, and path-collection powers.
- Added a dedicated TTS exporter for unique abilities and regenerated the card-sheet SVGs alongside the existing mystery card exports.
- Added TTS die-sheet exports for the yellow, orange, and red d6 layouts using a 3x3 template with the top row blank and the lower six cells mapped to current die faces.

## 2026-04-21

- Halved the track to a 60-space single loop (previously 120) so each space is a larger, more readable component at the table. Kept the finish band at the last space of the loop.
- Raised the win condition to 5 laps (previously 3) to preserve race length on the shorter loop, updated in the rulebook and `sim/game.py`.
- Cleared `data/shortcuts.csv` of active rows (header preserved) and removed shortcut rendering from the board export. Shortcuts are parked for a future pass.
- Rebuilt both board SVG generators around the new 60-space count with larger tile and road dimensions, updated goal copy and the page title subtitle to reflect 5 laps, and regenerated `assets/board.svg`, `assets/board_v2.svg`, and the TTS exports.

## 2026-04-14

- Bootstrapped the Racer Prototype from the system spec into the IV Studio project structure.
- Added the current natural-language rulebook with explicit baseline assumptions for ambiguous hooks, especially fuel failure and the initial ability market flow.
- Added CSV source data for dice faces, action rows, abilities, mystery cards, and a 120-space looping track.
- Implemented a deterministic Python simulation with:
  - turn-by-turn drafting and row resolution
  - multi-player support
  - dice movement, traps, coins, and mystery boxes
  - persistent abilities and one-use mystery cards
  - simple heuristic AI drafting and tactical play
  - batch simulation metrics for pace, fuel, coins, lap growth, and ability win rates
- Corrected the risky mixed-color dice row so players choose a die color before rolling rather than receiving an unintended best-of-both-colors advantage.
- Tightened simulation reporting so batch metrics better reflect round-level pace instead of only cumulative raw totals.
- Added a runnable script for single-game and batch simulation checks.
- Added a deterministic SVG board generator and exported the first board pass to stable asset and TTS paths.
- Reworked the board SVG into a winding track layout with visible shortcut lanes and a bridge concept, while compressing the action panel to the left 25% of the board.
- Added encoded shortcut data plus simulation support for entering, traversing, and reconnecting from shortcut paths over multiple turns.
- Reordered the action board so dice rows now appear above fuel, above ability bid, and at the end, and refreshed dice row data to use mixed-color pools instead of single-color rows.
- Simplified dice row board visuals to color-coded numbered slots driven by CSV display metadata.
- Reduced the first-player row to a single claim slot so only one player can draft it each round.
- Removed the zero-value coin and fuel slots so those rows only contain meaningful draft choices.
- Rebuilt the SVG board layout around a stricter 8px grid, boxed section structure, and consistent typography so panel text stays within fixed containers without shrinking.
- Added a project-level player-facing asset rule and updated the board copy so TTS outputs only show table-useful information instead of internal implementation notes.
- Removed the board-notes panel for more player space and changed Dice A, B, and C to fixed per-slot die colors in both the CSV data and the rulebook.
- Smoothed the board road into a dense curved spline so the racetrack reads as a continuous winding path instead of visibly segmented straight runs.
- Removed the experimental bridge layer and simplified the main track into a cleaner non-overlapping winding loop for easier prototype readability.
- Extended the winding loop back into the board center so the 120 spaces spread across a longer path and read more clearly at prototype scale.
- Removed shortcuts from the active prototype rules, simulation, and board export so the game can focus on a single-route race while we tune the core loop.
- Rebuilt the track shape around a more reference-inspired, highly winding single loop that stays non-self-crossing while preserving the same 120-space circuit.
- Expanded the mystery card deck with player-chosen trap shielding, a nearby-rival sabotage blast, drafting-line catch-up movement, and overclock die boosts.
- Added a project rule that gameplay CSVs should carry player-facing plain-language descriptions, and updated the mystery card data schema to include that text.
- Extended that description pattern across the remaining gameplay CSVs so abilities, action rows, dice faces, and track spaces now all carry player-facing rules text.
