import pytest
from simulation.theory.action import OfferBribery, TakeBribery, Vote, SingleOfferBribery
from simulation.theory.engine import Engine
from simulation.theory.utils import (
    ATTESTATORS_PER_SLOT,
    B,
    BASE_INCREMENT,
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
        W_p
        / (W_sum - W_p)
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
    assert (
        abs(wallet_state.address_to_money["A"] - reward_adv) < 1000
    )  # 1000 GWei is insignificant
    assert abs(wallet_state.address_to_money["H"] - reward_honest) < 1000


arguments = (
    (1, 2, 3),
    (10, 2, 3),
    (1, 20, 3),
    (1, 2, 30),
    (100, 20000, 3000),
)


@pytest.mark.parametrize("base_reward, deadline_reward, deadline_payback", arguments)
def test_declined_takeBribery(
    base_reward: int, deadline_reward: int, deadline_payback: int
):
    alpha = 0.1
    censor_votes = lambda _: []  # we censor every vote for simplicity of reward checks
    beta_full = 0.11  # (1 - alpha) * beta in the paper
    adv_power = int(alpha * ATTESTATORS_PER_SLOT)
    bribee_power = int(beta_full * ATTESTATORS_PER_SLOT)
    honest_power = ATTESTATORS_PER_SLOT - adv_power - bribee_power

    engine = Engine.make_engine(
        "AHA",
        entity_to_voting_power={"A": adv_power, "H": honest_power, "B": bribee_power},
    )
    # SLOT 1 - 0
    engine = engine.build_block(
        slot=1, parent_slot=0, knowledge=("A", "B"), censor_votes=censor_votes
    )
    head_H = engine.head("H")
    head_A = engine.head("A")
    head_B = engine.head("B")
    assert head_H == 0
    assert head_A == 1
    assert head_B == 1

    offer = OfferBribery(
        attests=(
            SingleOfferBribery(
                min_index=0,
                max_index=bribee_power - 1,
                from_slot=1,
                slot=1,
                deadline=3,
            ),
            SingleOfferBribery(
                min_index=0,
                max_index=bribee_power - 1,
                from_slot=2,
                slot=1,
                deadline=3,
            ),
        ),
        all_indices=1,
        bribee="B",
        briber="A",
        bribed_proposer="A",
        included_slots=frozenset({1}),
        excluded_slots=frozenset({2}),
    )
    # Offering bribe
    engine = engine.add_offer_bribery({"A": (offer,), "B": (offer,), "H": (offer,)})

    engine = engine.slot_progress()
    # SLOT 1 - 1
    engine = engine.add_votes(
        (
            Vote(
                entity="A",
                from_slot=1,
                min_index=0,
                max_index=adv_power - 1,
                to_slot=1,
            ),
            Vote(  # declining
                entity="B",
                from_slot=1,
                min_index=0,
                max_index=bribee_power - 1,
                to_slot=0,
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
    head_B = engine.head("B")
    assert head_H == 0
    assert head_A == 1
    assert head_B == 1

    engine = engine.slot_progress()
    # SLOT 2 - 0
    engine = engine.build_block(
        slot=2, parent_slot=head_H, knowledge=("A", "B"), censor_votes=censor_votes
    )
    engine = engine.slot_progress()
    # SLOT 2 - 1
    head_H = engine.head("H")
    head_A = engine.head("A")
    head_B = engine.head("B")
    assert head_H == 2
    assert head_A == 2
    assert head_B == 2

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
                entity="B",
                from_slot=2,
                min_index=0,
                max_index=bribee_power - 1,
                to_slot=2,
            ),
            Vote(
                entity="H",
                from_slot=2,
                min_index=0,
                max_index=honest_power - 1,
                to_slot=2,
            ),
        )
    )
    engine = engine.slot_progress()
    # SLOT 3 - 0

    head_H = engine.head("H")
    head_A = engine.head("A")
    head_A = engine.head("B")
    assert head_H == 2
    assert head_A == 2
    assert head_B == 2

    # Engine should not allow double voting
    take_bribery = TakeBribery(
        reference=OfferBribery,
        vote=Vote(
            entity="B",
            from_slot=1,
            min_index=0,
            max_index=bribee_power,
            to_slot=1,
        ),
        index=0,
    )
    try:
        engine.add_take_briberies(
            {"A": (take_bribery,), "H": (take_bribery,), "B": (take_bribery,)}
        )
        raise ValueError
    except Exception:
        pass

    engine = engine.build_block(
        slot=3,
        parent_slot=1,
        knowledge=("H", "B"),
        censor_votes=censor_votes,
        final=True,
    )
    engine = engine.add_knowledge({"H": (1,)})  # revealing previous slot

    head_H = engine.head("H")
    head_A = engine.head("A")
    head_B = engine.head("B")
    assert head_H == 2
    assert head_A == 2
    assert head_B == 2

    wallet_state = engine.blocks[2].wallet_state
    address_to_money = wallet_state.compute_real_address_to_money(
        base_reward=base_reward,
        deadline_reward=deadline_reward,
        deadline_payback=deadline_payback,
    )
    assert address_to_money.get("A", 0) == 0
    assert address_to_money.get("H", 0) == 0
    assert address_to_money.get("B", 0) == 0


@pytest.mark.parametrize("base_reward, deadline_reward, deadline_payback", arguments)
def test_accepted_takeBribery(
    base_reward: int, deadline_reward: int, deadline_payback: int
):
    alpha = 0.1
    censor_votes = lambda _: []  # we censor every vote for simplicity of reward checks
    beta_full = 0.11  # (1 - alpha) * beta in the paper
    adv_power = int(alpha * ATTESTATORS_PER_SLOT)
    bribee_power = int(beta_full * ATTESTATORS_PER_SLOT)
    honest_power = ATTESTATORS_PER_SLOT - adv_power - bribee_power

    engine = Engine.make_engine(
        "AHA",
        entity_to_voting_power={"A": adv_power, "H": honest_power, "B": bribee_power},
    )
    # SLOT 1 - 0
    engine = engine.build_block(
        slot=1, parent_slot=0, knowledge=("A", "B"), censor_votes=censor_votes
    )
    head_H = engine.head("H")
    head_A = engine.head("A")
    head_B = engine.head("B")
    assert head_H == 0
    assert head_A == 1
    assert head_B == 1

    offer = OfferBribery(
        attests=(
            SingleOfferBribery(
                min_index=0,
                max_index=bribee_power - 1,
                from_slot=1,
                slot=1,
                deadline=3,
            ),
            SingleOfferBribery(
                min_index=0,
                max_index=bribee_power - 1,
                from_slot=2,
                slot=1,
                deadline=3,
            ),
        ),
        all_indices=1,
        bribee="B",
        briber="A",
        bribed_proposer="A",
        included_slots=frozenset({1}),
        excluded_slots=frozenset({2}),
    )
    # Offering bribe
    engine = engine.add_offer_bribery({"A": (offer,), "B": (offer,), "H": (offer,)})

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
            Vote(  # accepting
                entity="B",
                from_slot=1,
                min_index=0,
                max_index=bribee_power - 1,
                to_slot=1,
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
    head_B = engine.head("B")
    assert head_H == 0
    assert head_A == 1
    assert head_B == 1

    engine = engine.slot_progress()
    # SLOT 2 - 0
    engine = engine.build_block(
        slot=2, parent_slot=head_H, knowledge=("A", "B"), censor_votes=censor_votes
    )
    engine = engine.slot_progress()
    # SLOT 2 - 1
    head_H = engine.head("H")
    head_A = engine.head("A")
    head_B = engine.head("B")
    assert head_H == 2
    assert head_A == 2
    assert head_B == 2

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
                entity="B",
                from_slot=2,
                min_index=0,
                max_index=bribee_power - 1,
                to_slot=1,
            ),
            Vote(
                entity="H",
                from_slot=2,
                min_index=0,
                max_index=honest_power - 1,
                to_slot=2,
            ),
        )
    )
    engine = engine.slot_progress()
    # SLOT 3 - 0

    head_H = engine.head("H")
    head_A = engine.head("A")
    head_A = engine.head("B")
    assert head_H == 2
    assert head_A == 2
    assert head_B == 2

    take_briberies = (
        TakeBribery(
            reference=offer,
            vote=Vote(
                entity="B",
                from_slot=1,
                min_index=0,
                max_index=bribee_power - 1,
                to_slot=1,
            ),
            index=0,
        ),
        TakeBribery(
            reference=offer,
            vote=Vote(
                entity="B",
                from_slot=2,
                min_index=0,
                max_index=bribee_power - 1,
                to_slot=1,
            ),
            index=1,
        ),
    )

    engine = engine.add_take_briberies(
        {"A": take_briberies, "H": take_briberies, "B": take_briberies}
    )

    engine = engine.build_block(
        slot=3,
        parent_slot=1,
        knowledge=("H", "B"),
        censor_votes=censor_votes,
        final=True,
    )
    engine = engine.add_knowledge({"H": (1,)})  # revealing previous slot

    head_H = engine.head("H")
    head_A = engine.head("A")
    head_B = engine.head("B")
    assert head_H == 3
    assert head_A == 3
    assert head_B == 3

    wallet_state = engine.blocks[3].wallet_state
    address_to_money = wallet_state.compute_real_address_to_money(
        base_reward=base_reward,
        deadline_reward=deadline_reward,
        deadline_payback=deadline_payback,
    )
    assert address_to_money.get("A", 0) == -base_reward - deadline_reward
    assert address_to_money.get("H", 0) == 0
    assert address_to_money.get("B", 0) == base_reward + deadline_reward


@pytest.mark.parametrize("base_reward, deadline_reward, deadline_payback", arguments)
def test_censored_takeBribery(
    base_reward: int, deadline_reward: int, deadline_payback: int
):
    alpha = 0.1
    censor_votes = lambda _: []  # we censor every vote for simplicity of reward checks
    beta_full = 0.11  # (1 - alpha) * beta in the paper
    adv_power = int(alpha * ATTESTATORS_PER_SLOT)
    bribee_power = int(beta_full * ATTESTATORS_PER_SLOT)
    honest_power = ATTESTATORS_PER_SLOT - adv_power - bribee_power

    engine = Engine.make_engine(
        "AHAH",
        entity_to_voting_power={"A": adv_power, "H": honest_power, "B": bribee_power},
    )
    # SLOT 1 - 0
    engine = engine.build_block(
        slot=1, parent_slot=0, knowledge=("A", "B"), censor_votes=censor_votes
    )
    head_H = engine.head("H")
    head_A = engine.head("A")
    head_B = engine.head("B")
    assert head_H == 0
    assert head_A == 1
    assert head_B == 1

    offer = OfferBribery(
        attests=(
            SingleOfferBribery(
                min_index=0,
                max_index=bribee_power - 1,
                from_slot=1,
                slot=1,
                deadline=3,
            ),
            SingleOfferBribery(
                min_index=0,
                max_index=bribee_power - 1,
                from_slot=2,
                slot=1,
                deadline=3,
            ),
        ),
        all_indices=1,
        bribee="B",
        briber="A",
        bribed_proposer="A",
        included_slots=frozenset({1}),
        excluded_slots=frozenset({2}),
    )
    # Offering bribe
    engine = engine.add_offer_bribery({"A": (offer,), "B": (offer,), "H": (offer,)})

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
            Vote(  # accepting
                entity="B",
                from_slot=1,
                min_index=0,
                max_index=bribee_power - 1,
                to_slot=1,
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
    head_B = engine.head("B")
    assert head_H == 0
    assert head_A == 1
    assert head_B == 1

    engine = engine.slot_progress()
    # SLOT 2 - 0
    engine = engine.build_block(
        slot=2, parent_slot=head_H, knowledge=("A", "B"), censor_votes=censor_votes
    )
    engine = engine.slot_progress()
    # SLOT 2 - 1
    head_H = engine.head("H")
    head_A = engine.head("A")
    head_B = engine.head("B")
    assert head_H == 2
    assert head_A == 2
    assert head_B == 2

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
                entity="B",
                from_slot=2,
                min_index=0,
                max_index=bribee_power - 1,
                to_slot=1,
            ),
            Vote(
                entity="H",
                from_slot=2,
                min_index=0,
                max_index=honest_power - 1,
                to_slot=2,
            ),
        )
    )
    engine = engine.slot_progress()
    # SLOT 3 - 0

    head_H = engine.head("H")
    head_A = engine.head("A")
    head_A = engine.head("B")
    assert head_H == 2
    assert head_A == 2
    assert head_B == 2

    take_briberies = (
        TakeBribery(
            reference=offer,
            vote=Vote(
                entity="B",
                from_slot=1,
                min_index=0,
                max_index=bribee_power - 1,
                to_slot=1,
            ),
            index=0,
        ),
        TakeBribery(
            reference=offer,
            vote=Vote(
                entity="B",
                from_slot=2,
                min_index=0,
                max_index=bribee_power - 1,
                to_slot=1,
            ),
            index=1,
        ),
    )

    engine = engine.add_take_briberies(
        {"A": take_briberies, "H": take_briberies, "B": take_briberies}
    )

    engine = engine.build_block(
        slot=3,
        parent_slot=1,
        knowledge=("H", "B"),
        censor_votes=censor_votes,
        censor_take_briberies=lambda _: [],  # censor takebriberies of bribee to fail deadline check
    )
    engine = engine.add_knowledge({"H": (1,)})  # revealing previous slot

    head_H = engine.head("H")
    head_A = engine.head("A")
    head_B = engine.head("B")
    assert head_H == 3
    assert head_A == 3
    assert head_B == 3

    wallet_state = engine.blocks[3].wallet_state
    address_to_money = wallet_state.compute_real_address_to_money(
        base_reward=base_reward,
        deadline_reward=deadline_reward,
        deadline_payback=deadline_payback,
    )
    assert address_to_money.get("A", 0) == 0
    assert address_to_money.get("H", 0) == 0
    assert address_to_money.get("B", 0) == 0

    engine = engine.slot_progress()
    engine = engine.slot_progress()

    # SLOT 4 - 0

    engine = engine.build_block(
        slot=4,
        parent_slot=3,
        knowledge=("A", "B"),
        censor_votes=censor_votes,
        final=True,
    )

    wallet_state = engine.blocks[4].wallet_state
    address_to_money = wallet_state.compute_real_address_to_money(
        base_reward=base_reward,
        deadline_reward=deadline_reward,
        deadline_payback=deadline_payback,
    )
    assert (
        address_to_money.get("A", 0)
        == -base_reward - deadline_payback - deadline_reward
    )
    assert address_to_money.get("H", 0) == 0
    assert address_to_money.get("B", 0) == base_reward
