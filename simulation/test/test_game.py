from frozendict import frozendict
import pytest
from simulation.theory.strategy.adversary import AdvParams
from simulation.theory.strategy.bribee import BribeeParams
from simulation.theory.strategy.game import Game
from simulation.theory.utils import ATTESTATORS_PER_SLOT, B, BASE_INCREMENT


smoke_arguments = [
    ("HAA", 0.4, 0.15, None),
    ("HA", 0.4, 0.201, None),
    ("HBA", 0.4, 0.201, None),
    ("HBB", 0.2, 0.351, None),
    ("HB", 0.4, 0.201, None),
    ("AHA", 0.1, 0.11, None),
    ("AHB", 0.1, 0.11, None),
    ("BHA", 0.1, 0.11, None),
    ("BHB", 0.1, 0.11, None),
    ("AAHA", 0.1, 0.06, None),
    ("ABHA", 0.1, 0.11, None),
    ("BBHA", 0.1, 0.11, None),
    ("BAHA", 0.1, 0.11, None),
    ("BBHB", 0.1, 0.11, None),
    ("BBHA", 0.1, 0.11, None),
    ("BAHB", 0.1, 0.11, None),
    ("AAHB", 0.1, 0.11, None),
    ("ABHB", 0.1, 0.11, None),
    ("AHA", 0.1, 0.05, 0.06),
]


@pytest.mark.parametrize("chain_string, alpha, beta, beta2", smoke_arguments)
def test_game_success_test(
    chain_string: str, alpha: float, beta: float, beta2: float | None
):
    adv_voting_power = int(alpha * ATTESTATORS_PER_SLOT)
    bribee1_voting_power = int(beta * ATTESTATORS_PER_SLOT)
    bribee2_voting_power = int(beta2 * ATTESTATORS_PER_SLOT) if beta2 else None
    honest = ATTESTATORS_PER_SLOT - adv_voting_power - bribee1_voting_power
    if bribee2_voting_power:
        honest -= bribee2_voting_power

    bribee_entities = {"B", "C"} if bribee2_voting_power else {"B"}
    game = Game(
        base_slot=0,
        chain_string=chain_string,
        base_reward_unit=2224,
        deadline_reward_unit=33,
        deadline_payback_unit=11,
        honest_entity="H",
        adv_entity="A",
        bribee_entities=bribee_entities,
        entity_to_voting_power={
            "H": honest,
            "A": adv_voting_power,
            "B": bribee1_voting_power,
            **({"C": bribee2_voting_power} if bribee2_voting_power else {}),
        },
    )
    table = game.compute_table()
    best_adv = AdvParams(
        censor_from_slot=None,
        patient=False,
        break_bad_slot=None,
    )
    best_bribee = BribeeParams(
        break_bad_slot=None,
        censoring_from_slot=None,
        send_votes_when_able=False,
        last_minute=False,
        only_sending_to_deadline_proposing_entity=False,
        finish_offers_regardless_of_abort=False,
    )
    outcome = table[(best_adv, (best_bribee,) * len(bribee_entities))]
    assert outcome.success


unit_arguments = [
    (10, 100, 1000),
    (1000, 320, 31),
    (21, 42, 120),
    (88, 97, 103),
    (1, 14, 500),
]


@pytest.mark.parametrize(
    "base_reward_unit, deadline_reward_unit, deadline_payback_unit", unit_arguments
)
def test_game_AHA(
    base_reward_unit: float, deadline_reward_unit: float, deadline_payback_unit: float
):
    alpha = 0.15
    beta = 0.06
    adv_voting_power = int(alpha * ATTESTATORS_PER_SLOT)
    bribee_voting_power = int(beta * ATTESTATORS_PER_SLOT)
    honest = ATTESTATORS_PER_SLOT - adv_voting_power - bribee_voting_power
    game = Game(
        base_slot=0,
        chain_string="AHA",
        base_reward_unit=base_reward_unit,
        deadline_reward_unit=deadline_reward_unit,
        deadline_payback_unit=deadline_payback_unit,
        honest_entity="H",
        adv_entity="A",
        bribee_entities={"B"},
        entity_to_voting_power={
            "H": honest,
            "A": adv_voting_power,
            "B": bribee_voting_power,
        },
    )
    table = game.compute_table()

    # Patient adversary
    for level in range(3):
        adv_strategy = AdvParams(
            censor_from_slot=None,
            patient=True,
            break_bad_slot=None,
        )
        bribee_strategy = BribeeParams(
            break_bad_slot=None,
            censoring_from_slot=None,
            send_votes_when_able=False,
            last_minute=level >= 1,
            only_sending_to_deadline_proposing_entity=level == 2,
            finish_offers_regardless_of_abort=False,
        )
        outcome = table[(adv_strategy, (bribee_strategy,))]
        assert outcome.success
        base_rewards = [
            payment
            for payment in outcome.wallet_state.ledger
            if payment.amount == round(base_reward_unit * bribee_voting_power) * 2
            and payment.from_address == "A"
            and payment.to_address == "B"
        ]
        assert base_rewards
        deadline_rewards = [
            payment
            for payment in outcome.wallet_state.ledger
            if payment.amount == round(deadline_reward_unit * bribee_voting_power) * 2
            and payment.from_address == "A"
            and payment.to_address == "B"
        ]
        assert deadline_rewards
        deadline_paybacks = [
            payment
            for payment in outcome.wallet_state.ledger
            if payment.amount == round(deadline_payback_unit * bribee_voting_power) * 2
            and payment.from_address == "A"
            and payment.to_address == "A"
        ]
        assert deadline_paybacks

    # Inpatient adversary
    for level in range(3):
        adv_strategy = AdvParams(
            censor_from_slot=None,
            patient=False,
            break_bad_slot=None,
        )
        bribee_strategy = BribeeParams(
            break_bad_slot=None,
            censoring_from_slot=None,
            send_votes_when_able=False,
            last_minute=level >= 1,
            only_sending_to_deadline_proposing_entity=level == 2,
            finish_offers_regardless_of_abort=False,
        )
        outcome = table[(adv_strategy, (bribee_strategy,))]
        assert outcome.success == (level == 0)
        base_rewards = [
            payment
            for payment in outcome.wallet_state.ledger
            if payment.amount == round(base_reward_unit * bribee_voting_power) * 2
            and payment.from_address == "A"
            and payment.to_address == "B"
        ]
        assert bool(base_rewards) == (level == 0)
        deadline_rewards = [
            payment
            for payment in outcome.wallet_state.ledger
            if payment.amount == round(deadline_reward_unit * bribee_voting_power) * 2
            and payment.from_address == "A"
            and payment.to_address == "B"
        ]
        assert bool(deadline_rewards) == (level == 0)
        deadline_paybacks = [
            payment
            for payment in outcome.wallet_state.ledger
            if payment.amount == round(deadline_payback_unit * bribee_voting_power) * 2
            and payment.from_address == "A"
            and payment.to_address == "A"
        ]
        assert bool(deadline_paybacks) == (level == 0)

    # Censorship
    adv_strategy = AdvParams(
        censor_from_slot=3,
        patient=False,
        break_bad_slot=None,
    )
    bribee_strategy = BribeeParams(
        break_bad_slot=None,
        censoring_from_slot=None,
        send_votes_when_able=False,
        last_minute=False,
        only_sending_to_deadline_proposing_entity=False,
        finish_offers_regardless_of_abort=False,
    )
    outcome = table[(adv_strategy, (bribee_strategy,))]
    base_rewards = [
        payment
        for payment in outcome.wallet_state.ledger
        if payment.amount == round(base_reward_unit * bribee_voting_power) * 2
        and payment.from_address == "A"
        and payment.to_address == "B"
    ]
    assert base_rewards
    deadline_rewards = [
        payment
        for payment in outcome.wallet_state.ledger
        if payment.amount == round(deadline_reward_unit * bribee_voting_power) * 2
        and payment.from_address == "A"
        and payment.to_address == "B"
    ]
    assert not deadline_rewards
    deadline_paybacks = [
        payment
        for payment in outcome.wallet_state.ledger
        if payment.amount == round(deadline_payback_unit * bribee_voting_power) * 2
        and payment.from_address == "A"
        and payment.to_address == "A"
    ]
    assert not deadline_paybacks

    # Finishing regardless of abort 1
    adv_strategy = AdvParams(
        censor_from_slot=None,
        patient=False,
        break_bad_slot=None,
    )
    bribee_strategy = BribeeParams(
        break_bad_slot=None,
        censoring_from_slot=None,
        send_votes_when_able=False,
        last_minute=True,
        only_sending_to_deadline_proposing_entity=False,
        finish_offers_regardless_of_abort=True,
    )
    outcome = table[(adv_strategy, (bribee_strategy,))]
    base_rewards = [
        payment
        for payment in outcome.wallet_state.ledger
        if payment.amount == round(base_reward_unit * bribee_voting_power) * 2
        and payment.from_address == "A"
        and payment.to_address == "B"
    ]
    assert base_rewards
    deadline_rewards = [
        payment
        for payment in outcome.wallet_state.ledger
        if payment.amount == round(deadline_reward_unit * bribee_voting_power) * 2
        and payment.from_address == "A"
        and payment.to_address == "B"
    ]
    assert not deadline_rewards
    deadline_paybacks = [
        payment
        for payment in outcome.wallet_state.ledger
        if payment.amount == round(deadline_payback_unit * bribee_voting_power) * 2
        and payment.from_address == "A"
        and payment.to_address == "A"
    ]
    assert not deadline_paybacks

    # Finishing regardless of abort 2
    adv_strategy = AdvParams(
        censor_from_slot=None,
        patient=True,
        break_bad_slot=2,
    )
    bribee_strategy = BribeeParams(
        break_bad_slot=None,
        censoring_from_slot=None,
        send_votes_when_able=False,
        last_minute=True,
        only_sending_to_deadline_proposing_entity=False,
        finish_offers_regardless_of_abort=True,
    )
    outcome = table[(adv_strategy, (bribee_strategy,))]
    assert not outcome.success
    base_rewards = [
        payment
        for payment in outcome.wallet_state.ledger
        if payment.amount == round(base_reward_unit * bribee_voting_power) * 2
        and payment.from_address == "A"
        and payment.to_address == "B"
    ]
    assert base_rewards
    deadline_rewards = [
        payment
        for payment in outcome.wallet_state.ledger
        if payment.amount == round(deadline_reward_unit * bribee_voting_power) * 2
        and payment.from_address == "A"
        and payment.to_address == "B"
    ]
    assert not deadline_rewards
    deadline_paybacks = [
        payment
        for payment in outcome.wallet_state.ledger
        if payment.amount == round(deadline_payback_unit * bribee_voting_power) * 2
        and payment.from_address == "A"
        and payment.to_address == "A"
    ]
    assert not deadline_paybacks

    # NOT finishing regardless of abort
    adv_strategy = AdvParams(
        censor_from_slot=None,
        patient=True,
        break_bad_slot=2,
    )
    bribee_strategy = BribeeParams(
        break_bad_slot=None,
        censoring_from_slot=None,
        send_votes_when_able=False,
        last_minute=True,
        only_sending_to_deadline_proposing_entity=False,
        finish_offers_regardless_of_abort=False,
    )
    outcome = table[(adv_strategy, (bribee_strategy,))]
    assert not outcome.success
    base_rewards = [
        payment
        for payment in outcome.wallet_state.ledger
        if payment.amount == round(base_reward_unit * bribee_voting_power) * 2
        and payment.from_address == "A"
        and payment.to_address == "B"
    ]
    assert base_rewards
    deadline_rewards = [
        payment
        for payment in outcome.wallet_state.ledger
        if payment.amount == round(deadline_reward_unit * bribee_voting_power) * 2
        and payment.from_address == "A"
        and payment.to_address == "B"
    ]
    assert not deadline_rewards
    deadline_paybacks = [
        payment
        for payment in outcome.wallet_state.ledger
        if payment.amount == round(deadline_payback_unit * bribee_voting_power) * 2
        and payment.from_address == "A"
        and payment.to_address == "A"
    ]
    assert not deadline_paybacks


@pytest.mark.parametrize(
    "base_reward_unit, deadline_reward_unit, deadline_payback_unit", unit_arguments
)
def test_game_HAA(
    base_reward_unit: float, deadline_reward_unit: float, deadline_payback_unit: float
):
    alpha = 0.4
    beta = 0.14
    adv_voting_power = int(alpha * ATTESTATORS_PER_SLOT)
    bribee_voting_power = int(beta * ATTESTATORS_PER_SLOT)
    honest = ATTESTATORS_PER_SLOT - adv_voting_power - bribee_voting_power
    game = Game(
        base_slot=0,
        chain_string="HAA",
        base_reward_unit=base_reward_unit,
        deadline_reward_unit=deadline_reward_unit,
        deadline_payback_unit=deadline_payback_unit,
        honest_entity="H",
        adv_entity="A",
        bribee_entities={"B"},
        entity_to_voting_power={
            "H": honest,
            "A": adv_voting_power,
            "B": bribee_voting_power,
        },
    )
    table = game.compute_table()

    # Patient adversary
    for level in range(3):
        adv_strategy = AdvParams(
            censor_from_slot=None,
            patient=True,
            break_bad_slot=None,
        )
        bribee_strategy = BribeeParams(
            break_bad_slot=None,
            censoring_from_slot=None,
            send_votes_when_able=False,
            last_minute=level >= 1,
            only_sending_to_deadline_proposing_entity=level == 2,
            finish_offers_regardless_of_abort=False,
        )
        outcome = table[(adv_strategy, (bribee_strategy,))]
        assert outcome.success
        base_rewards = [
            payment
            for payment in outcome.wallet_state.ledger
            if payment.amount == round(base_reward_unit * bribee_voting_power)
            and payment.from_address == "A"
            and payment.to_address == "B"
        ]
        assert base_rewards
        deadline_rewards = [
            payment
            for payment in outcome.wallet_state.ledger
            if payment.amount == round(deadline_reward_unit * bribee_voting_power)
            and payment.from_address == "A"
            and payment.to_address == "B"
        ]
        assert deadline_rewards
        deadline_paybacks = [
            payment
            for payment in outcome.wallet_state.ledger
            if payment.amount == round(deadline_payback_unit * bribee_voting_power)
            and payment.from_address == "A"
            and payment.to_address == "A"
        ]
        assert deadline_paybacks

    # Inpatient adversary
    for level in range(3):
        adv_strategy = AdvParams(
            censor_from_slot=None,
            patient=False,
            break_bad_slot=None,
        )
        bribee_strategy = BribeeParams(
            break_bad_slot=None,
            censoring_from_slot=None,
            send_votes_when_able=False,
            last_minute=level >= 1,
            only_sending_to_deadline_proposing_entity=level == 2,
            finish_offers_regardless_of_abort=False,
        )
        outcome = table[(adv_strategy, (bribee_strategy,))]
        assert outcome.success
        base_rewards = [
            payment
            for payment in outcome.wallet_state.ledger
            if payment.amount == round(base_reward_unit * bribee_voting_power)
            and payment.from_address == "A"
            and payment.to_address == "B"
        ]
        assert base_rewards
        deadline_rewards = [
            payment
            for payment in outcome.wallet_state.ledger
            if payment.amount == round(deadline_reward_unit * bribee_voting_power)
            and payment.from_address == "A"
            and payment.to_address == "B"
        ]
        assert deadline_rewards
        deadline_paybacks = [
            payment
            for payment in outcome.wallet_state.ledger
            if payment.amount == round(deadline_payback_unit * bribee_voting_power)
            and payment.from_address == "A"
            and payment.to_address == "A"
        ]
        assert deadline_paybacks

    # Censorship
    adv_strategy = AdvParams(
        censor_from_slot=3,
        patient=False,
        break_bad_slot=None,
    )
    bribee_strategy = BribeeParams(
        break_bad_slot=None,
        censoring_from_slot=None,
        send_votes_when_able=False,
        last_minute=False,
        only_sending_to_deadline_proposing_entity=False,
        finish_offers_regardless_of_abort=False,
    )
    outcome = table[(adv_strategy, (bribee_strategy,))]
    base_rewards = [
        payment
        for payment in outcome.wallet_state.ledger
        if payment.amount == round(base_reward_unit * bribee_voting_power)
        and payment.from_address == "A"
        and payment.to_address == "B"
    ]
    assert base_rewards
    deadline_rewards = [
        payment
        for payment in outcome.wallet_state.ledger
        if payment.amount == round(deadline_reward_unit * bribee_voting_power)
        and payment.from_address == "A"
        and payment.to_address == "B"
    ]
    assert not deadline_rewards
    deadline_paybacks = [
        payment
        for payment in outcome.wallet_state.ledger
        if payment.amount == round(deadline_payback_unit * bribee_voting_power)
        and payment.from_address == "A"
        and payment.to_address == "A"
    ]
    assert not deadline_paybacks
