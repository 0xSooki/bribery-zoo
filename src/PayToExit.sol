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
        bool claimed;
        uint256 auctionDeadline;
        BLS.G1Point pubkey;
        uint256 bribeAmount;
        address creator;
    }

    // Mainnet constants
    bytes4 public constant MAINNET_FORK_VERSION = 0x04000000;
    bytes32 public constant MAINNET_GENESIS_VALIDATORS_ROOT =
        0x4b363db94e286120d76eb905340fdd4e54bfe9f06bf33ff6cf5ad27f511bfe95;
    bytes4 public constant DOMAIN_VOLUNTARY_EXIT = 0x04000000;

    BLSVerify public immutable blsVerify;
    address public owner;

    mapping(address => ValidatorAuction) public validatorAuctions;
    mapping(address => uint256) public balances;

    modifier onlyOwner() {
        require(msg.sender == owner, "Not the owner");
        _;
    }

    constructor(address blsVerifyAddress) {
        owner = msg.sender;
        blsVerify = BLSVerify(blsVerifyAddress);
    }

    /**
     * @notice Create an auction for a validator to exit
     * @param targetEpoch The epoch by which the validator should exit
     * @param auctionDeadline When the auction ends
     * @param pubkey The validator's public key
     */
    function offerBribe(uint256 targetEpoch, uint256 auctionDeadline, BLS.G1Point memory pubkey) external payable {
        require(auctionDeadline > block.timestamp, "Auction deadline must be in future");
        validatorAuctions[msg.sender] = ValidatorAuction({
            epoch: targetEpoch,
            exited: false,
            claimed: false,
            auctionDeadline: auctionDeadline,
            pubkey: pubkey,
            bribeAmount: msg.value,
            creator: msg.sender
        });
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
    ) external {
        ValidatorAuction storage auction = validatorAuctions[briber];
        require(!auction.claimed, "Already claimed");

        require(
            verifyDepositProof(depositCount, depositDataRoot, depositIndex, depositProof, root), "Invalid deposit proof"
        );

        bytes32 signingRoot = Utils.compute_signing_root(
            auction.epoch, validatorIndex, MAINNET_FORK_VERSION, MAINNET_GENESIS_VALIDATORS_ROOT
        );

        // Verify the BLS signature for the voluntary exit
        require(blsVerify.verify(abi.encodePacked(signingRoot), signature, auction.pubkey), "Invalid BLS signature");
        auction.exited = true;

        require(block.timestamp < auction.auctionDeadline, "Auction not resolved");

        if (auction.exited) {
            payable(msg.sender).transfer(auction.bribeAmount);
        } else {
            payable(auction.creator).transfer(auction.bribeAmount);
        }
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
    }

    /**
     * @notice Withdraw funds from contract
     */
    function withdrawFunds() external {
        uint256 amount = balances[msg.sender];
        require(amount > 0, "No funds to withdraw");

        balances[msg.sender] = 0;
        payable(msg.sender).transfer(amount);
    }

    /**
     * @notice Get current epoch based on timestamp
     */
    function getCurrentEpoch() public view returns (uint256) {
        return block.timestamp / 12 / 32;
    }

    /**
     * @notice Get auction details for a briber
     */
    function getAuction(address briber) external view returns (ValidatorAuction memory) {
        return validatorAuctions[briber];
    }
}
