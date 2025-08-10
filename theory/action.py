from dataclasses import dataclass
from typing import Sequence


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
        - votes_needed: usually all the voting power of the bribed entity
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
        - base_reward: Amount payed to entity in case of takeBribery, regardless of deadline(s)
        - deadline_reward: Amount payed if all verifications were done before the deadline(s)
        - entity: Bribed entity
        - briber: Entity paying/offering the bribe
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
    briber: str
    slot_anchor: int | None


@dataclass
class VerifyOneAttestation(BribeeAction):
    reference: OfferBribery
    vote: Vote  # one can construct a vote from the message
    index: int


@dataclass(frozen=True)
class SinglePayToAttestState:
    original: OfferBribery
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
class ProposeBlock(AdvAction, BribeeAction):  # phase 0
    slot: int
    parent_slot: int
    pay_to_attests: Sequence[OfferBribery]  # can be empty
    claims: Sequence[VerifyOneAttestation]
