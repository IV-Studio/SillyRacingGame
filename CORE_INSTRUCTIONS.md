# Racer Prototype Core Instructions

Use these project-specific instructions alongside the IV Studio Codex Prototyping Protocol.

## Player-Facing Asset Rule

When generating visual assets for Tabletop Simulator or any other player-visible output:

- Prioritize player experience first.
- Design assets as if they are real board game components used at the table.
- Include only information that helps a player read, use, or enjoy the component during play.
- Do not include developer-facing notes, implementation status, simulation status, layout notes, data-pipeline notes, or system architecture notes on player-facing assets.
- Do not surface phrases like `encoded`, `data-driven`, `rules-active`, `simulation`, `prototype status`, or similar internal language on final player-visible outputs.
- Reference rules only when they help a player operate the component in real play.
- Prefer concise, table-usable reminders such as win condition, icon legends, turn order, and clearly readable labels.

## Asset Tone

- Visual outputs should feel like real board game artifacts, not debugging views.
- If space is limited, cut internal or explanatory text before cutting player-useful information.
- Favor readability, hierarchy, and quick table comprehension over documenting the underlying system.

## CSV Content Rule

- Structured data CSVs should include player-facing text whenever that content represents something a player can read, use, or reference during play.
- Prefer a plain-language `description` field for cards, abilities, and other gameplay content that has an effect a player needs to understand.
- Write CSV descriptions as component-ready rules text, not developer notes or implementation summaries.
- Keep CSV descriptions concise, explicit, and usable on physical or digital components without translation from internal terminology.
