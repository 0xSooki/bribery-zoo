from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from frozendict import frozendict

from simulation.theory.action import (
    BaseVote,
    Block,
    OfferBribery,
    PayToAttestState,
    TakeBribery,
    Vote,
    WalletState,
)
from simulation.theory.utils import (
    ATTESTATORS_PER_SLOT,
    B,
    BASE_INCREMENT,
    NUM_OF_VALIDATORS,
    PROPOSER_BOOST,
    Slot,
    W_p,
    W_sum,
    attestation_base_reward,
)


@dataclass(frozen=True)
class Engine:
    base_head_slot: int
    slot: Slot

    entity_to_voting_power: frozendict[str, int]
    slot_to_owner: frozendict[int, str]
    slot_to_votes: frozendict[int, int]
    slot_to_all_votes: frozendict[int, int]

    knowledge_of_blocks: frozendict[str, frozenset[int]]  # entity -> knowledge of slots
    blocks: frozendict[int, Block]
    # remaining_votes: frozendict[int, frozendict[str, float]]
    counted_votes: frozendict[BaseVote, frozenset[Vote]]
    offer_briberies: frozendict[
        str, frozenset[OfferBribery]
    ]  # entity -> known briberies (offchain)
    take_briberies: frozendict[str, frozenset[TakeBribery]]

    def change(self, new_data: dict[str, Any]) -> "Engine":
        data = dict(self.__dict__)  # shallow copy of self's data
        data.update(new_data)  # adding new data
        return Engine(**data)

    def head(self, entity: str) -> int:
        slot_to_acc_votes: dict[int, int] = defaultdict(int)
        knowledge = self.knowledge_of_blocks.get(entity, frozenset())
        for slot, votes in sorted(self.slot_to_votes.items(), key=lambda x: x[0]):
            if slot not in knowledge:
                continue
            slot_to_acc_votes[slot] += votes
            if slot == self.slot.num and self.blocks[slot].on_time:
                slot_to_acc_votes[slot] += PROPOSER_BOOST

            act_slot = self.blocks[slot].parent_slot
            while act_slot != self.base_head_slot:
                slot_to_acc_votes[act_slot] += slot_to_acc_votes[slot]
                act_slot = self.blocks[act_slot].parent_slot

        slot_to_desc: dict[int, list[int]] = defaultdict(list)
        knowledge = knowledge.union((self.base_head_slot,))
        for slot, block in self.blocks.items():
            if slot in knowledge:
                assert block.parent_slot in knowledge
                slot_to_desc[block.parent_slot].append(block.slot)

        head = self.base_head_slot
        while head in slot_to_desc:
            votes = [(desc, slot_to_acc_votes[desc]) for desc in slot_to_desc[head]]
            best = max(votes, key=lambda x: x[1])
            assert all([vote < best[1] for slot, vote in votes if slot != best[0]])
            head = best[0]

        return head

    @staticmethod
    def check_vote(votes: Iterable[Vote], new_vote: Vote) -> int | None:
        """
        If double voting happened, returns None
        If not, returns the new added votes
        """
        # base = BaseVote(new_vote.entity, new_vote.from_slot)
        # votes = self.counted_votes.get(base, frozenset())
        for vote in votes:
            if vote.to_slot == new_vote.to_slot:
                if vote == new_vote:
                    return 0
                assert (
                    new_vote.max_index < vote.min_index
                    or vote.max_index < new_vote.min_index
                ), "Fractured votes are not allowed, we expect clean separation"
            elif (
                new_vote.max_index >= vote.min_index
                and vote.max_index >= new_vote.min_index
            ):
                return None
        return new_vote.amount()

    def slot_progress(self) -> "Engine":
        slot_to_votes = self.slot_to_votes
        slot = self.slot + 1
        if slot.phase == 0:  # new slot
            slot_to_votes = self.slot_to_all_votes
        return self.change({"slot": slot, "slot_to_votes": slot_to_votes})

    def add_votes(self, votes: Iterable[Vote]) -> "Engine":
        assert self.slot.phase == 1
        counted_votes = dict(self.counted_votes)
        slot_to_votes = dict(self.slot_to_votes)
        slot_to_all_votes = dict(self.slot_to_all_votes)

        for vote in votes:
            assert (
                0
                <= vote.min_index
                <= vote.max_index
                < self.entity_to_voting_power[vote.entity]
            ), f"0 <= {vote.min_index=} <= {vote.max_index=} < {self.entity_to_voting_power[vote.entity]=}"
            assert vote.to_slot <= vote.from_slot <= self.slot.num
            base = BaseVote(vote.entity, vote.from_slot)
            additional_votes = Engine.check_vote(counted_votes.get(base, []), vote)
            assert additional_votes is not None, f"Double voting detected, {vote=}"
            slot_to_all_votes[vote.to_slot] = (
                slot_to_all_votes.get(vote.to_slot, 0) + additional_votes
            )
            if vote.from_slot != self.slot.num:

                slot_to_votes[vote.to_slot] = (
                    slot_to_votes.get(vote.to_slot, 0) + additional_votes
                )
            counted_votes[base] = counted_votes.get(base, frozenset()).union((vote,))

        return self.change(
            {
                "counted_votes": frozendict(counted_votes),
                "slot_to_votes": frozendict(slot_to_votes),
                "slot_to_all_votes": frozendict(slot_to_all_votes),
            }
        )

    def add_knowledge(self, entity_to_knowledge: dict[str, Iterable[int]]) -> "Engine":
        """
        Creates a new copy of engine with updated knowledge of blocks
        """

        knowledge = dict(self.knowledge_of_blocks)
        for entity, entry in entity_to_knowledge.items():
            knowledge[entity] = knowledge.get(entity, frozenset()).union(entry)

        return self.change({"knowledge_of_blocks": frozendict(knowledge)})

    def add_offer_bribery(
        self, entity_to_offer_bribery_knowledge: dict[str, Iterable[OfferBribery]]
    ) -> "Engine":
        offer_briberies = dict(self.offer_briberies)
        for entity, offers in entity_to_offer_bribery_knowledge.items():
            for offer in offers:
                for single in offer.attests:
                    assert (
                        single.slot in self.blocks or single.slot == self.base_head_slot
                    )  # H(m) exists already
            offer_briberies[entity] = offer_briberies.get(entity, frozenset()).union(
                offers
            )
        return self.change({"offer_briberies": offer_briberies})

    # take_briberies

    def add_take_briberies(
        self, entity_to_take_briberies_knowledge: dict[str, Iterable[TakeBribery]]
    ) -> "Engine":
        take_briberies = dict(self.take_briberies)
        for entity, takes in entity_to_take_briberies_knowledge.items():
            for take_bribery in takes:
                single_offer = take_bribery.reference.attests[take_bribery.index]
                assert take_bribery.reference.bribee == take_bribery.vote.entity
                assert single_offer.from_slot == take_bribery.vote.from_slot
                assert single_offer.slot == take_bribery.vote.to_slot
                assert single_offer.min_index == take_bribery.vote.min_index
                assert single_offer.max_index == take_bribery.vote.max_index

                base = BaseVote(take_bribery.vote.entity, take_bribery.vote.from_slot)
                assert (
                    Engine.check_vote(
                        self.counted_votes.get(base, []), take_bribery.vote
                    )
                    is not None
                )
            take_briberies[entity] = take_briberies.get(entity, frozenset()).union(
                takes
            )
        return self.change({"take_briberies": take_briberies})

    def build_block(
        self,
        slot: int,
        parent_slot: int,
        knowledge: Iterable[str] | None = None,
        final: bool = False,
        entity: str | None = None,
        censor_take_briberies: Callable[
            [Iterable[TakeBribery]], Iterable[TakeBribery]
        ] = lambda x: x,
        censor_votes: Callable[[Iterable[Vote]], Iterable[Vote]] = lambda x: x,
    ) -> "Engine":
        """
        Builds an engine with a new block considering every known transaction -> censorship functions -> block
        We only consider censoring out take briberies and votes. It doesn't makes sense to
        censor offer bribe function calls as it is sufficient to censor take bribery calls

        Arguments:
            - slot (int): Slot we are building the block at, doesn't have to be self.slot.num
            - parent_slot (int): parent block's slot
            - knowledge: Who will know the content of the block (other than the proposer)
            - final (bool): last block where funds are withdrawn/burned. Effectively symbolizes a block state after a long deadline
            - entity (str | None): proposer entity of the given slot
            - censor_take_briberies: Function censoring (not including) take_bribery calls in the block
            - censor_votes: Function censoring (not including) some votes in the block
        """
        assert slot not in self.blocks
        if entity is not None:
            assert self.slot_to_owner.get(slot, entity) == entity

        prev_state = (
            dict(self.blocks[parent_slot].pay_to_attests)
            if parent_slot in self.blocks
            else {}
        )
        wallet_state = (
            self.blocks[parent_slot].wallet_state
            if parent_slot in self.blocks
            else WalletState()
        )
        if entity is None:
            entity = self.slot_to_owner[slot]
        offer_briberies = self.offer_briberies.get(entity, frozenset())
        missing_offers = offer_briberies - frozenset(prev_state)

        for offer in missing_offers:
            prev_state[offer] = PayToAttestState(
                offer_bribery=offer,
                achieved=(False,) * len(offer.attests),
                before_deadline=(False,) * len(offer.attests),
                paid=False,
                extra_funds=False,
            )

        for take_bribery in censor_take_briberies(self.take_briberies.get(entity, [])):

            state = prev_state[take_bribery.reference]
            if (
                take_bribery.reference in prev_state
                and not state.achieved[take_bribery.index]
            ):
                deadline = take_bribery.reference.attests[take_bribery.index].deadline
                state = state.achieve(
                    take_bribery.index, deadline is None or slot <= deadline
                )
                if all(state.achieved) and not state.paid:

                    extra_funds = False
                    if all(state.before_deadline):
                        included = state.offer_bribery.included_slots
                        excluded = state.offer_bribery.excluded_slots

                        branch = {slot, self.base_head_slot}
                        _slot = parent_slot

                        while _slot != self.base_head_slot:
                            branch.add(_slot)
                            _slot = self.blocks[_slot].parent_slot

                        extra_funds = included.issubset(
                            branch
                        ) and not excluded.intersection(branch)

                    if extra_funds:
                        wallet_state = wallet_state.pay(
                            from_address=take_bribery.reference.briber,
                            to_address=take_bribery.reference.bribed_proposer,
                            amount=take_bribery.reference.deadline_payback,
                            comment="Proposer reward for not censoring",
                        )
                        wallet_state = wallet_state.pay(
                            from_address=take_bribery.reference.briber,
                            to_address=take_bribery.reference.bribee,
                            amount=take_bribery.reference.deadline_reward,
                            comment="Reward to bribee for voting timely",
                        )
                    wallet_state = wallet_state.pay(
                        from_address=take_bribery.reference.briber,
                        to_address=take_bribery.reference.bribee,
                        amount=take_bribery.reference.base_reward,
                        comment="Paying for base reward to bribee",
                    )
                    state = state.pay(extra_funds=extra_funds)
                prev_state[take_bribery.reference] = state

        included: set[Vote] = set()
        _slot = parent_slot
        while _slot != self.base_head_slot:
            included.update(self.blocks[_slot].votes)
            _slot = self.blocks[_slot].parent_slot

        all_votes = frozenset(
            {vote for entry in self.counted_votes.values() for vote in entry}
        )
        future_votes = {
            vote for vote in all_votes if vote.from_slot >= slot
        }  # only include slots from the past relative to 'slot'

        considerable = all_votes - future_votes

        votes = frozenset(censor_votes(considerable - included))

        stat: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        for vote in considerable:
            stat[vote.from_slot][vote.to_slot] += vote.amount()
        correct_heads: dict[int, int] = {}
        slots = {vote.from_slot for vote in votes}
        head = slot
        for curr_slot in sorted(slots, reverse=True):
            while head > curr_slot:
                head = self.blocks[head].parent_slot if head != slot else parent_slot
            correct_heads[curr_slot] = head

        for vote in votes:

            reward, punishment = attestation_base_reward(
                timeliness=(3 if correct_heads[vote.from_slot] == vote.to_slot else 2),
                common={
                    "W_s": sum(stat[vote.from_slot].values()) / ATTESTATORS_PER_SLOT,
                    "W_t": sum(stat[vote.from_slot].values()) / ATTESTATORS_PER_SLOT,
                    "W_h": stat[vote.from_slot][vote.to_slot] / ATTESTATORS_PER_SLOT,
                },
                slot_distance=slot - vote.from_slot,
            )
            assert reward >= 0 and punishment <= 0  # TODO: DELETE
            reward *= BASE_INCREMENT * B * vote.amount()
            punishment *= BASE_INCREMENT * B * vote.amount()

            wallet_state = wallet_state.pay(
                from_address="cons",
                to_address=vote.entity,
                amount=int(reward + punishment),
                comment="Consensus protocol paying for voting",
            )
            wallet_state = wallet_state.pay(  # paying to the proposer as well
                from_address="cons",
                to_address=entity,
                amount=int(reward * W_p / (W_sum - W_p)),
                comment="Consensus protocol paying for including votes",
            )

        if final:
            for offer, state in prev_state.items():
                if state.paid and not state.extra_funds:
                    wallet_state = wallet_state.pay(
                        from_address=offer.briber,
                        to_address="burned_money",
                        amount=offer.deadline_payback + offer.deadline_reward,
                        comment="Burning money of the briber",
                    )

        block = Block(
            slot=slot,
            parent_slot=parent_slot,
            on_time=slot == self.slot.num,
            wallet_state=wallet_state,
            pay_to_attests=frozendict(prev_state),
            votes=votes,
        )

        new_blocks = dict(self.blocks)
        new_blocks[slot] = block

        knowledge_of_blocks = dict(self.knowledge_of_blocks)
        knowledge_of_blocks[entity] = knowledge_of_blocks.get(
            entity, frozenset()
        ).union((slot,))
        if knowledge:
            for ent in knowledge:
                knowledge_of_blocks[ent] = knowledge_of_blocks.get(
                    ent, frozenset()
                ).union((slot,))

        return self.change(
            {
                "blocks": frozendict(new_blocks),
                "knowledge_of_blocks": frozendict(knowledge_of_blocks),
            }
        )

    def all_votes(self) -> set[Vote]:
        return {vote for votes in self.counted_votes.values() for vote in votes}

    @staticmethod
    def make_engine(
        chain_string: Iterable[str], entity_to_voting_power: dict[str, int]
    ) -> "Engine":
        return Engine(
            base_head_slot=0,
            slot=Slot(1, 0),
            entity_to_voting_power=frozendict(entity_to_voting_power),
            slot_to_owner=frozendict(
                {i + 1: owner for i, owner in enumerate(chain_string)}
            ),
            slot_to_votes=frozendict({i + 1: 0 for i in range(len(chain_string))}),
            slot_to_all_votes=frozendict({i + 1: 0 for i in range(len(chain_string))}),
            knowledge_of_blocks=frozendict(
                {entity: frozenset() for entity in entity_to_voting_power}
            ),
            blocks=frozendict(),
            counted_votes=frozendict(),
            offer_briberies=frozendict(
                {entity: frozenset() for entity in entity_to_voting_power}
            ),
            take_briberies=frozendict(
                {entity: frozenset() for entity in entity_to_voting_power}
            ),
        )
