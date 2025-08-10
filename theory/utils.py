from dataclasses import dataclass
import math

SLOTS_PER_EPOCH = 32
NUM_OF_VALIDATORS = 1_000_000  # must be divisable by SLOTS_PER_EPOCH
ATTESTATORS_PER_SLOT = NUM_OF_VALIDATORS // SLOTS_PER_EPOCH
PROPOSER_BOOST = 0.4 * ATTESTATORS_PER_SLOT
EFFECTIVE_BALANCE_INCREMENT = 1_000_000_000
BASE_REWARD_FACTOR = 64
B = EFFECTIVE_BALANCE_INCREMENT * BASE_REWARD_FACTOR // int(math.sqrt(NUM_OF_VALIDATORS))

@dataclass(frozen=True)
class Slot:
    num: int
    phase: int  # in {0, 1}

    def __add__(self, other: int) -> "Slot":
        numerical = 2 * self.num + self.phase + other
        return Slot(numerical // 2, numerical % 2)
