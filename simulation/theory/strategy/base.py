from abc import ABC, abstractmethod

from simulation.theory.engine import Engine


class IHonestStrategy(ABC):
    @abstractmethod
    def build(self, engine: Engine) -> Engine: ...

    @abstractmethod
    def vote(self, engine: Engine) -> Engine: ...


class IAdvStrategy(ABC):
    @abstractmethod
    def build(self, engine: Engine) -> Engine: ...

    @abstractmethod
    def offer_bribe(self, engine: Engine) -> Engine: ...

    @abstractmethod
    def vote(self, engine: Engine) -> Engine: ...

    @abstractmethod
    def send_others_votes(self, engine: Engine) -> Engine: ...

    @abstractmethod
    def withheld_blocks(self, engine: Engine) -> Engine: ...

    @abstractmethod
    def adjust_strategy(self, engine: Engine) -> Engine: ...


class IBribee(ABC):
    @abstractmethod
    def build(self, engine: Engine) -> Engine: ...

    @abstractmethod
    def vote(self, engine: Engine) -> Engine: ...

    @abstractmethod
    def take_bribe(self, engine: Engine) -> Engine: ...

    @abstractmethod
    def send_others_votes(self, engine: Engine) -> Engine: ...

    @abstractmethod
    def withheld_blocks(self, engine: Engine) -> Engine: ...


def plan(
    base_slot: int, chain_string: str, honest_entity: str
) -> tuple[dict[int, int], frozenset[int], frozenset[int]]:
    """
    Returns (plan_voting, included, excluded) tuple, where:
        - plan_voting[slot] means the correct head to vote for at slot
        - included: slots that must be in the branch according to the forking plan
        - excluded: slots that must not be in the branch according to the forking plan
    """
    plan_voting: dict[int, int] = {}
    nonbase_planned_branch = [
        slot
        for slot, chain_chr in enumerate(chain_string, start=base_slot + 1)
        if chain_chr != honest_entity
    ]
    planned_branch = [base_slot] + nonbase_planned_branch
    slot = base_slot + len(chain_string)
    slot_to_vote_idx = slot - 1
    while slot >= base_slot:
        while slot_to_vote_idx > 0 and planned_branch[slot_to_vote_idx] > slot:
            slot_to_vote_idx -= 1
        plan_voting[slot] = planned_branch[slot_to_vote_idx]
        slot -= 1

    included = frozenset(nonbase_planned_branch)
    excluded = (
        frozenset(range(base_slot + 1, base_slot + 1 + len(chain_string))) - included
    )

    return plan_voting, included, excluded


def chain_string_extract(
    base_slot: int, chain_string: str, honest_entity: str
) -> tuple[int, int]:
    before = True
    first_H = True
    last_H: int | None = None  # Slot(base_slot - 1, 1)
    last_E: int = base_slot
    for slot, chr in enumerate(chain_string, start=base_slot + 1):
        if chr == honest_entity:
            before = False
            if first_H:
                last_H = slot
        else:
            if before:
                last_E = slot
            else:
                first_H = False

    assert last_H is not None
    return last_E, last_H