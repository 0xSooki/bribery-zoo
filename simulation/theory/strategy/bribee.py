from typing import Callable, Iterable
from simulation.theory.action import OfferBribery, TakeBribery, Vote
from simulation.theory.engine import Engine
from simulation.theory.strategy.base import IBribee, chain_string_extract, plan


class BribeeStrategy(IBribee):
    def __init__(
        self,
        break_bad_slot: int | None,
        censoring_from_slot: int | None,
        send_votes_when_able: bool,
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
        self.only_sending_to_deadline_proposing_entity = (
            only_sending_to_deadline_proposing_entity
        )
        self.base_slot = base_slot
        self.chain_string = chain_string
        self.entitiy = entitiy
        self.honest_entity = honest_entity
        self.adv_entity = adv_entity
        self.bribee_entities = bribee_entities

        self.accepted_offers: set[OfferBribery] = set()
        self.already_voted_from: set[int] = []

        self.plan_correct_votes, self.included, self.excluded = plan(
            base_slot, chain_string, honest_entity
        )

        self.last_E, self.last_H = chain_string_extract(
            base_slot, chain_string, honest_entity
        )
        self.all_entities = self.bribee_entities.union(
            (self.adv_entity, self.honest_entity)
        )

        self.withheld_slots: list[int] = []
        self.aborted = False

    def is_breaking_bad(self, engine: Engine) -> bool:
        return (
            self.break_bad_slot is not None and engine.slot.num >= self.break_bad_slot
        )

    def abort(self, engine: Engine) -> Engine:
        return ...

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
            censor = lambda takes: [
                take for take in takes if take.reference.bribee == self.entitiy
            ]
        else:
            censor = lambda x: x

        return engine.build_block(
            slot=engine.slot.num,
            parent_slot=head,
            knowledge=knowledge,
            entity=self.entitiy,
            censor_take_briberies=censor,
        )

    def vote(self, engine: Engine) -> Engine:
        new_offers = (
            engine.offer_briberies.get(self.entitiy, frozenset()) - self.accepted_offers
        )
        for offer in new_offers:
            if self.break_bad_slot is None or all(
                attest_req.deadline is None
                or attest_req.deadline >= self.break_bad_slot
                for attest_req in offer.attests
            ):
                self.accepted_offers.add(offer)
                
                
        self.takes: list[TakeBribery] = []
        votes: list[Vote] = []
        if self.aborted:
            engine = self.share_knowledge(engine)
            head = engine.head(self.honest_entity)
            
            
            for slot in range(engine.slot.num, self.base_slot, -1):
                while head > slot:
                    head = engine.blocks[head].parent_slot
                
                if slot not in self.already_voted_from:
                    self.already_voted_from.add(slot)
                    votes.append(
                        Vote(
                            entity=self.entitiy,
                            from_slot=slot,
                            min_index=0,
                            max_index=engine.entity_to_voting_power[self.entitiy] - 1,
                            to_slot=head,
                        )
                    )
        else:
            if self.last_minute:
                for offer in self.accepted_offers:
                    assert self.entitiy == offer.bribee
                    for index, attest_req in enumerate(offer.attests):
                        if engine.slot.num == attest_req.deadline - 1:
                            vote = Vote(
                                entity=self.entitiy,
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
                    assert self.entitiy == offer.bribee
                    for index, attest_req in enumerate(offer.attests):
                        if engine.slot.num == attest_req.from_slot:
                            vote = Vote(
                                entity=self.entitiy,
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
        return engine.add_take_briberies(entity_to_take_briberies_knowledge={
            entity: self.takes for entity in self.all_entities
        })
        
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