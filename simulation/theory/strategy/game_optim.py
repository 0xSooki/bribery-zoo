from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence
from frozendict import frozendict
from simulation.theory.action import WalletState
from simulation.theory.strategy.base import Params
from simulation.theory.strategy.game import SymbolicRun
from simulation.theory.utils import Slot

import numpy as np


@dataclass
class Games:
    success: bool
    indices: Sequence[Sequence[int]]

    entity_to_reward: dict[str, int]
    damage_cost_ratios: Sequence[Sequence[float]]
    best_deviation: float


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
    weight_array = np.zeros(shape=sizes, dtype=np.int64)

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
            weight_array[*arr_idx] = wallet_state.address_to_money.get(player, 0)
            arr_idx = [1, player_idx] + base_idx
            if player == run.adv_player:
                weight_array[*arr_idx] = int(success)
            arr_idx = [2, player_idx] + base_idx
            weight_array[*arr_idx] = entity_to_blocks[player]
            arr_idx = [3, player_idx] + base_idx
            weight_array[*arr_idx] = entity_to_symbol_to_amount[player]["base_reward"]
            arr_idx = [4, player_idx] + base_idx
            weight_array[*arr_idx] = entity_to_symbol_to_amount[player][
                "deadline_reward"
            ]
            arr_idx = [5, player_idx] + base_idx
            weight_array[*arr_idx] = entity_to_symbol_to_amount[player][
                "deadline_payback"
            ]

    return table, params_to_index, index_to_params, weight_array


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
) -> Games | None:
    if np.sum(equillbria) == 0:
        return None
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
    
    deviations = deviation_vectorized(reward)
    best_deviation = np.min(deviations[:, everyonehappy].max(axis=0))
    indices = np.argwhere(everyonehappy)

    max_rewards = reward[:, *indices[0]]
    assert list(max_rewards) == [entity_to_reward[entity] for entity in all_params]

    deviations = [[dev[*index] for dev in deviations] for index in indices] # [deviation(reward, index) for index in indices]

    return Games(
        success=bool(np.sum(success & everyonehappy)),
        indices=indices,
        entity_to_reward=entity_to_reward,
        damage_cost_ratios=np.array(deviations),
        best_deviation=best_deviation
    )


def cannot_make_it_worse(
    reward: np.ndarray,
    min_values: list[int],
    all_params: dict[str, list[Params]],
    adv_player: str,
) -> np.ndarray:
    result = np.ones(shape=reward.shape[1:], dtype=bool)
    for idx, _ in enumerate(all_params):
        result &= min_values[idx] <= reward[idx]      

    return result


def deviation(reward: np.ndarray, point: Sequence[int]) -> list[float]:
    N: int = reward.shape[0]
    orig_rewards = reward[:, *point]
    result = [float("nan")] * N
    
    for player_idx in range(N):
        for other_idx in range(N):
            if player_idx == other_idx:
                continue
            slicer = [slice(None) if i == other_idx else point[i] for i in range(N)]
            costs = orig_rewards[other_idx] - reward[other_idx, *slicer]
            assert np.all(costs >= 0)
            damage = orig_rewards[player_idx] - reward[player_idx, *slicer]
            with np.errstate(divide="ignore", invalid="ignore"):
                result[player_idx] = np.nanmax([np.nanmax(damage / costs), result[player_idx]])
    return result

def deviation_vectorized(reward: np.ndarray) -> list[np.ndarray]:
    N: int = reward.shape[0]
    result: list[np.ndarray] = []
    for orig_player in range(N):
        max_deviation = np.full(shape=reward.shape[1:], fill_value=np.nan, dtype=np.float64)
        for other_player in range(N):
            if orig_player == other_player:
                continue
            
            current_deviation = np.full(reward.shape[1:], fill_value=2 * np.max(reward) + 1, dtype=np.int64)
            max_other_players_rewards = reward[other_player].max(axis=other_player, keepdims=True)
            max_other_players_rewards = np.broadcast_to(max_other_players_rewards, reward.shape[1:])
            
            max_mask = reward[other_player] == max_other_players_rewards
            cost = max_other_players_rewards - reward[other_player]
            current_deviation[max_mask] = reward[orig_player][max_mask]
            biggest_damage = np.min(current_deviation, axis=other_player, keepdims=True)
            biggest_damage = np.broadcast_to(biggest_damage, reward.shape[1:])
            
            eq_value = np.nanmax(np.array(biggest_damage - reward[orig_player], dtype=np.float64) / cost, axis=other_player, keepdims=True)
            eq_value = np.broadcast_to(eq_value, reward.shape[1:])
            
            best_eq_mask = max_mask & (biggest_damage == reward[orig_player])
            
            current_deviation = np.array(current_deviation, dtype=np.float64)
            current_deviation[best_eq_mask] = eq_value[best_eq_mask]
            max_deviation[~best_eq_mask] = np.inf
            
            max_deviation = np.fmax(max_deviation, current_deviation)
        result.append(max_deviation)
    return np.array(result)