from abc import ABC, abstractmethod

from simulation.theory.engine import Engine


class Params:
    pass


class IStrategy(ABC):
    @abstractmethod
    def build(self, engine: Engine) -> Engine: ...

    @abstractmethod
    def vote(self, engine: Engine) -> Engine: ...


class IHonestStrategy(IStrategy):
    pass


class IByzantineStrategy(IStrategy):
    base_slot: int
    chain_string: str
    honest_entity: str

    last_H: int
    last_E: int

    plan_correct_votes: dict[int, int]
    bad_votes: dict[int, int]
    included: frozenset[int]
    excluded: frozenset[int]

    @abstractmethod
    def send_others_votes(self, engine: Engine) -> Engine: ...

    @abstractmethod
    def withheld_blocks(self, engine: Engine) -> Engine: ...

    @abstractmethod
    def adjust_strategy(self, engine: Engine) -> Engine: ...

    def structural_anomaly(self, engine: Engine) -> bool:
        if engine.slot.num < self.last_H and any(
            engine.slot_to_owner[slot] != self.honest_entity
            and slot in engine.knowledge_of_blocks[self.honest_entity]
            for slot in range(self.base_slot + 1, self.last_H)
        ):
            return True

        for slot in range(self.base_slot + 1, engine.slot.num + 1):
            if slot in self.included:
                correct = self.plan_correct_votes[slot - 1]
            elif slot in self.excluded:
                correct = self.bad_votes[slot - 1]
            else:
                raise ValueError(
                    f"{slot=} must be in {self.included=} {self.excluded=}"
                )

            if correct != engine.blocks[slot].parent_slot:
                return True
        return False

    def setup_plan(self) -> None:
        """
        Sets up the following values:
            - plan_voting[slot] means the correct head to vote for at slot
            - bad_voting[slot] means whats the honest entity should vote for. Used for structural anomalies
            - included: slots that must be in the branch according to the forking plan
            - excluded: slots that must not be in the branch according to the forking plan
            - last_H: last honest slot
            - last_E: last secret slot in case of ex ante, for ex post it is base_slot
        """
        self.plan_correct_votes: dict[int, int] = {}
        self.bad_votes: dict[int, int] = {}
        nonbase_planned_branch = [
            slot
            for slot, chain_chr in enumerate(
                self.chain_string, start=self.base_slot + 1
            )
            if chain_chr != self.honest_entity
        ]
        self.included = frozenset(nonbase_planned_branch)
        self.excluded = (
            frozenset(
                range(self.base_slot + 1, self.base_slot + 1 + len(self.chain_string))
            )
            - self.included
        )
        planned_branch = [self.base_slot] + sorted(self.included)
        bad_branch = [self.base_slot] + sorted(self.excluded)

        slot = self.base_slot + len(self.chain_string)
        slot_to_vote_idx = len(planned_branch) - 1
        while slot >= self.base_slot:
            while slot_to_vote_idx > 0 and planned_branch[slot_to_vote_idx] > slot:
                slot_to_vote_idx -= 1
            self.plan_correct_votes[slot] = planned_branch[slot_to_vote_idx]
            slot -= 1

        slot = self.base_slot + len(self.chain_string)
        slot_to_vote_idx = len(bad_branch) - 1
        while slot >= self.base_slot:
            while slot_to_vote_idx > 0 and bad_branch[slot_to_vote_idx] > slot:
                slot_to_vote_idx -= 1
            self.bad_votes[slot] = bad_branch[slot_to_vote_idx]
            slot -= 1

        before = True
        first_H = True
        self.last_H = None  # Slot(base_slot - 1, 1)
        self.last_E = self.base_slot
        for slot, chr in enumerate(self.chain_string, start=self.base_slot + 1):
            if chr == self.honest_entity:
                before = False
                if first_H:
                    self.last_H = slot
            else:
                if before:
                    self.last_E = slot
                else:
                    first_H = False

        assert self.last_H is not None


class IAdvStrategy(IByzantineStrategy):
    @abstractmethod
    def offer_bribe(self, engine: Engine) -> Engine: ...


class IBribeeStrategy(IByzantineStrategy):
    @abstractmethod
    def take_bribe(self, engine: Engine) -> Engine: ...
