// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import {RLPEncode} from "lib/solidity-rlp-encode/contracts/RLPEncode.sol";

contract HeaderVerify {
    using RLPEncode for *;

    /**
     * @notice Block header structure for Cancun-era (post-Deneb) Ethereum blocks
     * https://github.com/ethereum/go-ethereum/blob/a9061cfd77a26634d459f824793335ea73be14da/core/types/block.go#L75
     * @dev Contains all 21 fields as defined in the Cancun hard fork
     */
    struct BlockHeader {
        bytes32 parentHash;
        bytes32 sha3Uncles;
        address miner;
        bytes32 stateRoot;
        bytes32 transactionsRoot;
        bytes32 receiptsRoot;
        bytes logsBloom;
        uint256 difficulty;
        uint256 number;
        uint256 gasLimit;
        uint256 gasUsed;
        uint256 timestamp;
        bytes extraData;
        bytes32 mixHash;
        bytes8 nonce;
        uint256 baseFeePerGas;
        bytes32 withdrawalsRoot;
        uint256 blobGasUsed;
        uint256 excessBlobGas;
        bytes32 parentBeaconBlockRoot;
        bytes32 requestsHash;
    }

    /**
     * @notice Verify a block hash against its header data using Cancun-era encoding
     * @param header The block header structure (must be Cancun-era format)
     * @param expectedHash The expected block hash
     * @return True if the computed hash matches the expected hash
     * @dev This contract only supports Cancun-era (21-field) block headers
     */
    function verifyBlockHash(BlockHeader memory header, bytes32 expectedHash) public pure returns (bool) {
        // Validate nonce for PoS era (must be zero since Cancun is post-merge)
        require(header.nonce == 0x0000000000000000, "Invalid nonce for Cancun era");

        bytes memory encoded = encodeHeader(header);
        bytes32 hash = keccak256(encoded);
        return hash == expectedHash;
    }

    /**
     * @notice Encode header for Cancun-era blocks (21 fields)
     * @dev This is the canonical RLP encoding for Cancun-era block headers
     * @param header The block header to encode
     * @return RLP-encoded header bytes
     */
    function encodeHeader(BlockHeader memory header) internal pure returns (bytes memory) {
        bytes[] memory items = new bytes[](21);
        items[0] = RLPEncode.encodeBytes(abi.encodePacked(header.parentHash));
        items[1] = RLPEncode.encodeBytes(abi.encodePacked(header.sha3Uncles));
        items[2] = RLPEncode.encodeAddress(header.miner);
        items[3] = RLPEncode.encodeBytes(abi.encodePacked(header.stateRoot));
        items[4] = RLPEncode.encodeBytes(abi.encodePacked(header.transactionsRoot));
        items[5] = RLPEncode.encodeBytes(abi.encodePacked(header.receiptsRoot));
        items[6] = RLPEncode.encodeBytes(header.logsBloom);
        items[7] = RLPEncode.encodeUint(header.difficulty);
        items[8] = RLPEncode.encodeUint(header.number);
        items[9] = RLPEncode.encodeUint(header.gasLimit);
        items[10] = RLPEncode.encodeUint(header.gasUsed);
        items[11] = RLPEncode.encodeUint(header.timestamp);
        items[12] = RLPEncode.encodeBytes(header.extraData);
        items[13] = RLPEncode.encodeBytes(abi.encodePacked(header.mixHash));
        items[14] = RLPEncode.encodeBytes(abi.encodePacked(header.nonce));
        items[15] = RLPEncode.encodeUint(header.baseFeePerGas);
        items[16] = RLPEncode.encodeBytes(abi.encodePacked(header.withdrawalsRoot));
        items[17] = RLPEncode.encodeUint(header.blobGasUsed);
        items[18] = RLPEncode.encodeUint(header.excessBlobGas);
        items[19] = RLPEncode.encodeBytes(abi.encodePacked(header.parentBeaconBlockRoot));
        items[20] = RLPEncode.encodeBytes(abi.encodePacked(header.requestsHash));

        return RLPEncode.encodeList(items);
    }

    /**
     * @notice Verify that a block header matches the on-chain blockhash
     * @param header The block header to verify
     * @return True if the header matches the on-chain blockhash
     * @dev This function can only verify blocks within the last 256 blocks
     */
    function verifyAgainstBlockhash(BlockHeader memory header) public view returns (bool) {
        require(header.number > 0, "Invalid block number");
        require(header.number < block.number, "Cannot verify future blocks");
        require(block.number - header.number <= 256, "Block too old for blockhash verification");

        bytes32 onChainHash = blockhash(header.number);
        require(onChainHash != 0, "Blockhash not available");

        return verifyBlockHash(header, onChainHash);
    }

    /**
     * @notice Get the computed hash for debugging purposes
     * @param header The block header to hash
     * @return The computed block hash
     */
    function getComputedHash(BlockHeader memory header) public pure returns (bytes32) {
        bytes memory encoded = encodeHeader(header);
        return keccak256(encoded);
    }
}
