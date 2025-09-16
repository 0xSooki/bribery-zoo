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

    function _getBlockHash(uint256 blockNumber) internal view override returns (bytes32) {
        if (useMockBlockhashes) return mockBlockhashes[blockNumber];
        return super._getBlockHash(blockNumber);
    }
}
