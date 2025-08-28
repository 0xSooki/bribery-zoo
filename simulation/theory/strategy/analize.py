from collections import defaultdict
from dataclasses import dataclass
from numbers import Real

from frozendict import frozendict
from simulation.theory.action import WalletState
from simulation.theory.engine import Engine
from simulation.theory.strategy.adversary import AdvParams
from simulation.theory.strategy.base import Params
from simulation.theory.strategy.bribee import BribeeParams
from simulation.theory.strategy.game import Game, SymbolicRun
from simulation.theory.utils import ATTESTATORS_PER_SLOT, B, BASE_INCREMENT, Slot

@dataclass
class GameParams:
    block_reward: int
    success_reward: int
    base_reward_unit: Real
    deadline_reward_unit: Real
    deadline_payback_unit: Real

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
    game_params: GameParams
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
    run: SymbolicRun,
    game_params: GameParams
) -> dict[frozendict[str, Params], GameOutcome]:
    table: dict[frozendict[str, Params], GameOutcome] = {}
    for params, (engine, events) in run.table.items():
        table[params] = concrete_outcome(engine, events, run.honest_player, run.adv_player, run.all_params, game_params)
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

def main():
    alpha = int(0.16 * ATTESTATORS_PER_SLOT)
    beta = int(0.05 * ATTESTATORS_PER_SLOT)
    honest = ATTESTATORS_PER_SLOT - alpha - beta

    game = Game(
        base_slot=0,
        chain_string="AHA",
        honest_entity="H",
        adv_entity="A",
        bribee_entities={"B"},
        entity_to_voting_power={"H": honest, "A": alpha, "B": beta},
    )
    best_adv = AdvParams(censor_from_slot=None, patient=True, break_bad_slot=None)
    best_bribee = BribeeParams(
        break_bad_slot=3,
        censoring_from_slot=None,
        send_votes_when_able=False,
        finish_offers_regardless_of_abort=False,
        last_minute=False,
        only_sending_to_deadline_proposing_entity=False,
    )
    #base_reward_unit=int(B * BASE_INCREMENT * 0.2),
        #deadline_reward_unit=0,  # B,
        #deadline_payback_unit=0,  # B,

    game_params = GameParams(
        block_reward=50_000_000,
        success_reward=50_000_000,
        base_reward_unit=int(B * BASE_INCREMENT * 0.2),
        deadline_reward_unit=0,
        deadline_payback_unit=0,
    )

    all_params = game.all_params()

    single = False
    if single:
        engine, events = game.play(best_adv, {"B": best_bribee})
        outcome = concrete_outcome(engine, events, "H", "A", all_params, game_params)
        print(outcome.success)
        print(outcome.wallet_state.address_to_money)
    else:
        run = game.compute_table()

        table = concrete_table(run, game_params)
        
        honest_player = game.honest_entity
        nashes = nash_equillibria(table, all_params)
        print(len(nashes))
        eq, outcome = max(nashes.items(), key=lambda x: x[1].rewards["B"])
        attacks = damage_cost_ratio(table, all_params, eq, alpha=0.5)
        pretty_print_equillibria(eq, outcome)
        print()
        pretty_print_deviations(attacks, table, eq)


if __name__ == "__main__":
    main()