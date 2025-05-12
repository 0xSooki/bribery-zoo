// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {BLS} from "solady/src/utils/ext/ithaca/BLS.sol";
import {BLSVerify} from "./BLSVerify.sol";

contract PayToFork {
    uint256 public bribeAmount;
    mapping(bytes32 => bool) public bribePaidForTarget;

    BLSVerify public blsVerifyInstance;
    address public owner;

    struct TargetHeader {
        BLS.G1Point AggPubkey;
        bytes attestData;
        uint256 count;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "PayToFork: Caller is not the owner");
        _;
    }

    constructor(uint256 _initialBribeAmount) payable {
        require(_initialBribeAmount > 0, "PayToFork: Bribe amount must be positive");
        bribeAmount = _initialBribeAmount;
        blsVerifyInstance = new BLSVerify();
        owner = msg.sender;
    }

    function calcTargetHash(TargetHeader calldata _targetHeader) public pure returns (bytes32) {
        bytes32 attestDataHash = keccak256(_targetHeader.attestData);
        return keccak256(
            abi.encodePacked(
                _targetHeader.AggPubkey.x_a,
                _targetHeader.AggPubkey.x_b,
                _targetHeader.AggPubkey.y_a,
                _targetHeader.AggPubkey.y_b,
                attestDataHash,
                _targetHeader.count
            )
        );
    }

    function defineTargetHeader(TargetHeader calldata _targetHeader) public onlyOwner {
        require(_targetHeader.count > 0, "PayToFork: Validator count must be positive");
        bytes32 targetHash = calcTargetHash(_targetHeader);
        bribePaidForTarget[targetHash] = false;
    }

    function acceptBribe(BLS.G2Point calldata _signature, TargetHeader calldata _targetHeader) public {
        bytes32 targetHash = calcTargetHash(_targetHeader);
        require(!bribePaidForTarget[targetHash], "PayToFork: Bribe already paid for this target");
        require(
            blsVerifyInstance.verify(_targetHeader.attestData, _signature, _targetHeader.AggPubkey),
            "PayToFork: Invalid BLS signature"
        );
        uint256 totalBribeToPay = _targetHeader.count * bribeAmount;
        require(address(this).balance >= totalBribeToPay, "PayToFork: Insufficient contract balance for this bribe");
        bribePaidForTarget[targetHash] = true;
        (bool success,) = msg.sender.call{value: totalBribeToPay}("");
        if (!success) {
            bribePaidForTarget[targetHash] = false;
            revert("PayToFork: Bribe payment failed");
        }
    }

    function depositFunds() public payable onlyOwner {
        require(msg.value > 0, "PayToFork: Deposit amount must be greater than zero.");
    }

    function withdrawFunds(uint256 _amount) public onlyOwner {
        require(address(this).balance >= _amount, "PayToFork: Not enough funds to withdraw.");
        (bool success,) = owner.call{value: _amount}("");
        require(success, "PayToFork: Ether withdrawal failed.");
    }

    function updateBribeAmount(uint256 _newBribeAmount) public onlyOwner {
        require(_newBribeAmount > 0, "PayToFork: New bribe amount must be positive");
        bribeAmount = _newBribeAmount;
    }

    receive() external payable {}
}
