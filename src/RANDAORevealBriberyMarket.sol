// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {BLS} from "solady/src/utils/ext/ithaca/BLS.sol";

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

    BLS.G1Point NEG_G1_GENERATOR = BLS.G1Point(
        bytes32(uint256(31827880280837800241567138048534752271)),
        bytes32(uint256(88385725958748408079899006800036250932223001591707578097800747617502997169851)),
        bytes32(uint256(22997279242622214937712647648895181298)),
        bytes32(uint256(46816884707101390882112958134453447585552332943769894357249934112654335001290))
    );

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
    function revealRANDAO(uint256 epochNumber, bytes32 randaoReveal, uint256[4] memory pubKey) public {}

    // This function must be called by market participants offering their bribes
    // The boolean function argument this funtcion needs is an indication of the bribing strategy
    // In this case the strategy space is just binary: publish or withhold the block
    function offerBribe(uint256 epochNumber, bool publishBlock) public payable {
        allOfferedBribes[epochNumber][publishBlock] = bribe({briber: msg.sender, value: msg.value});
        balances[msg.sender] += msg.value;
    }

    // This function must be called in Slot 30 of the given epoch
    function preCheck(uint256 _epochNumber) public {
        whatHappened[_epochNumber] =
            epochState({epochNumber: _epochNumber, randaoRevealEpoch30: block.prevrandao, publishedBlock31: false});
    }

    // This function must be called in Slot 1 of the next epoch after the bribe happened
    function postCheck(uint256 _epochNumber) public {
        if (block.prevrandao - uint256(RANDAOReveals[_epochNumber]) == whatHappened[_epochNumber].randaoRevealEpoch30) {
            whatHappened[_epochNumber].publishedBlock31 = true;
        }
    }

    // There should be also functions that allow the validator to claim the bribes and similarly another function that allows
    // validators whose bribe was not claimed by the manipulating validator to withdraw their money from the contract if they want
    // This is left as an exercise for the reader. :)
}
