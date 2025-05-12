// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {BLS} from "solady/src/utils/ext/ithaca/BLS.sol";
import {BLSVerify} from "./BLSVerify.sol";

contract PayToExit {
    uint256 public bribeAmount;
    mapping(uint256 => bool) public bribeTaken;

    BLSVerify public blsVerifyInstance;
    address public owner;

    modifier onlyOwner() {
        require(msg.sender == owner, "PayToExit: Caller is not the owner");
        _;
    }

    constructor(uint256 _initialBribeAmount) payable {
        require(_initialBribeAmount > 0, "PayToExit: Bribe amount must be positive");
        bribeAmount = _initialBribeAmount;

        blsVerifyInstance = new BLSVerify();
        owner = msg.sender;
    }

    function acceptBribe(
        uint256 validatorIndex,
        BLS.G1Point calldata pubkey,
        BLS.G2Point calldata signature,
        bytes memory message,
        bytes32[] calldata depositProof,
        bytes32 depositRoot
    ) external {
        require(address(this).balance >= bribeAmount, "PayToExit: Insufficient contract balance for this bribe.");
        require(!bribeTaken[validatorIndex], "PayToExit: Bribe already taken for this validator index.");

        bytes32 pubkeyHash = keccak256(abi.encodePacked(pubkey.x_a, pubkey.x_b, pubkey.x_a, pubkey.y_b));
        require(
            verifyDepositProof(pubkeyHash, validatorIndex, depositProof, depositRoot),
            "PayToExit: Invalid deposit proof."
        );

        require(blsVerifyInstance.verify(message, signature, pubkey), "PayToExit: Invalid BLS signature.");

        bribeTaken[validatorIndex] = true;

        (bool success,) = msg.sender.call{value: bribeAmount}("");
        if (!success) {
            bribeTaken[validatorIndex] = false;
            revert("PayToExit: Bribe payment transfer failed.");
        }
    }

    function verifyDepositProof(bytes32 leaf, uint256 index, bytes32[] calldata proof, bytes32 root)
        internal
        pure
        returns (bool)
    {
        bytes32 computedHash = leaf;
        for (uint256 i = 0; i < proof.length; i++) {
            bytes32 proofElement = proof[i];
            if ((index & 1) == 0) {
                computedHash = keccak256(abi.encodePacked(computedHash, proofElement));
            } else {
                computedHash = keccak256(abi.encodePacked(proofElement, computedHash));
            }
            index = index >> 1;
        }
        return computedHash == root;
    }

    function depositFunds() public payable onlyOwner {
        require(msg.value > 0, "PayToExit: Deposit amount must be greater than zero.");
    }

    function withdrawFunds(uint256 _amount) public onlyOwner {
        require(address(this).balance >= _amount, "PayToExit: Not enough funds to withdraw.");
        (bool success,) = owner.call{value: _amount}("");
        require(success, "PayToExit: Ether withdrawal failed.");
    }

    function updateBribeAmount(uint256 _newBribeAmount) public onlyOwner {
        require(_newBribeAmount > 0, "PayToExit: New bribe amount must be positive");
        bribeAmount = _newBribeAmount;
    }

    function epoch() public view returns (uint256) {
        return block.timestamp / 12 / 32;
    }
}
