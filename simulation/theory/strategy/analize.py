from collections import defaultdict
from dataclasses import dataclass
from numbers import Real
import os
import pickle
import time
from typing import Sequence

from frozendict import frozendict
import numpy as np
from tqdm import tqdm
from simulation.theory.action import WalletState
from simulation.theory.engine import Engine
from simulation.theory.strategy.adversary import AdvParams
from simulation.theory.strategy.base import Params
from simulation.theory.strategy.bribee import BribeeParams
from simulation.theory.strategy.game_optim import (
    GameParams,
    Games,
    PreGameOutcome,
    apply_params,
    best_case_reward,
    cannot_make_it_worse,
    deviation,
    fast_nash_equillibria,
    get_params,
    precompile_table,
)
from simulation.theory.strategy.game import Game, SymbolicRun
from simulation.theory.utils import ATTESTATORS_PER_SLOT, B, BASE_INCREMENT, Slot


@dataclass
class GameOutcome:
    rewards: dict[str, int]
    consensus_voting_rewards: dict[str, int]
    wallet_state: WalletState
    slot_to_canonical: dict[int, str]
    entity_to_blocks: dict[int, int]
    success: bool
    events: list[tuple[Slot, str]]


@dataclass
class PrecompiledOutcome:

    consensus_voting_rewards: dict[str, int]
    wallet_state: WalletState
    slot_to_canonical: dict[int, str]
    entity_to_blocks: dict[int, int]
    success: bool
    events: list[tuple[Slot, str]]


@dataclass
class Deviation:
    params: Params
    cost: int
    damage: int

    def ranking(self, alpha: float) -> float:
        if self.damage < 1_000:
            return 1 + self.cost  # we dont care about negligable attacks
        return (1 + self.cost) ** alpha / self.damage


def concrete_outcome(
    engine: Engine,
    events: list[tuple[Slot, str]],
    honest_player: str,
    adv_player: str,
    all_params: dict[str, list[Params]],
    game_params: GameParams,
) -> GameOutcome:
    head = engine.head(honest_player)
    _slot = head
    canonicals_slots: list[int] = []
    while _slot in engine.blocks:
        canonicals_slots.append(_slot)
        _slot = engine.blocks[_slot].parent_slot
    slot_to_canonical: dict[int, str] = {
        slot: "C" if slot in canonicals_slots else "N" for slot in engine.blocks
    }
    entity_to_blocks: dict[str, int] = defaultdict(int)
    success = True
    for slot, canonical in slot_to_canonical.items():
        if slot in engine.slot_to_owner:
            if (engine.slot_to_owner[slot] == honest_player) == (canonical == "C"):
                success = False
            if canonical == "C":
                entity_to_blocks[engine.slot_to_owner[slot]] += 1

    wallet_state = engine.blocks[head].wallet_state

    address_to_money = wallet_state.compute_real_address_to_money(
        base_reward=game_params.base_reward_unit,
        deadline_reward=game_params.deadline_reward_unit,
        deadline_payback=game_params.deadline_payback_unit,
    )
    for entity in all_params:
        address_to_money[entity] = (
            address_to_money.get(entity, 0)
            + entity_to_blocks[entity] * game_params.block_reward
            + bool(success and entity == adv_player) * game_params.success_reward
        )
    return GameOutcome(
        rewards=address_to_money,
        consensus_voting_rewards=dict(wallet_state.address_to_money),
        wallet_state=wallet_state,
        slot_to_canonical=slot_to_canonical,
        entity_to_blocks=entity_to_blocks,
        success=success,
        events=events,
    )


def concrete_table(
    run: SymbolicRun, game_params: GameParams
) -> dict[frozendict[str, Params], GameOutcome]:
    table: dict[frozendict[str, Params], GameOutcome] = {}
    for params, (engine, events) in run.table.items():
        table[params] = concrete_outcome(
            engine,
            events,
            run.honest_player,
            run.adv_player,
            run.all_params,
            game_params,
        )
    return table


def nash_equillibria(
    table: dict[frozendict[str, Params], GameOutcome],
    all_params: dict[str, list[Params]],
) -> dict[frozendict[str, Params], GameOutcome]:
    """
    Returning all those params -> outcome pairs, where params yield a Nash equillibria
    """
    equilibria: dict[frozendict[str, Params], GameOutcome] = {}

    # Cartesian product of all strategies for all players
    for strategies, outcome in table.items():

        is_equilibrium = True
        for player, params in all_params.items():
            current_payoff = outcome.rewards[player]
            # Check deviations for this player
            for alt_strategy in params:
                if alt_strategy == strategies[player]:
                    continue

                deviated_profile = dict(strategies)
                deviated_profile[player] = alt_strategy
                alt_payoff = table[frozendict(deviated_profile)].rewards[player]

                if alt_payoff > current_payoff:
                    is_equilibrium = False
                    break

            if not is_equilibrium:
                break

        if is_equilibrium:
            equilibria[strategies] = outcome

    return equilibria


def damage_cost_ratio(
    table: dict[frozendict[str, Params], GameOutcome],
    all_params: dict[str, list[Params]],
    equillibrium: frozendict[str, Params],
    alpha: float,
) -> dict[str, dict[str, Deviation | None]]:
    result: dict[str, dict[str, Deviation | None]] = {}
    for player, deviations in all_params.items():
        result[player] = {}
        for other_player in all_params:
            if player == other_player:
                continue
            value = table[equillibrium].rewards[other_player]
            best_deviation: Deviation | None = None
            for deviation in deviations:
                new_point = dict(equillibrium)
                new_point[player] = deviation
                new_values = table[frozendict(new_point)]
                assert new_values.rewards[player] <= table[equillibrium].rewards[player]
                cost = table[equillibrium].rewards[player] - new_values.rewards[player]
                damage = value - new_values.rewards[other_player]
                if damage > 0:
                    candidate = Deviation(deviation, cost, damage)
                    if best_deviation is None or best_deviation.ranking(
                        alpha
                    ) > candidate.ranking(alpha):
                        best_deviation = candidate
            result[player][other_player] = best_deviation
    return result


def pretty_print_events(events: list[tuple[Slot, str]]) -> None:
    for slot, event in events:
        print(f"Slot: {slot.num}: {event}")


def pretty_print_equillibria(
    eq: frozendict[str, Params],
    outcome: GameOutcome,
) -> None:
    for entity, params in eq.items():
        print(f"{entity}:")
        for attr, value in params.__dict__.items():
            print(f"  {attr}={value}")
        print()
    print("===================")
    for entity, reward in outcome.rewards.items():
        print(f"{entity} => {reward:_}")
    print()
    print("EVENTS FOR NASH EQUILLIBRIA:")
    pretty_print_events(outcome.events)


def pretty_print_deviations(
    attacks: dict[str, dict[str, Deviation | None]],
    table: dict[frozendict[str, Params], GameOutcome],
    eq: frozendict[str, Params],
) -> None:
    for attacker, entry in attacks.items():
        print("===========================")
        print(f"Attacker: {attacker}")
        for attacked, deviation in entry.items():
            print(f"  Attacked: {attacked}")
            if deviation is None:
                print("    -")
            else:
                print(f"    COST: {deviation.cost:_} => DAMAGE: {deviation.damage:_}")
                print(f"    New_params:")
                for attr, value in deviation.params.__dict__.items():
                    print(f"      {attr}={value}")
                print()
                print("EVENTS:")
                point = dict(eq)
                point[attacker] = deviation.params
                pretty_print_events(table[frozendict(point)].events)
                print()


class Analizer:
    pre_table: dict[frozendict[str, Params], PreGameOutcome]
    params_to_index: dict[str, dict[Params, int]]
    index_to_params: dict[str, dict[int, Params]]
    weight_array: np.ndarray
    all_params: dict[str, list[Params]]

    def __init__(
        self,
        chain_string: str,
        honest_entity: str,
        adv_entity: str,
        entity_to_alphas: dict[str, float],
    ):
        self.chain_string = chain_string
        self.honest_entity = honest_entity
        self.adv_entity = adv_entity
        self.bribee_entities = set(entity_to_alphas) - {
            self.adv_entity,
            self.honest_entity,
        }
        byzantine_voting_powers = {
            entity: int(ATTESTATORS_PER_SLOT * alpha)
            for entity, alpha in entity_to_alphas.items()
        }
        self.entity_to_voting_power = {
            self.honest_entity: ATTESTATORS_PER_SLOT
            - sum(byzantine_voting_powers.values()),
            **byzantine_voting_powers,
        }

        Game(
            base_slot=0,
            chain_string=self.chain_string,
            honest_entity=self.honest_entity,
            adv_entity=self.adv_entity,
            bribee_entities=self.bribee_entities,
            entity_to_voting_power=self.entity_to_voting_power,
        )

    def game(self):
        entity_to_voting_str = ",".join(
            [f"{entity}={vote}" for entity, vote in self.entity_to_voting_power.items()]
        )
        self.base_folder = os.path.join(
            "simulation", "cache", f"{self.chain_string}-{entity_to_voting_str}"
        )
        os.makedirs(self.base_folder, exist_ok=True)
        filename = os.path.join(self.base_folder, "precompiles.pkl")
        if os.path.exists(filename):
            print("Loading game from memory...")
            with open(filename, "rb") as f:
                (
                    self.pre_table,
                    self.params_to_index,
                    self.index_to_params,
                    self.weight_array,
                    self.all_params,
                ) = pickle.load(f)
            print("Loaded game")
        else:
            print("Playing games")
            game = Game(
                base_slot=0,
                chain_string=self.chain_string,
                honest_entity=self.honest_entity,
                adv_entity=self.adv_entity,
                bribee_entities=self.bribee_entities,
                entity_to_voting_power=self.entity_to_voting_power,
            )
            self.all_params = game.all_params()
            run = game.run_all()
            (
                self.pre_table,
                self.params_to_index,
                self.index_to_params,
                self.weight_array,
            ) = precompile_table(run)
            print("Done")
            print("Saving games...")
            with open(filename, "wb") as f:
                pickle.dump(
                    (
                        self.pre_table,
                        self.params_to_index,
                        self.index_to_params,
                        self.weight_array,
                        self.all_params,
                    ),
                    f,
                )
            print("Games saved")

        self.base_strategies = {
            entity: (
                AdvParams(
                    censor_from_slot=None,
                    patient=True,
                    break_bad_slot=0,
                )
                if entity == self.adv_entity
                else BribeeParams(
                    break_bad_slot=0,
                    censoring_from_slot=None,
                    send_votes_when_able=False,
                    finish_offers_regardless_of_abort=False,
                    last_minute=False,
                    only_sending_to_deadline_proposing_entity=False,
                )
            )
            for entity in self.all_params
        }
        self.base_big_index = [
            self.params_to_index[entity][param]
            for entity, param in self.base_strategies.items()
        ]

    def search_equillibrias(
        self, step: int, block_reward: int, success_reward: int, upper_bound: int
    ) -> dict[GameParams, Games | None]:
        filename = os.path.join(
            self.base_folder, f"{block_reward=},{success_reward=}.pkl"
        )

        result: dict[GameParams, Games | None] = {}
        if os.path.exists(filename):
            with open(filename, "rb") as f:
                result = pickle.load(f)

        bar = tqdm(total=(1 + upper_bound // step) ** 3, desc="Tables calculated")
        try:
            with np.errstate(divide="ignore", invalid="ignore"):
                for base_reward_unit in range(0, upper_bound + 1, step):
                    for deadline_reward_unit in range(0, upper_bound + 1, step):
                        for deadline_payback_unit in range(0, upper_bound + 1, step):
                            bar.update(1)
                            game_params = GameParams(
                                block_reward=block_reward,
                                success_reward=success_reward,
                                base_reward_unit=base_reward_unit,
                                deadline_reward_unit=deadline_reward_unit,
                                deadline_payback_unit=deadline_payback_unit,
                            )

                            if game_params in result:
                                continue
                            rewards = apply_params(self.weight_array, game_params)
                            base_strategy_rewards: list[float] = [
                                rewards[idx, *self.base_big_index]
                                for idx, _ in enumerate(self.all_params)
                            ]
                            filtered_pts = cannot_make_it_worse(
                                rewards,
                                base_strategy_rewards,
                                self.all_params,
                                self.adv_entity,
                            )
                            equill = fast_nash_equillibria(rewards)

                            result[game_params] = best_case_reward(
                                self.weight_array,
                                rewards,
                                equill & filtered_pts,
                                self.all_params,
                                self.adv_entity,
                            )

        except KeyboardInterrupt as ki:
            with open(filename, "wb") as f:
                pickle.dump(result, f)
            raise ki
        bar.close()

        with open(filename, "wb") as f:
            pickle.dump(result, f)
        return result

    def most_profiting_succesful_forks(
        self,
        table: dict[GameParams, Games | None],
        max_ratio: float,
    ) -> tuple[GameParams, dict[str, Params], int, Sequence[float], dict[str, float]] | None:
        def eval_games(games: Games) -> float:
            return (
                games.entity_to_reward[self.adv_entity]
                if any(max(ratios) <= max_ratio for ratios in games.damage_cost_ratios)
                else float("-inf")
            )

        successful_outcomes = [
            (params, outcome)
            for params, outcome in table.items()
            if outcome is not None
            and outcome.success
        ]
        if not successful_outcomes:
            return None
        game_params, games = max(
            successful_outcomes,
            key=lambda x: eval_games(x[1])
        )
        if eval_games(games) == float("-inf"):
            return None
        
        indices, ratios = max([(indices, ratios) for indices, ratios in zip(games.indices, games.damage_cost_ratios) if max(ratios) <= max_ratio], key=lambda x: sum(x[1]))

        strategy = {
            entity: self.index_to_params[entity][idx]
            for idx, entity in zip(indices, self.all_params)
        }
        rewards = apply_params(self.weight_array, game_params)
        base_rewards = {entity: reward for entity, reward in zip(self.all_params, rewards[:, *self.base_big_index])}
        return game_params, strategy, games.entity_to_reward, ratios, base_rewards


def main():
    analizer = Analizer(
        chain_string="HAA",
        honest_entity="H",
        adv_entity="A",
        entity_to_alphas={"A": 0.40, "B": 0.14},
    )
    analizer.game()
    table = analizer.search_equillibrias(
        step=200, upper_bound=6_200, block_reward=50_000_000, success_reward=150_000_000
    )
    max_ratio = 8
    best_fork = (
        analizer.most_profiting_succesful_forks(table, max_ratio)
    )
    if best_fork is None:
        print("Not found")
        return
    game_params, params, entity_to_rewards, ratios, base_rewards = best_fork

    print("Game params:")
    for attr, value in game_params.__dict__.items():
        if isinstance(value, int):
            print(f"  {attr}={value:_}")
        else:
            print(f"  {attr}={value}")
    print()
    for entity, params in params.items():
        print(f"Entity: {entity} => {entity_to_rewards[entity]:_} vs {base_rewards[entity]:_}")
        for attr, value in params.__dict__.items():
            print(f"  {attr}={value}")
        print()
    print()

    for entity, ratio in zip(analizer.all_params, ratios):
        print(f"  {entity} => {ratio}")
    #print(f"damage_cost_ratio={ratios}")
    #print(f"{len(table[game_params].indices)=}")

    # main()
if __name__ == "__main__":
    main()