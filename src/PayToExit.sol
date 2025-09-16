// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {BLS} from "solady/src/utils/ext/ithaca/BLS.sol";
import {BLSVerify} from "./BLSVerify.sol";
import {Utils} from "./Utils.sol";

contract PayToExit {
    using Utils for *;

    struct VoluntaryExit {
        uint256 epoch;
        uint256 validatorIndex;
    }

    struct ValidatorAuction {
        uint256 epoch;
        bool exited;
        mapping(uint256 => bool) claimed;
        uint256 auctionDeadline;
        BLS.G1Point aggpubkey;
        uint256 bribeAmount;
        uint256 pool;
        address creator;
    }

    bytes4 public constant MAINNET_FORK_VERSION = 0x04000000;
    bytes32 public constant MAINNET_GENESIS_VALIDATORS_ROOT =
        0x4b363db94e286120d76eb905340fdd4e54bfe9f06bf33ff6cf5ad27f511bfe95;

    BLSVerify public immutable blsVerify;
    address public owner;

    mapping(address => ValidatorAuction) public auctions;
    mapping(address => uint256) public balances;

    uint256 private _locked = 1;

    event AuctionOffered(address indexed creator, uint256 epoch, uint256 amount, uint256 pool, uint256 deadline);
    event AuctionClaimed(uint256 indexed validatorIndex, uint256 amount);
    event AuctionRefunded(address creator, uint256 amount);
    event FundsDeposited(address indexed depositor, uint256 amount);

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    modifier nonReentrant() {
        require(_locked == 1, "Reentrancy");
        _locked = 2;
        _;
        _locked = 1;
    }

    constructor(address blsVerifyAddress) {
        owner = msg.sender;
        blsVerify = BLSVerify(blsVerifyAddress);
    }

    /**
     * @notice Create an auction for a validator to exit
     * @param targetEpoch The epoch by which the validator should exit
     * @param auctionDeadline When the auction ends
     * @param aggpubkey The validator's public key
     */
    function offerBribe(uint256 targetEpoch, uint256 auctionDeadline, BLS.G1Point memory aggpubkey, uint256 bribeAmount)
        external
        payable
    {
        require(msg.value > 0, "No liquidity provided");
        require(auctionDeadline > block.timestamp + 60, "Deadline too short");
        ValidatorAuction storage auction = auctions[msg.sender];
        auction.epoch = targetEpoch;
        auction.auctionDeadline = auctionDeadline;
        auction.aggpubkey = aggpubkey;
        auction.bribeAmount = bribeAmount;
        auction.pool = msg.value;
        auction.creator = msg.sender;

        emit AuctionOffered(msg.sender, targetEpoch, bribeAmount, msg.value, auctionDeadline);
    }

    /**
     * @notice Claim bribe by providing exit proof
     */
    function takeBribe(
        address briber,
        uint256 validatorIndex,
        uint64 depositIndex,
        BLS.G2Point calldata signature,
        bytes32[] calldata depositProof,
        bytes32 depositDataRoot,
        uint64 depositCount,
        bytes32 root
    ) external nonReentrant {
        ValidatorAuction storage auction = auctions[briber];
        require(!auction.claimed[validatorIndex], "Claimed");
        require(auction.bribeAmount > 0, "No such auction");
        require(block.timestamp < auction.auctionDeadline, "Expired");
        require(
            verifyDepositProof(depositCount, depositDataRoot, depositIndex, depositProof, root), "Invalid deposit Proof"
        );
        bytes32 signingRoot = Utils.compute_signing_root(
            auction.epoch, validatorIndex, MAINNET_FORK_VERSION, MAINNET_GENESIS_VALIDATORS_ROOT
        );
        require(blsVerify.verify(abi.encodePacked(signingRoot), signature, auction.aggpubkey), "Invalid signature");
        auction.claimed[validatorIndex] = true;
        uint256 amount = auction.bribeAmount;
        auction.pool -= amount;
        (bool ok,) = msg.sender.call{value: amount}("");
        require(ok, "TransferFail");
        emit AuctionClaimed(validatorIndex, amount);
    }

    /**
     * @notice Refund the bribe to the creator if the auction has expired
     */
    function refund() external nonReentrant {
        ValidatorAuction storage auction = auctions[msg.sender];
        require(auction.bribeAmount > 0, "No such auction");
        require(block.timestamp >= auction.auctionDeadline, "Not Expired");
        require(msg.sender == auction.creator, "Not the owner of the auction");
        uint256 amount = auction.bribeAmount;
        auction.bribeAmount = 0;
        (bool ok,) = auction.creator.call{value: amount}("");
        require(ok, "Refund failed");

        emit AuctionRefunded(auction.creator, amount);
    }

    /**
     * @notice Verify deposit proof for validator
     */
    function verifyDepositProof(
        uint64 depositCount,
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
        bytes32 result = sha256(abi.encodePacked(node, Utils.to_little_endian64(depositCount), bytes24(0)));
        return result == root;
    }

    /**
     * @notice Deposit funds to contract
     */
    function depositFunds() external payable {
        balances[msg.sender] += msg.value;
        emit FundsDeposited(msg.sender, msg.value);
    }

    function bribeAmnt(address briber) external view returns (uint256) {
        return auctions[briber].bribeAmount;
    }
}
