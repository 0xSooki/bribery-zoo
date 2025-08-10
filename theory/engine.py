from collections import defaultdict
from dataclasses import dataclass, field
from itertools import chain
from typing import Iterable, Sequence

from frozendict import frozendict

from theory.utils import PROPOSER_BOOST


@dataclass(frozen=True)
class Slot:
    num: int
    phase: int  # in {0, 1}

    def __add__(self, other: int) -> "Slot":
        numerical = 2 * self.num + self.phase + other
        return Slot(numerical // 2, numerical % 2)


class Action:
    pass


class AdvAction(Action):
    pass


class BribeeAction(Action):
    pass

@dataclass(frozen=True)
class BaseVote:
    entity: str
    from_slot: int

@dataclass(frozen=True)
class Vote(BaseVote, AdvAction, BribeeAction): # phase 1
    min_index: int
    max_index: int
    to_slot: int
    
    def amount(self) -> int:
        return self.max_index - self.min_index + 1

@dataclass(frozen=True)
class SingleOfferBribery:
    """
    Attributes:
        - votes_needed: usually all the voting power of the bribed entity
        - from_slot: the votes are coming from
        - slot: slot to vote for
        - deadline:
            - not None: The claim of the reward must happen until the given slot number
    """

    votes_needed: float
    from_slot: int
    slot: int
    deadline: int | None


@dataclass(frozen=True)
class OfferBribe(AdvAction): # phase 1
    """
    Already signed transaction
    Attributes:
        - attests: All the attestation requests to be verified later (if one is missing, no payment)
        - base_reward: Amount payed to entity in case of takeBribery, regardless of deadline(s)
        - deadline_reward: Amount payed if all verifications were done before the deadline(s)
        - entity: Bribed entity
        - slot_anchor:
            - None: no protection
            - not None: The smart contract will verify whether this tx happened on the given slot
            or on a branch built on-top of it. If not, only base_reward can be issued
    """

    attests: Sequence[
        SingleOfferBribery
    ]  # Everyone of them must be verified for reward
    base_reward: int
    deadline_reward: int
    deadline_payback: int
    entity: str
    slot_anchor: int | None


@dataclass
class VerifyOneAttestation(BribeeAction):
    reference: OfferBribe
    vote: Vote # one can construct a vote from the message
    index: int


@dataclass(frozen=True)
class SinglePayToAttestState:
    original: OfferBribe
    achieved: Sequence[
        bool
    ]  # tracking which voting was achieved on this state of the blockchain
    before_deadline: Sequence[
        bool
    ]  # tracking whether the verification was done before deadline
    paid: bool

    def achieve(self, index: int, before_deadline: bool) -> "SinglePayToAttestState":
        copy_achieved = list(self.achieved)
        copy_achieved[index] = True
        copy_deadline = list(self.before_deadline)
        copy_deadline[index] = before_deadline

        return SinglePayToAttestState(
            original=self.original,
            achieved=tuple(copy_achieved),
            before_deadline=tuple(copy_deadline),
            paid=self.paid,
        )

    def pay(self) -> "SinglePayToAttestState":
        return SinglePayToAttestState(
            original=self.original,
            achieved=self.achieved,
            before_deadline=self.before_deadline,
            paid=True,
        )


@dataclass
class BuildBlock(AdvAction, BribeeAction): # phase 0
    slot: int
    parent_slot: int
    pay_to_attests: Sequence[OfferBribe]  # can be empty
    claims: Sequence[VerifyOneAttestation]


@dataclass(frozen=True)                           
class CommitToPropose(AdvAction):
    slot: int
    pay_to_attests: Sequence[OfferBribe]


@dataclass(frozen=True)
class ProposeBlock(AdvAction, BribeeAction):
    slot: int


@dataclass(frozen=True)
class WalletState:
    has_infinite_money: frozenset[str]
    address_to_money: frozendict[str, int]

    def pay(self, from_address: str, to_address: str, amount: int) -> "WalletState":
        assert amount > 0
        if from_address not in self.has_infinite_money:
            assert self.address_to_money[from_address] >= amount
        elif from_address not in self.address_to_money:
            self.address_to_money[from_address] = 0
        new_address_to_money = dict(self.address_to_money)
        if to_address not in new_address_to_money:
            new_address_to_money[to_address] = 0
        new_address_to_money[to_address] += amount
        new_address_to_money[from_address] -= amount
        return WalletState(self.has_infinite_money, frozendict(new_address_to_money))


@dataclass(frozen=True)
class Block:
    slot: int
    parent_slot: int
    on_time: bool  # proposed in the first 4 seconds of the slot

    wallet_state: WalletState
    pay_to_attests: frozendict[OfferBribe, SinglePayToAttestState]


@dataclass(frozen=True)
class OffChainGlobalState:
    commited_blocks: frozendict[int, CommitToPropose] = field(default_factory=frozendict)
    commited_briberies: Sequence[OfferBribe] = field(default_factory=tuple)
    

    def extend(
        self,
        commited_blocks: Sequence[CommitToPropose],
        commited_briberies: Sequence[OfferBribe],
    ) -> "OffChainGlobalState":
        new_commited_blocks: dict[int, list[CommitToPropose]] = defaultdict(list)
        for block in chain(self.commited_blocks.values(), commited_blocks):
            new_commited_blocks[block.slot] = new_commited_blocks[block.slot].extend(
                block.pay_to_attests
            )
        
        return OffChainGlobalState(
            commited_blocks=frozendict({
                slot: CommitToPropose(slot, tuple(set(commit)))
                for slot, commit in new_commited_blocks.items()
            }),
            commited_briberies=tuple(
                set(
                    [
                        *[
                            attest
                            for block in commited_blocks
                            for attest in block.pay_to_attests
                        ],
                        *self.commited_briberies,
                        *commited_briberies,
                    ]
                )
            ),
        )


@dataclass(frozen=True)
class Engine:
    base_head_slot: int
    slot: Slot

    slot_to_alphas: frozendict[int, float]
    slot_to_owner: frozendict[int, str]
    slot_to_votes: frozendict[int, float]

    blocks: frozendict[int, Block]
    remaining_votes: frozendict[int, frozendict[str, float]]
    counted_votes: frozendict[BaseVote, frozenset[Vote]]
    knowledge: OffChainGlobalState

    def head(self) -> int:
        slot_to_acc_votes: dict[int, float] = {}
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

    def check_vote_consistency(self, new_vote: Vote) -> bool:
        base = BaseVote(new_vote.entity, new_vote.from_slot)
        votes = self.counted_votes.get(base, frozenset())
        for vote in votes:
            if vote.to_slot != new_vote.to_slot and new_vote.max_index >= vote.min_index and vote.max_index >= new_vote.min_index):
                return False
        return True

    def progress(self, proposed: list[ProposeBlock], votes: list[Vote]) -> "Engine":
        new_blocks = dict(self.blocks)
        new_remaining_votes = dict(self.remaining_votes)

        if self.slot.phase == 0:
            if self.slot_to_owner[self.slot.num] == "H":
                assert not proposed
                assert not votes
                head = self.head()
                new_blocks[self.slot.num] = Block(
                    slot=self.slot.num,
                    parent_slot=head,
                    votes=0.0,
                    on_time=True,
                )
            else:
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
