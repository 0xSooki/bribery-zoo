from dataclasses import dataclass
import math

SLOTS_PER_EPOCH = 32
NUM_OF_VALIDATORS = 1_000_000  # must be divisable by SLOTS_PER_EPOCH
ATTESTATORS_PER_SLOT = NUM_OF_VALIDATORS // SLOTS_PER_EPOCH
PROPOSER_BOOST = int(0.4 * ATTESTATORS_PER_SLOT)
EFFECTIVE_BALANCE_INCREMENT = 1_000_000_000
BASE_INCREMENT = 32
BASE_REWARD_FACTOR = 64
B = (
    EFFECTIVE_BALANCE_INCREMENT
    * BASE_REWARD_FACTOR
    // int(math.sqrt(BASE_INCREMENT * 1_000_000_000 * NUM_OF_VALIDATORS))
)
W_s = 14
W_t = 26
W_h = 14
W_y = 2
W_p = 8
W_sum = 64

W_DICT = {
    "W_s": W_s,
    "W_t": W_t,
    "W_h": W_h,
    "W_y": W_y,
    "W_p": W_p,
    "W_sum": W_sum,
}

REWARD_MATRIX = [
    [
        {"W_s": -1, "W_t": -1},
        {"W_s": -1, "W_t": -1},
        {"W_s": -1, "W_t": -1},
        {"W_s": -1, "W_t": -1},
    ],
    [
        {"W_s": 1, "W_t": -1},
        {"W_s": 1, "W_t": -1},
        {"W_s": -1, "W_t": -1},
        {"W_s": -1, "W_t": -1},
    ],
    [
        {"W_s": 1, "W_t": 1},
        {"W_s": 1, "W_t": 1},
        {"W_s": -1, "W_t": 1},
        {"W_s": -1, "W_t": -1},
    ],
    [
        {"W_s": 1, "W_t": 1, "W_h": 1},
        {"W_s": 1, "W_t": 1},
        {"W_s": -1, "W_t": 1},
        {"W_s": -1, "W_t": -1},
    ],
]


def attestation_base_reward(
    timeliness: int, common: dict[str, float], slot_distance: int
) -> tuple[float, float]:
    """
    Arguments:
        - timeliness (int)
            0 -> Wrong source
            1 -> Correct source only
            2 -> Correct source and target only
            3 -> Correct source, target and head
        - common (dict[str, float])
            - relative amount of validators that agree on the specific attribute (source, target, head)
            - e.g. {"W_s": 1.0, "W_t": 0.95, "W_h": 0.7}
        - slot_distance (int): time of vote (e.g. 1 slot before its included in a block)
    """
    assert slot_distance > 0, f"{slot_distance=}"

    if slot_distance == 1:
        idx = 0
    elif slot_distance <= 5:
        idx = 1
    elif slot_distance <= 32:
        idx = 2
    else:
        idx = 3

    data = REWARD_MATRIX[timeliness][idx]
    return (
        sum(val * W_DICT[attr] * common[attr] for attr, val in data.items() if val >= 0)
        / W_sum,
        sum(val * W_DICT[attr] for attr, val in data.items() if val < 0) / W_sum,
    )


@dataclass(frozen=True)
class Slot:
    num: int
    phase: int  # in {0, 1}

    def __add__(self, other: int) -> "Slot":
        numerical = 2 * self.num + self.phase + other
        return Slot(numerical // 2, numerical % 2)

    def __le__(self, other: "Slot") -> bool:
        if self.num == other.num:
            return self.phase <= other.phase
        return self.num < other.num

    def __lt__(self, other: "Slot") -> bool:
        if self.num == other.num:
            return self.phase < other.phase
        return self.num < other.num
