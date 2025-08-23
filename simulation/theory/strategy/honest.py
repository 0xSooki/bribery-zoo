from dataclasses import dataclass
from typing import Collection
from simulation.theory.action import Vote
from simulation.theory.engine import Engine
from simulation.theory.strategy.base import IHonestStrategy


@dataclass
class HonestStrategy(IHonestStrategy):
    all_entities: Collection[str]
    chain_string: str
    entity: str = "H"

    def build(self, engine: Engine) -> Engine:
        head = engine.head(self.entity)
        return engine.build_block(
            slot=engine.slot.num,
            parent_slot=head,
            knowledge=self.all_entities,
            entity=self.entity,
            final=engine.slot.num > len(self.chain_string),
        )

    def vote(self, engine: Engine) -> Engine:
        head = engine.head(self.entity)
        return engine.add_votes(
            (
                Vote(
                    entity=self.entity,
                    from_slot=engine.slot.num,
                    min_index=0,
                    max_index=engine.entity_to_voting_power[self.entity],
                    to_slot=head,
                ),
            )
        )