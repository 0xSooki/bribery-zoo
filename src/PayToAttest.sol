// SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.13;

import {BLSVerify} from "./BLSVerify.sol";
import {BLS} from "solady/src/utils/ext/ithaca/BLS.sol";
import {MerkleTreeLib} from "solady/src/utils/MerkleTreeLib.sol";
import {Utils} from "./Utils.sol";

contract PayToAttest {
    using Utils for *;

    struct Checkpoint {
        uint256 epoch;
        bytes32 root;
    }

    struct AttestationData {
        uint256 slot;
        bytes32 beacon_block_root;
        Checkpoint source;
        Checkpoint target;
    }

    struct Auction {
        uint256 auctionDeadline;
        BLS.G1Point aggPubkey;
        bytes32 m;
        AttestationData data;
        uint256 amount;
        uint256 pool;
    }

    mapping(bytes32 => Auction) public auctions;
    mapping(bytes32 => bool) public claimed; // Claimed for the given signature hash

    address public owner;
    BLSVerify public immutable bls;

    constructor(address _bls) {
        owner = msg.sender;
        bls = BLSVerify(_bls);
    }

    function offerBribe(
        AttestationData calldata _data,
        BLS.G1Point memory _aggPubKey,
        uint256 _deadline,
        bytes32 _m,
        uint256 _amount
    ) public payable {
        require(auctions[_m].amount == 0, "Auction already exists");

        auctions[_m] = Auction(_deadline, _aggPubKey, _m, _data, _amount, msg.value);
    }

    function takeBribe(bytes32 _m, BLS.G2Point calldata sig) public {
        bytes32 sigHash = keccak256(abi.encodePacked(sig.x_c0_a, sig.x_c0_b, sig.x_c1_a, sig.x_c1_b));

        require(!claimed[sigHash], "Already claimed");

        Auction memory auction = auctions[_m];

        require(auction.pool - auction.amount >= 0, "Insufficient pool balance");

        require(bls.verify(abi.encodePacked(auction.m), sig, auction.aggPubkey), "Invalid signature");
        require(block.timestamp < auction.auctionDeadline, "Auction has ended");

        claimed[sigHash] = true;
        payable(msg.sender).transfer(auction.amount);
        auctions[_m].pool -= auction.amount;
    }

    function getAuction(bytes32 _m) public view returns (Auction memory) {
        return auctions[_m];
    }
}
