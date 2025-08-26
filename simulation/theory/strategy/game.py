from collections import defaultdict
from dataclasses import dataclass
import itertools
from numbers import Real

from frozendict import frozendict

from simulation.theory.action import WalletState
from simulation.theory.engine import Engine
from simulation.theory.strategy.adversary import AdvParams, AdvStrategy
from simulation.theory.strategy.base import (
    IAdvStrategy,
    IBribeeStrategy,
    IByzantineStrategy,
    IHonestStrategy,
    IStrategy,
)
from simulation.theory.strategy.bribee import BribeeParams, BribeeStrategy
from simulation.theory.strategy.honest import HonestStrategy
from simulation.theory.utils import ATTESTATORS_PER_SLOT, B, BASE_INCREMENT


@dataclass
class GameReport:
    wallet_state: WalletState
    slot_to_canonical: dict[int, str]
    entity_to_blocks: dict[int, int]
    success: bool


def extract_end_info(engine: Engine, honest_entity: str) -> GameReport:
    head = engine.head(honest_entity)
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
            if (engine.slot_to_owner[slot] == honest_entity) == (canonical == "C"):
                success = False
            if canonical == "C":
                entity_to_blocks[engine.slot_to_owner[slot]] += 1
    return GameReport(
        engine.blocks[head].wallet_state, slot_to_canonical, entity_to_blocks, success
    )


@dataclass
class Game:
    base_slot: int
    chain_string: str

    base_reward_unit: Real
    deadline_reward_unit: Real
    deadline_payback_unit: Real

    honest_entity: str
    adv_entity: str
    bribee_entities: set[str]

    entity_to_voting_power: dict[str, int]

    def honest_player(self) -> IHonestStrategy:
        return HonestStrategy(
            all_entities=self.bribee_entities.union(
                (self.adv_entity, self.honest_entity)
            ),
            base_slot=self.base_slot,
            chain_string=self.chain_string,
            entity=self.honest_entity,
        )

    def adv_player(self, params: AdvParams) -> IAdvStrategy:
        return AdvStrategy(
            censor_from_slot=params.censor_from_slot,
            base_reward_unit=self.base_reward_unit,
            deadline_reward_unit=self.deadline_reward_unit,
            deadline_payback_unit=self.deadline_payback_unit,
            patient=params.patient,
            break_bad_slot=params.break_bad_slot,
            base_slot=self.base_slot,
            chain_string=self.chain_string,
            entity=self.adv_entity,
            honest_entity=self.honest_entity,
            bribee_entities=self.bribee_entities,
        )

    def bribee_player(self, name: str, params: BribeeParams) -> IBribeeStrategy:
        return BribeeStrategy(
            break_bad_slot=params.break_bad_slot,
            censoring_from_slot=params.censoring_from_slot,
            send_votes_when_able=params.send_votes_when_able,
            last_minute=params.last_minute,
            only_sending_to_deadline_proposing_entity=params.only_sending_to_deadline_proposing_entity,
            base_slot=self.base_slot,
            chain_string=self.chain_string,
            entitiy=name,
            honest_entity=self.honest_entity,
            adv_entity=self.adv_entity,
            bribee_entities=self.bribee_entities,
        )

    def make_engine(self) -> Engine:
        return Engine.make_engine(
            chain_string=self.chain_string,
            entity_to_voting_power=self.entity_to_voting_power,
        )

    def play(
        self, adv_params: AdvParams, bribee_to_params: dict[str, BribeeParams]
    ) -> Engine:
        honest = self.honest_player()
        adversary = self.adv_player(adv_params)
        bribees = {
            name: self.bribee_player(name, params)
            for name, params in bribee_to_params.items()
        }

        players: dict[str, IStrategy] = {
            self.honest_entity: honest,
            self.adv_entity: adversary,
            **bribees,
        }
        byzantine_players: list[IByzantineStrategy] = [adversary, *bribees.values()]

        engine = self.make_engine()

        for proposer in self.chain_string:
            engine = players[proposer].build(engine)

            for byzantine in byzantine_players:
                engine = byzantine.adjust_strategy(engine)

            engine = adversary.offer_bribe(engine)

            engine = engine.slot_progress()

            for entity in players.values():
                engine = entity.vote(engine)

            for bribee in bribees.values():
                engine = bribee.take_bribe(engine)

            for byzantine in byzantine_players:
                engine = byzantine.send_others_votes(engine)

            for byzantine in byzantine_players:
                engine = byzantine.withheld_blocks(engine)

            for byzantine in byzantine_players:
                engine = byzantine.adjust_strategy(engine)

            engine = engine.slot_progress()
        return honest.build(engine)  # final transactions

    def all_adv_strategies(self) -> list[AdvParams]:
        result: list[AdvParams] = []
        for abort_slot in [None] + list(
            range(self.base_slot, self.base_slot + 1 + len(self.chain_string))
        ):
            for patient in [True, False]:
                result.append(
                    AdvParams(
                        censor_from_slot=None,
                        patient=patient,
                        break_bad_slot=abort_slot,
                    )
                )
                for censor_slot, owner in enumerate(
                    self.chain_string, start=self.base_slot + 1
                ):
                    if owner != self.adv_entity:
                        continue
                    result.append(
                        AdvParams(
                            censor_from_slot=censor_slot,
                            patient=patient,
                            break_bad_slot=abort_slot,
                        )
                    )
        return result

    def all_bribee_strategies(self, entity: str) -> list[BribeeParams]:
        result: list[BribeeParams] = []
        for censoring_slots, owner in [(None, entity)] + list(
            enumerate(self.chain_string, start=self.base_slot + 1)
        ):
            if owner != entity:
                continue
            for break_bad_slot in [None] + list(
                range(self.base_slot, self.base_slot + 1 + len(self.chain_string))
            ):
                for send_votes in [False, True]:
                    for level in range(3):

                        result.append(
                            BribeeParams(
                                break_bad_slot=break_bad_slot,
                                censoring_from_slot=censoring_slots,
                                send_votes_when_able=send_votes,
                                last_minute=level >= 1,
                                only_sending_to_deadline_proposing_entity=level == 2,
                            )
                        )
        return result

    def compute_table(
        self,
    ) -> dict[tuple[AdvParams, tuple[BribeeParams, ...]], GameReport]:
        adv_params = self.all_adv_strategies()
        all_bribee_params = [
            self.all_bribee_strategies(bribee) for bribee in self.bribee_entities
        ]

        result: dict[tuple[AdvParams, tuple[BribeeParams, ...]], GameReport] = {}
        cout = 0
        bribee_params = itertools.product(*all_bribee_params)
        for adv_param in adv_params:

            for bribee_settings in bribee_params:
                cout += 1
                # print((adv_param, bribee_settings))
                engine = self.play(
                    adv_params=adv_param,
                    bribee_to_params={
                        bribee: settings
                        for bribee, settings in zip(
                            self.bribee_entities, bribee_settings
                        )
                    },
                )
                result[(adv_param, bribee_settings)] = extract_end_info(
                    engine, self.honest_entity
                )
        print(cout)
        return result


def main():
    alpha = int(0.15 * ATTESTATORS_PER_SLOT)
    beta = int(0.06 * ATTESTATORS_PER_SLOT)
    honest = ATTESTATORS_PER_SLOT - alpha - beta

    game = Game(
        base_slot=0,
        chain_string="AHA",
        base_reward_unit=B * BASE_INCREMENT + 40,
        deadline_reward_unit=B,
        deadline_payback_unit=B,
        honest_entity="H",
        adv_entity="A",
        bribee_entities={"B"},
        entity_to_voting_power={"H": honest, "A": alpha, "B": beta},
    )
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
    )
    engine = game.play(best_adv, {"B": best_bribee})
    info = extract_end_info(engine, "H")
    print(info)
    """
    engine = game.play(
        adv_params=AdvParams(
            entity_to_censor_from_slot={"B": None},
            patient=False,
            break_bad_slot=None,
        ),
        bribee_to_params={
            "B": BribeeParams(
                break_bad_slot=None,
                censoring_from_slot=None,
                send_votes_when_able=True,
                last_minute=False,
                only_sending_to_deadline_proposing_entity=False,
            )
        },
    )
    info = extract_end_info(engine, "H")
    print(info)
    """


if __name__ == "__main__":
    main()
