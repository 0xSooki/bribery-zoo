// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {BLS} from "solady/src/utils/ext/ithaca/BLS.sol";
import {BLSVerify} from "./BLSVerify.sol";
import {Utils} from "./Utils.sol";

contract PayToExit {
    using Utils for *;

    struct VoluntaryExit {
        uint256 epoch;
        uint256 validator_index;
    }

    struct ValidatorAuction {
        uint256 epoch;
        uint256 validatorIndex;
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

    BLSVerify public immutable blsVerifyInstance;
    address public owner;

    mapping(uint256 => ValidatorAuction) public validatorAuctions;
    mapping(address => uint256) public balances;

    modifier onlyOwner() {
        require(msg.sender == owner, "Not the owner");
        _;
    }

    constructor(address _blsVerify) {
        owner = msg.sender;
        blsVerifyInstance = BLSVerify(_blsVerify);
    }

    /**
     * @notice Create an auction for a validator to exit
     * @param validatorIndex The validator index
     * @param targetEpoch The epoch by which the validator should exit
     * @param auctionDeadline When the auction ends
     * @param pubkey The validator's public key
     */
    function offerBribe(uint256 validatorIndex, uint256 targetEpoch, uint256 auctionDeadline, BLS.G1Point memory pubkey)
        external
        payable
    {
        require(auctionDeadline > block.timestamp, "Auction deadline must be in future");
        require(targetEpoch > getCurrentEpoch(), "Target epoch must be in future");

        validatorAuctions[validatorIndex] = ValidatorAuction({
            epoch: targetEpoch,
            validatorIndex: validatorIndex,
            exited: false,
            claimed: false,
            auctionDeadline: auctionDeadline,
            pubkey: pubkey,
            bribeAmount: msg.value,
            creator: msg.sender
        });
    }

    /**
     * @notice Submit proof that a validator has exited
     * @param validatorIndex The validator index
     * @param signature The BLS signature for the voluntary exit
     * @param depositProof Merkle proof of the validator's deposit
     * @param deposit_count The number of deposits in the tree
     */
    function submitExitProof(
        uint256 validatorIndex,
        BLS.G2Point calldata signature,
        bytes32[] calldata depositProof,
        uint64 deposit_count,
        bytes32 root
    ) public view {
        ValidatorAuction storage auction = validatorAuctions[validatorIndex];
        require(!auction.claimed, "Already claimed");

        // Verify the deposit proof
        bytes32 pubkeyHash =
            sha256(abi.encodePacked(auction.pubkey.x_a, auction.pubkey.x_b, auction.pubkey.y_a, auction.pubkey.y_b));
        require(
            verifyDepositProof(deposit_count, pubkeyHash, validatorIndex, depositProof, root), "Invalid deposit proof"
        );

        bytes32 signingRoot = Utils.compute_signing_root(
            auction.epoch, validatorIndex, MAINNET_FORK_VERSION, MAINNET_GENESIS_VALIDATORS_ROOT
        );

        // Verify the BLS signature for the voluntary exit
        require(
            blsVerifyInstance.verify(abi.encodePacked(signingRoot), signature, auction.pubkey), "Invalid BLS signature"
        );
    }

    function takeBribe(
        uint256 validatorIndex,
        BLS.G2Point calldata signature,
        bytes32[] calldata depositProof,
        uint64 deposit_count,
        bytes32 root
    ) external {
        ValidatorAuction storage auction = validatorAuctions[validatorIndex];
        require(!auction.claimed, "Already claimed");

        submitExitProof(validatorIndex, signature, depositProof, deposit_count, root);

        auction.exited = true;

        require(block.timestamp < auction.auctionDeadline, "Auction not resolved");

        if (auction.exited) {
            payable(msg.sender).transfer(auction.bribeAmount);
        } else {
            payable(auction.creator).transfer(auction.bribeAmount);
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

        bytes32 result = sha256(abi.encodePacked(node, Utils._to_little_endian64(deposit_count), bytes24(0)));
        return result == root;
    }

    function depositFunds() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdrawFunds() external {
        uint256 amount = balances[msg.sender];
        require(amount > 0, "No funds to withdraw");

        balances[msg.sender] = 0;
        payable(msg.sender).transfer(amount);
    }

    function getCurrentEpoch() public view returns (uint256) {
        return block.timestamp / 12 / 32;
    }

    function getAuction(uint256 validatorIndex) external view returns (ValidatorAuction memory) {
        return validatorAuctions[validatorIndex];
    }
}
