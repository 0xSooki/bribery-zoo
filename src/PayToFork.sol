// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {BLS} from "solady/src/utils/ext/ithaca/BLS.sol";
import {BLSVerify} from "./BLSVerify.sol";

contract PayToFork {
    address public owner;
    BLSVerify public blsVerifyInstance;

    struct TargetHeader {
        BLS.G1Point AggPubkey;
        bytes attestData;
    }

    TargetHeader public targetHeader;
    bool public isTargetSet;
    uint256 public bribeAmount;

    mapping(address => uint256) public payout;

    bool public forkSuccessful;

    modifier onlyOwner() {
        require(msg.sender == owner, "PayToFork: Caller is not the owner");
        _;
    }

    constructor() payable {
        owner = msg.sender;
        blsVerifyInstance = new BLSVerify();
    }

    function calcTargetHash(TargetHeader memory _targetHeader) public pure returns (bytes32) {
        bytes32 attestDataHash = keccak256(_targetHeader.attestData);
        return keccak256(
            abi.encodePacked(
                _targetHeader.AggPubkey.x_a,
                _targetHeader.AggPubkey.x_b,
                _targetHeader.AggPubkey.y_a,
                _targetHeader.AggPubkey.y_b,
                attestDataHash
            )
        );
    }

    function defineTargetHeader(TargetHeader calldata _targetHeader, uint256 _bribeAmount) public onlyOwner {
        require(_bribeAmount > 0, "PayToFork: Bribe amount must be positive");

        targetHeader = _targetHeader;
        bribeAmount = _bribeAmount;
        isTargetSet = true;
        forkSuccessful = false;
    }

    function takeBribe(BLS.G2Point calldata _signature) public {
        require(isTargetSet, "PayToFork: Active target not set");

        TargetHeader memory currentHeader = targetHeader;

        require(!(payout[msg.sender] > 0), "PayToFork: Already claimed for this target");

        require(
            blsVerifyInstance.verify(currentHeader.attestData, _signature, currentHeader.AggPubkey),
            "PayToFork: Invalid BLS signature"
        );

        payout[msg.sender] = bribeAmount;
    }

    function declareForkSuccess() public onlyOwner {
        require(isTargetSet, "PayToFork: Active target not set");
        forkSuccessful = true;
    }

    function withdrawPayout() public {
        require(forkSuccessful, "PayToFork: Fork not declared successful yet");
        uint256 amount = payout[msg.sender];
        require(amount > 0, "PayToFork: No payout available for you");
        require(address(this).balance >= amount, "PayToFork: Insufficient contract balance for payout");

        payout[msg.sender] = 0;
        (bool success,) = msg.sender.call{value: amount}("");
        if (!success) {
            payout[msg.sender] = amount;
            revert("PayToFork: Payout transfer failed");
        }
    }

    function updateBribeAmount(uint256 _newBribeAmount) public onlyOwner {
        require(_newBribeAmount > 0, "PayToFork: Bribe amount must be positive");
        bribeAmount = _newBribeAmount;
    }

    function depositFunds() public payable onlyOwner {
        require(msg.value > 0, "PayToFork: Deposit amount must be greater than zero.");
    }

    function withdrawFunds(uint256 _amount) public onlyOwner {
        require(address(this).balance >= _amount, "PayToFork: Not enough funds to withdraw.");
        (bool success,) = owner.call{value: _amount}("");
        require(success, "PayToFork: Ether withdrawal failed.");
    }

    receive() external payable {}
}
