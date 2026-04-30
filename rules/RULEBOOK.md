# Racer Prototype Rulebook

## Overview

Racer Prototype is a turn-based action-programming racing game for 2-4 players. Players draft five action pillars each round, resolve the action board from top to bottom, and try to complete 5 laps of the track before anyone else.

The circuit is a 60-space loop.

This rulebook reflects the current playable prototype and its simulation assumptions.

## Win Condition

The first player to complete 5 laps wins immediately, even if other actions remain unresolved that round.

## Round Structure

Each round has 2 phases.

### 1. Action Drafting

- Starting with the current first player and continuing clockwise, players place 1 pillar at a time.
- Each player places exactly 5 pillars per round.
- When a pillar is placed in a row, it takes the leftmost open slot in that row.
- If all visible slots in a row are full, no more pillars may be placed there this round.

### 2. Action Resolution

- Resolve rows from top to bottom in this order:
  1. First Player
  2. Gain Coins
  3. Dice Movement A
  4. Gain Fuel
  5. Fixed Movement
  6. Dice Movement B
  7. Ability Draft
  8. Dice Movement C
- Within each row, resolve occupied slots from left to right.
- If a player wins during row resolution, the game ends immediately.

## Player State

Each player tracks:

- position on the looping track
- completed laps
- coins
- fuel, capped at 7
- drafted persistent abilities
- a hand of one-use mystery cards

Players begin with:

- position `0`
- laps `0`
- coins `3`
- fuel `3`
- no abilities
- no mystery cards

## Action Rows

### First Player

- This row has only 1 slot.
- The player who claims it becomes first player for the next round.

### Gain Coins

Current slot rewards are `5, 3, 2, 1, 1`.

### Gain Fuel

Current slot rewards are `4, 3, 2, 1, 1`.
- Fuel cannot exceed 7.

### Fixed Movement

Current slot rewards are `+6, +4, +3, +2, +2, +1`.

### Ability Draft

- Players in this row bid coins for an available ability.
- Current cost slots are `7, 5, 4, 3, 2, 1`.
- Resolve bids from highest cost slot to lowest cost slot.
- A player must be able to pay the full printed cost to claim an ability.
- After paying, the player chooses one revealed ability from the current market.
- Overpaying is allowed and expected.
- If no abilities remain in the market, later bidders gain nothing.

At the start of each round, reveal `player count + 1` abilities from the ability deck to form the market.

### Dice Movement

There are 3 dice rows in the current prototype:

- Dice Movement A slots: `2 yellow`, `2 orange`, `1 red`, `1 yellow`, `1 orange`
- Dice Movement B slots: `2 orange`, `2 red`, `1 red`, `1 orange`, `1 yellow`
- Dice Movement C slots: `3 red`, `2 red`, `2 orange`, `1 red`, `1 yellow`

When resolving a dice row:

- Roll the exact die color and die count shown in the claimed slot.
- A player normally keeps 1 die result.
- Abilities may increase the number of dice rolled or the number of kept results.
- If a chosen result has a fuel cost, the player must pay it.

For board presentation, each dice slot shows:

- the die color used for that slot
- the number of dice rolled in that slot

## Dice

### Yellow Die

- Low variance
- No fuel costs
- Intended for stable movement

### Orange Die

- Medium variance
- Some faces cost fuel

### Red Die

- Highest variance
- Best peak movement
- Most fuel pressure

## Fuel Failure Rule

This prototype uses the following baseline implementation:

- A player cannot choose any die result they cannot afford.
- If every available result is unaffordable, the player takes the best affordable result among the remaining kept results.
- If no affordable kept result exists, that die action produces `0` movement.

This is an explicit balancing hook and may change after simulation review.

## Movement and Laps

- Movement always advances or retreats a player around the loop.
- Passing spaces does not trigger their effects by default.
- Only the final landed space triggers, unless an ability says otherwise.
- If an effect produces `0` movement, no new landing effect triggers.
- Completing a full loop increments laps by 1.
- Moving backward never reduces completed laps below 0.

## Track Effects

### Coins

- Landing on a coin space grants the coin amount in that space's metadata.
- The default amount is 1 if none is listed.

### Traps

- Trap spaces list a die color in metadata.
- When you land on a trap, roll that die and move backward by the rolled value.
- Negative trap die values are treated as `0` backward movement.
- Abilities or mystery cards that ignore traps can cancel this effect.

### Mystery Boxes

- Landing on a mystery box draws 1 mystery card.
- Mystery cards are kept in hand until used.

## Abilities

Abilities are persistent passive effects. The current card pool focuses on dice manipulation, trap mitigation, and movement economy.

Implemented baseline effect families include:

- roll extra dice
- keep extra dice
- reroll weak dice pools once
- upgrade allowed die colors
- ignore traps of a given color
- collect coins from passed spaces
- gain bonuses from risky dice
- reduce fuel pressure

Players may own multiple abilities, and their effects stack when compatible.

## Mystery Cards

Mystery cards are one-use tactical effects kept in hand until the player chooses the right moment to spend them. The current simulation uses AI heuristics to spend them when they are clearly beneficial.

Current implemented card families include:

- reroll a movement die pool
- gain extra movement
- gain fuel
- gain coins
- ignore a trap
- blast nearby rivals with a yellow-die trap effect
- gain catch-up movement after a move when rivals are just ahead
- add `+2` to a chosen die result

## AI Drafting Heuristic

The simulation uses a simple baseline AI:

- prefer high-value movement rows when behind
- value fuel if low
- value coins if poor or preparing for abilities
- contest first player when close to a new round lead matters
- use risky dice more often when fuel is healthy

The AI is intentionally simple so balance issues remain visible.

## Data and Simulation

- Structured content lives in CSV files under `data/`.
- Gameplay-content CSVs should include player-facing plain-language descriptions when the content represents something a player reads or uses during play, including abilities, mystery cards, action rows, dice faces, and track spaces.
- The simulation is deterministic when given a seed.
- Batch simulations are supported for balance testing and metric collection.

## Active Design Hooks

- fuel failure behavior
- yellow, orange, and red die balance
- number and strength of dice rows
- ability market pacing and card power
- impact of first player timing
