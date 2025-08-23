import math
from numbers import Real
from simulation.theory.action import OfferBribery, SingleOfferBribery, TakeBribery, Vote
from simulation.theory.engine import Engine
from simulation.theory.strategy.base import IAdvStrategy, chain_string_extract, plan
from simulation.theory.utils import PROPOSER_BOOST


class AdvStrategy(IAdvStrategy):
    def __init__(
        self,
        entity_to_censor_from_slot: dict[str, int | None],
        base_reward_unit: Real,
        deadline_reward_unit: Real,
        deadline_payback_unit: Real,
        patient: bool,
        base_slot: int,
        chain_string: str,
        entity: str,
        honest_entity: str,
        bribee_entities: set[str],
    ):
        self.entity_to_censor_from_slot = entity_to_censor_from_slot
        self.base_reward_unit = base_reward_unit
        self.deadline_payback_unit = deadline_payback_unit
        self.deadline_reward_unit = deadline_reward_unit
        self.patient = patient
        self.base_slot = base_slot
        self.chain_string = chain_string
        self.entity = entity
        self.honest_entity = honest_entity
        self.bribee_entities = bribee_entities
        self.all_entities = bribee_entities.union((entity, honest_entity))

        self.coorporating_bribees = set(
            self.bribee_entities
        )  # We will exclude anyone "malicious" and abort if plan is no longer feasible

        self.aborted: bool = False
        self.withheld_slots: list[int] = []

        self.plan_correct_votes, self.included, self.excluded = plan(
            base_slot, chain_string, honest_entity
        )

        self.last_E, self.last_H = chain_string_extract(
            base_slot, chain_string, honest_entity
        )

        self.offers: list[OfferBribery] = []

    def build(self, engine: Engine) -> Engine:
        if self.aborted:
            head = engine.head(self.honest_entity)
            knowledge = self.all_entities
        else:
            head = self.plan_correct_votes[
                engine.slot.num - 1
            ]  # we build on what we voted previously
            if engine.slot.num < self.last_H:
                knowledge = set(
                    self.chain_string[
                        engine.slot.num - self.base_slot : self.last_E - self.base_slot
                    ]
                )
                self.withheld_slots.append(engine.slot.num)
            else:
                knowledge = self.all_entities

        def to_filter(take_bribery: TakeBribery) -> bool:
            from_slot = self.entity_to_censor_from_slot[take_bribery.reference.bribee]
            return from_slot is None or engine.slot.num < from_slot

        return engine.build_block(
            slot=engine.slot.num,
            parent_slot=head,
            knowledge=knowledge,
            censor_take_briberies=lambda take_briberies: filter(
                to_filter, take_briberies
            ),
        )

    def offer_bribe(self, engine: Engine) -> Engine:
        if (
            self.aborted
            or engine.slot_to_owner[engine.slot.num] == self.honest_entity
            or engine.slot.num == self.base_slot + len(self.chain_string)
        ):
            return engine

        voting_slots = [engine.slot.num]
        deadline = engine.slot.num + 1
        for slot, owner in enumerate(
            self.chain_string[engine.slot.num - self.base_slot :],
            start=engine.slot.num,
        ):
            if owner != self.honest_entity:
                deadline = slot
                break
            voting_slots.append(slot)

        offer_briberies: list[OfferBribery] = []
        for bribee in self.coorporating_bribees:
            single_offers = tuple(
                SingleOfferBribery(
                    min_index=0,
                    max_index=engine.entity_to_voting_power[bribee] - 1,
                    from_slot=slot,
                    slot=engine.slot.num,
                    deadline=deadline,
                )
                for slot in voting_slots
            )
            all_indices = engine.entity_to_voting_power[bribee] * len(voting_slots)
            offer_briberies.append(
                OfferBribery(
                    attests=single_offers,
                    base_reward=math.ceil(self.base_reward_unit * all_indices),
                    deadline_reward=math.ceil(self.deadline_reward_unit * all_indices),
                    deadline_payback=math.ceil(
                        self.deadline_payback_unit * all_indices
                    ),
                    bribee=bribee,
                    briber=self.entity,
                    bribed_proposer=engine.slot_to_owner[deadline],
                    included_slots=self.included,
                    excluded_slots=self.excluded,
                )
            )

        self.offers.extend(offer_briberies)

        return engine.add_offer_bribery(
            entity_to_offer_bribery_knowledge={
                entity: offer_briberies for entity in self.all_entities
            }
        )

    def vote(self, engine: Engine) -> Engine:
        if self.aborted:
            head = engine.head(self.honest_entity)
        else:
            head = self.plan_correct_votes[engine.slot.num]
        return engine.add_votes(
            (
                Vote(
                    entity=self.entity,
                    from_slot=engine.slot.num,
                    min_index=0,
                    max_index=engine.entity_to_voting_power[self.entity] - 1,
                    to_slot=head,
                ),
            )
        )

    def send_others_votes(self, engine: Engine) -> Engine:
        take_briberies = engine.take_briberies.get(self.entity)
        if not take_briberies:
            return engine
        votes = {take.vote for take in take_briberies}
        all_votes = engine.all_votes()
        new_votes = votes - all_votes
        if new_votes:
            return engine.add_votes(new_votes)
        return engine

    def withheld_blocks(self, engine: Engine) -> Engine:
        if self.aborted:
            return engine
        if (
            engine.slot.num == self.last_H
        ):
            engine = engine.add_knowledge(
                entity_to_knowledge={
                    entity: self.withheld_slots for entity in self.all_entities
                }
            )
            self.withheld_slots = []

        return engine

    def structural_anomaly(self, engine: Engine) -> bool:
        if engine.slot.num < self.last_H and any(
            engine.slot_to_owner[slot] != self.honest_entity
            and slot in engine.knowledge_of_blocks[self.honest_entity]
            for slot in range(self.base_slot + 1, self.last_H)
        ):
            return True

        return any(
            self.plan_correct_votes[slot - 1] != engine.blocks[slot].parent_slot
            for slot in range(self.base_slot + 1, engine.slot.num + 1)
        )

    def abort(self, engine: Engine) -> Engine:
        self.aborted = True
        engine = engine.add_knowledge(
            entity_to_knowledge={
                entity: self.withheld_slots for entity in self.all_entities
            }
        )
        self.withheld_slots = []

        return engine

    def adjust_strategy(self, engine: Engine) -> Engine:
        """
        This function aborts the attack in case of unresolvable anomaly
        """
        if self.aborted:
            return engine
        if (
            engine.slot.phase == 0
            and engine.slot.num < self.last_H
            and engine.slot_to_owner[engine.slot.num] in self.bribee_entities
            and engine.slot.num
            not in engine.knowledge_of_blocks.get(self.honest_entity, [])
            and engine.sot.num in engine.knowledge_of_blocks.get(self.entity, [])
        ):
            self.withheld_slots.append(engine.slot.num)
        if self.structural_anomaly(engine):
            engine = self.abort()
        elif engine.slot.phase == 1:
            black_listed: set[str] = (
                set()
            )  # Set of votes we exclude from future offers because of late attestations
            # The attack can still work without their votes, later we compute if the attack is viable, otherwise we abort.
            all_votes = engine.all_votes()
            for offer in self.offers:
                for attest_request in offer.attests:
                    if self.patient:
                        condition = (
                            attest_request.deadline is not None
                            and engine.slot.num >= attest_request.deadline - 1
                        )
                    else:
                        condition = engine.slot.num >= attest_request.from_slot

                    if (
                        condition
                        and Vote(
                            entity=offer.bribee,
                            from_slot=attest_request.from_slot,
                            min_index=attest_request.min_index,
                            max_index=attest_request.max_index,
                            to_slot=attest_request.slot,
                        )
                        not in all_votes
                    ):
                        black_listed.add(offer.bribee)
            self.coorporating_bribees -= black_listed
            if black_listed.intersection(
                self.chain_string[engine.slot.num - self.base_slot :]
            ):  # we no longer trust
                engine = self.abort(engine)
            else:
                chain_string = self.chain_string
                untrusted_bribees = self.bribee_entities - self.coorporating_bribees
                E_voting_power = (
                    sum(
                        engine.entity_to_voting_power[entity]
                        for entity in self.coorporating_bribees
                    )
                    + engine.entity_to_voting_power[self.entity]
                )
                H_voting_power = (
                    sum(
                        engine.entity_to_voting_power[entity]
                        for entity in untrusted_bribees
                    )
                    + engine.entity_to_voting_power[self.honest_entity]
                )
                if self.chain_string[0] == self.honest_entity:
                    honest_votes = (len(self.chain_string) - 1) * H_voting_power
                    adv_votes = (
                        len(self.chain_string) - self.last_H + self.base_slot - 1
                    ) * E_voting_power + PROPOSER_BOOST
                else:
                    honest_votes = (
                        len(self.chain_string) - self.last_E + self.base_slot
                    ) * H_voting_power
                    adv_votes = len(chain_string) * E_voting_power + PROPOSER_BOOST
                for vote in all_votes:
                    if (
                        vote.entity in untrusted_bribees
                        and vote.to_slot in self.included
                    ):
                        # Already voted for adv branch, recounting votes
                        adv_votes += vote.amount()
                        honest_votes -= vote.amount()
                if honest_votes >= adv_votes:
                    engine = self.abort(
                        engine
                    )  # new plan will fail, lets minimize damages

        return engine