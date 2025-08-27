from dataclasses import dataclass, field
from typing import Sequence

from frozendict import frozendict


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
class Vote(BaseVote, AdvAction, BribeeAction):  # phase 1
    min_index: int
    max_index: int
    to_slot: int

    def amount(self) -> int:
        return self.max_index - self.min_index + 1


@dataclass(frozen=True)
class SingleOfferBribery:
    """
    Attributes:
        - min_index: min index of the bribee we expect voting
        - max_index: max index of the bribee we expect voting
        - from_slot: the votes are coming from
        - slot: slot to vote for
        - deadline:
            - not None: The claim of the reward must happen until the given slot number
    """

    min_index: int
    max_index: int
    from_slot: int
    slot: int
    deadline: int | None


@dataclass(frozen=True)
class OfferBribery(AdvAction):  # phase 1
    """
    Already signed transaction
    Attributes:
        - attests: All the attestation requests to be verified later (if one is missing, no payment)
        - base_reward: Amount payed to entity in case of takeBribery, regardless of deadline(s) or success of fork. The main reason is that we reward them if they do not double fork
        - deadline_reward: Amount payed if all verifications were done before the deadline(s) and fork succeded
        - bribee: Bribed entity
        - briber: Entity paying/offering the bribe
        - bribed_proposer: Entity payed if deadline+fork is successful. Usually the same entity to include the takeBribery (can be the bribee).
        - included_slots: The smart contract will verify whether this tx happened on a branch containing these slot numbers. If not, only base_reward can be issued
        - excluded_slots: The smart contract will verify whether this tx happened on a branch NOT containing any of these slot numbers. If it does, only base_reward can be issued
    """

    attests: Sequence[
        SingleOfferBribery
    ]  # Everyone of them must be verified for reward
    base_reward: int
    deadline_reward: int
    deadline_payback: int
    bribee: str
    briber: str
    bribed_proposer: str
    included_slots: frozenset[int]
    excluded_slots: frozenset[int]
    # TODO: bribee != entity (all the time)


@dataclass(frozen=True)
class TakeBribery(BribeeAction):
    reference: OfferBribery
    vote: Vote  # one can construct a vote from the message
    index: int


@dataclass(frozen=True)
class PayToAttestState:
    offer_bribery: OfferBribery
    achieved: Sequence[
        bool
    ]  # tracking which voting was achieved on this state of the blockchain
    before_deadline: Sequence[
        bool
    ]  # tracking whether the verification was done before deadline
    paid: bool
    extra_funds: bool

    def achieve(self, index: int, before_deadline: bool) -> "PayToAttestState":
        copy_achieved = list(self.achieved)
        copy_achieved[index] = True
        copy_deadline = list(self.before_deadline)
        copy_deadline[index] = before_deadline

        return PayToAttestState(
            offer_bribery=self.offer_bribery,
            achieved=tuple(copy_achieved),
            before_deadline=tuple(copy_deadline),
            paid=self.paid,
            extra_funds=self.extra_funds,
        )

    def pay(self, extra_funds: bool) -> "PayToAttestState":
        return PayToAttestState(
            offer_bribery=self.offer_bribery,
            achieved=self.achieved,
            before_deadline=self.before_deadline,
            paid=True,
            extra_funds=extra_funds,
        )


@dataclass
class BuildBlock(AdvAction, BribeeAction):  # phase 0
    slot: int
    parent_slot: int
    pay_to_attests: Sequence[OfferBribery]  # can be empty
    claims: Sequence[TakeBribery]


@dataclass(frozen=True)
class Payment:
    from_address: str
    to_address: str
    amount: int
    comment: str = ""


@dataclass(frozen=True)
class WalletState:
    # has_infinite_money: frozenset[str] = field(default_factory=lambda: HAS_INFINITE_MONEY)
    address_to_money: frozendict[str, int] = field(default_factory=frozendict)
    ledger: tuple[Payment, ...] = field(default_factory=tuple)

    def pay(self, payment: Payment) -> "WalletState":
        # assert amount > 0
        # if from_address not in self.has_infinite_money:
        #    assert self.address_to_money[from_address] >= amount
        new_address_to_money = dict(self.address_to_money)

        if payment.from_address not in self.address_to_money:
            new_address_to_money[payment.from_address] = 0

        if payment.to_address not in new_address_to_money:
            new_address_to_money[payment.to_address] = 0
        new_address_to_money[payment.to_address] += payment.amount
        new_address_to_money[payment.from_address] -= payment.amount
        new_ledger = list(self.ledger)
        new_ledger.append(payment)
        return WalletState(frozendict(new_address_to_money), ledger=tuple(new_ledger))


@dataclass(frozen=True)
class Block:
    slot: int
    parent_slot: int
    on_time: bool  # proposed in the first 4 seconds of the slot

    wallet_state: WalletState
    pay_to_attests: frozendict[OfferBribery, PayToAttestState]
    votes: Sequence[Vote]


@dataclass
class ProposeBlock:
    slot: int
    entities: Sequence[str]
