from simulation.theory.action import Vote
from simulation.theory.engine import Engine
from simulation.theory.utils import (
    ATTESTATORS_PER_SLOT,
    B,
    BASE_INCREMENT,
    NUM_OF_VALIDATORS,
    W_h,
    W_p,
    W_s,
    W_sum,
    W_t,
)


def test_fork_AHA():
    alpha = 0.201
    adv_power = int(alpha * ATTESTATORS_PER_SLOT)
    honest_power = ATTESTATORS_PER_SLOT - adv_power

    engine = Engine.make_engine(
        "AHA", entity_to_voting_power={"A": adv_power, "H": honest_power}
    )
    # SLOT 1 - 0
    engine = engine.build_block(slot=1, parent_slot=0)
    head_H = engine.head("H")
    head_A = engine.head("A")
    assert head_H == 0
    assert head_A == 1

    engine = engine.slot_progress()
    # SLOT 1 - 1
    engine = engine.add_votes(
        (
            Vote(
                entity="A",
                from_slot=1,
                min_index=0,
                max_index=adv_power - 1,
                to_slot=head_A,
            ),
            Vote(
                entity="H",
                from_slot=1,
                min_index=0,
                max_index=honest_power - 1,
                to_slot=head_H,
            ),
        )
    )

    head_H = engine.head("H")
    head_A = engine.head("A")
    assert head_H == 0
    assert head_A == 1

    engine = engine.slot_progress()
    # SLOT 2 - 0
    engine = engine.build_block(slot=2, parent_slot=head_H, knowledge=("A",))
    engine = engine.slot_progress()
    # SLOT 2 - 1
    head_H = engine.head("H")
    head_A = engine.head("A")
    assert head_H == 2
    assert head_A == 2

    engine = engine.add_votes(
        (
            Vote(
                entity="A",
                from_slot=2,
                min_index=0,
                max_index=adv_power - 1,
                to_slot=1,
            ),
            Vote(
                entity="H",
                from_slot=2,
                min_index=0,
                max_index=honest_power - 1,
                to_slot=head_H,
            ),
        )
    )
    engine = engine.slot_progress()
    # SLOT 3 - 0

    head_H = engine.head("H")
    head_A = engine.head("A")
    assert head_H == 2
    assert head_A == 2

    engine = engine.build_block(slot=3, parent_slot=1, knowledge=("H",))
    engine = engine.add_knowledge({"H": (1,)})  # revealing previous slot

    head_H = engine.head("H")
    head_A = engine.head("A")
    assert head_H == 3
    assert head_A == 3

    # Testing correct wallet state
    adv_reward_slot_1 = int(
        adv_power * B * BASE_INCREMENT * (W_s + W_t) / W_sum
    )  # not timely, but correct source and target
    honest_reward_slot_1 = int(
        honest_power * B * BASE_INCREMENT * (W_s + W_t) / W_sum
    )  # "wrong" head vote, but correct source and target

    adv_reward_slot_2 = int(
        adv_power * BASE_INCREMENT * B * (W_s + W_t + W_h * alpha) / W_sum
    )  # timely head vote
    honest_reward_slot_2 = int(
        honest_power * BASE_INCREMENT * B * (W_s + W_t) / W_sum
    )  # timely head vote

    inclusion_reward = int(
        W_p / (W_sum - W_p)
        * (
            adv_reward_slot_1
            + honest_reward_slot_1
            + adv_reward_slot_2
            + honest_reward_slot_2
        )
    )  # book, page 105

    reward_adv = adv_reward_slot_1 + adv_reward_slot_2 + inclusion_reward
    reward_honest = honest_reward_slot_1 + honest_reward_slot_2

    wallet_state = engine.blocks[3].wallet_state
    assert abs(wallet_state.address_to_money["A"] - reward_adv) < 1000 # 1000 GWei is insignificant
    assert abs(wallet_state.address_to_money["H"] - reward_honest) < 1000
