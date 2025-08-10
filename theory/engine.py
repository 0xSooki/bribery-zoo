from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

from frozendict import frozendict

from theory.action import (
    BaseVote,
    OfferBribery,
    ProposeBlock,
    SinglePayToAttestState,
    VerifyOneAttestation,
    Vote,
)
from theory.utils import HAS_INFINITE_MONEY, PROPOSER_BOOST, Slot


@dataclass(frozen=True)
class WalletState:
    # has_infinite_money: frozenset[str] = field(default_factory=lambda: HAS_INFINITE_MONEY)
    address_to_money: frozendict[str, int] = field(default_factory=frozendict)

    def pay(self, from_address: str, to_address: str, amount: int) -> "WalletState":
        #assert amount > 0
        #if from_address not in self.has_infinite_money:
        #    assert self.address_to_money[from_address] >= amount
        if from_address not in self.address_to_money:
            self.address_to_money[from_address] = 0
        new_address_to_money = dict(self.address_to_money)
        if to_address not in new_address_to_money:
            new_address_to_money[to_address] = 0
        new_address_to_money[to_address] += amount
        new_address_to_money[from_address] -= amount
        return WalletState(frozendict(new_address_to_money))


@dataclass(frozen=True)
class Block:
    slot: int
    parent_slot: int
    on_time: bool  # proposed in the first 4 seconds of the slot

    wallet_state: WalletState
    pay_to_attests: frozendict[OfferBribery, SinglePayToAttestState]
    votes: Sequence[Vote]

@dataclass(frozen=True)
class Engine:
    base_head_slot: int
    slot: Slot

    slot_to_alphas: frozendict[int, int]
    slot_to_owner: frozendict[int, str]
    slot_to_votes: frozendict[int, int]

    blocks: frozendict[int, Block]
    # remaining_votes: frozendict[int, frozendict[str, float]]
    counted_votes: frozendict[BaseVote, frozenset[Vote]]
    offer_briberies: frozendict[
        str, frozenset[OfferBribery]
    ]  # entity -> known briberies (offchain)
    take_briberies: frozendict[str, frozenset[VerifyOneAttestation]]
    votes: frozenset[Vote]

    def head(self) -> int:
        slot_to_acc_votes: dict[int, int] = {}
        for slot, votes in sorted(self.slot_to_votes.items(), key=lambda x: x[0]):

            slot_to_acc_votes[slot] = votes
            if slot == self.slot.num and self.blocks[slot].on_time:
                slot_to_acc_votes[slot] += PROPOSER_BOOST

            act_slot = self.blocks[slot].parent_slot
            while act_slot != self.base_head_slot:
                slot_to_acc_votes[act_slot] += slot_to_acc_votes[slot]
                act_slot = self.blocks[act_slot].parent_slot

        slot_to_desc: dict[int, list[int]] = defaultdict(list)
        for block in self.blocks.values():
            slot_to_desc[block.parent_slot].append(block.slot)

        head = self.base_head_slot
        while head in slot_to_desc:
            votes = [(desc, slot_to_acc_votes[desc]) for desc in slot_to_desc[head]]
            best = max(votes, key=lambda x: x[1])
            assert all([vote < best[1] for slot, vote in votes if slot != best[0]])
            head = best[0]

        return head

    def check_vote(self, new_vote: Vote) -> int | None:
        """
        If double voting happened, returns None
        If not, returns the new added votes
        """
        base = BaseVote(new_vote.entity, new_vote.from_slot)
        votes = self.counted_votes.get(base, frozenset())
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
        return True

    def build_fresh_block(self, slot: int, parent_slot: int, entity: str, censor: Callable[[Iterable[Vote]], Iterable[Vote]] | None = None) -> Block:
        prev_state = (
            dict(self.blocks[parent_slot].pay_to_attests)
            if parent_slot in self.blocks
            else {}
        )
        wallet_state = self.blocks[parent_slot].wallet_state if parent_slot in self.blocks else WalletState()
        offer_briberies = self.offer_briberies.get(entity, frozenset())
        missing_offers = offer_briberies - frozenset(prev_state)
        for offer in missing_offers:
            prev_state[offer] = SinglePayToAttestState(
                original=offer,
                achieved=(False,) * len(offer.attests),
                before_deadline=(False,) * len(offer.attests),
                paid=False,
            )
        for take_briberies in self.take_briberies.get(entity, frozenset()):
            state = prev_state[take_briberies.reference]
            if (
                take_briberies.reference in prev_state
                and not state.achieved[take_briberies.index]
            ):
                deadline = take_briberies.reference.attests[
                    take_briberies.index
                ].deadline
                state = state.achieve(
                    take_briberies.index, deadline is None or slot <= deadline
                )
                if all(state.achieved):
                    amount = take_briberies.reference.base_reward
                    if all(state.before_deadline):
                        amount += take_briberies.reference.deadline_reward
                    wallet_state.pay(
                        from_address=take_briberies.reference.briber,
                        to_address=take_briberies.reference.entity,
                        amount=amount,
                    )
                    state = state.pay()
                prev_state[take_briberies.reference] = state

        
        included = set()
        _slot = parent_slot
        while _slot != self.base_head_slot:
            included.update(self.blocks[_slot].votes)
            _slot = self.blocks[_slot].parent_slot
        
        votes = self.votes - included
        if censor is not None:
            votes = frozenset(censor(votes))

        # TODO: consensus rewarding/punishing included timely votes

        return Block(
            slot=slot,
            parent_slot=parent_slot,
            on_time=slot == self.slot.num,
            wallet_state=wallet_state,
            pay_to_attests=frozendict(prev_state),
            votes=votes,
        )

    def honest_phase0(
        self,
    ) -> None:
        head = self.head()
        # new_blocks[self.slot.num] =

    def progress(self, proposed: list[ProposeBlock], votes: list[Vote]) -> "Engine":
        new_blocks = dict(self.blocks)

        if self.slot.phase == 0:
            if self.slot_to_owner[self.slot.num] == "H":
                assert not proposed
                assert not votes

                new_blocks[self.slot.num] = Block(
                    slot=self.slot.num,
                    parent_slot=head,
                    votes=0.0,
                    on_time=True,
                )
            elif self.slot_to_owner[self.slot.num] == "A":
                for prop in proposed:
                    assert prop.block.slot not in new_blocks
                    assert not prop.block.on_time or prop.block.slot == self.slot.num
                    assert prop.block.votes == 0.0
                    new_blocks[prop.block.slot] = prop.block

                for vote in votes:
                    assert (
                        vote.from_slot != self.slot.num
                    )  # only previous, not the time for voting
                    assert new_remaining_votes[vote.from_slot] >= vote.amount
                    assert vote.from_slot >= vote.to_slot
                    new_remaining_votes[vote.from_slot] -= vote.amount
        else:
            for prop in proposed:
                assert prop.block.slot not in new_blocks
                assert not prop.block.on_time
                assert prop.block.votes == 0.0
                new_blocks[prop.block.slot] = prop.block
            # adding not same slot votes
            for vote in votes:

                if vote.from_slot != self.slot.num:
                    assert new_remaining_votes[vote.from_slot] >= vote.amount
                    assert vote.from_slot >= vote.to_slot
                    new_remaining_votes[vote.from_slot] -= vote.amount
                    if vote.to_slot != self.base_head_slot:
                        new_blocks[vote.to_slot] = Block(
                            slot=new_blocks[vote.to_slot].slot,
                            parent_slot=new_blocks[vote.to_slot].parent_slot,
                            votes=new_blocks[vote.to_slot].votes + vote.amount,
                            on_time=new_blocks[vote.to_slot].on_time,
                        )
            advance = Engine(
                base_head_slot=self.base_head_slot,
                slot=self.slot,
                slot_to_alphas=self.slot_to_alphas,
                slot_to_owner=self.slot_to_owner,
                blocks=frozendict(new_blocks),
                remaining_votes=frozendict(new_remaining_votes),
            )
            adv_head = advance.head()
            head = self.head()
            # assert (
            #    adv_head == head
            # )  # whether getting the new votes or not, it should not influence current voting

            if head != self.base_head_slot:

                if head == adv_head:
                    new_blocks[head] = Block(
                        slot=new_blocks[head].slot,
                        parent_slot=new_blocks[head].parent_slot,
                        votes=new_blocks[head].votes
                        + 1
                        - self.slot_to_alphas[self.slot.num],
                        on_time=new_blocks[head].on_time,
                    )
                else:
                    for h in [head, adv_head]:
                        new_blocks[h] = Block(
                            slot=new_blocks[h].slot,
                            parent_slot=new_blocks[h].parent_slot,
                            votes=new_blocks[h].votes
                            + VoteInterval(0.0, 1 - self.slot_to_alphas[self.slot.num]),
                            on_time=new_blocks[head].on_time,
                        )
            for vote in votes:
                if vote.from_slot == self.slot.num:
                    assert new_remaining_votes[vote.from_slot] >= vote.amount

                    assert vote.from_slot >= vote.to_slot
                    new_remaining_votes[vote.from_slot] -= vote.amount
                    if vote.to_slot != self.base_head_slot:
                        new_blocks[vote.to_slot] = Block(
                            slot=new_blocks[vote.to_slot].slot,
                            parent_slot=new_blocks[vote.to_slot].parent_slot,
                            votes=new_blocks[vote.to_slot].votes + vote.amount,
                            on_time=new_blocks[vote.to_slot].on_time,
                        )

        return Engine(
            base_head_slot=self.base_head_slot,
            slot=Slot(self.slot.num + self.slot.phase, phase=(self.slot.phase + 1) % 2),
            slot_to_alphas=self.slot_to_alphas,
            slot_to_owner=self.slot_to_owner,
            blocks=frozendict(new_blocks),
            remaining_votes=frozendict(new_remaining_votes),
        )
