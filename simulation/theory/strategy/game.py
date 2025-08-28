from dataclasses import dataclass
from itertools import product

from frozendict import frozendict

from simulation.theory.engine import Engine
from simulation.theory.strategy.adversary import AdvParams, AdvStrategy
from simulation.theory.strategy.base import (
    IAdvStrategy,
    IBribeeStrategy,
    IByzantineStrategy,
    IHonestStrategy,
    IStrategy,
    Params,
)
from simulation.theory.strategy.bribee import BribeeParams, BribeeStrategy
from simulation.theory.strategy.honest import HonestStrategy
from simulation.theory.utils import Slot





@dataclass
class SymbolicRun:
    table: dict[frozendict[str, Params], tuple[Engine, list[tuple[Slot, str]]]]
    all_params: dict[str, list[Params]]
    honest_player: str
    adv_player: str




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
            event_list=self.event_list,
            entity=self.honest_entity,
        )

    def adv_player(self, params: AdvParams) -> IAdvStrategy:
        return AdvStrategy(
            censor_from_slot=params.censor_from_slot,
            patient=params.patient,
            break_bad_slot=params.break_bad_slot,
            base_slot=self.base_slot,
            chain_string=self.chain_string,
            entity=self.adv_entity,
            honest_entity=self.honest_entity,
            bribee_entities=self.bribee_entities,
            event_list=self.event_list,
        )

    def bribee_player(self, name: str, params: BribeeParams) -> IBribeeStrategy:
        return BribeeStrategy(
            break_bad_slot=params.break_bad_slot,
            censoring_from_slot=params.censoring_from_slot,
            send_votes_when_able=params.send_votes_when_able,
            last_minute=params.last_minute,
            finish_offers_regardless_of_abort=params.finish_offers_regardless_of_abort,
            only_sending_to_deadline_proposing_entity=params.only_sending_to_deadline_proposing_entity,
            base_slot=self.base_slot,
            chain_string=self.chain_string,
            entitiy=name,
            honest_entity=self.honest_entity,
            adv_entity=self.adv_entity,
            bribee_entities=self.bribee_entities,
            event_list=self.event_list,
        )

    def make_engine(self) -> Engine:
        return Engine.make_engine(
            chain_string=self.chain_string,
            entity_to_voting_power=self.entity_to_voting_power,
        )

    def play(
        self, adv_params: AdvParams, bribee_to_params: dict[str, BribeeParams]
    ) -> tuple[Engine, list[tuple[Slot, str]]]:
        self.event_list: list[tuple[Slot, str]] = []
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
        return honest.build(engine), self.event_list  # final transactions

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
                        for finish_offer in [False, True]:
                            result.append(
                                BribeeParams(
                                    break_bad_slot=break_bad_slot,
                                    censoring_from_slot=censoring_slots,
                                    send_votes_when_able=send_votes,
                                    last_minute=level >= 1,
                                    only_sending_to_deadline_proposing_entity=level
                                    == 2,
                                    finish_offers_regardless_of_abort=finish_offer,
                                )
                            )
        return result

    def all_params(self) -> dict[str, list[Params]]:
        adv_params = self.all_adv_strategies()
        all_bribee_params = {
            bribee: self.all_bribee_strategies(bribee)
            for bribee in self.bribee_entities
        }
        return  {
            self.adv_entity: adv_params,
            **all_bribee_params,
        }

    def compute_table(
        self,
    ) -> SymbolicRun:
        adv_params = self.all_adv_strategies()
        all_bribee_params = {
            bribee: self.all_bribee_strategies(bribee)
            for bribee in self.bribee_entities
        }
        all_params =  {
            self.adv_entity: adv_params,
            **all_bribee_params,
        }

        result: SymbolicRun = SymbolicRun(
            table={},
            all_params=all_params,
            honest_player=self.honest_entity,
            adv_player=self.adv_entity,
        )
        bribee_params = list(product(*all_bribee_params.values()))
        for adv_param in adv_params:

            for bribee_settings in bribee_params:
                # print((adv_param, bribee_settings))
                engine, events = self.play(
                    adv_params=adv_param,
                    bribee_to_params={
                        bribee: settings
                        for bribee, settings in zip(
                            self.bribee_entities, bribee_settings
                        )
                    },
                )
                key = frozendict(
                    {
                        self.adv_entity: adv_param,
                        **{
                            entity: params
                            for entity, params in zip(
                                self.bribee_entities, bribee_settings
                            )
                        },
                    }
                )
                result.table[key] = (engine, events)

        return result

