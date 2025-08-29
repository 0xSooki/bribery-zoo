import numpy as np
import pytest
from simulation.theory.strategy.analize import concrete_table, nash_equillibria
from simulation.theory.strategy.game_optim import (
    GameParams,
    apply_params,
    base_index,
    fast_nash_equillibria,
    precompile_table,
)
from simulation.theory.strategy.game import Game
from simulation.theory.utils import ATTESTATORS_PER_SLOT


arguments = [
    ("AHA", 0.1, 0.14, 1000, 200302, 1046, 7381, 208),
]


@pytest.mark.parametrize(
    "chain_string, alpha, beta, block_reward, success_reward, base_reward_unit, deadline_reward_unit, deadline_payback_unit",
    arguments,
)
def test_rewards_matching(
    chain_string: str,
    alpha: float,
    beta: float,
    block_reward: int,
    success_reward: int,
    base_reward_unit: int,
    deadline_reward_unit: int,
    deadline_payback_unit: int,
):
    adv_voting_power = int(alpha * ATTESTATORS_PER_SLOT)
    bribee_voting_power = int(beta * ATTESTATORS_PER_SLOT)
    honest = ATTESTATORS_PER_SLOT - adv_voting_power - bribee_voting_power

    game = Game(
        base_slot=0,
        chain_string=chain_string,
        honest_entity="H",
        adv_entity="A",
        bribee_entities={"B"},
        entity_to_voting_power={
            "H": honest,
            "A": adv_voting_power,
            "B": bribee_voting_power,
        },
    )

    game_params = GameParams(
        block_reward=block_reward,
        success_reward=success_reward,
        base_reward_unit=base_reward_unit,
        deadline_reward_unit=deadline_reward_unit,
        deadline_payback_unit=deadline_payback_unit,
    )

    run = game.run_all()
    compiled_table = concrete_table(run, game_params)
    pre_table, params_to_index, _, array = precompile_table(run)

    fast_rewards = apply_params(array, game_params)
    fast_equill = fast_nash_equillibria(fast_rewards)
    equill = nash_equillibria(compiled_table, run.all_params)

    for params, outcome in compiled_table.items():
        assert outcome.success == pre_table[params].success
        assert outcome.wallet_state == pre_table[params].wallet_state
        assert outcome.events == pre_table[params].events
        assert outcome.entity_to_blocks == pre_table[params].entity_to_blocks
        assert outcome.slot_to_canonical == pre_table[params].slot_to_canonical
        for idx, player in enumerate(run.all_params):
            big_index = [idx] + base_index(params, params_to_index)
            fr_np = fast_rewards[*big_index]
            assert outcome.rewards.get(player, 0) == int(fr_np)

    assert int(np.sum(fast_equill)) == len(equill)
    for params in equill:
        big_index = base_index(params, params_to_index)
        assert fast_equill[*big_index]
