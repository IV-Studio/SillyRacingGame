from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.game import GameConfig, RacerGame, run_batch


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Racer Prototype simulations.")
    parser.add_argument("--players", type=int, default=3, help="Number of players.")
    parser.add_argument("--seed", type=int, default=1, help="Random seed.")
    parser.add_argument("--games", type=int, default=1, help="Number of games to simulate.")
    args = parser.parse_args()

    if args.games <= 1:
        game = RacerGame(ROOT, GameConfig(player_count=args.players, seed=args.seed))
        result = game.run()
        print(f"Winner: {result['winner']}")
        print(f"Rounds: {result['rounds']}")
        for player in result["players"]:
            abilities = ", ".join(ability.name for ability in player.abilities) or "none"
            cards = ", ".join(card.name for card in player.mystery_cards) or "none"
            print(
                f"{player.name}: laps={player.laps} pos={player.position} coins={player.coins} "
                f"fuel={player.fuel} abilities={abilities} cards={cards}"
            )
    else:
        summary = run_batch(ROOT, games=args.games, player_count=args.players, seed=args.seed)
        print(f"Games: {summary['games']}")
        print(f"Average rounds: {summary['average_rounds']:.2f}")
        print(f"Average movement per round: {summary['average_movement_per_round']:.2f}")
        print(f"Average lap progression: {summary['average_lap_progression']:.2f}")
        print(f"Win rates: {summary['win_rates']}")
        print(f"Average stats: {summary['average_stats']}")
        print(f"Ability win rates: {summary['ability_win_rates']}")


if __name__ == "__main__":
    main()
