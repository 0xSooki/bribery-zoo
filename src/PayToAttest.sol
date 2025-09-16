// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {BLSVerify} from "./BLSVerify.sol";
import {BLS} from "solady/src/utils/ext/ithaca/BLS.sol";
import {Utils} from "./Utils.sol";

contract PayToAttest {
    using Utils for *;

    struct Checkpoint {
        uint256 epoch;
        bytes32 root;
    }

    struct AttestationData {
        uint256 slot;
        bytes32 beaconBlockRoot;
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
        address creator;
    }

    // events
    event AuctionOffered(bytes32 indexed m, address indexed creator, uint256 deadline, uint256 amount, uint256 pool);
    event BribeClaimed(bytes32 indexed m, address indexed claimer, uint256 amount);
    event AuctionRefunded(bytes32 indexed m, address indexed creator, uint256 amount);

    mapping(bytes32 => Auction) public auctions;
    mapping(bytes32 => bool) public claimed;

    address public owner;
    BLSVerify public immutable blsVerify;

    constructor(address blsVerifyAddress) {
        owner = msg.sender;
        blsVerify = BLSVerify(blsVerifyAddress);
    }

    /**
     * @notice Create a bribe offer for attestation data
     */
    function offerBribe(
        AttestationData calldata data,
        BLS.G1Point memory aggPubKey,
        uint256 deadline,
        bytes32 m,
        uint256 amount
    ) public payable {
        require(auctions[m].amount == 0, "Auction already exists");
        require(msg.value >= amount);
        require(deadline > block.timestamp + 60, "Too short deadline");
        auctions[m] = Auction(deadline, aggPubKey, m, data, amount, msg.value, msg.sender);
        emit AuctionOffered(m, msg.sender, deadline, amount, msg.value);
    }

    /**
     * @notice Claim bribe by providing valid signature
     */
    function takeBribe(bytes32 m, BLS.G2Point calldata sig) public {
        bytes32 sigHash = keccak256(abi.encodePacked(sig.x_c0_a, sig.x_c0_b, sig.x_c1_a, sig.x_c1_b));

        require(!claimed[sigHash], "Already claimed");

        Auction memory auction = auctions[m];

        require(auction.pool - auction.amount >= 0, "Insufficient pool balance");

        require(blsVerify.verify(abi.encodePacked(auction.m), sig, auction.aggPubkey), "Invalid signature");
        require(block.timestamp < auction.auctionDeadline, "Auction has ended");

        claimed[sigHash] = true;
        auctions[m].pool -= auction.amount;
        (bool ok,) = msg.sender.call{value: auction.amount}("");
        require(ok, "Transfer failed");
        emit BribeClaimed(m, msg.sender, auction.amount);
    }

    /**
     * @notice Get auction details for a given message hash
     */
    function getAuction(bytes32 m) public view returns (Auction memory) {
        return auctions[m];
    }

    function refund(bytes32 m) external {
        Auction storage a = auctions[m];
        require(a.pool > 0, "No such auction");
        require(block.timestamp > a.auctionDeadline, "Auction still running");
        require(msg.sender == a.creator, "Not the owner of the auction");
        uint256 amount = a.pool;
        a.pool = 0;
        (bool ok,) = a.creator.call{value: amount}("");
        require(ok, "Refund failed");
        emit AuctionRefunded(m, a.creator, amount);
    }
}
