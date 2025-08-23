from collections import defaultdict
from dataclasses import dataclass

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
    slot_to_canonical: dict[int, str]
    entity_to_blocks: dict[int, int]
    success: bool


def extract_end_info(engine: Engine, honest_entity: str) -> GameReport:
    head = engine.head(honest_entity)
    canonicals_slots: list[int] = []
    while head in engine.blocks:
        canonicals_slots.append(head)
        head = engine.blocks[head].parent_slot
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
    return GameReport(slot_to_canonical, entity_to_blocks, success)


@dataclass
class Game:
    base_slot: int
    chain_string: str

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
            entity_to_censor_from_slot=params.entity_to_censor_from_slot,
            base_reward_unit=params.base_reward_unit,
            deadline_reward_unit=params.deadline_reward_unit,
            deadline_payback_unit=params.deadline_payback_unit,
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


def main():
    alpha = int(0.1 * ATTESTATORS_PER_SLOT)
    beta = int(0.11 * ATTESTATORS_PER_SLOT)
    honest = ATTESTATORS_PER_SLOT - alpha - beta

    game = Game(
        base_slot=0,
        chain_string="AHA",
        honest_entity="H",
        adv_entity="A",
        bribee_entities={"B"},
        entity_to_voting_power={"H": honest, "A": alpha, "B": beta},
    )
    engine = game.play(
        adv_params=AdvParams(
            entity_to_censor_from_slot={"B": None},
            base_reward_unit=B * BASE_INCREMENT + 40,
            deadline_reward_unit=B,
            deadline_payback_unit=B,
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


if __name__ == "__main__":
    main()
