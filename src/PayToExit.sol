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
        bytes32 depositRoot,
        uint64 deposit_count
    ) external {
        require(address(this).balance >= bribeAmount, "PayToExit: Insufficient contract balance for this bribe.");
        require(!bribeTaken[validatorIndex], "PayToExit: Bribe already taken for this validator index.");

        bytes32 pubkeyHash = keccak256(abi.encodePacked(pubkey.x_a, pubkey.x_b, pubkey.x_a, pubkey.y_b));
        require(
            verifyDepositProof(deposit_count, pubkeyHash, validatorIndex, depositProof, depositRoot),
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

    function verifyDepositProof(
        uint64 deposit_count,
        bytes32 leaf,
        uint256 index,
        bytes32[] calldata proof,
        bytes32 root
    ) internal pure returns (bool) {
        bytes32 node = leaf;
        for (uint256 i = 0; i < proof.length; i++) {
            bytes32 proofElement = proof[i];
            if ((index & 1) == 0) {
                node = sha256(abi.encodePacked(node, proofElement));
            } else {
                node = sha256(abi.encodePacked(proofElement, node));
            }
            index = index >> 1;
        }

        bytes32 result = sha256(abi.encodePacked(node, to_little_endian_64(deposit_count), bytes24(0)));
        return result == root;
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

    function to_little_endian_64(uint64 value) internal pure returns (bytes memory ret) {
        ret = new bytes(8);
        bytes8 bytesValue = bytes8(value);
        ret[0] = bytesValue[7];
        ret[1] = bytesValue[6];
        ret[2] = bytesValue[5];
        ret[3] = bytesValue[4];
        ret[4] = bytesValue[3];
        ret[5] = bytesValue[2];
        ret[6] = bytesValue[1];
        ret[7] = bytesValue[0];
    }
}
