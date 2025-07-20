// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {PayToBias} from "./PayToBias.sol";
import {HeaderVerify} from "./HeaderVerify.sol";

/**
 * @title PayToBiasTestable
 * @notice Testable version of PayToBias that allows mocking blockhash values
 */
contract PayToBiasTestable is PayToBias {
    mapping(uint256 => bytes32) public mockBlockhashes;
    bool public useMockBlockhashes;

    constructor(address _headerVerify) PayToBias(_headerVerify) {}

    function setMockBlockhash(uint256 blockNumber, bytes32 blockHash) external {
        mockBlockhashes[blockNumber] = blockHash;
    }

    function setUseMockBlockhashes(bool _useMock) external {
        useMockBlockhashes = _useMock;
    }

    function getBlockhash(uint256 blockNumber) internal view returns (bytes32) {
        if (useMockBlockhashes) {
            return mockBlockhashes[blockNumber];
        }
        return blockhash(blockNumber);
    }

    /**
     * @notice Claim that the validator failed to publish by providing 2-block proof
     * @param blockNumber The block number the validator should have published
     * @param parentHeader The header of block N-1 (before validator's slot)
     * @param nextHeader The header of block N+1 (after validator's slot)
     */
    function takeBribe(
        uint256 blockNumber,
        HeaderVerify.BlockHeader memory parentHeader,
        HeaderVerify.BlockHeader memory nextHeader
    ) external override {
        ValidatorAuction storage auction = validatorAuctions[blockNumber];
        require(auction.validator != address(0), "Auction does not exist");
        require(!auction.published, "Block was published");
        require(!auction.claimed, "Already claimed");

        // Verify block numbers
        require(parentHeader.number == blockNumber - 1, "Invalid parent block number");
        require(nextHeader.number == blockNumber, "Invalid next block number");

        // Get canonical block hashes from blockhash function (or mock)
        bytes32 parentHash = getBlockhash(blockNumber - 1);
        bytes32 nextHash = getBlockhash(blockNumber);

        // Ensure blocks are within the 256-block window for blockhash availability
        require(parentHash != bytes32(0), "Parent block hash not available");
        require(nextHash != bytes32(0), "Next block hash not available");

        // Verify block headers
        require(headerVerify.verifyBlockHash(parentHeader, parentHash), "Invalid parent block header or hash");
        require(headerVerify.verifyBlockHash(nextHeader, nextHash), "Invalid next block header or hash");

        require(
            nextHeader.parentHash == parentHash,
            "Next block should point to parent, proving validator block was skipped"
        );

        uint256 timeGap = nextHeader.timestamp - parentHeader.timestamp;

        if (timeGap > BLOCK_TIME + 4) {
            auction.published = false;
        } else {
            auction.published = true;
        }

        _resolveAuction(blockNumber);
    }
}
