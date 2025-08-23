Slot structure of game steps:
1. E: block building (can censor: takeBribe)
2. E: sending out (optional)
3. A: send offerBribe
4. E: Voting
5. B: send takeBribe with votes
6. A/B: send votes of Bribee when building (automatic, B would not takeBribe)
7. A/B: send withheld blocks

Adv: tries to fork by bribing every bribee entity
    Will not tolerate cases where projected declining is present. The following 2 scenarios are possible for assumptions in case of no voting:
        - assuming the not voting bribee will eventually accept the bribery
        - assuming the not voting bribee will vote against the adversary
    Based on the projectories of the assumptions, if the attack is not feasible, the attack is aborted:
        - not building on the losing branch
        - stop making offerBribe calls
    Additionally there are mock adv strategies that aborts the attack. All these before any damages of blocks can be made i.e. orphaned/missed blocks. The mock strategies include the honest one. For ex ante reorgs we abort IN THE SECRET BRANCH, while for ex post, the attacker either stops making offers during the honest branch or builds on it (without sacrificing blocks). The mock strategies should ensure that even if the adversary posts offerBribe tx's for fun, making them is still profitable (for bribees)!

Bribee:
    We add the honest (alturistic) bribee alongside 2 main categories of rational bribee strategies:
        - Secretly accepting the bribe, withholding votes until deadline
        - Accepting and voting regularly
    In case of abort from the adversary, they start behave honestly. They can also themselves start declining the voting at any moment, releasing withheld votes to the honest branch.



