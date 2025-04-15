// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

// briber inputs

contract PayToExit {
    uint256 bribeAmount;

    constructor(uint256 _bribeAmount) payable {
        bribeAmount = _bribeAmount;
    }

    mapping(uint256 => bool) bribeTaken;

    function takeBribe(address addr, uint256 validatorIndex) public {
        require(address(this).balance > bribeAmount, "Bribe should be ...");
        // require has not validatorindex takenn bribe before
        // require epoch e < current, current should be compute block.timestamp
        // ecdsa signature for pk_i on epooch e number and the validator_index i is valid
        // validators pubkey is in the withdrawal credential

        // given deposit root hash and merkle tree proof, its valid for
        // pk_i lies at index i
        // payout bribe to addr

        bribeTaken[validatorIndex] = true;
    }

    function epoch() public view returns (uint256) {
        bytes32 input;
        bytes32 epochNumber;
        assembly {
            let memPtr := mload(0x40)
            if iszero(staticcall(not(0), 0xfb, input, 32, memPtr, 32)) { invalid() }
            epochNumber := mload(memPtr)
        }
        return uint256(epochNumber);
    }

    // convenience functions, replenish pool if ran out
    // kill contract, redeem remaning money
}
