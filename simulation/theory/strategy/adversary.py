from dataclasses import dataclass
import math
from numbers import Real

from frozendict import frozendict
from simulation.theory.action import OfferBribery, SingleOfferBribery, TakeBribery, Vote
from simulation.theory.engine import Engine
from simulation.theory.strategy.base import IAdvStrategy, Params
from simulation.theory.utils import PROPOSER_BOOST, Slot


@dataclass(frozen=True)
class AdvParams(Params):
    censor_from_slot: int | None
    patient: bool
    break_bad_slot: int | None


class AdvStrategy(IAdvStrategy):
    def __init__(
        self,
        censor_from_slot: int | None,
        base_reward_unit: Real,
        deadline_reward_unit: Real,
        deadline_payback_unit: Real,
        patient: bool,
        break_bad_slot: int | None,
        base_slot: int,
        chain_string: str,
        entity: str,
        honest_entity: str,
        bribee_entities: set[str],
        event_list: list[tuple[Slot, str]],
    ):
        self.censor_from_slot = censor_from_slot
        self.base_reward_unit = base_reward_unit
        self.deadline_payback_unit = deadline_payback_unit
        self.deadline_reward_unit = deadline_reward_unit
        self.patient = patient
        self.break_bad_slot = break_bad_slot
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

        self.setup_plan()

        self.offers: list[OfferBribery] = []

        self.event_list = event_list

        if break_bad_slot == self.base_slot:
            self.aborted = True
            self.event_list.append(
                (Slot(self.base_slot, 1), f"[{self.entity}] I will behave honestly")
            )

    def build(self, engine: Engine) -> Engine:
        if self.aborted:
            head = engine.head(self.honest_entity)
            knowledge = self.all_entities
            self.event_list.append(
                (
                    engine.slot,
                    f"[{self.entity}] I already aborted, I build a block on top of slot {head}",
                )
            )
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
                self.event_list.append(
                    (
                        engine.slot,
                        f"[{self.entity}] I secretly build a block on top of {head}",
                    )
                )
            else:
                knowledge = self.all_entities
                self.event_list.append(
                    (engine.slot, f"[{self.entity}] I propose a block on top of {head}")
                )

        from_slot = self.censor_from_slot
        include = from_slot is None or engine.slot.num < from_slot
        if include:
            censor = lambda x: x
        else:
            censor = lambda x: []
            self.event_list.append(
                (
                    engine.slot,
                    f"[{self.entity}] I will actively censor take_bribe calls",
                )
            )

        return engine.build_block(
            slot=engine.slot.num,
            parent_slot=head,
            knowledge=knowledge,
            censor_take_briberies=censor,
        )

    def offer_bribe(self, engine: Engine) -> Engine:
        if (
            self.aborted
            or (
                engine.slot_to_owner[engine.slot.num] == self.honest_entity
                and engine.slot.num != self.base_slot + 1
            )
            or engine.slot.num == self.base_slot + len(self.chain_string)
        ):
            return engine

        voting_slots = {engine.slot.num}
        deadline = engine.slot.num + 1
        for slot, owner in enumerate(
            self.chain_string[engine.slot.num - self.base_slot :],
            start=engine.slot.num + 1,
        ):
            if owner != self.honest_entity:
                deadline = slot
                break
            voting_slots.add(slot)

        offer_briberies: list[OfferBribery] = []
        for bribee in self.coorporating_bribees:
            single_offers = tuple(
                SingleOfferBribery(
                    min_index=0,
                    max_index=engine.entity_to_voting_power[bribee] - 1,
                    from_slot=slot,
                    slot=self.plan_correct_votes[slot],
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
        for offer in offer_briberies:
            voting_str = ", ".join(
                [
                    f"{attest_req.from_slot} => {attest_req.slot}"
                    for attest_req in offer.attests
                ]
            )
            self.event_list.append(
                (
                    engine.slot,
                    f"[{self.entity}] I offered a bribe for {offer.bribee}. They should vote for {voting_str}",
                )
            )

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
        self.event_list.append((engine.slot, f"[{self.entity}] I vote for slot {head}"))

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
            self.event_list.append(
                (
                    engine.slot,
                    f"[{self.entity}] I have sent {len(new_votes)} out from take_bribe calls to everyone",
                )
            )
            return engine.add_votes(new_votes)
        return engine

    def withheld_blocks(self, engine: Engine) -> Engine:
        if self.aborted:
            return engine
        if engine.slot.num == self.last_H:
            engine = engine.add_knowledge(
                entity_to_knowledge={
                    entity: self.withheld_slots for entity in self.all_entities
                }
            )
            for slot in self.withheld_slots:
                self.event_list.append(
                    (engine.slot, f"[{self.entity}] I released slot {slot} to everyone")
                )
            self.withheld_slots = []

        return engine

    def abort(self, engine: Engine) -> Engine:
        self.event_list.append((engine.slot, f"[{self.entity}] Attack aborted..."))
        self.aborted = True
        engine = engine.add_knowledge(
            entity_to_knowledge={
                entity: self.withheld_slots for entity in self.all_entities
            }
        )
        if self.withheld_slots:
            self.event_list.append(
                (
                    engine.slot,
                    f"[{self.entity}] I released {len(self.withheld_slots)} block(s) to everyone",
                )
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
            and engine.slot.num in engine.knowledge_of_blocks.get(self.entity, [])
        ):
            self.withheld_slots.append(engine.slot.num)
        if self.structural_anomaly(engine):
            engine = self.abort(engine)
        elif self.break_bad_slot is not None and engine.slot.num >= self.break_bad_slot:
            self.event_list.append(
                (engine.slot, f"[{self.entity}] At this point, I was told to break bad")
            )
            engine = self.abort(engine)
        elif engine.slot.phase == 1:
            black_listed: set[str] = (
                set()
            )  # Set of votes we exclude from future offers because of late attestations
            # The attack can still work without their votes, later we compute if the attack is viable, otherwise we abort.
            all_votes = engine.all_votes()
            for offer in self.offers:
                for attest_request in offer.attests:
                    if any(
                        vote
                        for vote in all_votes
                        if vote.from_slot == attest_request.from_slot
                        and vote.entity == offer.bribee
                        and vote.min_index == attest_request.min_index
                        and vote.max_index == attest_request.max_index
                        and vote.to_slot != attest_request.slot
                    ):
                        condition = True
                    elif self.patient:
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
            if black_listed:
                self.event_list.append(
                    (
                        engine.slot,
                        f"[{self.entity}] I no longer trust: {', '.join(black_listed)}",
                    )
                )
            if black_listed.intersection(
                self.chain_string[engine.slot.num - self.base_slot :]
            ):  # we no longer trust
                engine = self.abort(engine)
                self.event_list.append(
                    (
                        engine.slot,
                        f"[{self.entity}] In the future a blacklisted validator will propose",
                    )
                )
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
                        len(self.chain_string) - self.last_E + self.base_slot - 1
                    ) * H_voting_power
                    adv_votes = (
                        len(chain_string) - 1
                    ) * E_voting_power + PROPOSER_BOOST
                for vote in all_votes:
                    if (
                        vote.entity in untrusted_bribees
                        and vote.to_slot in self.included
                    ):
                        # Already voted for adv branch, recounting votes
                        adv_votes += vote.amount()
                        honest_votes -= vote.amount()
                if honest_votes >= adv_votes:
                    self.event_list.append(
                        (
                            engine.slot,
                            f"[{self.entity}] Because of shortage of trusted bribees, the attack will fail, aborting to minimize damages",
                        )
                    )
                    engine = self.abort(
                        engine
                    )  # new plan will fail, lets minimize damages

        return engine
