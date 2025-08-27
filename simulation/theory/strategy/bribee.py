from dataclasses import dataclass
from typing import Callable, Iterable
from simulation.theory.action import OfferBribery, TakeBribery, Vote
from simulation.theory.engine import Engine
from simulation.theory.strategy.base import IBribeeStrategy, Params


@dataclass(frozen=True)
class BribeeParams(Params):
    break_bad_slot: int | None
    censoring_from_slot: int | None
    send_votes_when_able: bool
    finish_offers_regardless_of_abort: bool
    last_minute: bool
    only_sending_to_deadline_proposing_entity: bool


class BribeeStrategy(IBribeeStrategy):
    def __init__(
        self,
        break_bad_slot: int | None,
        censoring_from_slot: int | None,
        send_votes_when_able: bool,
        finish_offers_regardless_of_abort: bool,
        last_minute: bool,
        only_sending_to_deadline_proposing_entity: bool,
        base_slot: int,
        chain_string: str,
        entitiy: str,
        honest_entity: str,
        adv_entity: str,
        bribee_entities: set[str],
    ):
        assert (
            last_minute or not only_sending_to_deadline_proposing_entity
        )  # only_sending -> last_minute

        self.break_bad_slot = (
            break_bad_slot  # The bribee will not accept more blocks or build
        )
        self.censoring_from_slot = censoring_from_slot  # When building block, censoring all (but their own) takeBribe calls
        self.send_votes_when_able = send_votes_when_able
        self.last_minute = (
            last_minute  # the bribee sends the accepted votes at the last minute
        )
        self.finish_offers_regardless_of_abort = finish_offers_regardless_of_abort
        self.only_sending_to_deadline_proposing_entity = (
            only_sending_to_deadline_proposing_entity
        )
        self.base_slot = base_slot
        self.chain_string = chain_string
        self.entity = entitiy
        self.honest_entity = honest_entity
        self.adv_entity = adv_entity
        self.bribee_entities = bribee_entities

        self.accepted_offers: set[OfferBribery] = set()
        self.already_voted_from: set[int] = set()
        self.locked_slots_for_offers: set[int] = set()

        self.setup_plan()
        self.all_entities = self.bribee_entities.union(
            (self.adv_entity, self.honest_entity)
        )

        self.withheld_slots: list[int] = []
        self.aborted = False
        if break_bad_slot == self.base_slot:
            self.aborted = True

    def adjust_strategy(self, engine: Engine) -> Engine:
        """
        This function aborts the attack in case of unresolvable anomaly
        """
        if self.aborted:
            return engine
        if (
            engine.slot.phase == 0
            and engine.slot.num < self.last_H
            and engine.slot_to_owner[engine.slot.num]
            in self.bribee_entities.union((self.adv_entity,))
            and engine.slot.num
            not in engine.knowledge_of_blocks.get(self.honest_entity, [])
            and engine.slot.num in engine.knowledge_of_blocks.get(self.entity, [])
        ):
            self.withheld_slots.append(engine.slot.num)
        if self.structural_anomaly(engine) or (
            self.break_bad_slot is not None and engine.slot.num >= self.break_bad_slot
        ):
            engine = self.abort(engine)
        return engine

    def abort(self, engine: Engine) -> Engine:
        engine = self.share_knowledge(engine)
        self.aborted = True
        return engine

    def share_knowledge(self, engine: Engine) -> Engine:
        if not self.withheld_slots:
            return engine

        engine = engine.add_knowledge(
            entity_to_knowledge={
                entity: self.withheld_slots for entity in self.all_entities
            }
        )
        self.withheld_slots = []
        return engine

    def build(self, engine: Engine) -> Engine:
        if self.aborted:
            engine = self.share_knowledge(engine)
            head = engine.head(self.honest_entity)
            knowledge = self.all_entities
        else:
            head = self.plan_correct_votes[engine.slot.num - 1]
            if engine.slot.num < self.last_H:
                knowledge = set(
                    self.chain_string[
                        engine.slot.num - self.base_slot : self.last_E - self.base_slot
                    ]
                )

                self.withheld_slots.append(engine.slot.num)
            else:
                knowledge = self.all_entities

        censor: Callable[[Iterable[TakeBribery]], Iterable[TakeBribery]]
        if (
            self.censoring_from_slot is None
            or engine.slot.num < self.censoring_from_slot
        ):
            censor = lambda x: x
        else:
            censor = lambda takes: [
                take for take in takes if take.reference.bribee == self.entity
            ]

        return engine.build_block(
            slot=engine.slot.num,
            parent_slot=head,
            knowledge=knowledge,
            entity=self.entity,
            censor_take_briberies=censor,
        )

    def vote(self, engine: Engine) -> Engine:
        new_offers = (
            engine.offer_briberies.get(self.entity, frozenset()) - self.accepted_offers
        )
        for offer in new_offers:
            if offer.bribee != self.entity:
                continue
            if self.break_bad_slot is None or all(
                attest_req.deadline is None
                or attest_req.deadline >= self.break_bad_slot
                for attest_req in offer.attests
            ):
                self.accepted_offers.add(offer)
                for attest_req in offer.attests:
                    assert attest_req.from_slot not in self.locked_slots_for_offers
                    self.locked_slots_for_offers.add(attest_req.from_slot)

        self.takes: list[TakeBribery] = []
        votes: list[Vote] = []
        if self.aborted and not self.finish_offers_regardless_of_abort:
            engine = self.share_knowledge(engine)
            head = engine.head(self.honest_entity)

            for slot in range(engine.slot.num, self.base_slot, -1):
                while head > slot:
                    head = engine.blocks[head].parent_slot

                if slot not in self.already_voted_from:
                    self.already_voted_from.add(slot)
                    votes.append(
                        Vote(
                            entity=self.entity,
                            from_slot=slot,
                            min_index=0,
                            max_index=engine.entity_to_voting_power[self.entity] - 1,
                            to_slot=head,
                        )
                    )
        else:
            if (
                engine.slot.num not in self.locked_slots_for_offers
            ):  # if current vote is not locked, no problem, we just vote honestly :D
                honest_head = engine.head(self.honest_entity)
                votes.append(
                    Vote(
                        entity=self.entity,
                        from_slot=engine.slot.num,
                        min_index=0,
                        max_index=engine.entity_to_voting_power[self.entity] - 1,
                        to_slot=honest_head,
                    )
                )
                assert engine.slot.num not in self.already_voted_from
                self.already_voted_from.add(engine.slot.num)
            if self.last_minute:
                for offer in self.accepted_offers:
                    assert self.entity == offer.bribee
                    for index, attest_req in enumerate(offer.attests):
                        if engine.slot.num == attest_req.deadline - 1:
                            vote = Vote(
                                entity=self.entity,
                                from_slot=attest_req.from_slot,
                                min_index=attest_req.min_index,
                                max_index=attest_req.max_index,
                                to_slot=attest_req.slot,
                            )
                            self.takes.append(
                                TakeBribery(
                                    reference=offer,
                                    vote=vote,
                                    index=index,
                                )
                            )
                            assert attest_req.from_slot not in self.already_voted_from
                            self.already_voted_from.add(attest_req.from_slot)
                            if not self.only_sending_to_deadline_proposing_entity:
                                votes.append(vote)

            else:
                for offer in self.accepted_offers:
                    assert self.entity == offer.bribee
                    for index, attest_req in enumerate(offer.attests):
                        if engine.slot.num == attest_req.from_slot:
                            vote = Vote(
                                entity=self.entity,
                                from_slot=attest_req.from_slot,
                                min_index=attest_req.min_index,
                                max_index=attest_req.max_index,
                                to_slot=attest_req.slot,
                            )
                            self.takes.append(
                                TakeBribery(
                                    reference=offer,
                                    vote=vote,
                                    index=index,
                                )
                            )
                            votes.append(vote)
                            assert attest_req.from_slot not in self.already_voted_from
                            self.already_voted_from.add(attest_req.from_slot)

        if votes:
            return engine.add_votes(votes)
        return engine

    def take_bribe(self, engine: Engine) -> Engine:
        return engine.add_take_briberies(
            entity_to_take_briberies_knowledge={
                entity: self.takes for entity in self.all_entities
            }
        )

    def send_others_votes(self, engine: Engine) -> Engine:
        if self.send_votes_when_able:
            my_knowledge = engine.take_briberies.get(self.entity)
            if my_knowledge:
                engine = engine.add_votes({take.vote for take in my_knowledge})
        return engine

    def withheld_blocks(self, engine: Engine) -> Engine:
        if engine.slot.num == self.last_H:
            engine = self.share_knowledge(engine)
        return engine
