// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

contract RANDAORevealBriberyMarket {
    // Let's first just handle the case for a single tail slot
    // Future work should deal with the case when the validator offers bribes for k consecutive tail slots

    struct bribe {
        address briber; // The party offering the bribe for the validator
        uint256 value; // The value of the bribe offered to the validator (in wei)
    }
    /*
        Let's just consider the case when the amount of the bribe is transparent.
        Put differently, there is no sealed-bid auction at this point to keep things simple. 
        The first mapping has a key value uint256 denoting the epoch number, which the market takes place.
        The second mapping has a boolean key value indicating for/against (0/1 or withhold/publish the tail block)
        The value of the second mapping is the offered bribe
    */
    mapping(uint256 => mapping(bool => bribe)) allOfferedBribes;

    // Let's keep track of each user balances
    mapping(address => uint256) balances;

    // We gotta also store the RANDAO reveals (maybe later it is enough for efficiency reasons to store it only in CALLDATA?)
    // The epoch number is mapped to a valid RANDAO reveal (recall now, we only consider a single tail slot)
    mapping(uint256 => bytes32) RANDAOReveals;

    struct epochState {
        uint256 epochNumber;
        uint256 randaoRevealEpoch30;
        bool publishedBlock31;
    }

    // This mapping stores what happened on the canonical chain, i.e., the validator published or not published a block
    mapping(uint256 => epochState) whatHappened;

    // The corrupt validator reveals prematurely its RANDAO reveal in epochNumber
    // This EIP should help in implementing the BLS verification logic: https://github.com/ethereum/EIPs/blob/master/EIPS/eip-2537.md
    function revealRANDAO(
        uint256 epochNumber,
        bytes32 randaoReveal,
        uint256[4] memory pubKey
    ) public {
        // We need to verify the BLS signature (the RandaoReveal is a BLS signature on the epoch number)
        require(true);
        RANDAOReveals[epochNumber] = randaoReveal;
        // maybe we could/should emit an event here?

        bytes memory mIn = abi.encodePacked(uint256(0), randaoReveal); // 64 bytes: 32 zeros || 32-byte message
        (bool success, bytes memory hOut) = address(0x10).staticcall(mIn);
        require(success && hOut.length == 128, "Hash mapping failed");
    }

    function convertPublicKeyToG1(
        bytes memory pubKey
    ) public view returns (bytes memory) {
        require(pubKey.length == 48, "pubKey must be exactly 48 bytes");
        bytes memory input = new bytes(64);

        for (uint256 i = 0; i < 48; i++) {
            input[i + 16] = pubKey[i];
        }

        (bool success, bytes memory g1Point) = address(0x10).staticcall(input);
        require(success && g1Point.length == 128, "Mapping to G1 failed");
        return g1Point;
    }

    // This function must be called by market participants offering their bribes
    // The boolean function argument this funtcion needs is an indication of the bribing strategy
    // In this case the strategy space is just binary: publish or withhold the block
    function offerBribe(uint256 epochNumber, bool publishBlock) public payable {
        allOfferedBribes[epochNumber][publishBlock] = bribe({
            briber: msg.sender,
            value: msg.value
        });
        balances[msg.sender] += msg.value;
    }

    // This function must be called in Slot 30 of the given epoch
    function preCheck(uint256 _epochNumber) public {
        whatHappened[_epochNumber] = epochState({
            epochNumber: _epochNumber,
            randaoRevealEpoch30: block.prevrandao,
            publishedBlock31: false
        });
    }

    // This function must be called in Slot 1 of the next epoch after the bribe happened
    function postCheck(uint256 _epochNumber) public {
        if (
            block.prevrandao - uint256(RANDAOReveals[_epochNumber]) ==
            whatHappened[_epochNumber].randaoRevealEpoch30
        ) {
            whatHappened[_epochNumber].publishedBlock31 = true;
        }
    }

    // There should be also functions that allow the validator to claim the bribes and similarly another function that allows
    // validators whose bribe was not claimed by the manipulating validator to withdraw their money from the contract if they want
    // This is left as an exercise for the reader. :)
}
