from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence
from frozendict import frozendict
from simulation.theory.action import WalletState
from simulation.theory.strategy.base import Params
from simulation.theory.strategy.game import SymbolicRun
from simulation.theory.utils import Slot

import numpy as np


@dataclass(frozen=True)
class GameParams:
    block_reward: int
    success_reward: int
    base_reward_unit: int
    deadline_reward_unit: int
    deadline_payback_unit: int


@dataclass
class PreGameOutcome:
    wallet_state: WalletState
    slot_to_canonical: dict[int, str]
    entity_to_blocks: dict[int, int]
    success: bool
    events: list[tuple[Slot, str]]


def base_index(
    params: frozendict[str, Params], params_to_index: dict[str, dict[Params, int]]
) -> list[int]:
    return [params_to_index[entity][param] for entity, param in params.items()]


def get_params(
    index: Sequence[int],
    index_to_params: dict[str, dict[int, Params]],
    players: Sequence[str],
) -> frozendict[str, Params]:
    return frozendict(
        {player: index_to_params[player][idx] for idx, player in zip(index, players)}
    )


def precompile_table(
    run: SymbolicRun,
) -> tuple[
    dict[frozendict[str, Params], PreGameOutcome],
    dict[str, dict[Params, int]],
    dict[str, dict[int, Params]],
    np.ndarray,
]:
    sizes = [6, len(run.all_params)] + [
        len(params) for params in run.all_params.values()
    ]
    array = np.zeros(shape=sizes, dtype=np.int64)

    index_to_params: dict[str, dict[int, Params]] = {}
    params_to_index: dict[str, dict[Params, int]] = {}
    for entity, params in run.all_params.items():
        index_to_params[entity] = {}
        params_to_index[entity] = {}
        for i, param in enumerate(params):
            index_to_params[entity][i] = param
            params_to_index[entity][param] = i

    table: dict[frozendict[str, Params], PreGameOutcome] = {}
    for params, (engine, events) in run.table.items():
        base_idx = base_index(params, params_to_index)

        head = engine.head(run.honest_player)
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
                if (engine.slot_to_owner[slot] == run.honest_player) == (
                    canonical == "C"
                ):
                    success = False
                if canonical == "C":
                    entity_to_blocks[engine.slot_to_owner[slot]] += 1

        wallet_state = engine.blocks[head].wallet_state

        table[params] = PreGameOutcome(
            wallet_state=wallet_state,
            slot_to_canonical=slot_to_canonical,
            entity_to_blocks=entity_to_blocks,
            success=success,
            events=events,
        )
        entity_to_symbol_to_amount: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        for symbolic_tx in wallet_state.symbolic_ledger:
            entity_to_symbol_to_amount[symbolic_tx.from_address][
                symbolic_tx.symbol
            ] -= symbolic_tx.all_indices
            entity_to_symbol_to_amount[symbolic_tx.to_address][
                symbolic_tx.symbol
            ] += symbolic_tx.all_indices

        for player_idx, player in enumerate(run.all_params):
            arr_idx = [0, player_idx] + base_idx
            array[*arr_idx] = wallet_state.address_to_money.get(player, 0)
            arr_idx = [1, player_idx] + base_idx
            if player == run.adv_player:
                array[*arr_idx] = int(success)
            arr_idx = [2, player_idx] + base_idx
            array[*arr_idx] = entity_to_blocks[player]
            arr_idx = [3, player_idx] + base_idx
            array[*arr_idx] = entity_to_symbol_to_amount[player]["base_reward"]
            arr_idx = [4, player_idx] + base_idx
            array[*arr_idx] = entity_to_symbol_to_amount[player]["deadline_reward"]
            arr_idx = [5, player_idx] + base_idx
            array[*arr_idx] = entity_to_symbol_to_amount[player]["deadline_payback"]

    return table, params_to_index, index_to_params, array


def apply_params(array: np.ndarray, game_params: GameParams) -> np.ndarray:
    weights = np.array(
        [
            1,
            game_params.success_reward,
            game_params.block_reward,
            game_params.base_reward_unit,
            game_params.deadline_reward_unit,
            game_params.deadline_payback_unit,
        ],
        dtype=np.int64,
    )
    # result = array[0].copy()

    return np.tensordot(weights, array, axes=(0, 0))

    # for i in range(5):
    # result += array[i+1] * small_array[i]

    # return result


def fast_nash_equillibria(reward: np.ndarray) -> np.ndarray:
    N = reward.shape[0]
    eq_mask = np.ones(reward.shape[1:], dtype=bool)

    for player in range(N):
        # max reward over that player's strategy axis
        max_rewards = reward[player].max(axis=player, keepdims=True)

        # profiles where player is playing a max-reward strategy
        best_responses = reward[player] == max_rewards

        # require equilibrium profiles to be best responses for every player
        eq_mask &= best_responses

    return eq_mask


def best_case_reward(
    weight_array: np.ndarray,
    reward: np.ndarray,
    equillbria: np.ndarray,
    all_params: dict[str, list[Params]],
    adv_player: str,
):
    adv_idx = list(all_params).index(adv_player)
    success = weight_array[1, adv_idx]
    max_val: int = 0

    everyonehappy = np.ones_like(equillbria)

    entity_to_reward: dict[str, int] = {}
    for idx, entity in enumerate(all_params):
        if (
            entity == adv_player
        ):  # For excluding cases where only the adversary would be happy
            continue
        relevant = equillbria * reward[idx]
        max_val = int(np.max(relevant))
        everyonehappy &= max_val == relevant
        entity_to_reward[entity] = max_val

    assert np.sum(everyonehappy)

    relevant = everyonehappy * reward[adv_idx]
    adv_reward = int(np.max(relevant))
    assert adv_reward > 0
    everyonehappy &= relevant == adv_reward
    entity_to_reward[adv_player] = adv_reward

    assert np.sum(everyonehappy)

    indices = np.argwhere(everyonehappy)

    max_rewards = reward[:, *indices[0]]
    assert list(max_rewards) == [entity_to_reward[entity] for entity in all_params]

    return bool(np.sum(success & everyonehappy)), indices, entity_to_reward
