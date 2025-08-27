from collections import defaultdict
from dataclasses import dataclass
from itertools import product
from numbers import Real

from frozendict import frozendict

from simulation.theory.action import WalletState
from simulation.theory.engine import Engine
from simulation.theory.strategy.adversary import AdvParams, AdvStrategy
from simulation.theory.strategy.base import (
    IAdvStrategy,
    IBribeeStrategy,
    IByzantineStrategy,
    IHonestStrategy,
    IStrategy,
    Params,
)
from simulation.theory.strategy.bribee import BribeeParams, BribeeStrategy
from simulation.theory.strategy.honest import HonestStrategy
from simulation.theory.utils import ATTESTATORS_PER_SLOT, B, BASE_INCREMENT


@dataclass
class GameReport:
    wallet_state: WalletState
    slot_to_canonical: dict[int, str]
    entity_to_blocks: dict[int, int]
    success: bool


def extract_end_info(engine: Engine, honest_entity: str) -> GameReport:
    head = engine.head(honest_entity)
    _slot = head
    canonicals_slots: list[int] = []
    while _slot in engine.blocks:
        canonicals_slots.append(_slot)
        _slot = engine.blocks[_slot].parent_slot
    slot_to_canonical: dict[int, str] = {
        slot: "C" if slot in canonicals_slots else "N" for slot in engine.blocks
    }
    entity_to_blocks: dict[str, int] = defaultdict(int)
    success = True
    for slot, canonical in slot_to_canonical.items():
        if slot in engine.slot_to_owner:
            if (engine.slot_to_owner[slot] == honest_entity) == (canonical == "C"):
                success = False
            if canonical == "C":
                entity_to_blocks[engine.slot_to_owner[slot]] += 1
    return GameReport(
        engine.blocks[head].wallet_state, slot_to_canonical, entity_to_blocks, success
    )


@dataclass
class Game:
    base_slot: int
    chain_string: str

    base_reward_unit: Real
    deadline_reward_unit: Real
    deadline_payback_unit: Real

    honest_entity: str
    adv_entity: str
    bribee_entities: set[str]

    entity_to_voting_power: dict[str, int]

    def honest_player(self) -> IHonestStrategy:
        return HonestStrategy(
            all_entities=self.bribee_entities.union(
                (self.adv_entity, self.honest_entity)
            ),
            base_slot=self.base_slot,
            chain_string=self.chain_string,
            entity=self.honest_entity,
        )

    def adv_player(self, params: AdvParams) -> IAdvStrategy:
        return AdvStrategy(
            censor_from_slot=params.censor_from_slot,
            base_reward_unit=self.base_reward_unit,
            deadline_reward_unit=self.deadline_reward_unit,
            deadline_payback_unit=self.deadline_payback_unit,
            patient=params.patient,
            break_bad_slot=params.break_bad_slot,
            base_slot=self.base_slot,
            chain_string=self.chain_string,
            entity=self.adv_entity,
            honest_entity=self.honest_entity,
            bribee_entities=self.bribee_entities,
        )

    def bribee_player(self, name: str, params: BribeeParams) -> IBribeeStrategy:
        return BribeeStrategy(
            break_bad_slot=params.break_bad_slot,
            censoring_from_slot=params.censoring_from_slot,
            send_votes_when_able=params.send_votes_when_able,
            last_minute=params.last_minute,
            finish_offers_regardless_of_abort=params.finish_offers_regardless_of_abort,
            only_sending_to_deadline_proposing_entity=params.only_sending_to_deadline_proposing_entity,
            base_slot=self.base_slot,
            chain_string=self.chain_string,
            entitiy=name,
            honest_entity=self.honest_entity,
            adv_entity=self.adv_entity,
            bribee_entities=self.bribee_entities,
        )

    def make_engine(self) -> Engine:
        return Engine.make_engine(
            chain_string=self.chain_string,
            entity_to_voting_power=self.entity_to_voting_power,
        )

    def play(
        self, adv_params: AdvParams, bribee_to_params: dict[str, BribeeParams]
    ) -> Engine:
        honest = self.honest_player()
        adversary = self.adv_player(adv_params)
        bribees = {
            name: self.bribee_player(name, params)
            for name, params in bribee_to_params.items()
        }

        players: dict[str, IStrategy] = {
            self.honest_entity: honest,
            self.adv_entity: adversary,
            **bribees,
        }
        byzantine_players: list[IByzantineStrategy] = [adversary, *bribees.values()]

        engine = self.make_engine()

        for proposer in self.chain_string:
            engine = players[proposer].build(engine)

            for byzantine in byzantine_players:
                engine = byzantine.adjust_strategy(engine)

            engine = adversary.offer_bribe(engine)

            engine = engine.slot_progress()

            for entity in players.values():
                engine = entity.vote(engine)

            for bribee in bribees.values():
                engine = bribee.take_bribe(engine)

            for byzantine in byzantine_players:
                engine = byzantine.send_others_votes(engine)

            for byzantine in byzantine_players:
                engine = byzantine.withheld_blocks(engine)

            for byzantine in byzantine_players:
                engine = byzantine.adjust_strategy(engine)

            engine = engine.slot_progress()
        return honest.build(engine)  # final transactions

    def all_adv_strategies(self) -> list[AdvParams]:
        result: list[AdvParams] = []
        for abort_slot in [None] + list(
            range(self.base_slot, self.base_slot + 1 + len(self.chain_string))
        ):
            for patient in [True, False]:
                result.append(
                    AdvParams(
                        censor_from_slot=None,
                        patient=patient,
                        break_bad_slot=abort_slot,
                    )
                )
                for censor_slot, owner in enumerate(
                    self.chain_string, start=self.base_slot + 1
                ):
                    if owner != self.adv_entity:
                        continue
                    result.append(
                        AdvParams(
                            censor_from_slot=censor_slot,
                            patient=patient,
                            break_bad_slot=abort_slot,
                        )
                    )
        return result

    def all_bribee_strategies(self, entity: str) -> list[BribeeParams]:
        result: list[BribeeParams] = []
        for censoring_slots, owner in [(None, entity)] + list(
            enumerate(self.chain_string, start=self.base_slot + 1)
        ):
            if owner != entity:
                continue
            for break_bad_slot in [None] + list(
                range(self.base_slot, self.base_slot + 1 + len(self.chain_string))
            ):
                for send_votes in [False, True]:
                    for level in range(3):
                        for finish_offer in [False, True]:
                            result.append(
                                BribeeParams(
                                    break_bad_slot=break_bad_slot,
                                    censoring_from_slot=censoring_slots,
                                    send_votes_when_able=send_votes,
                                    last_minute=level >= 1,
                                    only_sending_to_deadline_proposing_entity=level
                                    == 2,
                                    finish_offers_regardless_of_abort=finish_offer,
                                )
                            )
        return result

    def compute_table(
        self,
    ) -> dict[tuple[AdvParams, tuple[BribeeParams, ...]], GameReport]:
        adv_params = self.all_adv_strategies()
        all_bribee_params = [
            self.all_bribee_strategies(bribee) for bribee in self.bribee_entities
        ]

        result: dict[tuple[AdvParams, tuple[BribeeParams, ...]], GameReport] = {}
        bribee_params = list(product(*all_bribee_params))
        for adv_param in adv_params:

            for bribee_settings in bribee_params:
                # print((adv_param, bribee_settings))
                engine = self.play(
                    adv_params=adv_param,
                    bribee_to_params={
                        bribee: settings
                        for bribee, settings in zip(
                            self.bribee_entities, bribee_settings
                        )
                    },
                )
                result[(adv_param, bribee_settings)] = extract_end_info(
                    engine, self.honest_entity
                )

        return result

    def convert_table(
        self,
        block_reward: int,
        success_reward: int,
        table: dict[tuple[AdvParams, tuple[BribeeParams, ...]], GameReport],
    ) -> dict[tuple[AdvParams, tuple[BribeeParams, ...]], dict[str, int]]:
        all_entities = self.bribee_entities.union((self.adv_entity, self.honest_entity))
        return {
            params: {
                entity: report.wallet_state.address_to_money.get(entity, 0)
                + report.entity_to_blocks.get(entity, 0) * block_reward
                + bool(report.success and entity == self.adv_entity) * success_reward
                for entity in all_entities
            }
            for params, report in table.items()
        }

    def nash_equillibria(
        self, table: dict[tuple[AdvParams, tuple[BribeeParams, ...]], dict[str, int]]
    ) -> list[tuple[dict[str, Params], dict[str, int]]]:
        adv_params = self.all_adv_strategies()
        all_bribee_params = {
            bribee: self.all_bribee_strategies(bribee)
            for bribee in self.bribee_entities
        }
        all_params: dict[str, list[Params]] = {
            self.adv_entity: adv_params,
            **all_bribee_params,
        }
        bribee_to_index = {b: i for i, b in enumerate(self.bribee_entities)}
        
        def value(params: dict[str, Params], entity: str) -> int:
            adv_param: AdvParams = None
            bribee_params: list[Params] = [None] * len(self.bribee_entities)
            for player, param in params.items():
                if player == self.adv_entity:
                    adv_param = param
                else:
                    bribee_params[bribee_to_index[player]] = param
            assert adv_param is not None
            assert not any(param is None for param in bribee_params)
            return table[(adv_param, tuple(bribee_params))][entity]

        players = list(all_params.keys())
        equilibria: list[tuple[dict[str, Params], dict[str, int]]] = []


        # Cartesian product of all strategies for all players
        for strategies in product(*(all_params[p] for p in players)):
            profile = {p: s for p, s in zip(players, strategies)}


            is_equilibrium = True
            for player in players:
                current_payoff = value(profile, player)
                # Check deviations for this player
                for alt_strategy in all_params[player]:
                    if alt_strategy == profile[player]:
                        continue

                    deviated_profile = profile.copy()
                    deviated_profile[player] = alt_strategy
                    alt_payoff = value(deviated_profile, player)


                    if alt_payoff > current_payoff:
                        is_equilibrium = False
                        break
            


                if not is_equilibrium:
                    break


            if is_equilibrium:
                equilibria.append((profile, {entity: value(profile, entity) for entity in players}))


        return equilibria

def pretty_print(eq: tuple[dict[str, Params], dict[str, int]]):
    for entity, params in eq[0].items():
        print(f"{entity}:")
        for attr, value in params.__dict__.items():
            print(f"    {attr}={value}")
        print()
    print("============")
    for entity, reward in eq[1].items():
        print(f"{entity} => {reward:_}")

def main():
    alpha = int(0.15 * ATTESTATORS_PER_SLOT)
    beta = int(0.06 * ATTESTATORS_PER_SLOT)
    honest = ATTESTATORS_PER_SLOT - alpha - beta

    game = Game(
        base_slot=0,
        chain_string="AHA",
        base_reward_unit=int(B * BASE_INCREMENT * 0.3),
        deadline_reward_unit=0, #B,
        deadline_payback_unit=0, #B,
        honest_entity="H",
        adv_entity="A",
        bribee_entities={"B"},
        entity_to_voting_power={"H": honest, "A": alpha, "B": beta},
    )
    best_adv = AdvParams(censor_from_slot=None, patient=True, break_bad_slot=0)
    best_bribee = BribeeParams(break_bad_slot=0, censoring_from_slot=None, send_votes_when_able=False, finish_offers_regardless_of_abort=False, last_minute=False, only_sending_to_deadline_proposing_entity=False)

    single = False
    if single:
        engine = game.play(best_adv, {"B": best_bribee})
        info = extract_end_info(engine, "H")
        print(info.success)
        print(info.wallet_state.address_to_money)
    else:
        raw_table = game.compute_table()
        
        
        table = game.convert_table(50_000_000, 50_000_000, raw_table)
        #print(table[(best_adv, (best_bribee,))])
        #exit()
        nash = game.nash_equillibria(table)
        print(len(nash))
        pretty_print(max(nash, key=lambda x: x[1]["B"]))
    


if __name__ == "__main__":
    main()
